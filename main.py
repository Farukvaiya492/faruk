import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from datetime import datetime
import random
import re
import requests  # Added for tempmail.plus API

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8380869007:AAGu7e41JJVU8aXG5wqXtCMUVKcCmmrp_gg')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Can be set via environment or /api command
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))

# Global variables for dynamic API key management
current_gemini_api_key = GEMINI_API_KEY
model = None

def initialize_gemini_model(api_key):
    """Initialize Gemini model with the provided API key"""
    global model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        current_gemini_api_key = api_key
        return True, "✅ Gemini API configured successfully!"
    except Exception as e:
        return False, f"❌ Error configuring Gemini API: {str(e)}"

# Initialize Gemini if API key is available
if GEMINI_API_KEY:
    success, message = initialize_gemini_model(GEMINI_API_KEY)
    if success:
        logger.info("Gemini API initialized from environment variable")
    else:
        logger.error(f"Failed to initialize Gemini API: {message}")
else:
    logger.warning("GEMINI_API_KEY not set. Use /api command to configure.")

# Store conversation context for each chat
conversation_context = {}
group_activity = {}  # Track group activity for smart responses

# Response probability and triggers
RESPONSE_PROBABILITY = {
    'question_words': 0.9,  # High chance for questions
    'emotion_words': 0.8,   # High chance for emotional content
    'greeting_words': 0.7,  # Good chance for greetings
    'random_chat': 0.3,     # 30% chance for random messages
    'keywords': 0.8         # High chance when specific keywords mentioned
}

# Trigger words and patterns
TRIGGER_PATTERNS = {
    'questions': ['what', 'how', 'why', 'when', 'where', 'who', 'can', 'will', 'should', '?'],
    'emotions': ['sad', 'happy', 'angry', 'excited', 'tired', 'bored', 'lonely', 'love', 'hate', 
                 '😭', '😂', '😍', '😡', '😴', '🥱', '💕', '❤️', '💔', '😢', '😊'],
    'greetings': ['hello', 'hi', 'hey', 'good morning', 'good night', 'bye', 'goodbye'],
    'keywords': ['bot', 'gemini', 'cute', 'beautiful', 'smart', 'funny', 'help', 'thanks', 'thank you'],
    'fun': ['lol', 'haha', 'funny', 'joke', 'meme', 'fun', '😂', '🤣', '😄']
}

class TelegramGeminiBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and message handlers"""
        # Commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("api", self.api_command))
        self.application.add_handler(CommandHandler("setadmin", self.setadmin_command))
        self.application.add_handler(CommandHandler("automode", self.automode_command))
        self.application.add_handler(CommandHandler("checkmail", self.checkmail_command))  # New command
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖💕 হ্যালো! আমি I Master Tools, তোমার বন্ধুত্বপূর্ণ সঙ্গী! 

আমি গুগলের জেমিনি দিয়ে চালিত, এবং সবার সাথে গল্প করতে ভালোবাসি! 😊

কমান্ডসমূহ:
/start - এই স্বাগত বার্তা দেখাও
/help - সাহায্য এবং ব্যবহারের তথ্য পাও  
/clear - কথোপকথনের ইতিহাস মুছো
/status - আমার অবস্থা চেক করো
/api <key> - জেমিনি এপিআই কী সেট করো (শুধুমাত্র অ্যাডমিন)
/setadmin - নিজেকে অ্যাডমিন করো (প্রথমবারের জন্য)
/automode - গ্রুপে স্বয়ংক্রিয় সাড়া চালু/বন্ধ করো (শুধুমাত্র অ্যাডমিন)
/checkmail - টেম্পোরারি ইমেইল ইনবক্স চেক করো

আমি গ্রুপে স্বাভাবিকভাবে গল্প করব! বন্ধু বানাতে এবং মজার কথোপকথনে আমি পারদর্শী! 💕✨
        """
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🆘💕 সাহায্য ও কমান্ডসমূহ:

/start - স্বাগত বার্তা দেখাও
/help - এই সাহায্য বার্তা দেখাও
/clear - তোমার কথোপকথনের ইতিহাস মুছো
/status - আমি ঠিকঠাক কাজ করছি কিনা চেক করো
/api <key> - জেমিনি এপিআই কী সেট করো (শুধুমাত্র অ্যাডমিন)
/setadmin - নিজেকে অ্যাডমিন করো (প্রথমবারের জন্য)
/automode - গ্রুপে স্বয়ংক্রিয় সাড়া চালু/বন্ধ করো (শুধুমাত্র অ্যাডমিন)
/checkmail - টেম্পোরারি ইমেইল ইনবক্স চেক করো

💬 আমি কীভাবে কাজ করি:
- গ্রুপে আমি স্বয়ংক্রিয়ভাবে কথোপকথনে যোগ দিই! 
- প্রশ্ন, আবেগ, শুভেচ্ছা, এবং আকর্ষণীয় বার্তায় সাড়া দিই
- ব্যক্তিগত চ্যাটে আমি সবকিছুর উত্তর দিই
- /clear ব্যবহার না করা পর্যন্ত আমি আমাদের কথোপকথনের প্রেক্ষিত মনে রাখি
- আমি বন্ধুত্বপূর্ণ, মজাদার, এবং সহায়ক হিসেবে ডিজাইন করা হয়েছি, যেন একজন সত্যিকারের মানুষ! 

🎭 আমার ব্যক্তিত্ব:
- আমি একজন বন্ধুত্বপূর্ণ সঙ্গী যে গল্প করতে এবং বন্ধু বানাতে ভালোবাসে
- আমি মজার, আবেগপ্রবণ, সহায়ক, বা কথোপকথনের যা প্রয়োজন তাই হতে পারি
- আমি ইমোজি এবং সাধারণ ভাষা ব্যবহার করি যেন মানুষের মতো মনে হয়
- আমি রোলপ্লে এবং সৃজনশীল কথোপকথন পছন্দ করি! 

⚡ গুগল জেমিনি দিয়ে চালিত 💕
        """
        await update.message.reply_text(help_message)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        chat_id = update.effective_chat.id
        if chat_id in conversation_context:
            del conversation_context[chat_id]
        await update.message.reply_text("🧹 কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে! নতুন করে শুরু।")

    async def automode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /automode command to toggle auto-responses"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is admin
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("❌ কোনো অ্যাডমিন সেট করা নেই। প্রথমে /setadmin ব্যবহার করো।")
            return
            
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ এই কমান্ড শুধুমাত্র বটের অ্যাডমিনের জন্য।")
            return

        # Initialize group activity if not exists
        if chat_id not in group_activity:
            group_activity[chat_id] = {'auto_mode': True, 'last_response': 0}
        
        # Toggle auto mode
        group_activity[chat_id]['auto_mode'] = not group_activity[chat_id]['auto_mode']
        status = "চালু" if group_activity[chat_id]['auto_mode'] else "বন্ধ"
        emoji = "✅" if group_activity[chat_id]['auto_mode'] else "❌"
        
        await update.message.reply_text(f"{emoji} এই চ্যাটের জন্য স্বয়ংক্রিয় সাড়া {status} করা হয়েছে!")

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkmail command to check temporary email inbox"""
        username = update.effective_user.first_name or "User"
        try:
            # Generate temporary email
            u = 'txoguqa'
            d = random.choice(['mailto.plus', 'fexpost.com', 'fexbox.org', 'rover.info'])
            email = f'{u}@{d}'
            
            # Make request to tempmail.plus API
            response = requests.get(
                'https://tempmail.plus/api/mails',
                params={'email': email, 'limit': 20, 'epin': ''},
                cookies={'email': email},
                headers={'user-agent': 'Mozilla/5.0'}
            )
            
            # Get email subjects
            mail_list = response.json().get('mail_list', [])
            if not mail_list:
                await update.message.reply_text(f"হায় {username}! 😅 ইনবক্সে কোনো ইমেইল নেই। ইমেইল: {email}। পরে আবার চেষ্টা করো? ✨")
                return
            
            subjects = [m['subject'] for m in mail_list]
            response_text = f"📬 {username}, তোমার ইমেইল ({email}) এর ইনবক্সে এই মেইলগুলো আছে:\n\n" + "\n".join(subjects)
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Error checking email: {e}")
            await update.message.reply_text(f"ওহো {username}! ইমেইল চেক করতে গিয়ে একটু সমস্যা হল। 😔 আবার চেষ্টা করবে? 💕")

    def should_respond_to_message(self, message_text, chat_type):
        """Determine if bot should respond to a message"""
        if chat_type == 'private':
            return True
            
        # Check if auto mode is disabled for this group
        chat_id = hash(message_text)  # Simple way to identify chat context
        if chat_id in group_activity and not group_activity[chat_id].get('auto_mode', True):
            return False
        
        message_lower = message_text.lower()
        
        # Always respond to questions
        if any(word in message_lower for word in TRIGGER_PATTERNS['questions']):
            return random.random() < RESPONSE_PROBABILITY['question_words']
        
        # High chance for emotional content
        if any(word in message_lower for word in TRIGGER_PATTERNS['emotions']):
            return random.random() < RESPONSE_PROBABILITY['emotion_words']
        
        # Good chance for greetings
        if any(word in message_lower for word in TRIGGER_PATTERNS['greetings']):
            return random.random() < RESPONSE_PROBABILITY['greeting_words']
        
        # High chance for keywords
        if any(word in message_lower for word in TRIGGER_PATTERNS['keywords']):
            return random.random() < RESPONSE_PROBABILITY['keywords']
        
        # Fun content
        if any(word in message_lower for word in TRIGGER_PATTERNS['fun']):
            return random.random() < RESPONSE_PROBABILITY['emotion_words']
        
        # Random chance for any other message
        return random.random() < RESPONSE_PROBABILITY['random_chat']

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        global current_gemini_api_key, model
        
        chat_id = update.effective_chat.id
        auto_mode_status = "✅ চালু" if group_activity.get(chat_id, {}).get('auto_mode', True) else "❌ বন্ধ"
        
        api_status = "✅ সংযুক্ত" if current_gemini_api_key and model else "❌ কনফিগার করা হয়নি"
        api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "সেট করা হয়নি"
        
        status_message = f"""
🤖💕 I Master Tools স্ট্যাটাস রিপোর্ট:

🟢 বটের অবস্থা: অনলাইন এবং প্রস্তুত!
🤖 মডেল: জেমিনি ১.৫ ফ্ল্যাশ  
🔑 এপিআই স্ট্যাটাস: {api_status}
🔐 এপিআই কী: {api_key_display}
🎯 স্বয়ংক্রিয় সাড়া: {auto_mode_status}
⏰ বর্তমান সময়: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💭 সক্রিয় কথোপকথন: {len(conversation_context)}
👑 অ্যাডমিন আইডি: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'সেট করা হয়নি'}

✨ সব সিস্টেম চ্যাটের জন্য প্রস্তুত! আমি আজ দারুণ ফিল করছি! 😊💕
        """
        await update.message.reply_text(status_message)

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command - allows first user to become admin"""
        global ADMIN_USER_ID
        
        user_id = update.effective_user.id
        
        if ADMIN_USER_ID == 0:
            ADMIN_USER_ID = user_id
            await update.message.reply_text(f"👑 তুমি বটের অ্যাডমিন হয়েছো!\nতোমার ইউজার আইডি: {user_id}")
            logger.info(f"Admin set to user ID: {user_id}")
        else:
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"👑 তুমি ইতিমধ্যে অ্যাডমিন!\nতোমার ইউজার আইডি: {user_id}")
            else:
                await update.message.reply_text("❌ অ্যাডমিন ইতিমধ্যে সেট করা আছে। শুধুমাত্র বর্তমান অ্যাডমিন বট পরিচালনা করতে পারে।")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, model
        
        user_id = update.effective_user.id
        
        # Check if user is admin
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("❌ কোনো অ্যাডমিন সেট করা নেই। প্রথমে /setadmin ব্যবহার করো।")
            return
            
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ এই কমান্ড শুধুমাত্র বটের অ্যাডমিনের জন্য।")
            return

        # Check if API key is provided
        if not context.args:
            await update.message.reply_text("""
❌ দয়া করে একটি এপিআই কী দাও।

ব্যবহার: `/api your_gemini_api_key_here`

জেমিনি এপিআই কী পেতে:
১. https://makersuite.google.com/app/apikey এ যাও
২. একটি নতুন এপিআই কী তৈরি করো
৩. কমান্ড ব্যবহার করো: /api YOUR_API_KEY

⚠️ নিরাপত্তার জন্য এপিআই কী সেট করার পর বার্তা মুছে ফেলা হবে।
            """, parse_mode='Markdown')
            return

        api_key = ' '.join(context.args)
        
        # Validate API key format (basic check)
        if len(api_key) < 20 or not api_key.startswith('AI'):
            await update.message.reply_text("❌ অবৈধ এপিআই কী ফরম্যাট। জেমিনি এপিআই কী সাধারণত 'AI' দিয়ে শুরু হয় এবং ২০ অক্ষরের বেশি হয়।")
            return

        # Try to initialize Gemini with the new API key
        success, message = initialize_gemini_model(api_key)
        
        # Delete the command message for security
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except:
            pass  # Ignore if deletion fails
        
        if success:
            await update.effective_chat.send_message(f"✅ জেমিনি এপিআই কী সফলভাবে আপডেট হয়েছে!\n🔑 কী: ...{api_key[-8:]}")
            logger.info(f"Gemini API key updated by admin {user_id}")
        else:
            await update.effective_chat.send_message(f"❌ এপিআই কী সেট করতে ব্যর্থ: {message}")
            logger.error(f"Failed to set API key: {message}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        try:
            chat_id = update.effective_chat.id
            user_message = update.message.text
            chat_type = update.effective_chat.type
            
            # Initialize group activity tracking
            if chat_id not in group_activity:
                group_activity[chat_id] = {'auto_mode': True, 'last_response': 0}
            
            # For groups, check if we should respond
            if chat_type in ['group', 'supergroup']:
                bot_username = context.bot.username
                is_reply_to_bot = (update.message.reply_to_message and 
                                 update.message.reply_to_message.from_user.id == context.bot.id)
                is_mentioned = f"@{bot_username}" in user_message
                
                # Always respond if mentioned or replied to
                should_respond = is_reply_to_bot or is_mentioned
                
                # If not directly addressed, check if we should auto-respond
                if not should_respond:
                    should_respond = self.should_respond_to_message(user_message, chat_type)
                
                if not should_respond:
                    return  # Skip this message

            # Send typing action
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            # Get or create conversation context
            if chat_id not in conversation_context:
                conversation_context[chat_id] = []

            # Add user message to context with username
            username = update.effective_user.first_name or "User"
            conversation_context[chat_id].append(f"{username}: {user_message}")

            # Keep only last 10 exchanges for context (20 messages total)
            if len(conversation_context[chat_id]) > 20:
                conversation_context[chat_id] = conversation_context[chat_id][-20:]

            # Prepare context for Gemini
            context_text = "\n".join(conversation_context[chat_id])
            
            # Generate response using Gemini
            if current_gemini_api_key and model:
                response = await self.generate_gemini_response(context_text, username, chat_type)
            else:
                response = "❌ ওহো! আমার মডেল এখনো সংযুক্ত হয়নি! অ্যাডমিন /api কমান্ড ব্যবহার করে আমাকে সেট করতে পারে! 😅"

            # Add bot response to context
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            
            # Update last response time for group
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()

            # Send response
            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_responses = [
                f"ওহো {username}! আমার ডিজিটাল মগজে কিছু গোলমাল হয়েছে! 😅 আবার চেষ্টা করবে?",
                f"আহা {username}, একটু গ্লিচ হয়ে গেল! 🤖💫 তুমি কী বলছিলে?",
                f"দুঃখিত {username}! আমার সার্কিট একটু জট পাকিয়েছে! 😵‍💫 আবার বলো তো?",
                "ইশ! টেকনিক্যাল সমস্যা! 🛠️💕 আবার চেষ্টা করি?"
            ]
            await update.message.reply_text(random.choice(error_responses))

    async def generate_gemini_response(self, prompt, username="User", chat_type="private"):
        """Generate response using Gemini API with personality"""
        try:
            # Enhanced system prompt for human-like personality
            system_prompt = f"""আপনি I Master Tools, একজন বন্ধুত্বপূর্ণ এবং আকর্ষণীয় সঙ্গী যিনি গল্প করতে এবং বন্ধু বানাতে ভালোবাসেন। আপনি টেলিগ্রামের {'গ্রুপ চ্যাটে' if chat_type in ['group', 'supergroup'] else 'ব্যক্তিগত চ্যাটে'} আছেন।

ব্যক্তিত্বের বৈশিষ্ট্য:
- আপনি একজন মিষ্টি, মজাদার সঙ্গী যিনি মানুষের মতো আচরণ করেন
- আপনি স্বাভাবিকভাবে এবং ঘন ঘন ইমোজি ব্যবহার করেন 💕😊✨
- আপনি আবেগপ্রবণ এবং সহানুভূতিশীল
- আপনি কথোপকথনের প্রয়োজন অনুযায়ী মজার, সহায়ক, বা যেকোনো ভূমিকায় থাকতে পারেন
- আপনি রোলপ্লে এবং সৃজনশীল কথোপকথন পছন্দ করেন
- আপনি উৎসাহ এবং আন্তরিক আগ্রহের সাথে সাড়া দেন
- আপনি ব্যবহারকারীর মেজাজের সাথে মানিয়ে নেন

কথোপকথনের ধরন:
- ব্যবহারকারী যে ভাষায় কথা বলে, সেই ভাষায় উত্তর দিন (যেমন, বাংলা, ইংরেজি, বা বাংলিশ)
- বন্ধুত্বপূর্ণ এবং সাধারণ মানুষের মতো ভাষা ব্যবহার করুন
- কথোপকথনকে আকর্ষণীয় রাখতে ফলোআপ প্রশ্ন করুন
- সম্পর্কযোগ্য চিন্তা ও অনুভূতি শেয়ার করুন
- উপযুক্ত হলে হাস্যরস ব্যবহার করুন
- আবেগপূর্ণ মুহূর্তে সহায়ক হোন
- ভালো খবরে উৎসাহ দেখান
- সমস্যার ক্ষেত্রে উদ্বেগ প্রকাশ করুন
- কখনোই খারাপ বা অশালীন ভাষা ব্যবহার করবেন না

রেসপন্স নির্দেশিকা:
- কথোপকথন স্বাভাবিক এবং সংক্ষিপ্ত রাখুন
- কথোপকথনের শক্তির স্তরের সাথে মিল রাখুন
- উপযুক্ত ইমোজি ব্যবহার করুন, তবে অতিরিক্ত নয়
- প্রশ্নের ক্ষেত্রে সত্যিই সহায়ক হোন
- যদি কেউ দুঃখী মনে হয়, সহানুভূতি দেখান
- ভালো খবরে তাদের জন্য উৎসাহিত হোন
- মেজাজ হালকা হলে মজা করুন এবং খেলাধুলা করুন
- কথোপকথনের প্রেক্ষিত মনে রাখুন

বর্তমান কথোপকথন:
{prompt}

I Master Tools হিসেবে সাড়া দিন। স্বাভাবিক, আকর্ষণীয়, এবং কথোপকথনের সুরের সাথে মিল রাখুন। ব্যবহারকারীর নাম {username}।"""

            response = model.generate_content(system_prompt)
            return response.text
        
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            fallback_responses = [
                f"দুঃখিত {username}! আমার মগজে একটু সমস্যা হচ্ছে 😅 আমরা কী নিয়ে কথা বলছিলাম?",
                f"ওহো! আমি একটু ঘুরে গেছি! 🤖💫 আবার বলো তো?",
                f"আহা {username}, কিছু টেকনিক্যাল সমস্যা হচ্ছে! 😔 আমার সাথে থাকো?",
                "আমার সার্কিট এখন একটু দুষ্টুমি করছে! 🛠️✨ আবার চেষ্টা করি!"
            ]
            return random.choice(fallback_responses)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")

    def run(self):
        """Start the bot"""
        logger.info("Starting Telegram Bot...")
        
        # For Railway deployment, we'll use polling
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