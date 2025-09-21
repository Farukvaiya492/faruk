import requests
import json
import time
import random
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# বটের টোকেন (আপনার বটের টোকেন দিয়ে প্রতিস্থাপন করুন)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# কনভারসেশন স্টেটস
UID, REGION, AMOUNT, CONFIRM = range(4)

# ইউজার ডেটা সংরক্ষণের জন্য ডিকশনারি
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start কমান্ডে ইউজারকে স্বাগতম বার্তা পাঠানো"""
    user = update.message.from_user
    welcome_text = (
        f"স্বাগতম {user.first_name}!\n\n"
        "FF Likes Bot - Free Fire লাইক পাঠানোর বট\n\n"
        "আপনার UID, Region এবং কতগুলো লাইক চান তা জানাবেন।\n\n"
        "শুরু করতে /like কমান্ড দিন অথবা নিচের বাটন ক্লিক করুন।"
    )
    
    # কীবোর্ড বাটন
    keyboard = [['/like']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """লাইক রিকোয়েস্ট শুরু করা"""
    await update.message.reply_text(
        "চলুন লাইক পাঠানো শুরু করি!\n\n"
        "প্রথমে আপনার Free Fire UID দিন:",
        reply_markup=ReplyKeyboardRemove()
    )
    return UID

async def get_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """UID সংগ্রহ করা"""
    uid = update.message.text.strip()
    user_data[update.message.chat_id] = {'uid': uid}
    
    await update.message.reply_text(
        "ভালো! এখন আপনার Region দিন (যেমন: asia, global, india ইত্যাদি):"
    )
    return REGION

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Region সংগ্রহ করা"""
    region = update.message.text.strip()
    user_data[update.message.chat_id]['region'] = region
    
    await update.message.reply_text(
        "কতগুলো লাইক চান? (ডিফল্ট: 100):\n\n"
        "আপনি 1-1000 এর মধ্যে সংখ্যা দিতে পারেন।"
    )
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """লাইকের পরিমাণ সংগ্রহ করা"""
    amount_text = update.message.text.strip()
    
    try:
        amount = int(amount_text)
        if amount < 1 or amount > 1000:
            await update.message.reply_text("দুঃখিত! শুধুমাত্র 1-1000 এর মধ্যে সংখ্যা দিন।")
            return AMOUNT
    except ValueError:
        await update.message.reply_text("দুঃখিত! শুধুমাত্র সংখ্যা দিন (যেমন: 100)")
        return AMOUNT
    
    user_data[update.message.chat_id]['amount'] = amount
    
    # কনফার্মেশন কীবোর্ড
    keyboard = [['হ্যাঁ', 'না']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    user_info = user_data[update.message.chat_id]
    await update.message.reply_text(
        f"আপনার তথ্য:\n\n"
        f"UID: {user_info['uid']}\n"
        f"Region: {user_info['region']}\n"
        f"লাইক: {user_info['amount']}\n\n"
        f"কি লাইক পাঠানো শুরু করব?",
        reply_markup=reply_markup
    )
    return CONFIRM

async def confirm_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """রিকোয়েস্ট কনফার্ম এবং প্রসেস করা"""
    choice = update.message.text.lower()
    
    if choice == 'হ্যাঁ':
        user_info = user_data[update.message.chat_id]
        
        # লোডিং মেসেজ
        loading_msg = await update.message.reply_text("⏳ লাইক পাঠানো হচ্ছে...")
        
        # API কে কল করা
        result = send_like_request(
            user_info['uid'], 
            user_info['region'], 
            user_info['amount']
        )
        
        # রেস্পন্স প্রসেস করা
        if 'error' in result:
            response_text = f"❌ সমস্যা হয়েছে:\n{result['error']}"
        else:
            response_text = f"✅ সফলভাবে লাইক পাঠানো হয়েছে!\n\n"
            if 'likes_sent' in result:
                response_text += f"পাঠানো লাইক: {result['likes_sent']}\n"
            if 'total_likes' in result:
                response_text += f"মোট লাইক: {result['total_likes']}\n"
        
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=loading_msg.message_id)
        await update.message.reply_text(response_text, reply_markup=ReplyKeyboardRemove())
        
    else:
        await update.message.reply_text(
            "রিকোয়েস্ট বাতিল করা হয়েছে। নতুন করে শুরু করতে /like দিন।",
            reply_markup=ReplyKeyboardRemove()
        )
    
    # কনভারসেশন শেষ
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কনভারসেশন ক্যান্সেল করা"""
    await update.message.reply_text(
        "রিকোয়েস্ট বাতিল করা হয়েছে। প্রয়োজন হলে আবার /like দিন।",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সাহায্য কমান্ড"""
    help_text = (
        "🤖 FF Likes Bot Help\n\n"
        "কমান্ডস:\n"
        "/start - বট শুরু করুন\n"
        "/like - লাইক পাঠানো শুরু করুন\n"
        "/help - এই সাহায্য বার্তা দেখান\n\n"
        "ব্যবহার:\n"
        "1. /like কমান্ড দিন\n"
        "2. আপনার UID দিন\n"
        "3. আপনার Region দিন\n"
        "4. কতগুলো লাইক চান তা দিন\n"
        "5. কনফার্ম করুন\n\n"
        "📝 নোট: এই বটটি শুধুমাত্র শিক্ষামূলক উদ্দেশ্যে তৈরি।"
    )
    await update.message.reply_text(help_text)

def send_like_request(uid, region, amount=100):
    """
    লাইক API-তে Chrome user agent দিয়ে রিকোয়েস্ট পাঠান
    """
    chrome_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    url = f"https://likes.ffgarena.cloud/api/v2/likes?uid={uid}&amount_of_likes={amount}&auth=trial-7d&region={region}"
    
    headers = {
        'User-Agent': chrome_user_agent,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://ffgarena.cloud',
        'Referer': 'https://ffgarena.cloud/',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"রিকোয়েস্ট ব্যর্থ হয়েছে, স্ট্যাটাস কোড: {response.status_code}"}
    
    except requests.exceptions.RequestException as e:
        return {"error": f"রিকোয়েস্ট এক্সেপশন: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON ডিকোড এরর: {str(e)}"}

def main():
    """মেইন ফাংশন - বট রান করা"""
    # বট অ্যাপ্লিকেশন তৈরি করুন
    application = Application.builder().token(BOT_TOKEN).build()
    
    # কনভারসেশন হ্যান্ডলার
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('like', like_command)],
        states={
            UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_uid)],
            REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_region)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_request)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # কমান্ড হ্যান্ডলার যোগ করুন
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    
    # বট শুরু করুন
    print("বট চলছে...")
    application.run_polling()

if __name__ == "__main__":
    main()