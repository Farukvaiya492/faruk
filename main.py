import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime, timedelta, timezone
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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
REMOVE_BG_API_KEY = '15smbepCfMYoHh7D7Cnzj9Z6'  # remove.bg API key
WEATHER_API_KEY = 'c1794a3c9faa01e4b5142313d4191ef8'  # Weatherstack API key
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))
GROUP_CHAT_USERNAME = '@VPSHUB_BD_CHAT'  # Group chat username for /like command
FREE_FIRE_LOGO_URL = 'https://i.ibb.co/v4ZMrFzh/46e17f0fc03734bf7b93defbc4e5b404.jpg'  # Replace with actual Free Fire logo URL

# API keys for external services
PHONE_API_KEY = 'num_live_Nf2vjeM19tHdi42qQ2LaVVMg2IGk1ReU2BYBKnvm'
BIN_API_KEY = 'kEXNklIYqLiLU657swFB1VXE0e4NF21G'

# Store conversation context, group activity, removebg state, and user likes
conversation_context = {}
group_activity = {}
removebg_state = {}  # To track which chats are expecting an image for /removebg
user_likes = {}  # To track user /like command usage with timestamps

async def validate_phone_number(phone_number: str, api_key: str, country_code: str = None):
    """
    Validate a phone number
    :param phone_number: Phone number to validate (string)
    :param api_key: Your API key
    :param country_code: Country code (e.g., BD, US) — optional
    :return: Formatted response string
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
━━━━━━•❅•°•❈•°•❅•━━━━━━
✅ Phone Number Validation Complete
📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}
━━━━━━•❅•°•❈•°•❅•━━━━━━
📞 Number: {data.get('number', 'N/A')}
🌍 Country: {data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})
📍 Location: {data.get('location', 'N/A')}
📡 Carrier: {data.get('carrier', 'N/A')}
📱 Line Type: {data.get('line_type', 'N/A')}
━━━━━━•❅•°•❈•°•❅•━━━━━━
𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸
"""
            else:
                return "❌ The phone number is not valid."
        else:
            return f"❌ Failed to fetch data: Status code {response.status_code}\nError: {response.text}"
    except Exception as e:
        logger.error(f"Error validating phone number: {e}")
        return "There was an issue validating the phone number. Shall we try again?"

async def validate_bin(bin_number: str, api_key: str):
    """
    Validate a BIN or IIN
    :param bin_number: First 6-11 digits of the card number
    :param api_key: Your API key
    :return: Formatted response string
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
━━━━━━•❅•°•❈•°•❅•━━━━━━
✅ BIN Validation Complete
📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}
━━━━━━•❅•°•❈•°•❅•━━━━━━
💳 BIN: {result.get('Bin', 'N/A')}
🏦 Card Brand: {result.get('CardBrand', 'N/A')}
🏛️ Issuing Institution: {result.get('IssuingInstitution', 'N/A')}
📋 Card Type: {result.get('CardType', 'N/A')}
🏷️ Card Category: {result.get('CardCategory', 'N/A')}
🌍 Issuing Country: {result.get('IssuingCountry', 'N/A')} ({result.get('IssuingCountryCode', 'N/A')})
━━━━━━•❅•°•❈•°•❅•━━━━━━
𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸
"""
        else:
            return "❌ The BIN is not valid."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error validating BIN: {e}")
        return f"❌ There was an issue validating the BIN: {str(e)}"

async def search_yts_multiple(query: str, limit: int = 5):
    """
    Search YouTube videos using abhi-api
    :param query: Search term
    :param limit: Maximum number of video results to display (default 5)
    :return: Formatted response string with new box design
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
                
            output_message = f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"🔍 YouTube Search Results for '{query}'\n"
            output_message += f"📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            
            for i, res in enumerate(results[:limit], 1):
                output_message += f"🎥 Video {i}:\n"
                output_message += f"📌 Title: {res.get('title', 'N/A')}\n"
                output_message += f"📺 Type: {res.get('type', 'N/A')}\n"
                output_message += f"👁️‍🗨️ Views: {res.get('views', 'N/A')}\n"
                output_message += f"📅 Uploaded: {res.get('uploaded', 'N/A')}\n"
                output_message += f"⏱️ Duration: {res.get('duration', 'N/A')}\n"
                output_message += f"📝 Description: {res.get('description', 'N/A')[:100]}...\n"
                output_message += f"📢 Channel: {res.get('channel', 'N/A')}\n"
                output_message += f"🔗 Link: {res.get('url', 'N/A')}\n"
                output_message += "\n"
            
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += "𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
            return output_message
        else:
            return "Sorry, I couldn’t find any results for your search. Try a different query!"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching YouTube: {e}")
        return "Something went wrong with the search. Please try again with a different term!"

async def get_ip_info(ip_address: str):
    """
    Fetch IP information using ipinfo.io
    :param ip_address: IP address to look up
    :return: Formatted response string with box design
    """
    url = f"https://ipinfo.io/{ip_address}/json"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        output_message = f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
        output_message += f"🌐 IP Information for '{ip_address}'\n"
        output_message += f"📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
        output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
        output_message += f"📍 IP: {data.get('ip', 'N/A')}\n"
        output_message += f"🖥️ Hostname: {data.get('hostname', 'N/A')}\n"
        output_message += f"🏙️ City: {data.get('city', 'N/A')}\n"
        output_message += f"🌍 Region: {data.get('region', 'N/A')}\n"
        output_message += f"🇺🇳 Country: {data.get('country', 'N/A')}\n"
        output_message += f"📌 Location: {data.get('loc', 'N/A')}\n"
        output_message += f"🏢 Organization: {data.get('org', 'N/A')}\n"
        output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
        output_message += "𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
        return output_message
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching IP info: {e}")
        return "Invalid IP address or error fetching data. Please try a different IP!"

async def get_country_info(country_name: str):
    """
    Fetch country information using restcountries.com
    :param country_name: Name of the country to look up
    :return: Formatted response string with box design
    """
    url = f"https://restcountries.com/v3.1/name/{country_name}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        country_data = response.json()
        
        if country_data:
            country = country_data[0]
            currency_info = "N/A"
            if 'currencies' in country and country['currencies']:
                first_currency = next(iter(country['currencies']))
                currency_name = country['currencies'][first_currency].get('name', 'N/A')
                currency_symbol = country['currencies'][first_currency].get('symbol', '')
                currency_info = f"{currency_name} ({currency_symbol})"
            
            capital = country.get('capital', ['N/A'])[0] if isinstance(country.get('capital'), list) else country.get('capital', 'N/A')
            
            output_message = f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"🌍 Country Information for '{country_name.title()}'\n"
            output_message += f"📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"🏳️ Name: {country.get('name', {}).get('common', 'N/A')}\n"
            output_message += f"🏛️ Capital: {capital}\n"
            output_message += f"👨‍👩‍👧‍👦 Population: {country.get('population', 'N/A')}\n"
            output_message += f"📏 Area: {country.get('area', 'N/A')} km²\n"
            output_message += f"🗣️ Languages: {', '.join(country.get('languages', {}).values()) if country.get('languages') else 'N/A'}\n"
            output_message += f"🚩 Flag: {country.get('flag', 'N/A')}\n"
            output_message += f"💰 Currency: {currency_info}\n"
            output_message += f"🌐 Region: {country.get('region', 'N/A')}\n"
            output_message += f"🗺️ Subregion: {country.get('subregion', 'N/A')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += "𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
            return output_message
        else:
            return "No information found for this country. Please try a different country name!"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching country info: {e}")
        return f"Error fetching country data: {str(e)}. Please try a different country name!"

async def get_weather_info(location: str):
    """
    Fetch weather information using Weatherstack API
    :param location: City or location name to look up
    :return: Formatted response string with box design
    """
    url = "http://api.weatherstack.com/current"
    params = {
        'access_key': WEATHER_API_KEY,
        'query': location
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if response.status_code == 200 and 'current' in data:
            current_weather = data['current']
            output_message = f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"☁ Weather Information for '{location.title()}'\n"
            output_message += f"📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"🌡️ Temperature: {current_weather.get('temperature', 'N/A')}°C\n"
            output_message += f"☁ Weather: {current_weather.get('weather_descriptions', ['N/A'])[0]}\n"
            output_message += f"💧 Humidity: {current_weather.get('humidity', 'N/A')}% \n"
            output_message += f"💨 Wind Speed: {current_weather.get('wind_speed', 'N/A')} km/h\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += "𝗖�_r𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
            return output_message
        else:
            error_info = data.get("error", {}).get("info", "Unknown error")
            return f"Error fetching weather data: {error_info}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather info: {e}")
        return f"Error fetching weather data: {str(e)}. Please try a different location!"

async def remove_background(image_data: bytes, chat_id: int):
    """
    Remove background from an image using remove.bg API
    :param image_data: Bytes of the image file
    :param chat_id: Telegram chat ID for logging
    :return: Tuple of (success, response_content or error_message)
    """
    url = 'https://api.remove.bg/v1.0/removebg'
    try:
        response = requests.post(
            url,
            files={'image_file': ('image.jpg', image_data)},
            data={'size': 'auto'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY}
        )
        if response.status_code == 200:
            return True, response.content
        else:
            logger.error(f"remove.bg API error for chat {chat_id}: {response.status_code} - {response.text}")
            return False, f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        logger.error(f"Error removing background for chat {chat_id}: {e}")
        return False, f"Error removing background: {str(e)}"

async def get_binance_ticker(symbol: str):
    """
    Fetch 24hr ticker data for a specific symbol from Binance API
    :param symbol: Trading pair symbol (e.g., BTCUSDT)
    :return: Formatted response string with box design
    """
    url = 'https://api4.binance.com/api/v3/ticker/24hr'
    full_url = f"{url}?symbol={symbol}"
    
    try:
        response = requests.get(full_url)
        if response.status_code == 200:
            data = response.json()
            output_message = f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"💹 24hr Ticker Data for {data['symbol']}\n"
            output_message += f"📅 System Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += f"💰 Last Price: {data.get('lastPrice', 'N/A')}\n"
            output_message += f"📈 Price Change (24h): {data.get('priceChange', 'N/A')}\n"
            output_message += f"📊 Price Change Percent: {data.get('priceChangePercent', 'N/A')}% \n"
            output_message += f"🔺 24h High Price: {data.get('highPrice', 'N/A')}\n"
            output_message += f"🔻 24h Low Price: {data.get('lowPrice', 'N/A')}\n"
            output_message += f"📉 24h Volume: {data.get('volume', 'N/A')}\n"
            output_message += f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            output_message += "𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
            return output_message
        else:
            logger.error(f"Binance API error: {response.status_code} - {response.text}")
            return f"❌ Error fetching ticker data: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Binance ticker data: {e}")
        return f"❌ Error fetching ticker data: {str(e)}"

async def send_like(uid: str):
    """
    Send likes to a Free Fire UID using the new API
    :param uid: Free Fire user ID
    :return: Dictionary with response data
    """
    api_url = f"https://api-likes-alliff-v3.vercel.app/like?uid={uid}"
    
    try:
        response = requests.get(api_url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return {
                "dev": "@Farukvaiya01",  # Hardcoded developer name as requested
                "name": data.get("name", "N/A"),
                "uid": data.get("uid", "N/A"),
                "likes_before": data.get("likes_before", 0),
                "likes_after": data.get("likes_after", 0),
                "likes_added": data.get("likes_added", 0),
                "status": "Success ✅"
            }
        else:
            return {"status": f"Error: {response.status_code}"}
    except Exception as e:
        return {"status": f"Error: {str(e)}"}

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
        self.application.add_handler(CommandHandler("setmodel", self.setmodel_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("validatephone", self.validatephone_command))
        self.application.add_handler(CommandHandler("validatebin", self.validatebin_command))
        self.application.add_handler(CommandHandler("yts", self.yts_command))
        self.application.add_handler(CommandHandler("ipinfo", self.ipinfo_command))
        self.application.add_handler(CommandHandler("countryinfo", self.countryinfo_command))
        self.application.add_handler(CommandHandler("weather", self.weather_command))
        self.application.add_handler(CommandHandler("removebg", self.removebg_command))
        self.application.add_handler(CommandHandler("binance", self.binance_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, self.handle_photo))
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
- /clear: Clear conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number>: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
- /weather <location>: Fetch current weather information
- /removebg: Remove the background from an uploaded image
- /binance <symbol>: Fetch 24hr ticker data for a Binance trading pair
- /like <uid>: Send likes to a Free Fire UID
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini AI API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

In groups, mention @I MasterTools or reply to my messages to get a response. I'm excited to chat with you!
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
- /clear: Clear your conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number>: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
- /weather <location>: Fetch current weather information
- /removebg: Remove the background from an uploaded image
- /binance <symbol>: Fetch 24hr ticker data for a Binance trading pair
- /like <uid>: Send likes to a Free Fire UID
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini AI API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

My personality:
- I'm a friendly companion who loves chatting and making friends
- I'm an expert in coding and provide accurate, well-explained solutions
- I adapt to your mood and conversation needs
- I use natural, engaging language to feel like a real person
- I enjoy roleplay and creative conversations

Powered by Google Gemini
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
            if chat_id in removebg_state:
                del removebg_state[chat_id]
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
            api_status = "Not configured (Gemini API disabled)"
            api_key_display = "Not set"
            status_message = f"""
Here's the I Master Tools status report:

Bot Status: Online and ready
Model: Not applicable (Gemini API disabled)
API Status: {api_status}
API Key: {api_key_display}
Group Responses: Mention or reply only
Current Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}
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
        """Handle /api command to set Gemini AI API key"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.message.reply_text("Gemini AI API is disabled in this version. Use other commands like /weather, /ipinfo, or /like!")

    async def setmodel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmodel command to choose Gemini model"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.message.reply_text("Model selection is disabled as Gemini API is not configured. Use other commands like /info or /weather!")

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

        status = "Private Chat" if is_private else "Unknown"
        if not is_private:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                status = "Admin" if member.status in ["administrator", "creator"] else "Member"
            except Exception as e:
                logger.error(f"Error checking group role: {e}")
                status = "Unknown"

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

        keyboard = [[InlineKeyboardButton("View Profile", url=f"tg://user?id={user_id}")]] if user.username else []

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

    async def validatephone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatephone command to validate a phone number"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /validatephone <phone_number> [country_code]\nExample: /validatephone 01613950781 BD")
            return

        phone_number = context.args[0]
        country_code = context.args[1] if len(context.args) > 1 else None
        response_message = await validate_phone_number(phone_number, PHONE_API_KEY, country_code)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def validatebin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatebin command to validate a BIN number"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /validatebin <bin_number>\nExample: /validatebin 324000")
            return

        bin_number = context.args[0]
        response_message = await validate_bin(bin_number, BIN_API_KEY)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def yts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /yts command to search YouTube videos"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /yts <query> [limit]\nExample: /yts heat waves 3")
            return

        query = ' '.join(context.args[:-1]) if len(context.args) > 1 and context.args[-1].isdigit() else ' '.join(context.args)
        limit = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else 5
        response_message = await search_yts_multiple(query, limit)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def ipinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ipinfo command to fetch IP address information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /ipinfo <ip_address>\nExample: /ipinfo 203.0.113.123")
            return

        ip_address = context.args[0]
        response_message = await get_ip_info(ip_address)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def countryinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /countryinfo command to fetch country information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /countryinfo <country_name>\nExample: /countryinfo bangladesh")
            return

        country_name = ' '.join(context.args)
        if not re.match(r'^[\x00-\x7F]*$', country_name):
            await update.message.reply_text("Please enter the country name in English. For example, use 'Bangladesh' instead of 'বাংলাদেশ'.")
            return

        response_message = await get_country_info(country_name)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /weather command to fetch current weather information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /weather <location>\nExample: /weather Dhaka")
            return

        location = ' '.join(context.args)
        response_message = await get_weather_info(location)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def removebg_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removebg command to initiate background removal"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        removebg_state[chat_id] = True
        await update.message.reply_text(
            "Please upload an image to remove its background. I'll process it and send back the result!"
        )

    async def binance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /binance command to fetch 24hr ticker data"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /binance <symbol>\nExample: /binance BTCUSDT")
            return

        symbol = context.args[0].upper()
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        response_message = await get_binance_ticker(symbol)
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_message,
            reply_to_message_id=update.message.message_id
        )

    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command to send likes to a Free Fire UID with rate limiting"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if chat_type in ['group', 'supergroup'] and update.message.chat.link != 'https://t.me/VPSHUB_BD_CHAT':
            await update.message.reply_text("This command can only be used in @VPSHUB_BD_CHAT group.")
            return

        if len(context.args) != 1:
            await update.message.reply_text("Usage: /like <UID>")
            return

        if user_id != ADMIN_USER_ID:
            last_like_time = user_likes.get(user_id)
            current_time = datetime.now(timezone(timedelta(hours=8)))
            if last_like_time and (current_time - last_like_time).total_seconds() < 24 * 60 * 60:
                time_left = 24 * 60 * 60 - (current_time - last_like_time).total_seconds()
                hours_left = int(time_left // 3600)
                minutes_left = int((time_left % 3600) // 60)
                await update.message.reply_text(
                    f"⚠ You can use the /like command once every 24 hours.\n"
                    f"Please wait {hours_left} hours and {minutes_left} minutes for your next attempt."
                )
                return

        uid = context.args[0]
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        result = await send_like(uid)
        
        if "likes_added" in result:
            message = (
                f"🔥 𝗙𝗥𝗘𝗘𝗙𝗜𝗥𝗘 𝗨𝗜𝗗 𝗦𝗧𝗔𝗧𝗨𝗦 🔥\n"
                f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
                f"📅 Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
                f"🆔 UID: {result['uid']}\n"
                f"👤 Name: {result['name']}\n"
                f"📊 Likes Before: {result['likes_before']}\n"
                f"📈 Likes After: {result['likes_after']}\n"
                f"➕ Likes Added: {result['likes_added']}\n"
                f"👨‍💻 Developer: {result['dev']}\n"
                f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
            )
            if user_id != ADMIN_USER_ID:
                user_likes[user_id] = datetime.now(timezone(timedelta(hours=8)))
        else:
            # Check for specific error case
            error_message = result.get('status', 'Unknown error')
            if error_message.lower().startswith("error:") and "likes_already_send" in error_message.lower():
                message = (
                    f"🔥 𝗙𝗥𝗘𝗘𝗙𝗜𝗥𝗘 �_L𝗜𝗞𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 🔥\n"
                    f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
                    f"📅 Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
                    f"❌ Failed to Send Likes\n"
                    f"✅ Success: False\n"
                    f"📩 Message: likes_already_send\n"
                    f"👨‍💻 Developer: @Farukvaiya01\n"
                    f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
                )
            else:
                message = (
                    f"🔥 𝗙𝗥𝗘𝗘𝗙𝗜𝗥𝗘 𝗟𝗜𝗞𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 🔥\n"
                    f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
                    f"📅 Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n"
                    f"❌ Failed to send likes.\n"
                    f"📩 Status: {error_message}\n"
                    f"👨‍💻 Developer: @Farukvaiya01\n"
                    f"━━━━━━•❅•°•❈•°•❅•━━━━━━\n"
                )
        
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=FREE_FIRE_LOGO_URL,
            caption=message,
            reply_to_message_id=update.message.message_id
        )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads for background removal"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if chat_id not in removebg_state or not removebg_state[chat_id]:
            return

        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            image_data = await file.download_as_bytearray()
            success, result = await remove_background(image_data, chat_id)

            if success:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=result,
                    caption=f"✅ Background removed successfully!\n📅 Time: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08')}\n━━━━━━•❅•°•❈•°•❅•━━━━━━\n𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
                )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=FREE_FIRE_LOGO_URL,
                    caption=f"❌ Failed to remove background: {result}"
                )

            if chat_id in removebg_state:
                del removebg_state[chat_id]

        except Exception as e:
            logger.error(f"Error handling photo for chat {chat_id}: {e}")
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=FREE_FIRE_LOGO_URL,
                caption="Something went wrong while processing the image. Please try again!"
            )
            if chat_id in removebg_state:
                del removebg_state[chat_id]

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
            await update.message.reply_text("Sorry, text-based AI responses are disabled as Gemini API is not configured. Try commands like /weather, /ipinfo, or /like!")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("Something went wrong. Shall we try again?")

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
    logger.warning("Gemini AI API not configured. Use /setadmin and /api commands to set up.")
    bot = TelegramGeminiBot()
    bot.run()

if __name__ == '__main__':
    main()