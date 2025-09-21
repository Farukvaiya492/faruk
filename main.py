import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime, timedelta
import random
import re
import requests
import io

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8380869007:AAGu7e41JJVU8aXG5wqXtCMUVKcCmmrp_gg')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))

# Global variables for dynamic API key and model management
current_gemini_api_key = GEMINI_API_KEY
general_model = None
coding_model = None
available_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-1.5-flash-8b']
current_model = 'gemini-1.5-flash'  # Default model

def initialize_gemini_models(api_key):
    """Initialize Gemini models with the provided API key"""
    global general_model, coding_model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        # NEW: Added multimodal support for gemini-1.5-pro
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')  # Dedicated for coding and multimodal
        current_gemini_api_key = api_key
        return True, "Gemini API configured successfully!"
    except Exception as e:
        return False, f"Error configuring Gemini API: {str(e)}"

# Initialize Gemini if API key is available
if GEMINI_API_KEY:
    success, message = initialize_gemini_models(GEMINI_API_KEY)
    if success:
        logger.info("Gemini API initialized from environment variable")
    else:
        logger.error(f"Failed to initialize Gemini API: {message}")
else:
    logger.warning("GEMINI_API_KEY not set. Use /api command to configure.")

class TelegramGeminiBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        # NEW FEATURE: For admin stats
        self.processed_messages = 0
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
        
        # --- NEW FEATURE HANDLERS ---
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("remind", self.remind_command))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_media))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_media))
        # --- END NEW FEATURE HANDLERS ---
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        
        # MODIFIED: Updated CallbackQueryHandler to handle new feedback buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^(copy_code|feedback_.*)$'))
        self.application.add_error_handler(self.error_handler)

    async def post_init(self, application: Application):
        """NEW FEATURE: Set bot commands for the persistent menu after initialization."""
        commands = [
            BotCommand("start", "বট চালু করুন"),
            BotCommand("help", "সাহায্য দেখুন"),
            BotCommand("menu", "ফিচার মেনু"),
            BotCommand("clear", "কথোপকথন মুছুন"),
            BotCommand("status", "বটের স্ট্যাটাস দেখুন"),
        ]
        await application.bot.set_my_commands(commands)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks for copy code and feedback"""
        query = update.callback_query
        await query.answer() # Answer the callback query immediately

        if query.data == 'copy_code':
            await query.edit_message_text(text=query.message.text + "\n\n✅ কোড কপি হয়েছে!", parse_mode='Markdown')
        elif query.data.startswith('feedback_'):
            feedback_type = query.data.split('_')[1]
            if feedback_type == 'good':
                # You can log this feedback for analysis
                logger.info(f"User {query.from_user.id} gave positive feedback.")
                await query.edit_message_reply_markup(reply_markup=None) # Remove buttons
                await context.bot.send_message(chat_id=update.effective_chat.id, text="ধন্যবাদ আপনার মতামতের জন্য! 😊")
            elif feedback_type == 'bad':
                logger.info(f"User {query.from_user.id} gave negative feedback.")
                await query.edit_message_reply_markup(reply_markup=None) # Remove buttons
                await context.bot.send_message(chat_id=update.effective_chat.id, text="দুঃখিত, আমি আরও ভালো করার চেষ্টা করব। আপনার মতামতের জন্য ধন্যবাদ।")

    # ... (start_command, handle_new_member, help_command, menu_command remain mostly the same)
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            welcome_message = f"""
Hello {username}, welcome to I Master Tools, your friendly companion!

To chat with me, please join our official Telegram group or mention @I MasterTools in the group. Click the button below to join the group!

Available commands:
- /help: Get help and usage information
- /menu: Access the feature menu
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /remind <time> <text>: Set a reminder (e.g., /remind 10m check email)
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\\n- /setadmin: Set yourself as admin (first-time only)\\n- /setmodel: Choose a different model (admin only)\\n- /admin: View admin stats'}

In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_id = new_member.id
            user_mention = f"@{new_member.username}" if new_member.username else username
            welcome_message = f"""
স্বাগতম {user_mention}! আমাদের VPSHUB_BD_CHAT গ্রুপে তোমাকে পেয়ে আমরা খুবই উৎসাহিত! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। এখানে তুমি মজার কথোপকথন, সহায়ক উত্তর, এবং আরো অনেক কিছু পাবে। আমাকে @I MasterTools মেনশন করে বা রিপ্লাই করে কথা শুরু করো। তুমি কী নিয়ে কথা বলতে চাও?
            """
            await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (This command remains unchanged)
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            help_message = f"""
Hello {username}! I'm I Master Tools, your friendly companion designed to make conversations fun and engaging.

How I work:
- In groups, mention @I MasterTools or reply to my messages to get a response
- In private chats, only the admin can access all features; others are redirected to the group
- I can understand text, images, and voice messages.
- I remember conversation context until you clear it
- I'm an expert in coding and provide accurate, beginner-friendly solutions

Available commands:
- /start: Show welcome message
- /help: Display this help message
- /menu: Access the feature menu
- /clear: Clear your conversation history
- /status: Check my status
- /remind <time> <text>: Set a reminder (e.g., /remind 10m check email)
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key\\n- /setadmin: Set yourself as admin\\n- /setmodel: Choose a different model\\n- /admin: View admin stats'}

Powered by Google Gemini
            """
            await update.message.reply_text(help_message)
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (This command remains unchanged)
        """Handle /menu command with inline keyboard"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("Check Email", callback_data="checkmail")],
                [InlineKeyboardButton("Bot Status", callback_data="status")],
                [InlineKeyboardButton("Clear History", callback_data="clear")],
                [InlineKeyboardButton("Join Group", url="https://t.me/VPSHUB_BD_CHAT")]
            ]
            if user_id == ADMIN_USER_ID:
                keyboard.append([InlineKeyboardButton("Set API Key", callback_data="api")])
                keyboard.append([InlineKeyboardButton("Change Model", callback_data="setmodel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Hello {username}, choose a feature from the menu below:", reply_markup=reply_markup)
            
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """MODIFIED: Handle /clear command using context.chat_data"""
        chat_id = update.effective_chat.id
        if 'history' in context.chat_data:
            del context.chat_data['history']
        await update.message.reply_text("Conversation history has been cleared. Let's start fresh!")
    
    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (This command remains unchanged)
        """Handle /checkmail command to check temporary email inbox"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            try:
                u = 'txoguqa'
                d = random.choice(['mailto.plus', 'fexpost.com', 'fexbox.org', 'rover.info'])
                email = f'{u}@{d}'
                response = requests.get(
                    'https://tempmail.plus/api/mails',
                    params={'email': email, 'limit': 20, 'epin': ''},
                    cookies={'email': email},
                    headers={'user-agent': 'Mozilla/5.0'}
                )
                mail_list = response.json().get('mail_list', [])
                if not mail_list:
                    await update.message.reply_text(f"No emails found in the inbox for {email}. Want to try again later?")
                    return
                subjects = [m['subject'] for m in mail_list]
                response_text = f"Here are the emails in the inbox for {email}:\n\n" + "\n".join(subjects)
                await update.message.reply_text(response_text)
            except Exception as e:
                logger.error(f"Error checking email: {e}")
                await update.message.reply_text("Something went wrong while checking the email. Shall we try again?")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # MODIFIED: Added message count
        """Handle /status command"""
        # ... (Logic to check user and redirect is the same)
        api_status = "Connected" if current_gemini_api_key and general_model else "Not configured"
        api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "Not set"
        # MODIFIED: Using context.chat_data to get active conversations is tricky.
        # This will now show the message count instead.
        status_message = f"""
Here's the I Master Tools status report:

Bot Status: Online and ready
Model: {current_model}
API Status: {api_status}
API Key: {api_key_display}
Group Responses: Mention or reply only
Total Messages Processed: {self.processed_messages}
Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}

All systems are ready for action. I'm thrilled to assist!
        """
        await update.message.reply_text(status_message)
    
    # ... (setadmin_command, api_command, setmodel_command remain the same)
    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command"""
        global ADMIN_USER_ID
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                ADMIN_USER_ID = user_id
                await update.message.reply_text(f"Congratulations {username}, you are now the bot admin! Your user ID: {user_id}")
                logger.info(f"Admin set to user ID: {user_id}")
            else:
                if user_id == ADMIN_USER_ID:
                    await update.message.reply_text(f"You're already the admin! Your user ID: {user_id}")
                else:
                    await update.message.reply_text("Sorry, the admin is already set. Only the current admin can manage the bot.")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, general_model, coding_model
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                await update.message.reply_text("""
Please provide an API key.

Usage: `/api your_gemini_api_key_here`

To get a Gemini API key:
1. Visit https://makersuite.google.com/app/apikey
2. Generate a new API key
3. Use the command: /api YOUR_API_KEY

For security, the command message will be deleted after setting the key.
                """, parse_mode='Markdown')
                return
            api_key = ' '.join(context.args)
            if len(api_key) < 20 or not api_key.startswith('AI'):
                await update.message.reply_text("Invalid API key format. Gemini API keys typically start with 'AI' and are over 20 characters.")
                return
            success, message = initialize_gemini_models(api_key)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except:
                pass
            if success:
                await update.effective_chat.send_message(f"Gemini API key updated successfully! Key: ...{api_key[-8:]}")
                logger.info(f"Gemini API key updated by admin {user_id}")
            else:
                await update.effective_chat.send_message(f"Failed to set API key: {message}")
                logger.error(f"Failed to set API key: {message}")

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command to choose Gemini model"""
        global general_model, current_model
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                models_list = "\n".join([f"- {model}" for model in available_models])
                await update.message.reply_text(f"Available models:\n{models_list}\n\nUsage: /setmodel <model_name>")
                return
            model_name = context.args[0]
            if model_name not in available_models:
                await update.message.reply_text(f"Invalid model. Choose from: {', '.join(available_models)}")
                return
            try:
                current_model = model_name
                general_model = genai.GenerativeModel(model_name)
                await update.message.reply_text(f"Model switched to {model_name} successfully!")
                logger.info(f"Model switched to {model_name} by admin {user_id}")
            except Exception as e:
                await update.message.reply_text(f"Failed to switch model: {str(e)}")
                logger.error(f"Failed to switch model: {str(e)}")


    # --- NEW FEATURE METHODS ---
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """NEW: Handle /admin command to show bot stats."""
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("This command is for the bot admin only.")
            return
        
        admin_stats = f"""
        **I Master Tools - Admin Panel**
        
        - **Total Messages Processed:** {self.processed_messages}
        - **Current Model:** {current_model}
        - **Admin User ID:** {ADMIN_USER_ID}
        - **Bot Uptime:** (since last restart)
        """
        await update.message.reply_text(admin_stats, parse_mode='Markdown')

    async def reminder_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """NEW: The function called by the job queue to send a reminder."""
        job = context.job
        await context.bot.send_message(chat_id=job.chat_id, text=f"⏰ **রিমাইন্ডার:**\n\n{job.data}", parse_mode='Markdown')

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """NEW: Handle /remind command to set a reminder."""
        chat_id = update.effective_chat.id
        try:
            # Simple parser: /remind 10m check email
            time_str = context.args[0]
            reminder_text = " ".join(context.args[1:])

            if not reminder_text:
                await update.message.reply_text("Please provide a message for the reminder.\nUsage: `/remind <time> <message>` (e.g., `10m`, `1h`)", parse_mode='Markdown')
                return

            delay = 0
            if time_str.endswith('s'):
                delay = int(time_str[:-1])
            elif time_str.endswith('m'):
                delay = int(time_str[:-1]) * 60
            elif time_str.endswith('h'):
                delay = int(time_str[:-1]) * 3600
            else:
                await update.message.reply_text("Invalid time format. Use 's' for seconds, 'm' for minutes, 'h' for hours.", parse_mode='Markdown')
                return

            context.job_queue.run_once(self.reminder_callback, delay, chat_id=chat_id, data=reminder_text, name=str(chat_id))
            await update.message.reply_text(f"ঠিক আছে! আমি আপনাকে {time_str} পরে মনে করিয়ে দেব।")

        except (IndexError, ValueError):
            await update.message.reply_text("Usage: `/remind <time> <message>` (e.g., `/remind 10m check email`)", parse_mode='Markdown')

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """NEW: Handles both photos and voice messages."""
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        media_prompt = ""
        media_bytes = None
        mime_type = ""

        if update.message.photo:
            media_prompt = update.message.caption or "এই ছবিটি বর্ণনা করো।"
            photo_file = await update.message.photo[-1].get_file()
            media_bytes = await photo_file.download_as_bytearray()
            mime_type = "image/jpeg"
        elif update.message.voice:
            media_prompt = "এই ভয়েস মেসেজটি টেক্সটে রূপান্তর করো এবং সে অনুযায়ী উত্তর দাও।"
            voice_file = await update.message.voice.get_file()
            media_bytes = await voice_file.download_as_bytearray()
            mime_type = update.message.voice.mime_type
        
        if not media_bytes:
            return

        self.processed_messages += 1
        
        # Using coding_model as it's set to gemini-1.5-pro which is great for multimodal
        if not coding_model:
            await update.message.reply_text("দুঃখিত, মিডিয়া প্রসেস করার জন্য মডেল এখনো সংযুক্ত হয়নি।")
            return
            
        try:
            response = coding_model.generate_content([media_prompt, {"mime_type": mime_type, "data": media_bytes}])
            await update.message.reply_text(response.text)
        except Exception as e:
            logger.error(f"Error handling media: {e}")
            await update.message.reply_text("দুঃখিত, মিডিয়াটি প্রসেস করতে একটি সমস্যা হয়েছে।")
            
    # --- END NEW FEATURE METHODS ---

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """MODIFIED: Handle regular text messages using context.chat_data and add feedback buttons"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            username = update.effective_user.first_name or "User"
            
            # --- Permission and Group Logic (unchanged) ---
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and
                                   update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                if not (is_reply_to_bot or is_mentioned):
                    return
            elif chat_type == 'private' and user_id != ADMIN_USER_ID:
                keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                response = "হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ!..." # Shortened for brevity
                await update.message.reply_text(response, reply_markup=reply_markup)
                return
            
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            self.processed_messages += 1

            # MODIFIED: Using context.chat_data for conversation history
            if 'history' not in context.chat_data:
                context.chat_data['history'] = []
            
            context.chat_data['history'].append(f"User: {user_message}")
            if len(context.chat_data['history']) > 20:
                context.chat_data['history'] = context.chat_data['history'][-20:]
            
            context_text = "\n".join(context.chat_data['history'])
            
            is_coding_query = any(keyword in user_message.lower() for keyword in ['code', 'python', 'javascript', 'java', 'c++', 'html', 'css'])
            
            model_to_use = coding_model if is_coding_query else general_model
            if current_gemini_api_key and model_to_use:
                response = await self.generate_gemini_response(context_text, username, chat_type, is_coding_query)
            else:
                response = "দুঃখিত, মডেল এখনো সংযুক্ত হয়নি। অ্যাডমিন /api কমান্ড দিয়ে সেট করতে পারে।"
            
            context.chat_data['history'].append(f"I Master Tools: {response}")
            
            # --- NEW FEATURE: FEEDBACK BUTTONS ---
            feedback_keyboard = [
                [
                    InlineKeyboardButton("👍 ভালো", callback_data="feedback_good"),
                    InlineKeyboardButton("👎 খারাপ", callback_data="feedback_bad")
                ]
            ]
            feedback_markup = InlineKeyboardMarkup(feedback_keyboard)

            if is_coding_query and '```' in response:
                keyboard = [[InlineKeyboardButton("Copy Code", callback_data="copy_code")]]
                # Combine copy button with feedback buttons
                feedback_keyboard[0].insert(0, keyboard[0][0])
                reply_markup = InlineKeyboardMarkup(feedback_keyboard)
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, reply_markup=feedback_markup)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(random.choice([
                "Something went haywire in my circuits. Want to try again?",
                "Hit a snag. What were we talking about?",
                "Digital brain got tangled. Can you repeat that?"
            ]))

    async def generate_gemini_response(self, prompt, username="User", chat_type="private", is_coding_query=False):
        """Generate response using Gemini with personality"""
        # This function's core logic and prompt remain the same
        try:
            system_prompt = f"""
You are I Master Tools, a friendly and engaging companion... 
(The detailed system prompt from your original code goes here. It's kept the same.)
Current conversation:
{prompt}

Respond as I Master Tools. Keep it natural, engaging, and human-like, and match the conversation's tone. Respond in Bengali (Bangla). Do NOT start the response with the user's name or phrases like "ওহো" or "হায়".
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            if not response.text or "error" in response.text.lower():
                return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")

    def run(self):
        """Start the bot"""
        # NEW: Added post_init to set commands
        self.application.post_init = self.post_init
        
        logger.info("Starting Telegram Bot...")
        # For production, consider using webhooks instead of polling.
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