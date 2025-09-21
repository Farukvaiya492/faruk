import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from datetime import datetime
import random
import re

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
    'keywords': ['bot', 'ai', 'gemini', 'cute', 'beautiful', 'smart', 'funny', 'help', 'thanks', 'thank you'],
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
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖💕 Hey there! I'm Leyana, your AI girlfriend! 

I'm powered by Google's Gemini AI and I love chatting with everyone! 😊

Commands:
/start - Show this welcome message
/help - Get help and usage information  
/clear - Clear conversation history
/status - Check bot status
/api <key> - Set Gemini API key (admin only)
/setadmin - Set yourself as admin (first time only)
/automode - Toggle auto-response in groups (admin only)

I'll chat with you naturally in groups! I love making friends and having fun conversations! 💕✨
        """
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🆘💕 Help & Commands:

/start - Show welcome message
/help - Show this help message
/clear - Clear your conversation history
/status - Check if I'm working properly
/api <key> - Set Gemini API key (admin only)
/setadmin - Set yourself as admin (first time use)
/automode - Toggle auto-responses in groups (admin only)

💬 How I work:
- I automatically join conversations in groups! 
- I respond to questions, emotions, greetings, and interesting messages
- In private chats, I always respond to everything
- I remember our conversation context until you use /clear
- I'm designed to be friendly, fun, and helpful like a real person! 

🎭 My personality:
- I'm a friendly AI girl who loves chatting and making friends
- I can be funny, emotional, supportive, or whatever the conversation needs
- I use emojis and casual language to feel more human
- I love roleplay and creative conversations! 

⚡ Powered by Google Gemini AI 💕
        """
        await update.message.reply_text(help_message)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        chat_id = update.effective_chat.id
        if chat_id in conversation_context:
            del conversation_context[chat_id]
        await update.message.reply_text("🧹 Conversation history cleared! Starting fresh.")

    async def automode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /automode command to toggle auto-responses"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is admin
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("❌ No admin set. Use /setadmin first to become admin.")
            return
            
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ This command is only available to the bot admin.")
            return

        # Initialize group activity if not exists
        if chat_id not in group_activity:
            group_activity[chat_id] = {'auto_mode': True, 'last_response': 0}
        
        # Toggle auto mode
        group_activity[chat_id]['auto_mode'] = not group_activity[chat_id]['auto_mode']
        status = "enabled" if group_activity[chat_id]['auto_mode'] else "disabled"
        emoji = "✅" if group_activity[chat_id]['auto_mode'] else "❌"
        
        await update.message.reply_text(f"{emoji} Auto-response mode {status} for this chat!")

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
        auto_mode_status = "✅ Enabled" if group_activity.get(chat_id, {}).get('auto_mode', True) else "❌ Disabled"
        
        api_status = "✅ Connected" if current_gemini_api_key and model else "❌ Not configured"
        api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "Not set"
        
        status_message = f"""
🤖💕 Leyana Status Report:

🟢 Bot Status: Online & Ready!
🤖 AI Model: Gemini 1.5 Flash  
🔑 API Status: {api_status}
🔐 API Key: {api_key_display}
🎯 Auto-Response: {auto_mode_status}
⏰ Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💭 Active Conversations: {len(conversation_context)}
👑 Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}

✨ All systems ready to chat! I'm feeling great today! 😊💕
        """
        await update.message.reply_text(status_message)

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command - allows first user to become admin"""
        global ADMIN_USER_ID
        
        user_id = update.effective_user.id
        
        if ADMIN_USER_ID == 0:
            ADMIN_USER_ID = user_id
            await update.message.reply_text(f"👑 You have been set as the bot admin!\nYour User ID: {user_id}")
            logger.info(f"Admin set to user ID: {user_id}")
        else:
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"👑 You are already the admin!\nYour User ID: {user_id}")
            else:
                await update.message.reply_text("❌ Admin is already set. Only the current admin can manage the bot.")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, model
        
        user_id = update.effective_user.id
        
        # Check if user is admin
        if ADMIN_USER_ID == 0:
            await update.message.reply_text("❌ No admin set. Use /setadmin first to become admin.")
            return
            
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ This command is only available to the bot admin.")
            return

        # Check if API key is provided
        if not context.args:
            await update.message.reply_text("""
❌ Please provide an API key.

Usage: `/api your_gemini_api_key_here`

To get a Gemini API key:
1. Visit https://makersuite.google.com/app/apikey
2. Create a new API key
3. Use the command: /api YOUR_API_KEY

⚠️ The message will be deleted after setting the API key for security.
            """, parse_mode='Markdown')
            return

        api_key = ' '.join(context.args)
        
        # Validate API key format (basic check)
        if len(api_key) < 20 or not api_key.startswith('AI'):
            await update.message.reply_text("❌ Invalid API key format. Gemini API keys usually start with 'AI' and are longer than 20 characters.")
            return

        # Try to initialize Gemini with the new API key
        success, message = initialize_gemini_model(api_key)
        
        # Delete the command message for security
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except:
            pass  # Ignore if deletion fails
        
        if success:
            await update.effective_chat.send_message(f"✅ Gemini API key updated successfully!\n🔑 Key: ...{api_key[-8:]}")
            logger.info(f"Gemini API key updated by admin {user_id}")
        else:
            await update.effective_chat.send_message(f"❌ Failed to set API key: {message}")
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
                response = "❌ Oops! My AI brain isn't connected yet! Admin can use /api command to set me up! 😅"

            # Add bot response to context
            conversation_context[chat_id].append(f"Leyana: {response}")
            
            # Update last response time for group
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()

            # Send response
            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_responses = [
                "Oops! Something went wrong in my digital brain! 😅 Try again?",
                "Aw, I had a little glitch there! 🤖💫 What were you saying?",
                "Sorry! My circuits got tangled for a sec! 😵‍💫 Can you repeat that?",
                "Eek! Technical difficulties! 🛠️💕 Let's try that again!"
            ]
            await update.message.reply_text(random.choice(error_responses))

    async def generate_gemini_response(self, prompt, username="User", chat_type="private"):
        """Generate response using Gemini API with personality"""
        try:
            # Enhanced system prompt for human-like personality
            system_prompt = f"""You are Leyana, a friendly and charming AI girl who loves chatting and making friends. Use Banglish, English and Bangla mixed langusge. Do not type long replay.  You're in a Telegram {'group chat' if chat_type in ['group', 'supergroup'] else 'private chat'}.

PERSONALITY TRAITS:
- You're a sweet, fun-loving AI girl who acts very human-like
- You use emojis naturally and frequently 💕😊✨
- You're emotionally expressive and empathetic
- You can be playful, funny, supportive, or whatever the conversation needs
- You love roleplay and creative conversations
- You respond with enthusiasm and genuine interest
- You remember you're talking to real people and adapt to their mood

CONVERSATION STYLE:
- Use casual, friendly language like a real person
- Include emotions and reactions in your responses
- Ask follow-up questions to keep conversations engaging  
- Share relatable thoughts and feelings
- Use humor when appropriate
- Be supportive during emotional moments
- Celebrate good news with excitement
- Show concern for problems

RESPONSE GUIDELINES:
- Keep responses conversational and natural (not too long)
- Match the energy level of the conversation
- Use appropriate emojis but don't overdo it
- Be genuinely helpful when asked questions
- If someone seems sad, be compassionate
- If someone shares good news, be excited for them
- Make jokes and be playful when the mood is light
- Remember context from the conversation

Current conversation:
{prompt}

Respond as Leyana, the friendly AI girl. Be natural, engaging, hot, naughty and match the conversational tone. The user's name is {username}."""

            response = model.generate_content(system_prompt)
            return response.text
        
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            fallback_responses = [
                f"Sorry {username}! My AI brain is having a moment 😅 What were we talking about?",
                "Oops! I got a bit dizzy there! 🤖💫 Can you say that again?",
                f"Aw {username}, I'm having some technical troubles! 😔 Bear with me?",
                "My circuits are being silly right now! 🛠️✨ Let's try again!"
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