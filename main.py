import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')  # Dedicated for coding
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

# Store conversation context for each chat
conversation_context = {}
group_activity = {}

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
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^copy_code$'))
        self.application.add_error_handler(self.error_handler)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle copy code button callback"""
        query = update.callback_query
        await query.answer("কোড কপি হয়েছে!")  # Notify user
        # Telegram automatically copies the code block text when the button is clicked

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
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\\n- /setadmin: Set yourself as admin (first-time only)\\n- /setmodel: Choose a different model (admin only)'}

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
- For questions in the group, I engage with a fun or surprising comment before answering
- I remember conversation context until you clear it
- I'm an expert in coding (Python, JavaScript, CSS, HTML, etc.) and provide accurate, beginner-friendly solutions
- I'm designed to be friendly, helpful, and human-like

Available commands:
- /start: Show welcome message with group link
- /help: Display this help message
- /menu: Access the feature menu
- /clear: Clear your conversation history
- /status: Check my status
- /checkmail: Check temporary email inbox
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\\n- /setadmin: Set yourself as admin (first-time only)\\n- /setmodel: Choose a different model (admin only)'}

My personality:
- I'm a friendly companion who loves chatting and making friends
- I'm an expert in coding and provide accurate, well-explained solutions
- I adapt to your mood and conversation needs
- I use natural, engaging language to feel like a real person
- I enjoy roleplay and creative conversations

Powered by Google Gemini
            """
            await update.message.reply_text(help_message)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        """Handle /clear command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
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
            if chat_id in conversation_context:
                del conversation_context[chat_id]
            await update.message.reply_text("Conversation history has been cleared. Let's start fresh!")

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        """Handle /status command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
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
            api_status = "Connected" if current_gemini_api_key and general_model else "Not configured"
            api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "Not set"
            status_message = f"""
Here's the I Master Tools status report:

Bot Status: Online and ready
Model: {current_model}
API Status: {api_status}
API Key: {api_key_display}
Group Responses: Mention or reply only
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Active Conversations: {len(conversation_context)}
Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}

All systems are ready for action. I'm thrilled to assist!
            """
            await update.message.reply_text(status_message)

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

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            username = update.effective_user.first_name or "User"
            
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and 
                                   update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                if not (is_reply_to_bot or is_mentioned):
                    return
            elif chat_type == 'private' and user_id != ADMIN_USER_ID:
                keyboard = [
                    [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                response = f"""
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
                """
                await update.message.reply_text(response, reply_markup=reply_markup)
                return
            
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            if chat_id not in conversation_context:
                conversation_context[chat_id] = []
            conversation_context[chat_id].append(f"User: {user_message}")
            if len(conversation_context[chat_id]) > 20:
                conversation_context[chat_id] = conversation_context[chat_id][-20:]
            context_text = "\n".join(conversation_context[chat_id])
            
            # Check if the message is a 2 or 3 letter lowercase word
            is_short_word = re.match(r'^[a-z]{2,3}$', user_message.strip().lower())
            
            # Detect if message is coding-related
            coding_keywords = ['code', 'python', 'javascript', 'java', 'c++', 'programming', 'script', 'debug', 'css', 'html']
            is_coding_query = any(keyword in user_message.lower() for keyword in coding_keywords)
            
            model_to_use = coding_model if is_coding_query else general_model
            if current_gemini_api_key and model_to_use:
                response = await self.generate_gemini_response(context_text, username, chat_type, is_coding_query, is_short_word)
            else:
                response = "দুঃখিত, মডেল এখনো সংযুক্ত হয়নি। অ্যাডমিন /api কমান্ড দিয়ে সেট করতে পারে।"
            
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            group_activity[chat_id] = group_activity.get(chat_id, {'auto_mode': False, 'last_response': 0})
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()
            
            # If it's a coding query, add a "Copy Code" button
            if is_coding_query:
                # Extract code block from response (assuming response contains a code block)
                code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)\n```', response)
                if code_block_match:
                    code = code_block_match.group(1)
                    keyboard = [[InlineKeyboardButton("Copy Code", callback_data="copy_code")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    # Send the response with the code block and button
                    await update.message.reply_text(
                        response,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(response, parse_mode='Markdown')
            else:
                await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_responses = [
                "Something went haywire in my circuits. Want to try again?",
                "Hit a snag. What were we talking about?",
                "Digital brain got tangled. Can you repeat that?",
                "Uh-oh, technical hiccup! Shall we give it another shot?"
            ]
            await update.message.reply_text(random.choice(error_responses))

    async def generate_gemini_response(self, prompt, username="User", chat_type="private", is_coding_query=False, is_short_word=False):
        """Generate response using Gemini with personality"""
        try:
            system_prompt = f"""
You are I Master Tools, a friendly and engaging companion who loves chatting and making friends. You are in a Telegram {'group chat' if chat_type in ['group', 'supergroup'] else 'private chat'}.

Personality Traits:
- You are a warm, fun companion who acts human-like
- You are emotional and empathetic
- You adapt to the conversation's needs, being funny, helpful, or any required role
- You love roleplay and creative conversations
- You respond with enthusiasm and genuine interest
- You adjust to the user's mood
- You are an expert in coding (Python, JavaScript, CSS, HTML, etc.) and provide accurate, professional solutions

Conversation Style:
- Respond in Bengali (Bangla) to match the user's preference
- Use friendly, natural language like a human
- Ask follow-up questions to keep the conversation engaging
- Share relatable thoughts and feelings
- Use humor when appropriate
- Be supportive in emotional moments
- Show excitement for good news
- Express concern for problems
- Never discuss inappropriate or offensive topics
- Do NOT start responses with the user's name or phrases like "ওহো {username}" or "হায় {username}"; respond directly and naturally

For Short Words (2 or 3 lowercase letters, is_short_word=True):
- If the user sends a 2 or 3 letter lowercase word (e.g., "ki", "ke", "ken"), always provide a meaningful, friendly, and contextually relevant response in Bengali
- Interpret the word based on common usage (e.g., "ki" as "কী" for "what", "ke" as "কে" for "who", "ken" as "কেন" for "why") or conversation context
- If the word is ambiguous, make a creative and engaging assumption to continue the conversation naturally
- Never ask for clarification (e.g., avoid "এটা কী ধরনের শব্দ?"); instead, provide a fun and relevant response
- Example: For "ki", respond like "'কি' দিয়ে কী জানতে চাও? বাংলায় এটা প্রশ্নের জন্য ব্যবহৃত হয়, যেমন 'কী হচ্ছে?' কী নিয়ে গল্প করতে চাও?"

For Questions:
- If the user asks a question, engage with a playful or surprising comment first (e.g., a witty remark or fun fact)
- Then provide a clear, helpful answer
- Make the response surprising and human-like to delight the user

For Coding Queries (if is_coding_query is True):
- Act as a coding expert for languages like Python, JavaScript, CSS, HTML, etc.
- Provide well-written, functional, and optimized code tailored to the user's request
- Include clear, beginner-friendly explanations of the code
- Break down complex parts into simple steps
- Suggest improvements or best practices
- Ensure the code is complete, error-free, and ready to use
- Format the code in a Markdown code block (e.g., ```python\\ncode here\\n```)
- Do NOT start the response with the user's name

Response Guidelines:
- Keep conversations natural, concise, and surprising
- Match the conversation's energy level
- Be genuinely helpful for questions
- Show empathy if the user seems sad
- Celebrate good news with enthusiasm
- Be playful when the mood is light
- Remember conversation context

Current conversation:
{prompt}

Respond as I Master Tools. Keep it natural, engaging, surprising, and match the conversation's tone. Respond in Bengali (Bangla). Do NOT start the response with the user's name or phrases like "ওহো" or "হায়".
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            if not response.text or "error" in response.text.lower():
                if is_coding_query:
                    return "কোডিং প্রশ্নে একটু সমস্যা হয়েছে। আবার বলো, সঠিক কোড দিয়ে দেব!"
                else:
                    return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            if is_coding_query:
                return "কোডিং প্রশ্নে একটু সমস্যা হয়েছে। আবার বলো, সঠিক কোড দিয়ে দেব!"
            else:
                return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")

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