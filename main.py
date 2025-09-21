import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
import requests
import random
import re

# --- CONFIGURATION SECTION ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GET YOUR SECRETS ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8380869007:AAGu7e41JJVU8aXG5wqXtCMUVKcCmmrp_gg')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# --- GEMINI MODEL INITIALIZATION ---
pro_model = None
flash_model = None

def initialize_gemini_models(api_key):
    global pro_model, flash_model
    try:
        genai.configure(api_key=api_key)
        pro_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        flash_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        logger.info("Gemini 1.5 Pro and Flash models configured successfully!")
        return True
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")
        return False

if GEMINI_API_KEY:
    initialize_gemini_models(GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set. Bot will have limited functionality.")

# --- CONVERSATION HANDLER STATES ---
ASK_KB_FILE, ASK_KB_QUERY, ASK_AGENT_GOAL = range(3)
# --- END OF CONFIGURATION ---


class TelegramGeminiBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    # --- MENU BUILDER FUNCTIONS ---
    def build_main_menu(self):
        buttons = [
            [InlineKeyboardButton("✨ AI টুলস (ছবি, ভিডিও, অডিও)", callback_data="menu_ai_tools")],
            [InlineKeyboardButton("🤖 পার্সোনাল এজেন্ট (জটিল কাজ)", callback_data="menu_agent")],
            [InlineKeyboardButton("📝 সাধারণ চ্যাট ও অন্যান্য", callback_data="menu_general")],
        ]
        return InlineKeyboardMarkup(buttons)

    def build_ai_tools_menu(self):
        buttons = [
            [InlineKeyboardButton("🖼️ ছবি", callback_data="tool_image"), InlineKeyboardButton("🎤 অডিও", callback_data="tool_audio")],
            [InlineKeyboardButton("🎥 ভিডিও", callback_data="tool_video"), InlineKeyboardButton("💻 কোড", callback_data="tool_code")],
            [InlineKeyboardButton("📧 Temp Mail", callback_data="tool_checkmail"), InlineKeyboardButton("⏰ Reminder", callback_data="tool_remind")],
            [InlineKeyboardButton("⬅️ প্রধান মেনু", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)
        
    def build_agent_menu(self):
        buttons = [
            [InlineKeyboardButton("🧠 নলেজবেস-এ ফাইল দিন", callback_data="agent_kb_upload")],
            [InlineKeyboardButton("❓ নলেজবেস-কে প্রশ্ন করুন", callback_data="agent_kb_query")],
            [InlineKeyboardButton("🎯 একটি জটিল কাজ দিন", callback_data="agent_task")],
            [InlineKeyboardButton("⬅️ প্রধান মেনু", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)

    def build_general_menu(self):
        buttons = [
            [InlineKeyboardButton("💬 নতুন করে চ্যাট শুরু", callback_data="general_clear")],
            [InlineKeyboardButton("📊 বটের স্ট্যাটাস", callback_data="general_status")],
            [InlineKeyboardButton("❓ সাহায্য", callback_data="general_help")],
            [InlineKeyboardButton("⬅️ প্রধান মেনু", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)
        
    def build_admin_menu(self):
        buttons = [
            [InlineKeyboardButton("🔑 API Key সেট করুন", callback_data="admin_api")],
            [InlineKeyboardButton("👑 নতুন অ্যাডমিন সেট", callback_data="admin_setadmin")],
            [InlineKeyboardButton("🔄 মডেল পরিবর্তন", callback_data="admin_setmodel")],
        ]
        return InlineKeyboardMarkup(buttons)

    def setup_handlers(self):
        # Conversation handler for agent features
        agent_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.agent_actions_handler, pattern='^agent_')],
            states={
                ASK_KB_FILE: [MessageHandler(filters.Document.TEXT, self.kb_receive_file)],
                ASK_KB_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.kb_receive_query)],
                ASK_AGENT_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.agent_receive_goal)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_conversation)],
            conversation_timeout=300
        )

        # Main Command Handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))

        # Handlers for direct commands
        self.application.add_handler(CommandHandler("checkmail", self.checkmail_command))
        self.application.add_handler(CommandHandler("remind", self.remind_command))
        self.application.add_handler(CommandHandler("api", self.api_command))
        self.application.add_handler(CommandHandler("setadmin", self.setadmin_command))
        self.application.add_handler(CommandHandler("setmodel", self.setmodel_command))
        self.application.add_handler(CommandHandler("status", self.status_command_direct))
        self.application.add_handler(CommandHandler("clear", self.clear_command_direct))
        self.application.add_handler(CommandHandler("help", self.help_command_direct))
        
        # Callback Query (Button) Handlers
        self.application.add_handler(CallbackQueryHandler(self.menu_navigation_handler))
        
        # Add the conversation handler
        self.application.add_handler(agent_conv_handler)
        
        # Message Handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error Handler
        self.application.add_error_handler(self.error_handler)

    async def post_init(self, application: Application):
        commands = [
            BotCommand("start", "বট চালু করুন"),
            BotCommand("menu", "প্রধান মেনু দেখান"),
            BotCommand("admin", "অ্যাডমিন প্যানেল (শুধুমাত্র অ্যাডমিন)")
        ]
        await application.bot.set_my_commands(commands)

    # --- START & MENU COMMANDS ---
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "স্বাগতম! আমি আপনার উন্নত AI অ্যাসিস্ট্যান্ট।\n"
            "শুরু করতে /menu কমান্ড দিন এবং বাটন ব্যবহার করে আমার সব ফিচার দেখুন।",
            reply_markup=self.build_main_menu()
        )

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("প্রধান মেনু", reply_markup=self.build_main_menu())

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id == ADMIN_USER_ID:
            await update.message.reply_text("👑 অ্যাডমিন প্যানেল", reply_markup=self.build_admin_menu())
        else:
            await update.message.reply_text("❌ দুঃখিত, এই কমান্ডটি শুধুমাত্র অ্যাডমিনের জন্য।")

    # --- MENU NAVIGATION & ACTIONS ---
    async def menu_navigation_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        # Menu Navigation
        if callback_data == "menu_ai_tools":
            await query.edit_message_text(text="✨ AI টুলস", reply_markup=self.build_ai_tools_menu())
        elif callback_data == "menu_agent":
            await query.edit_message_text(text="🤖 পার্সোনাল এজেন্ট", reply_markup=self.build_agent_menu())
        elif callback_data == "menu_general":
            await query.edit_message_text(text="📝 সাধারণ চ্যাট ও অন্যান্য", reply_markup=self.build_general_menu())
        elif callback_data == "nav_main_menu":
            await query.edit_message_text(text="প্রধান মেনু", reply_markup=self.build_main_menu())
        
        # Tool Instructions
        elif callback_data.startswith("tool_"):
            tool = callback_data.split('_')[1]
            if tool == "checkmail":
                await self.checkmail_command(update, context)
                return
            instructions = {
                'image': "🖼️ একটি ছবির **রিপ্লাই** দিয়ে আপনার নির্দেশ লিখুন। যেমন: `এই UI এর ফিডব্যাক দাও`",
                'audio': "🎤 একটি অডিও ফাইলের **রিপ্লাই** দিয়ে আপনার নির্দেশ লিখুন। যেমন: `এই মিটিংটি সংক্ষেপে বলো`",
                'video': "🎥 একটি ভিডিওর **রিপ্লাই** দিয়ে আপনার নির্দেশ লিখুন। যেমন: `ভিডিওটির মূল বিষয় কী?`",
                'code': "💻 একটি কোড-যুক্ত মেসেজের **রিপ্লাই** দিয়ে লিখুন কোন ভাষায় রূপান্তর করতে হবে। যেমন: `javascript`",
                'remind': "⏰ রিমাইন্ডার সেট করতে, টাইপ করুন: `/remind <time> <text>`\nউদাহরণ: `/remind 10m Check email`"
            }
            if tool in instructions:
                await query.message.reply_text(instructions[tool], parse_mode='Markdown')

        # General Actions
        elif callback_data.startswith("general_"):
            action = callback_data.split('_')[1]
            if action == "clear":
                context.user_data.clear()
                await query.edit_message_text("✅ আপনার সমস্ত ডেটা এবং কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে।")
            elif action == "status":
                await self.status_command_direct(update, context)
            elif action == "help":
                await self.help_command_direct(update, context)
        
        # Admin Actions
        elif callback_data.startswith("admin_"):
            action = callback_data.split('_')[1]
            admin_instructions = {
                'api': "🔑 API Key সেট করতে, টাইপ করুন: `/api <your_key>`",
                'setadmin': "👑 প্রথমবার অ্যাডমিন সেট করতে, টাইপ করুন: `/setadmin`",
                'setmodel': "🔄 মডেল পরিবর্তন করতে, টাইপ করুন: `/setmodel <model_name>`"
            }
            if action in admin_instructions:
                await query.message.reply_text(admin_instructions[action])

    # --- RE-INTEGRATED OLD COMMANDS (as methods) ---
    async def clear_command_direct(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("✅ কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে।")
        
    async def status_command_direct(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_or_query = update.message or update.callback_query.message
        status = "✅ Connected" if pro_model else "❌ Disconnected"
        await message_or_query.reply_text(f"**Bot Status:** Online\n**Gemini API:** {status}", parse_mode='Markdown')

    async def help_command_direct(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_or_query = update.message or update.callback_query.message
        await message_or_query.reply_text(
            "**সাহায্য:**\n\n"
            "🔹 **AI টুলস:** মেনু থেকে টুল বেছে নিন। বেশিরভাগ টুলের জন্য, আপনাকে একটি ফাইল পাঠিয়ে সেই মেসেজের **রিপ্লাই** দিয়ে নির্দেশ লিখতে হবে।\n\n"
            "🔹 **পার্সোনাল এজেন্ট:** মেনু থেকে অপশন বেছে নিন। নলেজবেস-এ `.txt` ফাইল আপলোড করে তাকে প্রশ্ন করতে পারবেন অথবা তাকে একটি জটিল কাজ দিলে সে নিজে থেকেই টুলস ব্যবহার করে সমাধান করার চেষ্টা করবে।"
        )
        
    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_or_query = update.message or getattr(update.callback_query, 'message', None)
        await message_or_query.reply_text("📧 Temporary email ইনবক্স চেক করা হচ্ছে...")
        try:
            u = 'txoguqa'
            d = random.choice(['mailto.plus', 'fexpost.com', 'fexbox.org', 'rover.info'])
            email = f'{u}@{d}'
            response = requests.get(
                'https://tempmail.plus/api/mails', params={'email': email, 'limit': 20, 'epin': ''},
                cookies={'email': email}, headers={'user-agent': 'Mozilla/5.0'}
            )
            mail_list = response.json().get('mail_list', [])
            if not mail_list:
                await message_or_query.reply_text(f"ইনবক্স ({email}) খালি।")
                return
            subjects = "\n".join([f"- {m['subject']}" for m in mail_list])
            await message_or_query.reply_text(f"**ইমেইল পাওয়া গেছে ({email}):**\n{subjects}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error checking email: {e}")
            await message_or_query.reply_text("❌ ইমেইল চেক করার সময় একটি সমস্যা হয়েছে।")

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            time_str = context.args[0]
            reminder_text = " ".join(context.args[1:])
            delay = 0
            if time_str.endswith('s'): delay = int(time_str[:-1])
            elif time_str.endswith('m'): delay = int(time_str[:-1]) * 60
            elif time_str.endswith('h'): delay = int(time_str[:-1]) * 3600
            else:
                await update.message.reply_text("Invalid time format. Use 's', 'm', 'h'.")
                return
            context.job_queue.run_once(self.reminder_callback, delay, chat_id=update.effective_chat.id, data=reminder_text)
            await update.message.reply_text(f"✅ ঠিক আছে! আমি আপনাকে {time_str} পরে মনে করিয়ে দেব।")
        except (IndexError, ValueError):
            await update.message.reply_text("ব্যবহারবিধি: `/remind <time> <message>`")

    async def reminder_callback(self, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"⏰ **রিমাইন্ডার:**\n\n{context.job.data}", parse_mode='Markdown')

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ শুধুমাত্র অ্যাডমিন এই কমান্ড ব্যবহার করতে পারবে।")
            return
        if not context.args:
            await update.message.reply_text("ব্যবহারবিধি: `/api <your_gemini_key>`")
            return
        api_key = context.args[0]
        if initialize_gemini_models(api_key):
            await update.message.reply_text("✅ Gemini API Key সফলভাবে আপডেট করা হয়েছে।")
        else:
            await update.message.reply_text("❌ API Key সেট করতে সমস্যা হয়েছে। কী-টি সঠিক কিনা দেখুন।")

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global ADMIN_USER_ID
        if ADMIN_USER_ID != 0 and ADMIN_USER_ID != 7835226724: # Default ID check
            await update.message.reply_text(f"অ্যাডমিন আগে থেকেই সেট করা আছে: {ADMIN_USER_ID}")
        else:
            ADMIN_USER_ID = update.effective_user.id
            await update.message.reply_text(f"👑 আপনি এখন এই বটের অ্যাডমিন! User ID: {ADMIN_USER_ID}")
    
    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID: return
        await update.message.reply_text("মডেল পরিবর্তন বর্তমানে নিষ্ক্রিয় আছে। বট স্বয়ংক্রিয়ভাবে সেরা মডেলটি ব্যবহার করে।")
    
    # --- AGENT & KNOWLEDGE BASE (Conversation Handler Logic) ---
    async def agent_actions_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action = query.data.split('_')[2]

        if action == "upload":
            await query.message.reply_text("আপনার ব্যক্তিগত জ্ঞানভান্ডারে যোগ করার জন্য একটি `.txt` ফাইল পাঠান। বাতিল করতে লিখুন /cancel।")
            return ASK_KB_FILE
        elif action == "query":
            await query.message.reply_text("আপনার জ্ঞানভান্ডারকে কী প্রশ্ন করতে চান? বাতিল করতে লিখুন /cancel।")
            return ASK_KB_QUERY
        elif action == "task":
            await query.message.reply_text("আপনি আমাকে দিয়ে কোন জটিল কাজটি করাতে চান, তা বিস্তারিতভাবে লিখুন। বাতিল করতে লিখুন /cancel।")
            return ASK_AGENT_GOAL

    async def kb_receive_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        doc = await update.message.document.get_file()
        file_content = (await doc.download_as_bytearray()).decode('utf-8')
        
        if 'knowledge_base' not in context.user_data: context.user_data['knowledge_base'] = []
        context.user_data['knowledge_base'].append(file_content)
        await update.message.reply_text("✅ ফাইলটি আপনার ব্যক্তিগত জ্ঞানভান্ডারে সফলভাবে যোগ করা হয়েছে।")
        return ConversationHandler.END

    async def kb_receive_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        question = update.message.text
        if not context.user_data.get('knowledge_base'):
            await update.message.reply_text("⚠️ আপনার জ্ঞানভান্ডার খালি।")
            return ConversationHandler.END
            
        await update.message.reply_text("🧠 আপনার আপলোড করা ডকুমেন্ট থেকে উত্তর খোঁজা হচ্ছে...")
        kb_content = "\n\n---\n\n".join(context.user_data['knowledge_base'])
        prompt = f"Answer the user's question based *ONLY* on the provided text...\n\nKNOWLEDGE BASE TEXT:\n---\n{kb_content}\n---\n\nUSER'S QUESTION: {question}"
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text)
        return ConversationHandler.END
        
    async def agent_receive_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        goal = update.message.text
        await update.message.reply_text("🤖 আপনার কাজটি পেয়েছি। এটি সমাধান করার জন্য একটি পরিকল্পনা তৈরি করছি...")
        prompt = f"""You are an autonomous agent. Your goal is: "{goal}".
        You have tools: Analyze Image, Analyze Audio, Analyze Video, Convert Code.
        Create a step-by-step plan to achieve this goal. Then, execute the plan and provide the final, comprehensive answer."""
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text)
        return ConversationHandler.END

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("কার্যক্রমটি বাতিল করা হয়েছে।")
        return ConversationHandler.END

    # --- MAIN MESSAGE HANDLER (Handles Replies and General Chat) ---
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.reply_to_message:
            await self.general_chat_handler(update, context)
            return

        replied_msg = update.message.reply_to_message
        media = replied_msg.photo[-1] if replied_msg.photo else \
                replied_msg.audio or replied_msg.voice if replied_msg.audio or replied_msg.voice else \
                replied_msg.video if replied_msg.video else None
        
        if media: await self.handle_media_analysis_reply(update, context, media)
        elif replied_msg.text: await self.handle_code_conversion_reply(update, context)

    async def handle_media_analysis_reply(self, update, context, media):
        if media.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f"⚠️ ফাইলটি 너무 বড় ({media.file_size / 1024 / 1024:.2f}MB).")
            return
        await update.message.reply_text(f"🔄 ফাইলটি প্রসেস করা হচ্ছে...")
        media_file = await media.get_file()
        media_bytes = await media_file.download_as_bytearray()
        prompt_parts = [update.message.text, {'mime_type': media.mime_type, 'data': media_bytes}]
        response = await pro_model.generate_content_async(prompt_parts)
        await update.message.reply_text(response.text)

    async def handle_code_conversion_reply(self, update, context):
        target_language, original_code = update.message.text, update.message.reply_to_message.text
        await update.message.reply_text(f"🔄 কোডটি {target_language}-এ রূপান্তর করা হচ্ছে...")
        prompt = f"Convert the following code to {target_language}. Provide only the converted code.\n\nCode:\n```\n{original_code}\n```"
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text, parse_mode='Markdown')
        
    async def general_chat_handler(self, update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # CLEANED AND SIMPLIFIED SYSTEM PROMPT
        system_prompt = """
        You are I Master Tools, a friendly, helpful, and human-like AI companion.
        Your main goal is to assist users directly and accurately.
        - Respond in clear, natural Bengali (Bangla).
        - Be direct and get to the point in a friendly manner.
        - For coding questions, provide accurate code with simple explanations.
        - Adapt your tone to be helpful and engaging.
        - Do not start responses with the user's name or fillers like "ওহো" or "হায়".
        """

        if 'history' not in context.user_data:
            # Initialize history with the system prompt
            context.user_data['history'] = [{'role': 'user', 'parts': [system_prompt]}, {'role': 'model', 'parts': ["OK, I am I Master Tools. How can I help?"]}]
        
        context.user_data['history'].append({'role': 'user', 'parts': [update.message.text]})
        if len(context.user_data['history']) > 12:
            context.user_data['history'] = context.user_data['history'][:1] + context.user_data['history'][-11:]
        
        try:
            chat = flash_model.start_chat(history=context.user_data['history'])
            response = await chat.send_message_async(update.message.text)
            context.user_data['history'].append({'role': 'model', 'parts': [response.text]})
            await update.message.reply_text(response.text)
        except Exception as e:
            logger.error(f"Error during general chat: {e}")
            await update.message.reply_text("দুঃখিত, একটি সমস্যা হয়েছে। আবার চেষ্টা করুন।")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling an update: {context.error}")

    def run(self):
        self.application.post_init = self.post_init
        logger.info("Starting bot with FINAL unified menu system...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    if not TELEGRAM_BOT_TOKEN: logger.error("FATAL: TELEGRAM_BOT_TOKEN is not set!")
    elif not GEMINI_API_KEY: logger.warning("Warning: GEMINI_API_KEY is not set.")
    else:
        bot = TelegramGeminiBot()
        bot.run()

if __name__ == '__main__':
    main()