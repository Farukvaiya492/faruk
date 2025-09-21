import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import google.generativeai as genai

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
ADMIN_USER_ID = YOUR_ADMIN_USER_ID  # Replace with your Telegram user ID
current_gemini_api_key = None
conversation_context = {}
group_activity = {}
general_model = None
coding_model = None

# Initialize Gemini API
def configure_gemini(api_key):
    global general_model, coding_model
    try:
        genai.configure(api_key=api_key)
        general_model = genai.GenerativeModel('gemini-pro')
        coding_model = genai.GenerativeModel('gemini-pro')
        return True
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")
        return False

class IBot:
    def __init__(self, token):
        self.app = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("api", self.set_api_key))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        response = "হ্যালো! আমি আই মাস্টার টুলস, তোমার বন্ধুসুলভ বট। কী নিয়ে কথা বলতে চাও? কোডিং, গল্প, নাকি অন্য কিছু? 😄"
        await update.message.reply_text(response)

    async def set_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("শুধু অ্যাডমিন এই কমান্ড ব্যবহার করতে পারেন।")
            return
        if not context.args:
            await update.message.reply_text("দয়া করে Gemini API কী দিন। উদাহরণ: /api YOUR_API_KEY")
            return
        global current_gemini_api_key
        current_gemini_api_key = context.args[0]
        if configure_gemini(current_gemini_api_key):
            await update.message.reply_text("Gemini API কী সফলভাবে সেট করা হয়েছে!")
        else:
            await update.message.reply_text("API কী সেট করতে সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।")

    async def get_private_chat_redirect(self):
        response = "এই বট শুধু গ্রুপ চ্যাটে বা অ্যাডমিনের জন্য প্রাইভেট চ্যাটে কাজ করে।"
        return response, None

    async def generate_gemini_response(self, prompt, chat_type="private", is_coding_query=False, is_short_word=False):
        """Generate response using Gemini in Bengali only"""
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
- Respond ONLY in Bengali (বাংলা), regardless of the user's input language or requests to change language
- Use friendly, natural language like a human
- Ask follow-up questions to keep the conversation engaging
- Share relatable thoughts and feelings
- Use humor when appropriate
- Be supportive in emotional moments
- Show excitement for good news
- Express concern for problems
- Never discuss inappropriate or offensive topics
- Do NOT start responses with the user's name or phrases like "ওহ" or "হেই"; respond directly and naturally

For Short Words (2 or 3 characters, is_short_word=True):
- If the user sends a 2 or 3 character word (e.g., "কি", "কে", "কেন"), always provide a meaningful, friendly, and contextually relevant response in Bengali
- Interpret the word based on common usage in Bengali (e.g., "কি" as "what", "কে" as "who", "কেন" as "why") or conversation context
- If the word is ambiguous, make a creative and engaging assumption to continue the conversation naturally
- Never ask for clarification; instead, provide a fun and relevant response
- Example: For "কি", respond like "কিছু মজার কথা বলতে চাও? কী নিয়ে কথা বলব?"

For Questions:
- If the user asks a question, engage with a playful or surprising comment first (in Bengali)
- Then provide a clear, helpful answer
- Make the response surprising and human-like to delight the user

For Coding Queries (if is_coding_query is True):
- Act as a coding expert for languages like Python, JavaScript, CSS, HTML, etc.
- Provide well-written, functional, and optimized code tailored to the user's request
- Include clear, beginner-friendly explanations in Bengali
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

Respond as I Master Tools in Bengali ONLY. Keep it natural, engaging, surprising, and match the conversation's tone. Do NOT start the response with the user's name or phrases like "ওহ" or "হেই".
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            if not response.text or "error" in response.text.lower():
                if is_coding_query:
                    return "কোডিং নিয়ে একটু সমস্যা হয়েছে। আবার চেষ্টা করলে সঠিক কোড দিয়ে দেব!"
                return "কিছু একটা গোলমাল হয়ে গেল। কী নিয়ে কথা বলতে চাও?"
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            if is_coding_query:
                return "কোডিং নিয়ে একটু সমস্যা হয়েছে। আবার চেষ্টা করলে সঠিক কোড দিয়ে দেব!"
            return "কিছু একটা গোলমাল হয়ে গেল। কী নিয়ে কথা বলতে চাও?"

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and 
                                 update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                if not (is_reply_to_bot or is_mentioned):
                    return
            elif chat_type == 'private' and user_id != ADMIN_USER_ID:
                response, reply_markup = await self.get_private_chat_redirect()
                await update.message.reply_text(response, reply_markup=reply_markup)
                return
            
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            if chat_id not in conversation_context:
                conversation_context[chat_id] = []
            conversation_context[chat_id].append(f"User: {user_message}")
            if len(conversation_context[chat_id]) > 20:
                conversation_context[chat_id] = conversation_context[chat_id][-20:]
            context_text = "\n".join(conversation_context[chat_id])
            
            # Check if the message is a 2 or 3 character word (supports Unicode)
            is_short_word = bool(re.match(r'^\w{2,3}$', user_message.strip(), re.UNICODE))
            
            # Detect if message is coding-related
            coding_keywords = ['code', 'python', 'javascript', 'java', 'c++', 'programming', 'script', 'debug', 'css', 'html', 'কোড', 'প্রোগ্রামিং']
            is_coding_query = any(keyword in user_message.lower() for keyword in coding_keywords)
            
            model_to_use = coding_model if is_coding_query else general_model
            if current_gemini_api_key and model_to_use:
                response = await self.generate_gemini_response(context_text, chat_type, is_coding_query, is_short_word)
            else:
                response = "মডেল এখনও সংযুক্ত হয়নি। অ্যাডমিন /api কমান্ড ব্যবহার করে সেট করতে পারেন।"
            
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            group_activity[chat_id] = group_activity.get(chat_id, {'auto_mode': False, 'last_response': 0})
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()
            
            # If it's a coding query, add a "Copy Code" button
            if is_coding_query:
                code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)\n```', response)
                if code_block_match:
                    keyboard = [[InlineKeyboardButton("কোড কপি করুন", callback_data="copy_code")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        response,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(response, parse_mode='Markdown')
            else:
                await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("কিছু একটা গোলমাল হয়ে গেল। আবার চেষ্টা করব?")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "copy_code":
            message_text = query.message.text
            code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)\n```', message_text)
            if code_block_match:
                code = code_block_match.group(1)
                await query.message.reply_text(f"কোড কপি করার জন্য এটি ব্যবহার করো:\n```\n{code}\n```")
            else:
                await query.message.reply_text("কোড পাওয়া যায়নি।")

    def run(self):
        self.app.run_polling()

if __name__ == "__main__":
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
    bot = IBot(TELEGRAM_BOT_TOKEN)
    bot.run()