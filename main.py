import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime
import random
import re
import requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))

# Global variables
current_gemini_api_key = GEMINI_API_KEY
general_model = None
coding_model = None
available_models = [
    'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash',
    'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro',
    'gemini-1.5-flash-8b'
]
current_model = 'gemini-1.5-flash'
conversation_context = {}
group_activity = {}
user_command_usage = {}  # Track command usage per user

def initialize_gemini_models(api_key):
    """Initialize Gemini models with the provided API key"""
    global general_model, coding_model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')
        current_gemini_api_key = api_key
        logger.info("Gemini API configured successfully")
        return True, "Gemini API configured successfully!"
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {str(e)}")
        return False, f"Error configuring Gemini API: {str(e)}"

if GEMINI_API_KEY:
    success, message = initialize_gemini_models(GEMINI_API_KEY)
    if success:
        logger.info("Gemini API initialized from environment variable")
    else:
        logger.error(f"Failed to initialize Gemini API: {message}")

def check_command_limit(user_id, command):
    """Check if user has exceeded daily command limit"""
    current_time = datetime.now().timestamp()
    if user_id not in user_command_usage:
        user_command_usage[user_id] = {}
    
    if command not in user_command_usage[user_id]:
        user_command_usage[user_id][command] = {'count': 0, 'last_reset': current_time}
    
    # Reset count if 24 hours have passed
    if current_time - user_command_usage[user_id][command]['last_reset'] >= 86400:  # 24 hours in seconds
        user_command_usage[user_id][command] = {'count': 0, 'last_reset': current_time}
    
    # Set limit based on command
    max_limit = 1 if command == "like" else 2  # 1 for /like, 2 for others
    
    # Check if limit is exceeded
    if user_command_usage[user_id][command]['count'] >= max_limit:
        return False, f"😕 Sorry! You've exceeded the daily limit ({max_limit} time{'s' if max_limit > 1 else ''}) for this command. Try again after 24 hours! 🚀"
    
    # Increment usage count
    user_command_usage[user_id][command]['count'] += 1
    return True, ""

class TelegramGeminiBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("api", self.api_command))
        self.application.add_handler(CommandHandler("setadmin", self.setadmin_command))
        self.application.add_handler(CommandHandler("checkmail", self.checkmail_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("setmodel", self.setmodel_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(CommandHandler("level", self.level_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^copy_code$'))
        self.application.add_error_handler(self.error_handler)

    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command to add and fetch Free Fire player likes"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        # Check daily command limit (1 time per day for /like)
        allowed, limit_message = check_command_limit(user_id, "like")
        if not allowed:
            await update.message.reply_text(limit_message, parse_mode='Markdown')
            return

        if not context.args:
            await update.message.reply_text("Usage: /like <uid> [region]\nExample: /like 3533918864 BD", parse_mode='Markdown')
            return

        uid = context.args[0]
        region = context.args[1] if len(context.args) > 1 else "BD"

        try:
            # Hypothetical POST request to add like (replace with actual API endpoint)
            post_response = requests.post(
                f"https://api.freefire.garena.com/{region}/{uid}/like",  # Replace with actual endpoint
                json={"increment": 1},
                headers={"Authorization": "Bearer YOUR_API_TOKEN"}  # Replace with actual token
            )

            if post_response.status_code == 200:
                # Fetch updated data
                response = requests.get(f"https://free-fire-visit-api.vercel.app/{region}/{uid}")
                data = response.json()

                if data.get("fail") == 0:
                    reply_text = f"""
🎮 *Free Fire Like Checker* 🔥
━━━━━━━━━━━━━━━━
*Nickname:* {data['nickname']}
*UID:* {data['uid']}
*Region:* 🇧🇦 {data['region']}
*Likes:* {data['likes']}
━━━━━━━━━━━━━━━━
Like added! 🎉 This player now has {data['likes']} likes! Want to check another UID? Just say `/like <uid> [region]`!
"""
                    await update.message.reply_text(reply_text, parse_mode='Markdown')
                else:
                    await update.message.reply_text(
                        "😕 Oops! No data found. Check the UID or region and try again! `/like <uid> [region]`",
                        parse_mode='Markdown'
                    )
            else:
                await update.message.reply_text(
                    "😕 Failed to add like. API error! Try again! `/like <uid> [region]`",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error adding/fetching Free Fire likes: {e}")
            await update.message.reply_text(
                "😕 Trouble adding or checking likes. Try again! `/like <uid> [region]`",
                parse_mode='Markdown'
            )

    # Other methods (start_command, help_command, etc.) remain unchanged
    # For brevity, only the modified parts are shown

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = f"""
Hello {username}, welcome to I Master Tools, your friendly companion!

To chat with me, please join our official Telegram group or mention @I MasterTools in the group. Click the button below to join the group!

Available commands:
- /help: Get help and usage information
- /menu: Access the feature menu
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /like <uid> [region]: Add and check Free Fire player likes (1 time per day)
- /level <uid> [region]: Check Free Fire player level (2 times per day)
- /stats <uid> [region]: Check Free Fire player stats (2 times per day)
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            help_message = f"""
Hello {username}! I'm I Master Tools, your friendly companion designed to make conversations fun and engaging.

How I work:
- In groups, mention @I MasterTools or reply to my messages to get a response
- In private chats, only the admin can access all features; others are redirected to the group
- For questions in the group, I engage with a fun or surprising comment before answering
- I remember conversation context until you clear it
- I'm an expert in coding (Python, JavaScript, CSS, HTML, etc.) and provide accurate, beginner-friendly solutions
- I'm designed to be friendly, helpful, and human-like
- Free Fire /like command is limited to 1 use per day per user; /level and /stats are limited to 2 uses per day

Available commands:
- /start: Show welcome message with group link
- /help: Display this help message
- /menu: Access the feature menu
- /clear: Clear your conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /like <uid> [region]: Add and check Free Fire player likes (1 time per day)
- /level <uid> [region]: Check Free Fire player level (2 times per day)
- /stats <uid> [region]: Check Free Fire player stats (2 times per day)
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

My personality:
- I'm a friendly companion who loves chatting and making friends
- I'm an expert in coding and provide accurate, well-explained solutions
- I adapt to your mood and conversation needs
- I use natural, engaging language to feel like a real person
- I enjoy roleplay and creative conversations

Powered by Google Gemini
            """
            await update.message.reply_text(help_message, reply_markup=reply_markup)

    async def get_private_chat_redirect(self):
        """Return redirect message for non-admin private chats"""
        keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return """
Hello, thanks for wanting to chat with me! I'm I Master Tools, your friendly companion. To have fun and helpful conversations with me, please join our official group. Click the button below to join the group and mention @I MasterTools to start chatting. I'm waiting for you there!
        """, reply_markup

    # Other methods (unchanged) would go here

    def run(self):
        """Start the bot"""
        logger.info("Starting Telegram Bot...")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

def main():
    """Main function"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not provided!")
        return
    logger.info("Starting Telegram Bot...")
    logger.info(f"Admin User ID: {ADMIN_USER_ID}")
    if current_gemini_api_key:
        logger.info("Gemini API configured and ready")
    else:
        logger.warning("Gemini API not configured. Use /setadmin and /api commands to set up.")
    bot = TelegramGeminiBot()
    bot.run()

if __name__ == '__main__':
    main()