import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))

# Global variables for dynamic API key and model management
current_gemini_api_key = GEMINI_API_KEY
general_model = None
coding_model = None
available_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-1.5-flash-8b']
current_model = 'gemini-1.5-flash'  # Default model

# Store conversation context for each chat
conversation_context = {}
group_activity = {}

# Store user language preferences: 'bn' or 'en'
user_languages = {}

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

# Context persistence functions
def save_context():
    try:
        with open('context.json', 'w') as f:
            json.dump(conversation_context, f)
    except Exception as e:
        logger.error(f"Failed to save context: {e}")

def load_context():
    global conversation_context
    try:
        with open('context.json', 'r') as f:
            conversation_context = json.load(f)
    except FileNotFoundError:
        conversation_context = {}
    except Exception as e:
        logger.error(f"Failed to load context: {e}")

load_context()

def get_text(user_id, bn_text, en_text):
    """Return text based on user's language preference"""
    return bn_text if user_languages.get(user_id, 'bn') == 'bn' else en_text

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
        self.application.add_handler(CommandHandler("lang", self.lang_command))
        self.application.add_handler(CommandHandler("adminstats", self.adminstats_command))

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.spam_filter))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^copy_code$'))
        self.application.add_error_handler(self.error_handler)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle copy code button callback"""
        query = update.callback_query
        await query.answer(get_text(query.from_user.id, "কোড কপি হয়েছে!", "Code copied!"))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response = get_text(
                user_id,
                """
হ্যালো, আমার সাথে কথা বলতে চাওয়ার জন্য ধন্যবাদ! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। আমার সাথে মজার এবং সহায়ক কথোপকথনের জন্য, দয়া করে আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে গ্রুপে যাও এবং আমাকে @I MasterTools মেনশন করে কথা শুরু করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
                """,
                f"""
Hello, thank you for wanting to chat with me! I am I Master Tools, your friendly companion. For fun and helpful conversations, please join our official group. Click the button below to join and mention @I MasterTools to start chatting. I'll be waiting for you there!
                """
            )
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            welcome_message = get_text(
                user_id,
                f"""
Hello {username}, welcome to I Master Tools, your friendly companion!

To chat with me, please join our official Telegram group or mention @I MasterTools in the group. Click the button below to join the group!

Available commands:
- /help: Get help and usage information
- /menu: Access the feature menu
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}
                
In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
                """,
                f"""
Hello {username}, welcome to I Master Tools, your friendly companion!

To chat with me, please join our official Telegram group or mention @I MasterTools in the group. Click the button below to join the group!

Available commands:
- /help: Get help and usage information
- /menu: Access the feature menu
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}
                
In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
                """
            )
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_id = new_member.id
            user_mention = f"@{new_member.username}" if new_member.username else username
            welcome_message = get_text(
                user_id,
                f"""
স্বাগতম {user_mention}! আমাদের VPSHUB_BD_CHAT গ্রুপে তোমাকে পেয়ে আমরা খুবই উৎসাহিত! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী। এখানে তুমি মজার কথোপকথন, সহায়ক উত্তর, এবং আরো অনেক কিছু পাবে। আমাকে @I MasterTools মেনশন করে বা রিপ্লাই করে কথা শুরু করো। তুমি কী নিয়ে কথা বলতে চাও?
                """,
                f"""
Welcome {user_mention}! We are excited to have you in VPSHUB_BD_CHAT group! I am I Master Tools, your friendly companion. Here you will find fun conversations, helpful answers, and much more. Mention me @I MasterTools or reply to start chatting. What would you like to talk about?
                """
            )
            await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        keyboard = [
            [InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        response = get_text(
            user_id,
            """
হেল্প কমান্ড:  
- /start: বট শুরু করুন  
- /help: সাহায্য পান  
- /clear: কথোপকথন মুছে ফেলুন  
- /status: বটের অবস্থা দেখুন  
- /checkmail: টেম্পোরারি ইমেইল চেক করুন  
- /lang <bn/en>: ভাষা পরিবর্তন করুন  
- /setmodel <model_name>: মডেল পরিবর্তন (এডমিন)  
- /api <key>: Gemini API কী সেট করুন (এডমিন)  
- /adminstats: এডমিন স্ট্যাটাস দেখুন  
            """,
            """
Help commands:  
- /start: Start the bot  
- /help: Get help  
- /clear: Clear conversation history  
- /status: Check bot status  
- /checkmail: Check temporary email inbox  
- /lang <bn/en>: Change language  
- /setmodel <model_name>: Change model (admin only)  
- /api <key>: Set Gemini API key (admin only)  
- /adminstats: View admin stats  
            """
        )
        await update.message.reply_text(response, reply_markup=reply_markup)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        conversation_context.pop(str(user_id), None)
        save_context()
        await update.message.reply_text(get_text(user_id, "আপনার কথোপকথন মুছে ফেলা হয়েছে।", "Your conversation history has been cleared."))

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        status_msg = get_text(
            user_id,
            f"বর্তমান মডেল: {current_model}\nGemini API কী সেট আছে: {'হ্যাঁ' if current_gemini_api_key else 'না'}",
            f"Current model: {current_model}\nGemini API key set: {'Yes' if current_gemini_api_key else 'No'}"
        )
        await update.message.reply_text(status_msg)

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text(get_text(user_id, "আপনার অনুমতি নেই।", "You are not authorized."))
            return
        if not context.args:
            await update.message.reply_text(get_text(user_id, "দয়া করে API কী প্রদান করুন।", "Please provide an API key."))
            return
        api_key = context.args[0]
        success, msg = initialize_gemini_models(api_key)
        if success:
            await update.message.reply_text(get_text(user_id, "Gemini API সফলভাবে কনফিগার হয়েছে।", "Gemini API configured successfully."))
        else:
            await update.message.reply_text(get_text(user_id, f"ত্রুটি: {msg}", f"Error: {msg}"))

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Placeholder: আপনার নিজের লজিক এখানে যোগ করুন
        await update.message.reply_text(get_text(update.effective_user.id, "এই ফিচারটি এখনও উপলব্ধ নয়।", "This feature is not available yet."))

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Placeholder for temporary email checking logic
        await update.message.reply_text(get_text(update.effective_user.id, "টেম্পোরারি ইমেইল চেক ফিচার আসছে।", "Temporary email check feature coming soon."))

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Placeholder for menu options
        await update.message.reply_text(get_text(update.effective_user.id, "মেনু ফিচার আসছে।", "Menu feature coming soon."))

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text(get_text(user_id, "আপনার অনুমতি নেই।", "You are not authorized."))
            return
        if not context.args or context.args[0] not in available_models:
            await update.message.reply_text(get_text(user_id, f"সঠিক মডেল নাম দিন। উপলব্ধ মডেল: {', '.join(available_models)}", f"Please provide a valid model name. Available models: {', '.join(available_models)}"))
            return
        global current_model
        current_model = context.args[0]
        success, msg = initialize_gemini_models(current_gemini_api_key)
        await update.message.reply_text(msg)

    async def lang_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args or context.args[0].lower() not in ['bn', 'en']:
            await update.message.reply_text("Usage: /lang bn or /lang en")
            return
        user_languages[user_id] = context.args[0].lower()
        await update.message.reply_text(get_text(user_id, "ভাষা সফলভাবে পরিবর্তন হয়েছে।", "Language changed successfully."))

    async def adminstats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text(get_text(user_id, "আপনার অনুমতি নেই।", "You are not authorized."))
            return
        stats = f"Current model: {current_model}\nActive chats: {len(conversation_context)}\nAPI Key set: {'Yes' if current_gemini_api_key else 'No'}"
        await update.message.reply_text(stats)

    async def spam_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.lower()
        # উদাহরণ স্প্যাম শব্দ
        spam_words = ['spamword1', 'spamword2', 'buy now', 'free money']
        if any(word in text for word in spam_words):
            try:
                await update.message.delete()
                await update.message.reply_text(get_text(update.effective_user.id, "স্প্যাম মেসেজ ডিলিট করা হয়েছে।", "Spam message deleted."))
            except Exception as e:
                logger.error(f"Failed to delete spam message: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        # এখানে আপনার Gemini API কল করে রেসপন্স তৈরি করবেন
        # উদাহরণস্বরূপ, সরল রেসপন্স:
        response = f"আপনি বললেন: {text}" if user_languages.get(user_id, 'bn') == 'bn' else f"You said: {text}"
        await update.message.reply_text(response)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(get_text(update.effective_user.id, "ছবি পেয়েছি, কিন্তু এখনো প্রক্রিয়াকরণ সাপোর্ট নেই।", "Photo received, but processing is not supported yet."))

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(get_text(update.effective_user.id, "ভয়েস মেসেজ পেয়েছি, কিন্তু এখনো প্রক্রিয়াকরণ সাপোর্ট নেই।", "Voice message received, but processing is not supported yet."))

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        try:
            if update and hasattr(update, "message") and update.message:
                await update.message.reply_text(get_text(update.effective_user.id, "দুঃখিত, কিছু একটা ভুল হয়েছে। আবার চেষ্টা করুন।", "Sorry, something went wrong. Please try again."))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    def run(self):
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramGeminiBot()
    bot.run()