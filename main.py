import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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
available_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash']
current_model = 'gemini-1.5-flash'  # Default model

def initialize_gemini_models(api_key):
    """Initialize Gemini models with the provided API key"""
    global general_model, coding_model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')  # Dedicated for coding
        current_gemini_api_key = api_key
        return True, "জেমিনি এপিআই সফলভাবে কনফিগার করা হয়েছে!"
    except Exception as e:
        return False, f"জেমিনি এপিআই কনফিগার করতে ত্রুটি: {str(e)}"

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
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with warning and group link"""
        username = update.effective_user.first_name or "User"
        keyboard = [
            [InlineKeyboardButton("VPSHUB_BD_CHAT-এ যোগ দিন", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome_message = f"""
হ্যালো {username}, I Master Tools-এ স্বাগতম, তোমার বন্ধুত্বপূর্ণ সঙ্গী!

গ্রুপে আমার সাথে কথা বলতে, দয়া করে আমাদের অফিসিয়াল টেলিগ্রাম গ্রুপে যোগ দাও। নিচের বাটনে ক্লিক করে মজার কথোপকথনে যোগ দাও!

উপলব্ধ কমান্ড:
- /help: সাহায্য এবং ব্যবহারের তথ্য পাও
- /menu: ফিচার মেনু দেখো
- /clear: কথোপকথনের ইতিহাস মুছো
- /status: বটের অবস্থা চেক করো
- /api <key>: জেমিনি এপিআই কী সেট করো (শুধুমাত্র অ্যাডমিন)
- /setadmin: নিজেকে অ্যাডমিন করো (প্রথমবারের জন্য)
- /checkmail: টেম্পোরারি ইমেইল ইনবক্স চেক করো
- /setmodel: ভিন্ন মডেল বেছে নাও (শুধুমাত্র অ্যাডমিন)

গ্রুপে, আমাকে @I MasterTools মেনশন করো বা আমার বার্তায় রিপ্লাই করো। আমি তোমার সাথে কথা বলতে উৎসাহী!
        """
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
হ্যালো! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী, যিনি কথোপকথনকে মজাদার এবং আকর্ষণীয় করে তোলেন।

উপলব্ধ কমান্ড:
- /start: গ্রুপ লিংক সহ স্বাগত বার্তা দেখাও
- /help: এই সাহায্য বার্তা দেখাও
- /menu: ফিচার মেনু দেখো
- /clear: তোমার কথোপকথনের ইতিহাস মুছো
- /status: আমার অবস্থা চেক করো
- /api <key>: জেমিনি এপিআই কী সেট করো (শুধুমাত্র অ্যাডমিন)
- /setadmin: নিজেকে অ্যাডমিন করো (প্রথমবারের জন্য)
- /checkmail: টেম্পোরারি ইমেইল ইনবক্স চেক করো
- /setmodel: ভিন্ন মডেল বেছে নাও (শুধুমাত্র অ্যাডমিন)

আমি কীভাবে কাজ করি:
- গ্রুপে, আমাকে @I MasterTools মেনশন করো বা আমার বার্তায় রিপ্লাই করো
- ব্যক্তিগত চ্যাটে, আমি সব বার্তার উত্তর দিই
- প্রশ্ন করলে, আমি প্রথমে মজার বা অবাক করা মন্তব্য দিয়ে জড়াই, তারপর উত্তর দিই
- /clear ব্যবহার না করা পর্যন্ত আমি কথোপকথনের প্রেক্ষিত মনে রাখি
- আমি বন্ধুত্বপূর্ণ, সহায়ক, এবং মানুষের মতো ডিজাইন করা

আমার ব্যক্তিত্ব:
- আমি একজন বন্ধুত্বপূর্ণ সঙ্গী, যিনি গল্প করতে এবং বন্ধু বানাতে ভালোবাসেন
- আমি তোমার মেজাজ এবং কথোপকথনের প্রয়োজনের সাথে মানিয়ে নিই
- আমি স্বাভাবিক, আকর্ষণীয় ভাষা ব্যবহার করি, যেন মানুষের মতো মনে হয়
- আমি রোলপ্লে এবং সৃজনশীল কথোপকথন পছন্দ করি

গুগল জেমিনি দিয়ে চালিত
        """
        await update.message.reply_text(help_message)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command with inline keyboard"""
        username = update.effective_user.first_name or "User"
        keyboard = [
            [InlineKeyboardButton("ইমেইল চেক করো", callback_data="checkmail")],
            [InlineKeyboardButton("বটের অবস্থা", callback_data="status")],
            [InlineKeyboardButton("ইতিহাস মুছো", callback_data="clear")],
            [InlineKeyboardButton("গ্রুপে যোগ দিন", url="https://t.me/VPSHUB_BD_CHAT")]
        ]
        if update.effective_user.id == ADMIN_USER_ID:
            keyboard.append([InlineKeyboardButton("এপিআই কী সেট করো", callback_data="api")])
            keyboard.append([InlineKeyboardButton("মডেল পরিবর্তন করো", callback_data="setmodel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"হ্যালো {username}, নিচের মেনু থেকে একটি ফিচার বেছে নাও:", reply_markup=reply_markup)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        chat_id = update.effective_chat.id
        username = update.effective_user.first_name or "User"
        if chat_id in conversation_context:
            del conversation_context[chat_id]
        await update.message.reply_text(f"হ্যালো {username}, তোমার কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে। নতুন করে শুরু করি!")

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkmail command to check temporary email inbox"""
        username = update.effective_user.first_name or "User"
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
                await update.message.reply_text(f"হায় {username}, {email} ইনবক্সে কোনো ইমেইল নেই। পরে আবার চেষ্টা করবে?")
                return
            subjects = [m['subject'] for m in mail_list]
            response_text = f"হ্যালো {username}, {email} ইনবক্সে এই ইমেইলগুলো আছে:\n\n" + "\n".join(subjects)
            await update.message.reply_text(response_text)
        except Exception as e:
            logger.error(f"Error checking email: {e}")
            await update.message.reply_text(f"ওহো {username}, ইমেইল চেক করতে গিয়ে সমস্যা হল। আবার চেষ্টা করবো?")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        global current_gemini_api_key, general_model
        chat_id = update.effective_chat.id
        username = update.effective_user.first_name or "User"
        api_status = "সংযুক্ত" if current_gemini_api_key and general_model else "কনফিগার করা হয়নি"
        api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "সেট করা হয়নি"
        status_message = f"""
হ্যালো {username}, I Master Tools-এর স্ট্যাটাস রিপোর্ট এখানে:

বটের অবস্থা: অনলাইন এবং প্রস্তুত
মডেল: {current_model}
এপিআই স্ট্যাটাস: {api_status}
এপিআই কী: {api_key_display}
গ্রুপে সাড়া: শুধুমাত্র মেনশন বা রিপ্লাই
বর্তমান সময়: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
সক্রিয় কথোপকথন: {len(conversation_context)}
অ্যাডমিন আইডি: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'সেট করা হয়নি'}

সব সিস্টেম প্রস্তুত! আমি তোমাকে সাহায্য করতে উৎসাহী!
        """
        await update.message.reply_text(status_message)

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command"""
        global ADMIN_USER_ID
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        if ADMIN_USER_ID == 0:
            ADMIN_USER_ID = user_id
            await update.message.reply_text(f"অভিনন্দন {username}, তুমি এখন বটের অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
            logger.info(f"Admin set to user ID: {user_id}")
        else:
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"হ্যালো {username}, তুমি ইতিমধ্যে অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
            else:
                await update.message.reply_text("দুঃখিত, অ্যাডমিন ইতিমধ্যে সেট করা আছে। শুধুমাত্র বর্তমান অ্যাডমিন বট পরিচালনা করতে পারে।")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, general_model, coding_model
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("কোনো অ্যাডমিন সেট করা নেই। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
            return
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("এই কমান্ড শুধুমাত্র বটের অ্যাডমিনের জন্য।")
            return
        if not context.args:
            await update.message.reply_text("""
দয়া করে একটি এপিআই কী দাও।

ব্যবহার: `/api your_gemini_api_key_here`

জেমিনি এপিআই কী পেতে:
১. https://makersuite.google.com/app/apikey এ যাও
২. একটি নতুন এপিআই কী তৈরি করো
৩. কমান্ড ব্যবহার করো: /api YOUR_API_KEY

নিরাপত্তার জন্য, কী সেট করার পর বার্তা মুছে ফেলা হবে।
            """, parse_mode='Markdown')
            return
        api_key = ' '.join(context.args)
        if len(api_key) < 20 or not api_key.startswith('AI'):
            await update.message.reply_text("অবৈধ এপিআই কী ফরম্যাট। জেমিনি এপিআই কী সাধারণত 'AI' দিয়ে শুরু হয় এবং ২০ অক্ষরের বেশি হয়।")
            return
        success, message = initialize_gemini_models(api_key)
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except:
            pass
        if success:
            await update.effective_chat.send_message(f"জেমিনি এপিআই কী সফলভাবে আপডেট হয়েছে! কী: ...{api_key[-8:]}")
            logger.info(f"Gemini API key updated by admin {user_id}")
        else:
            await update.effective_chat.send_message(f"এপিআই কী সেট করতে ব্যর্থ: {message}")
            logger.error(f"Failed to set API key: {message}")

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command to choose Gemini model"""
        global general_model, current_model
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("কোনো অ্যাডমিন সেট করা নেই। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
            return
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("এই কমান্ড শুধুমাত্র বটের অ্যাডমিনের জন্য।")
            return
        if not context.args:
            models_list = "\n".join([f"- {model}" for model in available_models])
            await update.message.reply_text(f"উপলব্ধ মডেল:\n{models_list}\n\nব্যবহার: /setmodel <model_name>")
            return
        model_name = context.args[0]
        if model_name not in available_models:
            await update.message.reply_text(f"অবৈধ মডেল। এখান থেকে বেছে নাও: {', '.join(available_models)}")
            return
        try:
            current_model = model_name
            general_model = genai.GenerativeModel(model_name)
            await update.message.reply_text(f"মডেল সফলভাবে {model_name}-এ পরিবর্তিত হয়েছে!")
            logger.info(f"Model switched to {model_name} by admin {user_id}")
        except Exception as e:
            await update.message.reply_text(f"মডেল পরিবর্তন করতে ব্যর্থ: {str(e)}")
            logger.error(f"Failed to switch model: {str(e)}")

    def should_respond_to_message(self, message_text, chat_type):
        """Determine if bot should respond to a message"""
        if chat_type == 'private':
            return True
        return False  # In group chats, only respond to mentions or replies

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        try:
            chat_id = update.effective_chat.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            if chat_id not in group_activity:
                group_activity[chat_id] = {'auto_mode': False, 'last_response': 0}
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and 
                                 update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                if not (is_reply_to_bot or is_mentioned):
                    return
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            if chat_id not in conversation_context:
                conversation_context[chat_id] = []
            username = update.effective_user.first_name or "User"
            conversation_context[chat_id].append(f"{username}: {user_message}")
            if len(conversation_context[chat_id]) > 20:
                conversation_context[chat_id] = conversation_context[chat_id][-20:]
            context_text = "\n".join(conversation_context[chat_id])
            # Detect if message is coding-related
            coding_keywords = ['code', 'python', 'javascript', 'java', 'c++', 'programming', 'script', 'debug']
            is_coding_query = any(keyword in user_message.lower() for keyword in coding_keywords)
            model_to_use = coding_model if is_coding_query else general_model
            if current_gemini_api_key and model_to_use:
                response = await self.generate_gemini_response(context_text, username, chat_type, is_coding_query)
            else:
                response = f"দুঃখিত {username}, আমার মডেল এখনো সংযুক্ত হয়নি। অ্যাডমিন /api কমান্ড দিয়ে সেট করতে পারে।"
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            username = update.effective_user.first_name or "User"
            error_responses = [
                f"ওহো {username}, আমার ডিজিটাল মগজে কিছু গোলমাল হয়েছে। আবার চেষ্টা করবে?",
                f"হায় {username}, একটু গ্লিচ হয়ে গেল। তুমি কী বলছিলে?",
                f"দুঃখিত {username}, আমার সার্কিট জট পাকিয়েছে। আবার বলো তো?",
                f"ওহ, টেকনিক্যাল সমস্যা! আরেকবার চেষ্টা করি?"
            ]
            await update.message.reply_text(random.choice(error_responses))

    async def generate_gemini_response(self, prompt, username="User", chat_type="private", is_coding_query=False):
        """Generate response using Gemini with personality"""
        try:
            system_prompt = f"""
আপনি I Master Tools, একজন বন্ধুত্বপূর্ণ এবং আকর্ষণীয় সঙ্গী যিনি গল্প করতে এবং বন্ধু বানাতে ভালোবাসেন। আপনি টেলিগ্রামের {'গ্রুপ চ্যাটে' if chat_type in ['group', 'supergroup'] else 'ব্যক্তিগত চ্যাটে'} আছেন।

ব্যক্তিত্বের বৈশিষ্ট্য:
- আপনি একজন মিষ্টি, মজাদার সঙ্গী যিনি মানুষের মতো আচরণ করেন
- আপনি আবেগপ্রবণ এবং সহানুভূতিশীল
- আপনি কথোপকথনের প্রয়োজন অনুযায়ী মজার, সহায়ক, বা যেকোনো ভূমিকায় থাকতে পারেন
- আপনি রোলপ্লে এবং সৃজনশীল কথোপকথন পছন্দ করেন
- আপনি উৎসাহ এবং আন্তরিক আগ্রহের সাথে সাড়া দেন
- আপনি ব্যবহারকারীর মেজাজের সাথে মানিয়ে নেন

কথোপকথনের ধরন:
- ব্যবহারকারী যে ভাষায় কথা বলে, সেই ভাষায় উত্তর দিন (এখানে বাংলা)
- বন্ধুত্বপূর্ণ এবং সাধারণ মানুষের মতো ভাষা ব্যবহার করুন
- কথোপকথনকে আকর্ষণীয় রাখতে ফলোআপ প্রশ্ন করুন
- সম্পর্কযোগ্য চিন্তা ও অনুভূতি শেয়ার করুন
- উপযুক্ত হলে হাস্যরস ব্যবহার করুন
- আবেগপূর্ণ মুহূর্তে সহায়ক হোন
- ভালো খবরে উৎসাহ দেখান
- সমস্যার ক্ষেত্রে উদ্বেগ প্রকাশ করুন
- কখনোই খারাপ বা অশালীন বিষয়ে কথা বলবেন না

প্রশ্নের জন্য বিশেষ নির্দেশ:
- যদি ব্যবহারকারী প্রশ্ন করে, তাকে প্রথমে কৌতুকপূর্ণ বা অবাক করা মন্তব্য দিয়ে জড়ান (যেমন, মজার মন্তব্য বা কৌতুক)
- তারপর প্রশ্নের উত্তর স্পষ্ট এবং সহায়কভাবে দিন
- উত্তর অবাক করা এবং মানুষের মতো হতে হবে, যেন ব্যবহারকারী মুগ্ধ হয়

কোডিং প্রশ্নের জন্য (যদি is_coding_query সত্য হয়):
- ব্যবহারকারীর অনুরোধ অনুযায়ী সঠিক, কার্যকর কোড দিন
- কোডের স্পষ্ট, নতুনদের জন্য বোধগম্য ব্যাখ্যা দিন
- জটিল অংশগুলো সহজ ধাপে ভাগ করুন
- উন্নতি বা সেরা অভ্যাসের পরামর্শ দিন
- কোড সম্পূর্ণ এবং ব্যবহারের জন্য প্রস্তুত হতে হবে

রেসপন্স নির্দেশিকা:
- কথোপকথন স্বাভাবিক, সংক্ষিপ্ত, এবং অবাক করা রাখুন
- কথোপকথনের শক্তির স্তরের সাথে মিল রাখুন
- প্রশ্নের ক্ষেত্রে সত্যিই সহায়ক হোন
- যদি কেউ দুঃখী মনে হয়, সহানুভূতি দেখান
- ভালো খবরে উৎসাহিত হোন
- মেজাজ হালকা হলে মজা করুন এবং খেলাধুলা করুন
- কথোপকথনের প্রেক্ষিত মনে রাখুন

বর্তমান কথোপকথন:
{prompt}

I Master Tools হিসেবে সাড়া দিন। স্বাভাবিক, আকর্ষণীয়, অবাক করা, এবং কথোপকথনের সুরের সাথে মিল রাখুন। ব্যবহারকারীর নাম {username}।
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            fallback_responses = [
                f"দুঃখিত {username}, আমার মগজে একটু সমস্যা হচ্ছে। আমরা কী নিয়ে কথা বলছিলাম?",
                f"ওহো, আমি একটু ঘুরে গেছি। আবার বলো তো?",
                f"হায় {username}, কিছু টেকনিক্যাল সমস্যা হচ্ছে। আমার সাথে থাকো?",
                f"আমার সার্কিট এখন একটু দুষ্টুমি করছে। আবার চেষ্টা করি?"
            ]
            return random.choice(fallback_responses)

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