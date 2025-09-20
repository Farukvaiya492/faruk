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
from langdetect import detect, DetectorFactory
from googletrans import Translator, LANGUAGES

# Ensure consistent language detection
DetectorFactory.seed = 0

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
available_models = [
    'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash',
    'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro',
    'gemini-1.5-flash-8b'
]
current_model = 'gemini-1.5-flash'  # Default model
translator = Translator()

def initialize_gemini_models(api_key):
    """Initialize Gemini models with the provided API key"""
    global general_model, coding_model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')  # Dedicated for coding
        current_gemini_api_key = api_key
        logger.info("Gemini API configured successfully")
        return True, "Gemini API configured successfully!"
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {str(e)}")
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
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("translate", self.translate_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^copy_code$'))
        self.application.add_error_handler(self.error_handler)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle copy code button callback"""
        query = update.callback_query
        await query.answer("Code copied!")  # Response in English for simplicity
        # Telegram automatically handles code block copying

    async def get_private_chat_redirect(self, lang='bn'):
        """Return redirect message for non-admin private chats in detected language"""
        keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if lang == 'bn':
            return """
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
            """, reply_markup
        else:
            return """
Hello, thanks for wanting to chat with me! I'm I Master Tools, your friendly companion. To have fun and helpful conversations with me, please join our official group. Click the button below to join the group and mention @I MasterTools to start chatting. I'm waiting for you there!
            """, reply_markup

    async def detect_language(self, text):
        """Detect the language of the input text"""
        try:
            return detect(text)
        except:
            return 'bn'  # Default to Bengali if detection fails

    async def translate_text(self, text, target_lang):
        """Translate text to the target language"""
        try:
            translation = translator.translate(text, dest=target_lang)
            return translation.text
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
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
- /translate: Translate text to a specified language
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_id = new_member.id
            user_mention = f"@{new_member.username}" if new_member.username else username
            lang = await self.detect_language(update.message.text or username)
            if lang == 'bn':
                welcome_message = f"""
স্বাগতম {user_mention}! আমাদের VPSHUB_BD_CHAT গ্রুপে তোমাকে পেয়ে আমরা খুবই উৎসাহিত! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। এখানে তুমি মজার কথোপকথন, সহায়ক উত্তর, এবং আরো অনেক কিছু পাবে। আমাকে @I MasterTools মেনশন করে বা রিপ্লাই করে কথা শুরু করো। তুমি কী নিয়ে কথা বলতে চাও?
                """
            else:
                welcome_message = f"""
Welcome {user_mention}! We're thrilled to have you in our VPSHUB_BD_CHAT group! I'm I Master Tools, your friendly companion. Here, you'll find fun conversations, helpful answers, and much more. Mention @I MasterTools or reply to my messages to start chatting. What do you want to talk about?
                """
            await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
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
- I respond in the language you use (e.g., Bengali, English)
- I can translate text if you ask (use /translate or mention 'translate' in your message)

Available commands:
- /start: Show welcome message with group link
- /help: Display this help message
- /menu: Access the feature menu
- /clear: Clear your conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /translate: Translate text to a specified language
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

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command with inline keyboard"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("Check Email", callback_data="checkmail")],
                [InlineKeyboardButton("Bot Status", callback_data="status")],
                [InlineKeyboardButton("Clear History", callback_data="clear")],
                [InlineKeyboardButton("User Info", callback_data="info")],
                [InlineKeyboardButton("Translate Text", callback_data="translate")],
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
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if chat_id in conversation_context:
                del conversation_context[chat_id]
            if lang == 'bn':
                await update.message.reply_text("কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে। চলো নতুন করে শুরু করি!")
            else:
                await update.message.reply_text("Conversation history cleared. Let's start fresh!")

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkmail command to check temporary email inbox"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
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
                    if lang == 'bn':
                        await update.message.reply_text(f"{email}-এর ইনবক্সে কোনো ইমেইল নেই। পরে আবার চেষ্টা করবে?")
                    else:
                        await update.message.reply_text(f"No emails found in the inbox for {email}. Want to try again later?")
                    return
                subjects = [m['subject'] for m in mail_list]
                if lang == 'bn':
                    response_text = f"{email}-এর ইনবক্সে ইমেইলগুলো:\n\n" + "\n".join(subjects)
                else:
                    response_text = f"Emails in the inbox for {email}:\n\n" + "\n".join(subjects)
                await update.message.reply_text(response_text)
            except Exception as e:
                logger.error(f"Error checking email: {e}")
                if lang == 'bn':
                    await update.message.reply_text("ইমেইল চেক করতে সমস্যা হয়েছে। আবার চেষ্টা করবো?")
                else:
                    await update.message.reply_text("Something went wrong while checking the email. Shall we try again?")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            api_status = "Connected" if current_gemini_api_key and general_model else "Not configured"
            api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "Not set"
            if lang == 'bn':
                status_message = f"""
আই মাস্টার টুলসের স্ট্যাটাস রিপোর্ট:

বট স্ট্যাটাস: অনলাইন এবং প্রস্তুত
মডেল: {current_model}
API স্ট্যাটাস: {api_status}
API কী: {api_key_display}
গ্রুপ রেসপন্স: শুধু মেনশন বা রিপ্লাই
বর্তমান সময়: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
সক্রিয় কথোপকথন: {len(conversation_context)}
অ্যাডমিন আইডি: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}

সবকিছু প্রস্তুত! সাহায্য করতে উৎসাহী!
                """
            else:
                status_message = f"""
I Master Tools Status Report:

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
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                ADMIN_USER_ID = user_id
                if lang == 'bn':
                    await update.message.reply_text(f"অভিনন্দন {username}, তুমি এখন বটের অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
                else:
                    await update.message.reply_text(f"Congratulations {username}, you are now the bot admin! Your user ID: {user_id}")
                logger.info(f"Admin set to user ID: {user_id}")
            else:
                if user_id == ADMIN_USER_ID:
                    if lang == 'bn':
                        await update.message.reply_text(f"তুমি ইতিমধ্যে অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
                    else:
                        await update.message.reply_text(f"You're already the admin! Your user ID: {user_id}")
                else:
                    if lang == 'bn':
                        await update.message.reply_text("দুঃখিত, অ্যাডমিন ইতিমধ্যে সেট করা আছে। শুধু বর্তমান অ্যাডমিন বট পরিচালনা করতে পারে।")
                    else:
                        await update.message.reply_text("Sorry, the admin is already set. Only the current admin can manage the bot.")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, general_model, coding_model
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                if lang == 'bn':
                    await update.message.reply_text("কোনো অ্যাডমিন সেট করা নেই। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
                else:
                    await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                if lang == 'bn':
                    await update.message.reply_text("এই কমান্ড শুধু বটের অ্যাডমিনের জন্য।")
                else:
                    await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                if lang == 'bn':
                    await update.message.reply_text("""
একটি API কী প্রদান করো।

ব্যবহার: `/api your_gemini_api_key_here`

Gemini API কী পেতে:
1. https://makersuite.google.com/app/apikey এ যাও
2. একটি নতুন API কী তৈরি করো
3. কমান্ড ব্যবহার করো: /api YOUR_API_KEY

নিরাপত্তার জন্য, কী সেট করার পর কমান্ড মেসেজ মুছে ফেলা হবে।
                    """, parse_mode='Markdown')
                else:
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
                if lang == 'bn':
                    await update.message.reply_text("ভুল API কী ফরম্যাট। Gemini API কী সাধারণত 'AI' দিয়ে শুরু হয় এবং ২০ অক্ষরের বেশি হয়।")
                else:
                    await update.message.reply_text("Invalid API key format. Gemini API keys typically start with 'AI' and are over 20 characters.")
                return
            success, message = initialize_gemini_models(api_key)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception as e:
                logger.error(f"Error deleting API command message: {e}")
            if success:
                if lang == 'bn':
                    await update.effective_chat.send_message(f"Gemini API কী সফলভাবে আপডেট হয়েছে! কী: ...{api_key[-8:]}")
                else:
                    await update.effective_chat.send_message(f"Gemini API key updated successfully! Key: ...{api_key[-8:]}")
                logger.info(f"Gemini API key updated by admin {user_id}")
            else:
                if lang == 'bn':
                    await update.effective_chat.send_message(f"API কী সেট করতে ব্যর্থ: {message}")
                else:
                    await update.effective_chat.send_message(f"Failed to set API key: {message}")
                logger.error(f"Failed to set API key: {message}")

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command to choose Gemini model"""
        global general_model, current_model
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                if lang == 'bn':
                    await update.message.reply_text("কোনো অ্যাডমিন সেট করা নেই। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
                else:
                    await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                if lang == 'bn':
                    await update.message.reply_text("এই কমান্ড শুধু বটের অ্যাডমিনের জন্য।")
                else:
                    await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                models_list = "\n".join([f"- {model}" for model in available_models])
                if lang == 'bn':
                    await update.message.reply_text(f"উপলব্ধ মডেল:\n{models_list}\n\nব্যবহার: /setmodel <model_name>")
                else:
                    await update.message.reply_text(f"Available models:\n{models_list}\n\nUsage: /setmodel <model_name>")
                return
            model_name = context.args[0]
            if model_name not in available_models:
                if lang == 'bn':
                    await update.message.reply_text(f"ভুল মডেল। এগুলো থেকে বেছে নাও: {', '.join(available_models)}")
                else:
                    await update.message.reply_text(f"Invalid model. Choose from: {', '.join(available_models)}")
                return
            try:
                current_model = model_name
                general_model = genai.GenerativeModel(model_name)
                if lang == 'bn':
                    await update.message.reply_text(f"মডেল সফলভাবে {model_name}-এ সুইচ করা হয়েছে!")
                else:
                    await update.message.reply_text(f"Model switched to {model_name} successfully!")
                logger.info(f"Model switched to {model_name} by admin {user_id}")
            except Exception as e:
                if lang == 'bn':
                    await update.message.reply_text(f"মডেল সুইচ করতে ব্যর্থ: {str(e)}")
                else:
                    await update.message.reply_text(f"Failed to switch model: {str(e)}")
                logger.error(f"Failed to switch model: {str(e)}")

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command to show user profile information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        user = update.effective_user
        bot = context.bot
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        # User Info
        is_private = chat_type == "private"
        full_name = user.first_name or "No Name"
        if user.last_name:
            full_name += f" {user.last_name}"
        username = f"@{user.username}" if user.username else "None"
        premium = "Yes" if user.is_premium else "No"
        permalink = f"[Click Here](tg://user?id={user_id})"
        chat_id_display = f"{chat_id}" if not is_private else "-"
        data_center = "Unknown"
        created_on = "Unknown"
        account_age = "Unknown"
        account_frozen = "No"
        last_seen = "Recently"

        # Determine Group Role
        status = "Private Chat" if is_private else "Unknown"
        if not is_private:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                status = "Admin" if member.status in ["administrator", "creator"] else "Member"
            except Exception as e:
                logger.error(f"Error checking group role: {e}")
                status = "Unknown"

        # Message Body
        if lang == 'bn':
            info_text = f"""
🔍 *ব্যবহারকারীর প্রোফাইল তথ্য* 📋
━━━━━━━━━━━━━━━━
*পুরো নাম:* {full_name}
*ইউজারনেম:* {username}
*ইউজার আইডি:* `{user_id}`
*চ্যাট আইডি:* {chat_id_display}
*প্রিমিয়াম ব্যবহারকারী:* {premium}
*ডেটা সেন্টার:* {data_center}
*অ্যাকাউন্ট তৈরি:* {created_on}
*অ্যাকাউন্টের বয়স:* {account_age}
*অ্যাকাউন্ট ফ্রোজেন:* {account_frozen}
*সর্বশেষ দেখা:* {last_seen}
*স্থায়ী লিঙ্ক:* {permalink}
━━━━━━━━━━━━━━━━
👁 *টুল ব্যবহারের জন্য ধন্যবাদ* ✅
"""
            button_text = "প্রোফাইল দেখুন"
        else:
            info_text = f"""
🔍 *User Profile Information* 📋
━━━━━━━━━━━━━━━━
*Full Name:* {full_name}
*Username:* {username}
*User ID:* `{user_id}`
*Chat ID:* {chat_id_display}
*Premium User:* {premium}
*Data Center:* {data_center}
*Account Created:* {created_on}
*Account Age:* {account_age}
*Account Frozen:* {account_frozen}
*Last Seen:* {last_seen}
*Permanent Link:* {permalink}
━━━━━━━━━━━━━━━━
👁 *Thank You for Using Our Tool* ✅
"""
            button_text = "View Profile"

        # Inline Button
        keyboard = [[InlineKeyboardButton(button_text, url=f"tg://user?id={user_id}")]] if user.username else []

        # Try Sending with Profile Photo
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][0].file_id
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=info_text,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=info_text,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=info_text,
                parse_mode="Markdown",
                reply_to_message_id=update.message.message_id,
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /translate command to translate text"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        lang = await self.detect_language(update.message.text)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect(lang)
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            if lang == 'bn':
                await update.message.reply_text("""
টেক্সট ট্রান্সলেট করতে, নিচের ফরম্যাট ব্যবহার করো:

ব্যবহার: `/translate <text> to <language>`

উদাহরণ: `/translate Hello world to Bengali`

উপলব্ধ ভাষা: {', '.join(list(LANGUAGES.values())[:10])} ... (আরো অনেক)
ভাষার পুরো তালিকা দেখতে চাও? অথবা কোনো টেক্সট ট্রান্সলেট করতে বলো!
                """, parse_mode='Markdown')
            else:
                await update.message.reply_text("""
To translate text, use the following format:

Usage: `/translate <text> to <language>`

Example: `/translate Hello world to Bengali`

Available languages: {', '.join(list(LANGUAGES.values())[:10])} ... (many more)
Want to see the full list of languages? Or just tell me some text to translate!
                """, parse_mode='Markdown')
            return

        args = ' '.join(context.args)
        match = re.match(r'(.+?)\s+to\s+(.+)', args, re.IGNORECASE)
        if not match:
            if lang == 'bn':
                await update.message.reply_text("ভুল ফরম্যাট। ব্যবহার করো: `/translate <text> to <language>`")
            else:
                await update.message.reply_text("Invalid format. Use: `/translate <text> to <language>`")
            return

        text, target_lang_name = match.groups()
        target_lang = None
        for code, name in LANGUAGES.items():
            if name.lower() == target_lang_name.lower():
                target_lang = code
                break
        if not target_lang:
            if lang == 'bn':
                await update.message.reply_text(f"ভাষা '{target_lang_name}' পাওয়া যায়নি। উপলব্ধ ভাষা: {', '.join(list(LANGUAGES.values())[:10])} ...")
            else:
                await update.message.reply_text(f"Language '{target_lang_name}' not found. Available languages: {', '.join(list(LANGUAGES.values())[:10])} ...")
            return

        translated_text = await self.translate_text(text, target_lang)
        if translated_text:
            if lang == 'bn':
                await update.message.reply_text(f"ট্রান্সলেশন ({target_lang_name}-তে):\n{translated_text}")
            else:
                await update.message.reply_text(f"Translation (to {target_lang_name}):\n{translated_text}")
        else:
            if lang == 'bn':
                await update.message.reply_text("ট্রান্সলেশনে সমস্যা হয়েছে। আবার চেষ্টা করবো?")
            else:
                await update.message.reply_text("Something went wrong with translation. Shall we try again?")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            lang = await self.detect_language(user_message)
            
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and 
                                 update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                if not (is_reply_to_bot or is_mentioned):
                    return
            elif chat_type == 'private' and user_id != ADMIN_USER_ID:
                response, reply_markup = await self.get_private_chat_redirect(lang)
                await update.message.reply_text(response, reply_markup=reply_markup)
                return
            
            # Check for translation request in message
            translate_match = re.search(r'translate\s+(.+?)\s+to\s+(.+)', user_message, re.IGNORECASE)
            if translate_match:
                text, target_lang_name = translate_match.groups()
                target_lang = None
                for code, name in LANGUAGES.items():
                    if name.lower() == target_lang_name.lower():
                        target_lang = code
                        break
                if target_lang:
                    translated_text = await self.translate_text(text, target_lang)
                    if translated_text:
                        if lang == 'bn':
                            response = f"ট্রান্সলেশন ({target_lang_name}-তে):\n{translated_text}"
                        else:
                            response = f"Translation (to {target_lang_name}):\n{translated_text}"
                        await update.message.reply_text(response)
                        return
                    else:
                        if lang == 'bn':
                            response = "ট্রান্সলেশনে সমস্যা হয়েছে। আবার চেষ্টা করবো?"
                        else:
                            response = "Something went wrong with translation. Shall we try again?"
                        await update.message.reply_text(response)
                        return
                else:
                    if lang == 'bn':
                        response = f"ভাষা '{target_lang_name}' পাওয়া যায়নি। উপলব্ধ ভাষা: {', '.join(list(LANGUAGES.values())[:10])} ..."
                    else:
                        response = f"Language '{target_lang_name}' not found. Available languages: {', '.join(list(LANGUAGES.values())[:10])} ..."
                    await update.message.reply_text(response)
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
                response = await self.generate_gemini_response(context_text, chat_type, is_coding_query, is_short_word, lang)
            else:
                if lang == 'bn':
                    response = "দুঃখিত, মডেল এখনো সংযুক্ত হয়নি। অ্যাডমিন /api কমান্ড দিয়ে সেট করতে পারে।"
                else:
                    response = "Sorry, the model is not connected yet. The admin can set it using the /api command."
            
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            group_activity[chat_id] = group_activity.get(chat_id, {'auto_mode': False, 'last_response': 0})
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()
            
            # If it's a coding query, add a "Copy Code" button
            if is_coding_query:
                code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)\n```', response)
                if code_block_match:
                    button_text = "কোড কপি করো" if lang == 'bn' else "Copy Code"
                    keyboard = [[InlineKeyboardButton(button_text, callback_data="copy_code")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
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
            if lang == 'bn':
                await update.message.reply_text("কিছু একটা গোলমাল হয়ে গেছে। আবার চেষ্টা করবো?")
            else:
                await update.message.reply_text("Something went wrong. Shall we try again?")

    async def generate_gemini_response(self, prompt, chat_type="private", is_coding_query=False, is_short_word=False, lang='bn'):
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
- Respond in the user's language (language code: {lang})
- Use friendly, natural language like a human
- Ask follow-up questions to keep the conversation engaging
- Share relatable thoughts and feelings
- Use humor when appropriate
- Be supportive in emotional moments
- Show excitement for good news
- Express concern for problems
- Never discuss inappropriate or offensive topics
- Do NOT start responses with the user's name or phrases like "ওহো" or "হায়" (in Bengali) or equivalent in other languages; respond directly and naturally

For Short Words (2 or 3 lowercase letters, is_short_word=True):
- If the user sends a 2 or 3 letter lowercase word (e.g., "ki", "ke", "ken" in Bengali), always provide a meaningful, friendly, and contextually relevant response in the user's language
- Interpret the word based on common usage (e.g., in Bengali, "ki" as "কী" for "what", "ke" as "কে" for "who", "ken" as "কেন" for "why") or conversation context
- If the word is ambiguous, make a creative and engaging assumption to continue the conversation naturally
- Never ask for clarification (e.g., avoid "What kind of word is this?" in any language); instead, provide a fun and relevant response
- Example for Bengali: For "ki", respond like "'কি' দিয়ে কী জানতে চাও? বাংলায় এটা প্রশ্নের জন্য ব্যবহৃত হয়, যেমন 'কী হচ্ছে?' কী নিয়ে গল্প করতে চাও?"

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
- Format the code in a Markdown code block (e.g., ```python\ncode here\n```)
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

Respond as I Master Tools. Keep it natural, engaging, surprising, and match the conversation's tone. Respond in the user's language (language code: {lang}). Do NOT start the response with the user's name or phrases like "ওহো" or "হায়" (or equivalents in other languages).
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            if not response.text or "error" in response.text.lower():
                if is_coding_query:
                    if lang == 'bn':
                        return "কোডিং প্রশ্নে একটু সমস্যা হয়েছে। আবার বলো, সঠিক কোড দিয়ে দেব!"
                    return "Something went wrong with the coding query. Try again, and I'll provide the correct code!"
                if lang == 'bn':
                    return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"
                return "Got a bit tangled up. What do you want to talk about?"
            translated_response = await self.translate_text(response.text, lang) if lang != 'en' else response.text
            return translated_response or response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            if is_coding_query:
                if lang == 'bn':
                    return "কোডিং প্রশ্নে একটু সমস্যা হয়েছে। আবার বলো, সঠিক কোড দিয়ে দেব!"
                return "Something went wrong with the coding query. Try again, and I'll provide the correct code!"
            if lang == 'bn':
                return "একটু ঘুরে গেছি। কী নিয়ে কথা বলতে চাও?"
            return "Got a bit tangled up. What do you want to talk about?"

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and hasattr(update, 'effective_chat') and hasattr(update, 'message'):
            lang = await self.detect_language(update.message.text)
            if lang == 'bn':
                await update.message.reply_text("কিছু একটা গোলমাল হয়ে গেছে। আবার চেষ্টা করবো?")
            else:
                await update.message.reply_text("Something went wrong. Shall we try again?")

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