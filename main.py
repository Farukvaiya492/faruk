import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
import io

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8380869007:AAGu7e41JJVU8aXG5wqXtCMUVKcCmmrp_gg')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# --- GEMINI MODELS ---
pro_model = None
flash_model = None

def initialize_gemini_models(api_key):
    global pro_model, flash_model
    try:
        genai.configure(api_key=api_key)
        pro_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        flash_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        logger.info("Gemini Pro and Flash models configured successfully!")
        return True
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")
        return False

if GEMINI_API_KEY:
    initialize_gemini_models(GEMINI_API_KEY)

# --- NEW CONVERSATION HANDLER STATES ---
ASK_KB_FILE, ASK_KB_QUERY, ASK_AGENT_GOAL = range(3)

class TelegramGeminiBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    # --- MENU BUILDERS ---
    def build_main_menu(self):
        buttons = [
            [InlineKeyboardButton("✨ AI টুলস", callback_data="menu_ai_tools")],
            [InlineKeyboardButton("👤 পার্সোনাল এজেন্ট", callback_data="menu_agent")],
            [InlineKeyboardButton("📝 সাধারণ চ্যাট", callback_data="menu_general")],
            [InlineKeyboardButton("⚙️ সেটিংস ও সাহায্য", callback_data="menu_settings")],
        ]
        return InlineKeyboardMarkup(buttons)

    def build_ai_tools_menu(self):
        buttons = [
            [InlineKeyboardButton("🖼️ ছবি বিশ্লেষণ", callback_data="tool_image")],
            [InlineKeyboardButton("🎤 অডিও প্রসেস", callback_data="tool_audio")],
            [InlineKeyboardButton("🎥 ভিডিও বিশ্লেষণ", callback_data="tool_video")],
            [InlineKeyboardButton("💻 কোড রূপান্তর", callback_data="tool_code")],
            [InlineKeyboardButton("⬅️ পেছনে যান", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)
        
    def build_agent_menu(self):
        buttons = [
            [InlineKeyboardButton("🧠 নলেজবেস-এ আপলোড", callback_data="agent_kb_upload")],
            [InlineKeyboardButton("❓ নলেজবেস-কে প্রশ্ন", callback_data="agent_kb_query")],
            [InlineKeyboardButton("🤖 জটিল কাজ দিন", callback_data="agent_task")],
            [InlineKeyboardButton("⬅️ পেছনে যান", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)

    def build_general_menu(self):
        buttons = [
            [InlineKeyboardButton("💬 নতুন করে শুরু (হিস্ট্রি মুছুন)", callback_data="general_clear")],
            [InlineKeyboardButton("⬅️ পেছনে যান", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)
        
    def build_settings_menu(self):
        buttons = [
            [InlineKeyboardButton("📊 স্ট্যাটাস দেখুন", callback_data="settings_status")],
            [InlineKeyboardButton("❓ কীভাবে ব্যবহার করবেন", callback_data="settings_help")],
            [InlineKeyboardButton("⬅️ পেছনে যান", callback_data="nav_main_menu")],
        ]
        return InlineKeyboardMarkup(buttons)

    def setup_handlers(self):
        # --- NEW CONVERSATION HANDLER FOR AGENT FEATURES ---
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.agent_actions_handler, pattern='^agent_')],
            states={
                ASK_KB_FILE: [MessageHandler(filters.Document.TEXT, self.kb_receive_file)],
                ASK_KB_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.kb_receive_query)],
                ASK_AGENT_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.agent_receive_goal)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_conversation)],
            conversation_timeout=300
        )

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CallbackQueryHandler(self.menu_navigation_handler, pattern='^menu_'))
        self.application.add_handler(CallbackQueryHandler(self.tool_selection_handler, pattern='^tool_'))
        self.application.add_handler(CallbackQueryHandler(self.general_actions_handler, pattern='^general_'))
        self.application.add_handler(CallbackQueryHandler(self.settings_actions_handler, pattern='^settings_'))
        self.application.add_handler(CallbackQueryHandler(self.navigation_handler, pattern='^nav_'))
        self.application.add_handler(conv_handler)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_error_handler(self.error_handler)

    async def post_init(self, application: Application):
        await application.bot.set_my_commands([BotCommand("menu", "Show the main menu")])

    # --- COMMAND HANDLERS ---
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "স্বাগতম! আমি আপনার উন্নত AI অ্যাসিস্ট্যান্ট।\n"
            "শুরু করতে /menu কমান্ড দিন এবং বাটন ব্যবহার করে আমার সব ফিচার দেখুন।",
            reply_markup=self.build_main_menu()
        )

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("MAIN MENU", reply_markup=self.build_main_menu())

    # --- MENU NAVIGATION & ACTIONS ---
    async def menu_navigation_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        menu_type = query.data.split('_')[1]

        menus = {
            'ai_tools': ("✨ AI Tools", self.build_ai_tools_menu()),
            'agent': ("👤 Personal Agent", self.build_agent_menu()),
            'general': ("📝 General Chat", self.build_general_menu()),
            'settings': ("⚙️ Settings & Help", self.build_settings_menu()),
        }
        
        if menu_type in menus:
            text, markup = menus[menu_type]
            await query.edit_message_text(text=text, reply_markup=markup)

    async def navigation_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "nav_main_menu":
            await query.edit_message_text(text="MAIN MENU", reply_markup=self.build_main_menu())

    async def tool_selection_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        tool = query.data.split('_')[1]
        instructions = {
            'image': "🖼️ একটি ছবির রিপ্লাই দিয়ে বর্ণনা লিখুন, কী বিশ্লেষণ করতে হবে। যেমন: `এই UI এর ফিডব্যাক দাও`",
            'audio': "🎤 একটি অডিও ফাইলের রিপ্লাই দিয়ে বর্ণনা লিখুন। যেমন: `এই মিটিংটি সংক্ষেপে বলো`",
            'video': "🎥 একটি ভিডিওর রিপ্লাই দিয়ে বর্ণনা লিখুন। যেমন: `ভিডিওটির মূল বিষয় কী?`",
            'code': "💻 একটি কোড ব্লকের রিপ্লাই দিয়ে লিখুন কোন ভাষায় রূপান্তর করতে হবে। যেমন: `javascript`",
        }
        await query.message.reply_text(f"**নির্দেশনা:**\n{instructions.get(tool, 'Invalid tool selected.')}", parse_mode='Markdown')
        # We now expect the user to reply to a message and write a text command
        # This will be handled by the main handle_message function
    
    async def general_actions_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "general_clear":
            context.user_data.clear() # Clears everything for the user, including KB
            await query.edit_message_text("✅ আপনার সমস্ত ডেটা এবং কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে।")

    async def settings_actions_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "settings_status":
            status = "Connected" if pro_model else "Disconnected"
            await query.message.reply_text(f"**Bot Status:** Online\n**Gemini API:** {status}")
        elif query.data == "settings_help":
             await query.message.reply_text("To use any AI Tool, reply to the relevant file/text with your instructions.")

    # --- AGENT & KNOWLEDGE BASE ---
    async def agent_actions_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action = query.data.split('_')[2]

        if action == "upload":
            await query.message.reply_text("Please send a `.txt` file to add to your knowledge base. Send /cancel to stop.")
            return ASK_KB_FILE
        elif action == "query":
            await query.message.reply_text("What would you like to ask your knowledge base? Send /cancel to stop.")
            return ASK_KB_QUERY
        elif action == "task":
            await query.message.reply_text("Please describe the complex goal you want me to achieve. Send /cancel to stop.")
            return ASK_AGENT_GOAL

    async def kb_receive_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        doc = await update.message.document.get_file()
        file_content = (await doc.download_as_bytearray()).decode('utf-8')
        
        if 'knowledge_base' not in context.user_data:
            context.user_data['knowledge_base'] = []
        
        context.user_data['knowledge_base'].append(file_content)
        await update.message.reply_text("✅ File added to your knowledge base successfully!")
        return ConversationHandler.END

    async def kb_receive_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        question = update.message.text
        if 'knowledge_base' not in context.user_data or not context.user_data['knowledge_base']:
            await update.message.reply_text("Your knowledge base is empty. Please upload a file first.")
            return ConversationHandler.END
            
        await update.message.reply_text("🧠 Thinking based on your documents...")
        kb_content = "\n\n---\n\n".join(context.user_data['knowledge_base'])
        prompt = f"""
        You are a helpful assistant. Answer the user's question based *ONLY* on the provided text from their knowledge base.
        If the answer is not in the text, say "I don't have information about that in your knowledge base."

        KNOWLEDGE BASE TEXT:
        ---
        {kb_content}
        ---

        USER'S QUESTION:
        {question}
        """
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text)
        return ConversationHandler.END
        
    async def agent_receive_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        goal = update.message.text
        await update.message.reply_text("🤖 Processing your complex goal... I will think step-by-step.")
        
        prompt = f"""
        You are an autonomous agent. Your goal is: "{goal}".
        You have the following tools available: Analyze Image, Analyze Audio, Analyze Video, Convert Code.
        
        Think step-by-step to create a plan to achieve this goal. If the goal requires information from a previous message (like an image or code), assume you have access to it.
        
        1. **Create the plan.**
        2. **Execute the plan.**
        3. **Provide the final, complete answer.**
        """
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text)
        return ConversationHandler.END

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

    # --- MAIN MESSAGE HANDLER for REPLIES ---
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.reply_to_message:
            # This is a general chat message, handle it conversationally
            await self.general_chat_handler(update, context)
            return

        # This is a reply, so it might be an instruction for a tool
        replied_msg = update.message.reply_to_message
        user_instruction = update.message.text
        
        media = None
        media_type = None
        
        # Determine media type from replied message
        if replied_msg.photo:
            media, media_type = replied_msg.photo[-1], "image"
        elif replied_msg.audio or replied_msg.voice:
            media, media_type = replied_msg.audio or replied_msg.voice, "audio"
        elif replied_msg.video:
            media, media_type = replied_msg.video, "video"
        elif replied_msg.text:
            # Could be a code conversion request
            await self.handle_code_conversion_reply(update, context)
            return
        
        if media:
            await self.handle_media_analysis_reply(update, context, media, media_type)

    async def handle_media_analysis_reply(self, update, context, media, media_type):
        if media.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f"File is too large ({media.file_size / 1024 / 1024:.2f}MB). Max 20MB.")
            return

        await update.message.reply_text(f"🔄 Processing your instruction for the {media_type}...")
        media_file = await media.get_file()
        media_bytes = await media_file.download_as_bytearray()
        
        prompt_parts = [update.message.text, {'mime_type': media.mime_type, 'data': media_bytes}]
        response = await pro_model.generate_content_async(prompt_parts)
        await update.message.reply_text(response.text)

    async def handle_code_conversion_reply(self, update, context):
        target_language = update.message.text
        original_code = update.message.reply_to_message.text
        await update.message.reply_text(f"🔄 Converting code to {target_language}...")
        
        prompt = f"Convert the following code to {target_language}. Provide only the converted code in a formatted block.\n\nCode:\n```\n{original_code}\n```"
        response = await pro_model.generate_content_async(prompt)
        await update.message.reply_text(response.text, parse_mode='Markdown')
        
    async def general_chat_handler(self, update, context):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        if 'history' not in context.user_data:
            context.user_data['history'] = []
            
        context.user_data['history'].append({'role': 'user', 'parts': [update.message.text]})
        if len(context.user_data['history']) > 10:
            context.user_data['history'] = context.user_data['history'][-10:]
            
        chat = flash_model.start_chat(history=context.user_data['history'])
        response = await chat.send_message_async(update.message.text)
        context.user_data['history'].append({'role': 'model', 'parts': [response.text]})
        
        await update.message.reply_text(response.text)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling an update: {context.error}")

    def run(self):
        self.application.post_init = self.post_init
        logger.info("Starting bot with unified menu system...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN not provided!")
        return
    if not GEMINI_API_KEY:
        logger.warning("Warning: GEMINI_API_KEY not set.")
    
    bot = TelegramGeminiBot()
    bot.run()

if __name__ == '__main__':
    main()