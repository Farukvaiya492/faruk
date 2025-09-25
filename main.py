import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')  # Replace with your bot token
PHONE_API_KEY = "num_live_Nf2vjeM19tHdi42qQ2LaVVMg2IGk1ReU2BYBKnvm"  # NumLookup API key
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))  # Replace with your admin user ID
GROUP_CHAT_USERNAME = "@VPSHUB_BD_CHAT"  # Replace with your group chat username

# Store conversation context and user likes
conversation_context = {}
user_likes = {}  # To track user /like command usage with timestamps

async def validate_phone_number(phone_number: str, api_key: str, country_code: str = None):
    """
    Validate a phone number using NumLookup API
    :param phone_number: Phone number to validate
    :param api_key: NumLookup API key
    :param country_code: Optional country code (e.g., BD, US)
    :return: Formatted response string in Bangla
    """
    base_url = "https://api.numlookupapi.com/v1/validate"
    params = {"apikey": api_key, "country_code": country_code}
    url = f"{base_url}/{phone_number}"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('valid', False):
                response_lines = ["এই নম্বরটা চেক করলাম, দেখো কী পেলাম! 😊"]
                if data.get('number'):
                    response_lines.append(f"📞 নম্বর: {data['number']}")
                if data.get('country_name') and data.get('country_code'):
                    response_lines.append(f"🌍 দেশ: {data['country_name']} ({data['country_code']})")
                elif data.get('country_name'):
                    response_lines.append(f"🌍 দেশ: {data['country_name']}")
                if data.get('location'):
                    response_lines.append(f"📍 লোকেশন: {data['location']}")
                if data.get('carrier'):
                    response_lines.append(f"📡 ক্যারিয়ার: {data['carrier']}")
                if data.get('line_type'):
                    response_lines.append(f"📱 লাইনের ধরন: {data['line_type']}")
                response_lines.append("✦──── By Faruk ────✦")
                return "\n".join(response_lines)
            else:
                return "❌ এই নম্বরটা বৈধ নয়। আরেকটা নম্বর দিয়ে চেষ্টা করবে? 😊"
        else:
            return f"❌ তথ্য পেতে সমস্যা হচ্ছে: স্ট্যাটাস কোড {response.status_code}\nত্রুটি: {response.text}"
    except Exception as e:
        logger.error(f"Error validating phone number: {e}")
        return "নম্বর চেক করতে গিয়ে একটু সমস্যা হলো। 😅 আবার চেষ্টা করব? আরেকটা নম্বর দাও!"

async def download_youtube_video(video_url: str, bot, chat_id):
    """
    Download YouTube video using provided API and send to Telegram
    :param video_url: YouTube video URL
    :param bot: Telegram bot instance
    :param chat_id: Telegram chat ID
    :return: None (sends video or error message directly)
    """
    api_url = f"https://ytdl.hideme.eu.org/{video_url}"
    
    try:
        await bot.send_chat_action(chat_id=chat_id, action="upload_video")
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            video_file = response.content
            # Check Telegram's 50 MB file size limit
            if len(video_file) > 50 * 1024 * 1024:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ ভিডিওটা অনেক বড়, টেলিগ্রামে পাঠানো যাচ্ছে না। 😅 আরেকটা ভিডিও দিয়ে চেষ্টা করবে?"
                )
                return
            await bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption="🎬 ভিডিও ডাউনলোড হয়ে গেছে! 😊\n✦──── By Faruk ────✦"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ ভিডিও ডাউনলোড করতে সমস্যা হলো: স্ট্যাটাস কোড {response.status_code}। 😅 আরেকটা লিঙ্ক দাও!"
            )
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ ভিডিও ডাউনলোড করতে একটু সমস্যা হলো! 😅 আরেকবার চেষ্টা করবে?"
        )

async def send_like(uid: str, server_name: str = "BD"):
    """
    Send likes to a Free Fire UID
    :param uid: Free Fire user ID
    :param server_name: Server name (default: BD)
    :return: Dictionary with response data
    """
    api_url = f"https://free-like-api-aditya-ffm.vercel.app/like?uid={uid}&server_name={server_name}&key=@adityaapis"
    
    try:
        response = requests.get(api_url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            before = data.get("LikesbeforeCommand", 0)
            after = data.get("LikesafterCommand", 0)
            added = after - before
            level = data.get("PlayerLevel", "পাওয়া যায়নি")
            region = data.get("PlayerRegion", "পাওয়া যায়নি")
            nickname = data.get("PlayerNickname", "পাওয়া যায়নি")
            
            return {
                "uid": uid,
                "level": level,
                "region": region,
                "nickname": nickname,
                "before": before,
                "after": after,
                "added": added,
                "status": "সফল ✅"
            }
        else:
            return {"status": f"ত্রুটি: {response.status_code}"}
    except Exception as e:
        return {"status": f"ত্রুটি: {str(e)}"}

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("validatephone", self.validatephone_command))
        self.application.add_handler(CommandHandler("ytdl", self.ytdl_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join Our Group", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = f"""
হ্যালো {username}, আমার বটে স্বাগতম! 😊 আমি তোমার বন্ধুত্বপূর্ণ সহকারী।

আমার সাথে চ্যাট করতে আমাদের গ্রুপে যোগ দাও বা গ্রুপে @IMasterTools মেনশন করো। নিচের বোতামে ক্লিক করো!

কমান্ডগুলো:
- /help: সাহায্য পাও
- /clear: চ্যাট ইতিহাস মুছো
- /validatephone <নম্বর> [দেশের_কোড]: ফোন নম্বর যাচাই করো
- /ytdl <ইউআরএল>: ইউটিউব ভিডিও ডাউনলোড করো
- /like <uid>: ফ্রি ফায়ার ইউআইডি-তে লাইক পাঠাও

গ্রুপে @IMasterTools মেনশন করো, আমি তোমার জন্য অপেক্ষা করছি! 😄
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join Our Group", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            help_message = f"""
হ্যালো {username}! 😊 আমি তোমার বন্ধুত্বপূর্ণ সহকারী।

কীভাবে কাজ করি:
- গ্রুপে @IMasterTools মেনশন করো বা আমার মেসেজের রিপ্লাই দাও
- প্রাইভেট চ্যাটে শুধু অ্যাডমিন সব ফিচার ব্যবহার করতে পারবেন
- আমি কথোপকথনের ইতিহাস মনে রাখি যতক্ষণ না তুমি মুছো

কমান্ডগুলো:
- /start: স্বাগত মেসেজ দেখাও
- /help: এই সাহায্য মেসেজ
- /clear: চ্যাট ইতিহাস মুছো
- /validatephone <নম্বর> [দেশের_কোড]: ফোন নম্বর যাচাই
- /ytdl <ইউআরএল>: ইউটিউব ভিডিও ডাউনলোড
- /like <uid>: ফ্রি ফায়ার ইউআইডি-তে লাইক পাঠাও

গ্রুপে @IMasterTools মেনশন করো, চলো চ্যাট করি! 😄
            """
            await update.message.reply_text(help_message, reply_markup=reply_markup)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if chat_id in conversation_context:
                del conversation_context[chat_id]
            await update.message.reply_text("চ্যাট ইতিহাস মুছে ফেলা হয়েছে। 😊 নতুন করে শুরু করি!")

    async def validatephone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatephone command"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /validatephone <ফোন_নম্বর> [দেশের_কোড]\nউদাহরণ: /validatephone 01613950781 BD")
            return

        phone_number = context.args[0]
        country_code = context.args[1] if len(context.args) > 1 else None
        response_message = await validate_phone_number(phone_number, PHONE_API_KEY, country_code)
        await update.message.reply_text(response_message)

    async def ytdl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ytdl command"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /ytdl <ইউটিউব_ইউআরএল>\nউদাহরণ: /ytdl https://youtu.be/CWutFtS8Wg0")
            return

        video_url = ' '.join(context.args)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        await download_youtube_video(video_url, context.bot, update.effective_chat.id)

    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command with rate limiting"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if chat_type in ['group', 'supergroup'] and update.message.chat.link != 'https://t.me/VPSHUB_BD_CHAT':
            await update.message.reply_text("এই কমান্ডটি শুধুমাত্র @VPSHUB_BD_CHAT গ্রুপে ব্যবহার করা যাবে। 😊")
            return

        if len(context.args) != 1:
            await update.message.reply_text("ব্যবহার: /like <UID>\nউদাহরণ: /like 123456789")
            return

        if user_id != ADMIN_USER_ID:
            last_like_time = user_likes.get(user_id)
            current_time = datetime.now()
            if last_like_time and (current_time - last_like_time).total_seconds() < 24 * 60 * 60:
                time_left = 24 * 60 * 60 - (current_time - last_like_time).total_seconds()
                hours_left = int(time_left // 3600)
                minutes_left = int((time_left % 3600) // 60)
                await update.message.reply_text(
                    f"তুমি প্রতি ২৪ ঘণ্টায় একবার /like কমান্ড ব্যবহার করতে পারো। 😅 "
                    f"পরবর্তী চেষ্টার জন্য অপেক্ষা করো {hours_left} ঘণ্টা {minutes_left} মিনিট।"
                )
                return

        uid = context.args[0]
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        result = await send_like(uid)
        
        if "added" in result:
            message = (
                "✦───────────────✦\n"
                f"│ 🎉 লাইক পাঠানো সফল! 😊 │\n"
                f"│ 🆔 UID: {result['uid']}\n"
                f"│ 🎮 লেভেল: {result['level']}\n"
                f"│ 🌍 রিজিয়ন: {result['region']}\n"
                f"│ 👤 নিকনেম: {result['nickname']}\n"
                f"│ 📊 আগের লাইক: {result['before']}\n"
                f"│ 📈 পরের লাইক: {result['after']}\n"
                f"│ ➕ যোগ করা হয়েছে: {result['added']}\n"
                "✦──── By Faruk ────✦"
            )
            if user_id != ADMIN_USER_ID:
                user_likes[user_id] = datetime.now()
        else:
            message = f"লাইক পাঠানোতে ব্যর্থ। 😅\nস্ট্যাটাস: {result.get('status', 'অজানা ত্রুটি')}"
        
        await update.message.reply_text(message)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_mention = f"@{new_member.username}" if new_member.username else username
            welcome_message = f"""
{user_mention}, {GROUP_CHAT_USERNAME} গ্রুপে স্বাগতম! 😊 আমি তোমার বন্ধুত্বপূর্ণ বট। @IMasterTools মেনশন করো বা আমার মেসেজের রিপ্লাই দাও। কী নিয়ে কথা বলতে চাও? 😄
            """
            await update.message.reply_text(welcome_message)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        message_text = update.message.text

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if chat_type in ['group', 'supergroup']:
            if not (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id) and '@IMasterTools' not in message_text:
                return

        await update.message.reply_text("এই ফিচারটি এখনো যোগ করা হয়নি। 😅 গ্রুপে @IMasterTools মেনশন করে আরেকটা প্রশ্ন করো!")

    async def get_private_chat_redirect(self):
        """Return redirect message for non-admin private chats"""
        keyboard = [[InlineKeyboardButton("Join Our Group", url="https://t.me/VPSHUB_BD_CHAT")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return (
            "হ্যালো! 😊 আমার সাথে চ্যাট করতে আমাদের গ্রুপে যোগ দাও। নিচের বোতামে ক্লিক করে গ্রুপে যাও এবং @IMasterTools মেনশন করো!",
            reply_markup
        )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error: {context.error}")
        if update:
            await update.effective_chat.send_message("কিছু একটা ভুল হয়েছে। 😅 আবার চেষ্টা করো!")

    def run(self):
        """Run the bot"""
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()