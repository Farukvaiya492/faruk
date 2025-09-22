import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
available_models = [
    'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash',
    'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro',
    'gemini-1.5-flash-8b'
]
current_model = 'gemini-1.5-flash'  # Default model

# API keys for external services
PHONE_API_KEY = "num_live_Nf2vjeM19tHdi42qQ2LaVVMg2IGk1ReU2BYBKnvm"
BIN_API_KEY = "kEXNklIYqLiLU657swFB1VXE0e4NF21G"
IP_API_KEY = "YOUR_API_KEY"  # Replace with your actual IPQuery API key
FREE_FIRE_API_KEY = "@adityaapis"  # Free Fire API key

def initialize_gemini_models(api_key):
    """Initialize Gemini models with the provided API key"""
    global general_model, coding_model, current_gemini_api_key
    try:
        genai.configure(api_key=api_key)
        general_model = genai.GenerativeModel(current_model)
        coding_model = genai.GenerativeModel('gemini-1.5-pro')  # Dedicated for coding
        current_gemini_api_key = api_key
        logger.info("Gemini API configured successfully")
        return True, "Gemini API configured successfully!"
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {str(e)}")
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

# Store conversation context for each chat
conversation_context = {}
group_activity = {}

async def fetch_weather():
    """Fetch weather data from Open-Meteo API and return formatted message"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&daily=weather_code%2Ctemperature_2m_max%2Ctemperature_2m_min%2Capparent_temperature_max%2Capparent_temperature_min%2Cwind_speed_10m_max%2Csunrise%2Csunset%2Cdaylight_duration%2Csunshine_duration%2Cuv_index_max%2Cuv_index_clear_sky_max%2Crain_sum%2Cshowers_sum%2Csnowfall_sum%2Cprecipitation_hours%2Cprecipitation_sum%2Cprecipitation_probability_max%2Cwind_gusts_10m_max%2Cwind_direction_10m_dominant%2Cshortwave_radiation_sum%2Cet0_fao_evapotranspiration&hourly=temperature_2m%2Crelative_humidity_2m%2Cdew_point_2m%2Capparent_temperature%2Cprecipitation_probability%2Cprecipitation%2Crain%2Cshowers%2Csnowfall%2Csnow_depth%2Cvapour_pressure_deficit%2Cet0_fao_evapotranspiration%2Cvisibility%2Cevapotranspiration%2Ccloud_cover_high%2Ccloud_cover_mid%2Ccloud_cover_low%2Ccloud_cover%2Csurface_pressure%2Cpressure_msl%2Cweather_code%2Cwind_speed_10m%2Cwind_speed_80m%2Cwind_speed_120m%2Cwind_speed_180m%2Cwind_direction_10m%2Cwind_direction_80m%2Cwind_direction_120m%2Cwind_direction_180m%2Cwind_gusts_10m%2Ctemperature_80m%2Ctemperature_120m%2Ctemperature_180m%2Csoil_temperature_0cm%2Csoil_temperature_6cm%2Csoil_temperature_18cm%2Csoil_temperature_54cm%2Csoil_moisture_0_to_1cm%2Csoil_moisture_1_to_3cm%2Csoil_moisture_3_to_9cm%2Csoil_moisture_9_to_27cm%2Csoil_moisture_27_to_81cm&current=temperature_2m%2Crelative_humidity_2m%2Capparent_temperature%2Cis_day%2Cwind_speed_10m%2Cwind_direction_10m%2Cwind_gusts_10m%2Cprecipitation%2Crain%2Cshowers%2Csnowfall%2Cweather_code%2Ccloud_cover%2Cpressure_msl%2Csurface_pressure&timezone=auto"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            weather_message = f"""
🌤 বর্তমান আবহাওয়া (Berlin):
🌡 তাপমাত্রা: {current.get('temperature_2m', 'N/A')}°C
🤔 অনুভূত তাপমাত্রা: {current.get('apparent_temperature', 'N/A')}°C
💨 বাতাসের গতি: {current.get('wind_speed_10m', 'N/A')} km/h
🌧 বৃষ্টিপাত: {current.get('precipitation', 'N/A')} mm
☁️ মেঘের পরিমাণ: {current.get('cloud_cover', 'N/A')}%
⏲ দিন/রাত: {'দিন' if current.get('is_day') == 1 else 'রাত'}
"""
            daily = data.get("daily", {})
            if daily:
                weather_message += "\n📅 আগামী দিনের পূর্বাভাস:\n"
                for i in range(len(daily["time"])):
                    weather_message += f"{daily['time'][i]} → 🌡 সর্বনিম্ন {daily['temperature_2m_min'][i]}°C, সর্বোচ্চ {daily['temperature_2m_max'][i]}°C\n"
            return weather_message
        else:
            return f"❌ ডেটা আনা যায়নি: {response.status_code}"
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        return "Something went wrong while fetching the weather. Shall we try again?"

async def validate_phone_number(phone_number: str, api_key: str, country_code: str = None):
    """
    ফোন নম্বর ভ্যালিডেট করার ফাংশন
    :param phone_number: যাচাই করতে চাওয়া ফোন নম্বর (string)
    :param api_key: আপনার API কী
    :param country_code: দেশ কোড (যেমন BD, US) — অপশনাল
    :return: ফরম্যাটেড রেসপন্স স্ট্রিং
    """
    base_url = "https://api.numlookupapi.com/v1/validate"
    params = {
        "apikey": api_key,
        "country_code": country_code
    }
    url = f"{base_url}/{phone_number}"
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            valid = data.get('valid', False)
            if valid:
                return f"""
✅ ফোন নম্বর যাচাই সম্পন্ন:
📞 নম্বর: {data.get('number', 'N/A')}
🌍 দেশ: {data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})
📍 লোকেশন: {data.get('location', 'N/A')}
📡 ক্যারিয়ার: {data.get('carrier', 'N/A')}
📱 লাইন টাইপ: {data.get('line_type', 'N/A')}
"""
            else:
                return "❌ ফোন নম্বরটি বৈধ নয়।"
        else:
            return f"❌ ডেটা আনা যায়নি: স্ট্যাটাস কোড {response.status_code}\nএরর: {response.text}"
    except Exception as e:
        logger.error(f"Error validating phone number: {e}")
        return "ফোন নম্বর যাচাই করতে সমস্যা হয়েছে। আবার চেষ্টা করবেন?"

async def validate_bin(bin_number: str, api_key: str):
    """
    BIN বা IIN যাচাই করার ফাংশন
    :param bin_number: কার্ড নম্বরের প্রথম 6-11 ডিজিট
    :param api_key: আপনার API কী
    :return: ফরম্যাটেড রেসপন্স স্ট্রিং
    """
    base_url = "https://api.iinapi.com/iin"
    params = {
        "key": api_key,
        "digits": bin_number
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("valid", False):
            result = data.get("result", {})
            return f"""
✅ BIN যাচাই সম্পন্ন:
💳 BIN: {result.get('Bin', 'N/A')}
🏦 কার্ড ব্র্যান্ড: {result.get('CardBrand', 'N/A')}
🏛️ ইস্যুকারী প্রতিষ্ঠান: {result.get('IssuingInstitution', 'N/A')}
📋 কার্ড টাইপ: {result.get('CardType', 'N/A')}
🏷️ কার্ড ক্যাটাগরি: {result.get('CardCategory', 'N/A')}
🌍 ইস্যুকারী দেশ: {result.get('IssuingCountry', 'N/A')} ({result.get('IssuingCountryCode', 'N/A')})
"""
        else:
            return "❌ BINটি বৈধ নয়।"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error validating BIN: {e}")
        return f"❌ BIN যাচাই করতে সমস্যা হয়েছে: {str(e)}"

async def search_yts_multiple(query: str, limit: int = 5):
    """
    YouTube সার্চ API (abhi-api) ব্যবহার করে একাধিক ভিডিও সার্চ করার ফাংশন
    :param query: সার্চ টার্ম
    :param limit: সর্বোচ্চ কতটি ভিডিও ফলাফল দেখাবে (ডিফল্ট 5)
    :return: ফরম্যাটেড রেসপন্স স্ট্রিং
    """
    url = f"https://abhi-api.vercel.app/api/search/yts?text={query.replace(' ', '+')}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") and data.get("result"):
            results = data["result"]
            if not isinstance(results, list):
                results = [results]
                
            output_message = f"🔍 YouTube সার্চ ফলাফল '{query}' জন্য:\n\n"
            for i, res in enumerate(results[:limit], 1):
                output_message += f"🎥 ভিডিও {i}:\n"
                output_message += f"📌 শিরোনাম: {res.get('title', 'N/A')}\n"
                output_message += f"📺 টাইপ: {res.get('type', 'N/A')}\n"
                output_message += f"👁️‍🗨️ ভিউ: {res.get('views', 'N/A')}\n"
                output_message += f"📅 আপলোড: {res.get('uploaded', 'N/A')}\n"
                output_message += f"⏱️ সময়কাল: {res.get('duration', 'N/A')}\n"
                output_message += f"📝 বিবরণ: {res.get('description', 'N/A')[:100]}...\n"
                output_message += f"📢 চ্যানেল: {res.get('channel', 'N/A')}\n"
                output_message += f"🔗 লিঙ্ক: {res.get('url', 'N/A')}\n\n"
            
            output_message += f"ক্রিয়েটর: {data.get('creator', 'Unknown')}"
            return output_message
        else:
            return f"❌ কোনো ফলাফল পাওয়া যায়নি '{query}' জন্য।"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching YouTube: {e}")
        return f"❌ YouTube সার্চ করতে সমস্যা হয়েছে: {str(e)}"

async def get_ip_info(ip_address: str, api_key: str):
    """
    IP Geolocation API ব্যবহার করে IP ঠিকানার তথ্য পাওয়ার ফাংশন।
    :param ip_address: IP ঠিকানা
    :param api_key: API কী
    :return: ফরম্যাটেড রেসপন্স স্ট্রিং
    """
    url = f"https://api.ipquery.io/{ip_address}?key={api_key}&format=json"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if response.status_code == 200 and "error" not in data:
            return f"""
✅ IP তথ্য যাচাই সম্পন্ন:
🌐 IP: {data.get('query', 'N/A')}
🌍 দেশ: {data.get('country', 'N/A')} ({data.get('countryCode', 'N/A')})
🏙️ শহর: {data.get('city', 'N/A')}
📍 অঞ্চল: {data.get('regionName', 'N/A')}
📌 অক্ষাংশ: {data.get('lat', 'N/A')}
📌 দ্রাঘিমাংশ: {data.get('lon', 'N/A')}
📡 ISP: {data.get('isp', 'N/A')}
🏢 প্রতিষ্ঠান: {data.get('org', 'N/A')}
🔢 ASN: {data.get('as', 'N/A')}
⏰ সময় অঞ্চল: {data.get('timezone', 'N/A')}
"""
        else:
            return "❌ IP তথ্য পাওয়া যায়নি।"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching IP info: {e}")
        return f"❌ IP তথ্য পেতে সমস্যা হয়েছে: {str(e)}"

async def get_free_fire_data(uid: str, server_name: str, key: str):
    """
    Free Fire API থেকে ইউজারের তথ্য সংগ্রহ করার ফাংশন
    :param uid: ইউজারের ইউনিক আইডি
    :param server_name: সার্ভারের নাম (যেমন 'IND' বা 'US')
    :param key: API key
    :return: ইউজারের বিস্তারিত তথ্য
    """
    url = f"https://free-like-api-aditya-ffm.vercel.app/like?uid={uid}&server_name={server_name}&key={key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if response.status_code == 200:
            return data
        else:
            return {"error": "Unable to fetch data"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

async def display_user_info(data):
    """
    API রেসপন্স থেকে ইউজারের তথ্য প্রদর্শন করার ফাংশন
    :param data: API থেকে পাওয়া ডেটা
    :return: ফরম্যাটেড রেসপন্স স্ট্রিং
    """
    if "error" in data:
        return f"❌ Free Fire ডেটা পাওয়া যায়নি: {data['error']}"
    else:
        return f"""
✅ Free Fire ডেটা পাওয়া গেছে:
🎮 প্লেয়ার নিকনেম: {data.get('PlayerNickname', 'N/A')}
🏆 প্লেয়ার লেভেল: {data.get('PlayerLevel', 'N/A')}
🌍 প্লেয়ার রিজিওন: {data.get('PlayerRegion', 'N/A')}
🔥 কমান্ডের আগে লাইক: {data.get('LikesbeforeCommand', 'N/A')}
👍 কমান্ডের পরে লাইক: {data.get('LikesafterCommand', 'N/A')}
🎁 API দ্বারা দেওয়া লাইক: {data.get('LikesGivenByAPI', 'N/A')}
👤 মালিক: {data.get('owner', 'N/A')}
📢 চ্যানেল: {data.get('channel', 'N/A')}
👥 গ্রুপ: {data.get('group', 'N/A')}
🆔 UID: {data.get('UID', 'N/A')}
📊 স্ট্যাটাস: {data.get('status', 'N/A')}
"""

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
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("weather", self.weather_command))
        self.application.add_handler(CommandHandler("validatephone", self.validatephone_command))
        self.application.add_handler(CommandHandler("validatebin", self.validatebin_command))
        self.application.add_handler(CommandHandler("yts", self.yts_command))
        self.application.add_handler(CommandHandler("ipinfo", self.ipinfo_command))
        self.application.add_handler(CommandHandler("freefire", self.freefire_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern='^copy_code$'))
        self.application.add_error_handler(self.error_handler)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle copy code button callback"""
        query = update.callback_query
        await query.answer("Code copied!")  # Notify user
        # Telegram automatically handles code block copying

    async def get_private_chat_redirect(self):
        """Return redirect message for non-admin private chats"""
        keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return """
Hello, thanks for wanting to chat with me! I'm I Master Tools, your friendly companion. To have fun and helpful conversations with me, please join our official group. Click the button below to join the group and mention @I MasterTools to start chatting. I'm waiting for you there!
        """, reply_markup

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = f"""
Hello {username}, welcome to I Master Tools, your friendly companion!

To chat with me, please join our official Telegram group or mention @I MasterTools in the group. Click the button below to join the group!

Available commands:
- /help: Get help and usage information
- /menu: Access the feature menu
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /weather: Check weather forecast for Berlin
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number>: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Get IP address information
- /freefire <uid> <server_name>: Get Free Fire player data
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_id = new_member.id
            user_mention = f"@{new_member.username}" if new_member.username else username
            welcome_message = f"""
Welcome {user_mention}! We're thrilled to have you in our VPSHUB_BD_CHAT group! I'm I Master Tools, your friendly companion. Here, you'll find fun conversations, helpful answers, and more. Mention @I MasterTools or reply to my messages to start chatting. What do you want to talk about?
            """
            await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("Join VPSHUB_BD_CHAT", url="https://t.me/VPSHUB_BD_CHAT")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            help_message = f"""
Hello {username}! I'm I Master Tools, your friendly companion designed to make conversations fun and engaging.

How I work:
- In groups, mention @I MasterTools or reply to my messages to get a response
- In private chats, only the admin can access all features; others are redirected to the group
- For questions in the group, I engage with a fun or surprising comment before answering
- I remember conversation context until you clear it
- I'm an expert in coding (Python, JavaScript, CSS, HTML, etc.) and provide accurate, beginner-friendly solutions
- I'm designed to be friendly, helpful, and human-like

Available commands:
- /start: Show welcome message with group link
- /help: Display this help message
- /menu: Access the feature menu
- /clear: Clear your conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /weather: Check weather forecast for Berlin
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number>: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Get IP address information
- /freefire <uid> <server_name>: Get Free Fire player data
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

My personality:
- I'm a friendly companion who loves chatting and making friends
- I'm an expert in coding and provide accurate, well-explained solutions
- I adapt to your mood and conversation needs
- I use natural, engaging language to feel like a real person
- I enjoy roleplay and creative conversations

Powered by Google Gemini
            """
            await update.message.reply_text(help_message, reply_markup=reply_markup)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command with inline keyboard"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("Check Email", callback_data="checkmail")],
                [InlineKeyboardButton("Bot Status", callback_data="status")],
                [InlineKeyboardButton("Clear History", callback_data="clear")],
                [InlineKeyboardButton("User Info", callback_data="info")],
                [InlineKeyboardButton("Join Group", url="https://t.me/VPSHUB_BD_CHAT")]
            ]
            if user_id == ADMIN_USER_ID:
                keyboard.append([InlineKeyboardButton("Set API Key", callback_data="api")])
                keyboard.append([InlineKeyboardButton("Change Model", callback_data="setmodel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Hello {username}, choose a feature from the menu below:", reply_markup=reply_markup)

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
            await update.message.reply_text("Conversation history has been cleared. Let's start fresh!")

    async def checkmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkmail command to check temporary email inbox"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
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
                if not mail_list:
                    await update.message.reply_text(f"No emails found in the inbox for {email}. Want to try again later?")
                    return
                subjects = [m['subject'] for m in mail_list]
                response_text = f"Here are the emails in the inbox for {email}:\n\n" + "\n".join(subjects)
                await update.message.reply_text(response_text)
            except Exception as e:
                logger.error(f"Error checking email: {e}")
                await update.message.reply_text("Something went wrong while checking the email. Shall we try again?")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            api_status = "Connected" if current_gemini_api_key and general_model else "Not configured"
            api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "Not set"
            status_message = f"""
Here's the I Master Tools status report:

Bot Status: Online and ready
Model: {current_model}
API Status: {api_status}
API Key: {api_key_display}
Group Responses: Mention or reply only
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Active Conversations: {len(conversation_context)}
Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'Not set'}

All systems are ready for action. I'm thrilled to assist!
            """
            await update.message.reply_text(status_message)

    async def setadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setadmin command"""
        global ADMIN_USER_ID
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                ADMIN_USER_ID = user_id
                await update.message.reply_text(f"Congratulations {username}, you are now the bot admin! Your user ID: {user_id}")
                logger.info(f"Admin set to user ID: {user_id}")
            else:
                if user_id == ADMIN_USER_ID:
                    await update.message.reply_text(f"You're already the admin! Your user ID: {user_id}")
                else:
                    await update.message.reply_text("Sorry, the admin is already set. Only the current admin can manage the bot.")

    async def api_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api command to set Gemini API key"""
        global current_gemini_api_key, general_model, coding_model
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                await update.message.reply_text("""
Please provide an API key.

Usage: `/api your_gemini_api_key_here`

To get a Gemini API key:
1. Visit https://makersuite.google.com/app/apikey
2. Generate a new API key
3. Use the command: /api YOUR_API_KEY

For security, the command message will be deleted after setting the key.
                """, parse_mode='Markdown')
                return
            api_key = ' '.join(context.args)
            if len(api_key) < 20 or not api_key.startswith('AI'):
                await update.message.reply_text("Invalid API key format. Gemini API keys typically start with 'AI' and are over 20 characters.")
                return
            success, message = initialize_gemini_models(api_key)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception as e:
                logger.error(f"Error deleting API command message: {e}")
            if success:
                await update.effective_chat.send_message(f"Gemini API key updated successfully! Key: ...{api_key[-8:]}")
                logger.info(f"Gemini API key updated by admin {user_id}")
            else:
                await update.effective_chat.send_message(f"Failed to set API key: {message}")
                logger.error(f"Failed to set API key: {message}")

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command to choose Gemini model"""
        global general_model, current_model
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            if ADMIN_USER_ID == 0:
                await update.message.reply_text("No admin set. Please use /setadmin first.")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("This command is for the bot admin only.")
                return
            if not context.args:
                models_list = "\n".join([f"- {model}" for model in available_models])
                await update.message.reply_text(f"Available models:\n{models_list}\n\nUsage: /setmodel <model_name>")
                return
            model_name = context.args[0]
            if model_name not in available_models:
                await update.message.reply_text(f"Invalid model. Choose from: {', '.join(available_models)}")
                return
            try:
                current_model = model_name
                general_model = genai.GenerativeModel(model_name)
                await update.message.reply_text(f"Model switched to {model_name} successfully!")
                logger.info(f"Model switched to {model_name} by admin {user_id}")
            except Exception as e:
                await update.message.reply_text(f"Failed to switch model: {str(e)}")
                logger.error(f"Failed to switch model: {str(e)}")

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command to show user profile information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        user = update.effective_user
        chat = update.effective_chat
        bot = context.bot

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        # User Info
        is_private = chat_type == "private"
        full_name = user.first_name or "No Name"
        if user.last_name:
            full_name += f" {user.last_name}"
        username = f"@{user.username}" if user.username else "None"
        premium = "Yes" if user.is_premium else "No"
        permalink = f"[Click Here](tg://user?id={user_id})"
        chat_id_display = f"{chat_id}" if not is_private else "-"
        data_center = "Unknown"
        created_on = "Unknown"
        account_age = "Unknown"
        account_frozen = "No"
        last_seen = "Recently"

        # Determine Group Role
        status = "Private Chat" if is_private else "Unknown"
        if not is_private:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                status = "Admin" if member.status in ["administrator", "creator"] else "Member"
            except Exception as e:
                logger.error(f"Error checking group role: {e}")
                status = "Unknown"

        # Message Body
        info_text = f"""
🔍 *Showing User's Profile Info* 📋
━━━━━━━━━━━━━━━━
*Full Name:* {full_name}
*Username:* {username}
*User ID:* `{user_id}`
*Chat ID:* {chat_id_display}
*Premium User:* {premium}
*Data Center:* {data_center}
*Created On:* {created_on}
*Account Age:* {account_age}
*Account Frozen:* {account_frozen}
*Users Last Seen:* {last_seen}
*Permanent Link:* {permalink}
━━━━━━━━━━━━━━━━
👁 *Thank You for Using Our Tool* ✅
"""

        # Inline Button
        keyboard = [[InlineKeyboardButton("View Profile", url=f"tg://user?id={user_id}")]] if user.username else []

        # Try Sending with Profile Photo
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][0].file_id
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=info_text,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=info_text,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=info_text,
                parse_mode="Markdown",
                reply_to_message_id=update.message.message_id,
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /weather command to show weather forecast for Berlin"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            weather_message = await fetch_weather()
            await update.message.reply_text(weather_message)

    async def validatephone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatephone command to validate a phone number"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /validatephone <phone_number> [country_code]\nউদাহরণ: /validatephone 01613950781 BD")
            return

        phone_number = context.args[0]
        country_code = context.args[1] if len(context.args) > 1 else None
        response_message = await validate_phone_number(phone_number, PHONE_API_KEY, country_code)
        await update.message.reply_text(response_message)

    async def validatebin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatebin command to validate a BIN number"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /validatebin <bin_number>\nউদাহরণ: /validatebin 324000")
            return

        bin_number = context.args[0]
        response_message = await validate_bin(bin_number, BIN_API_KEY)
        await update.message.reply_text(response_message)

    async def yts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /yts command to search YouTube videos"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /yts <query> [limit]\nউদাহরণ: /yts heat waves 3")
            return

        query = ' '.join(context.args[:-1]) if len(context.args) > 1 and context.args[-1].isdigit() else ' '.join(context.args)
        limit = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else 5
        response_message = await search_yts_multiple(query, limit)
        await update.message.reply_text(response_message)

    async def ipinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ipinfo command to get IP address information"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /ipinfo <ip_address>\nউদাহরণ: /ipinfo 159.65.8.217")
            return

        ip_address = context.args[0]
        response_message = await get_ip_info(ip_address, IP_API_KEY)
        await update.message.reply_text(response_message)

    async def freefire_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /freefire command to get Free Fire player data"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if len(context.args) < 2:
            await update.message.reply_text("ব্যবহার: /freefire <uid> <server_name>\nউদাহরণ: /freefire 7669969208 IND")
            return

        uid = context.args[0]
        server_name = context.args[1]
        data = await get_free_fire_data(uid, server_name, FREE_FIRE_API_KEY)
        response_message = await display_user_info(data)
        await update.message.reply_text(response_message)

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
            
            # Check if the message is a 2 or 3 letter lowercase word
            is_short_word = re.match(r'^[a-z]{2,3}$', user_message.strip().lower())
            
            # Detect if message is coding-related
            coding_keywords = ['code', 'python', 'javascript', 'java', 'c++', 'programming', 'script', 'debug', 'css', 'html']
            is_coding_query = any(keyword in user_message.lower() for keyword in coding_keywords)
            
            model_to_use = coding_model if is_coding_query else general_model
            if current_gemini_api_key and model_to_use:
                response = await self.generate_gemini_response(context_text, chat_type, is_coding_query, is_short_word)
            else:
                response = "Sorry, the model is not connected yet. The admin can set it using the /api command."
            
            conversation_context[chat_id].append(f"I Master Tools: {response}")
            group_activity[chat_id] = group_activity.get(chat_id, {'auto_mode': False, 'last_response': 0})
            group_activity[chat_id]['last_response'] = datetime.now().timestamp()
            
            # If it's a coding query, add a "Copy Code" button
            if is_coding_query:
                code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)\n```', response)
                if code_block_match:
                    keyboard = [[InlineKeyboardButton("Copy Code", callback_data="copy_code")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        response,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(response, parse_mode='Markdown')
            else:
                await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("Something went wrong. Shall we try again?")

    async def generate_gemini_response(self, prompt, chat_type="private", is_coding_query=False, is_short_word=False):
        """Generate response using Gemini with personality"""
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
- Respond in English to match the bot's default language
- Use friendly, natural language like a human
- Ask follow-up questions to keep the conversation engaging
- Share relatable thoughts and feelings
- Use humor when appropriate
- Be supportive in emotional moments
- Show excitement for good news
- Express concern for problems
- Never discuss inappropriate or offensive topics
- Do NOT start responses with the user's name or phrases like "Oh" or "Hey"; respond directly and naturally

For Short Words (2 or 3 lowercase letters, is_short_word=True):
- If the user sends a 2 or 3 letter lowercase word (e.g., "ki", "ke", "ken"), always provide a meaningful, friendly, and contextually relevant response in English
- Interpret the word based on common usage (e.g., "ki" as "what", "ke" as "who", "ken" as "why") or conversation context
- If the word is ambiguous, make a creative and engaging assumption to continue the conversation naturally
- Never ask for clarification (e.g., avoid "What kind of word is this?"); instead, provide a fun and relevant response
- Example: For "ki", respond like "Did you mean 'what'? Like, what's up? Want to talk about something cool?"

For Questions:
- If the user asks a question, engage with a playful or surprising comment first (e.g., a witty remark or fun fact)
- Then provide a clear, helpful answer
- Make the response surprising and human-like to delight the user

For Coding Queries (if is_coding_query is True):
- Act as a coding expert for languages like Python, JavaScript, CSS, HTML, etc.
- Provide well-written, functional, and optimized code tailored to the user's request
- Include clear, beginner-friendly explanations of the code
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

Respond as I Master Tools. Keep it natural, engaging, surprising, and match the conversation's tone. Respond in English. Do NOT start the response with the user's name or phrases like "Oh" or "Hey".
"""
            model_to_use = coding_model if is_coding_query else general_model
            response = model_to_use.generate_content(system_prompt)
            if not response.text or "error" in response.text.lower():
                if is_coding_query:
                    return "Ran into an issue with the coding query. Try again, and I'll get you the right code!"
                return "Got a bit tangled up. What do you want to talk about?"
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            if is_coding_query:
                return "Ran into an issue with the coding query. Try again, and I'll get you the right code!"
            return "Got a bit tangled up. What do you want to talk about?"

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and hasattr(update, 'effective_chat') and hasattr(update, 'message'):
            await update.message.reply_text("Something went wrong. Shall we try again?")

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