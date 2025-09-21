import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import random
import requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8380869007:AAGu7e41JJVU8aXG5wqXtCMUVKcCmmrp_gg')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))

# Store conversation context
conversation_context = {}

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and callback handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("checkmail", self.checkmail_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("api", self.api_command))
        self.application.add_handler(CommandHandler("setadmin", self.setadmin_command))
        self.application.add_handler(CommandHandler("setmodel", self.setmodel_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_error_handler(self.error_handler)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        if not query or not query.data or not query.message:
            logger.error(f"Invalid callback query: query={query}, data={getattr(query, 'data', None)}, message={getattr(query, 'message', None)}")
            return
        callback_data = query.data
        try:
            await query.answer()
        except Exception as e:
            logger.error(f"Error answering callback query: {str(e)}")

        user_id = query.from_user.id
        chat_id = query.message.chat.id
        chat_type = query.message.chat.type
        logger.info(f"Button callback: data={callback_data}, user_id={user_id}, chat_type={chat_type}")

        # Handle non-admin private chat redirect
        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await query.message.reply_text(response, reply_markup=reply_markup)
            return

        # Command mapping
        command_mapping = {
            "start": self.start_command,
            "help": self.help_command,
            "clear": self.clear_command,
            "status": self.status_command,
            "checkmail": self.checkmail_command,
            "info": self.info_command,
            "api": self.api_command,
            "setmodel": self.setmodel_command,
            "setadmin": self.setadmin_command
        }

        try:
            if callback_data in command_mapping:
                mock_update = Update(
                    update_id=update.update_id,
                    callback_query=query,
                    message=query.message
                )
                mock_update.effective_user = query.from_user
                mock_update.effective_chat = query.message.chat
                context.args = []  # Reset args for button-triggered commands
                await command_mapping[callback_data](mock_update, context)
            else:
                logger.warning(f"Unknown callback data: {callback_data}")
                await query.message.reply_text(
                    "Oops! This button is lost in space. 🚀 Try another one!",
                    reply_markup=await self.get_menu_keyboard(user_id)
                )
        except Exception as e:
            logger.error(f"Error in button callback for {callback_data}: {str(e)}", exc_info=True)
            await query.message.reply_text(
                f"Something went wrong with that action. 😔 Try again or use /menu!",
                reply_markup=await self.get_menu_keyboard(user_id)
            )

    async def get_menu_keyboard(self, user_id):
        """Generate the menu keyboard dynamically"""
        keyboard = [
            [
                InlineKeyboardButton("🚀 Start", callback_data="start"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("📧 Check Email", callback_data="checkmail"),
                InlineKeyboardButton("📊 Status", callback_data="status")
            ],
            [
                InlineKeyboardButton("🗑️ Clear History", callback_data="clear"),
                InlineKeyboardButton("👤 User Info", callback_data="info")
            ],
            [
                InlineKeyboardButton("🔗 Join Group", url="https://t.me/VPSHUB_BD_CHAT")
            ]
        ]
        if user_id == ADMIN_USER_ID:
            keyboard.append([
                InlineKeyboardButton("🔑 Set API", callback_data="api"),
                InlineKeyboardButton("⚙️ Set Model", callback_data="setmodel")
            ])
            keyboard.append([
                InlineKeyboardButton("👑 Set Admin", callback_data="setadmin")
            ])
        return InlineKeyboardMarkup(keyboard)

    async def get_private_chat_redirect(self):
        """Return redirect message for non-admin private chats"""
        keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return """
Hello, thanks for reaching out! I'm I Master Tools, your friendly companion. To chat with me, join our official group by clicking below and mention @IMasterTools. I'm waiting for you there!
        """, reply_markup

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            reply_markup = await self.get_menu_keyboard(user_id)
            welcome_message = f"""
Hello {username}, welcome to I Master Tools!

Join our group or mention @IMasterTools to chat. Explore features with the buttons below!

Commands:
- /help: Get help
- /menu: Show menu
- /clear: Clear history
- /status: Check bot status
- /checkmail: Check email
- /info: User info
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set API key (admin)\n- /setadmin: Set admin\n- /setmodel: Set model (admin)'}
            """
            await self._send_response(update, welcome_message, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            reply_markup = await self.get_menu_keyboard(user_id)
            help_message = f"""
Hello {username}! I'm I Master Tools, your friendly companion.

How I work:
- In groups, mention @IMasterTools or reply to my messages
- In private chats, only admin can use all features
- I'm fun, helpful, and human-like!

Commands:
- /start: Welcome message
- /help: This message
- /menu: Feature menu
- /clear: Clear history
- /status: Bot status
- /checkmail: Check email
- /info: User info
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set API key (admin)\n- /setadmin: Set admin\n- /setmodel: Set model (admin)'}
            """
            await self._send_response(update, help_message, reply_markup=reply_markup)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            reply_markup = await self.get_menu_keyboard(user_id)
            response = f"🌟 Hello {username}, welcome to I Master Tools! 🌟\nTap a button to explore:"
            await self._send_response(update, response, reply_markup=reply_markup)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            if chat_id in conversation_context:
                del conversation_context[chat_id]
            response = "Conversation history cleared. Let's start fresh!"
            await self._send_response(update, response)

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkmail command"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
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
                response_text = f"No emails found for {email}." if not mail_list else \
                                f"Emails for {email}:\n\n" + "\n".join(m['subject'] for m in mail_list)
                await self._send_response(update, response_text)
            except Exception as e:
                logger.error(f"Error checking email: {str(e)}")
                await self._send_response(update, "Error checking email. Try again?")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            status_message = f"""
I Master Tools Status:
Bot: Online
Conversations: {len(conversation_context)}
Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Ready to assist! 🚀
            """
            await self._send_response(update, status_message)

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command"""
        global ADMIN_USER_ID
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                ADMIN_USER_ID = user_id
                response = f"Congratulations {username}, you're now the admin! ID: {user_id}"
                logger.info(f"Admin set to user ID: {user_id}")
            else:
                response = f"You're already admin! ID: {user_id}" if user_id == ADMIN_USER_ID else \
                          "Admin already set. Only the admin can manage the bot."
            await self._send_response(update, response)

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await self._send_response(update, "No admin set. Use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await self._send_response(update, "This command is for admins only.")
                return
            if not context.args:
                response = "Usage: /api <your_api_key>\nGet a key from https://makersuite.google.com/app/apikey"
                await self._send_response(update, response)
                return
            api_key = ' '.join(context.args)
            response = f"API key set: ...{api_key[-8:]}" if api_key else "Invalid API key."
            await self._send_response(update, response)

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await self._send_response(update, "No admin set. Use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await self._send_response(update, "This command is for admins only.")
                return
            if not context.args:
                response = "Usage: /setmodel <model_name>\nAvailable: gemini-1.5-flash, gemini-1.5-pro"
                await self._send_response(update, response)
                return
            model_name = context.args[0]
            response = f"Model set to {model_name}." if model_name else "Invalid model."
            await self._send_response(update, response)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        chat_type = update.effective_chat.type if update.effective_chat else 'unknown'

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await self._send_response(update, response, reply_markup=reply_markup)
            return

        target_user = update.effective_user
        full_name = target_user.first_name or "No Name"
        if target_user.last_name:
            full_name += f" {target_user.last_name}"
        username = f"@{target_user.username}" if target_user.username else "None"
        info_text = f"""
User Info:
Name: {full_name}
Username: {username}
User ID: {user_id}
Chat ID: {chat_id if chat_type != 'private' else '-'}
Role: {'Admin' if user_id == ADMIN_USER_ID else 'User'}
        """
        await self._send_response(update, info_text)

    async def _send_response(self, update: Update, text: str, parse_mode: str = None, reply_markup=None):
        """Helper method to send response"""
        try:
            if update.message:
                await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            elif update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                logger.error("No valid message or callback query to send response")
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update error: {context.error}", exc_info=True)
        if update and hasattr(update, 'effective_chat'):
            user_id = update.effective_user.id if update.effective_user else 0
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(
                    "Something went wrong. 😔 Try /menu!",
                    reply_markup=await self.get_menu_keyboard(user_id)
                )
            elif hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(
                    "Something went wrong. 😔 Try /menu!",
                    reply_markup=await self.get_menu_keyboard(user_id)
                )

    def run(self):
        """Start the bot"""
        logger.info("Starting Telegram Bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not provided!")
        return
    logger.info(f"Admin User ID: {ADMIN_USER_ID}")
    bot = TelegramBot()
    bot.run()

if __name__ == '__main__':
    main()