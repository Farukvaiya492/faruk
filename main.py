import os
import logging
import google.generativeai as genai
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
REMOVE_BG_API_KEY = '15smbepCfMYoHh7D7Cnzj9Z6'  # remove.bg API key
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7835226724'))
PORT = int(os.getenv('PORT', 8000))
WEATHER_API_KEY = "c1794a3c9faa01e4b5142313d4191ef8"  # Weatherstack API key

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

# Store conversation context and state for removebg
conversation_context = {}
group_activity = {}
removebg_state = {}  # To track which chats are expecting an image for /removebg

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
✅ Phone Number Validation Complete:
📞 Number: {data.get('number', 'N/A')}
🌍 Country: {data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})
📍 Location: {data.get('location', 'N/A')}
📡 Carrier: {data.get('carrier', 'N/A')}
📱 Line Type: {data.get('line_type', 'N/A')}
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
✅ BIN Validation Complete:
💳 BIN: {result.get('Bin', 'N/A')}
🏦 Card Brand: {result.get('CardBrand', 'N/A')}
🏛️ Issuing Institution: {result.get('IssuingInstitution', 'N/A')}
📋 Card Type: {result.get('CardType', 'N/A')}
🏷️ Card Category: {result.get('CardCategory', 'N/A')}
🌍 Issuing Country: {result.get('IssuingCountry', 'N/A')} ({result.get('IssuingCountryCode', 'N/A')})
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
                
            # New box design using ┏, ┗, ━, ┃
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ 🔍 YouTube Search Results for '{query}' ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            
            for i, res in enumerate(results[:limit], 1):
                output_message += f"┃ 🎥 Video {i}:\n"
                output_message += f"┃ 📌 Title: {res.get('title', 'N/A')}\n"
                output_message += f"┃ 📺 Type: {res.get('type', 'N/A')}\n"
                output_message += f"┃ 👁️‍🗨️ Views: {res.get('views', 'N/A')}\n"
                output_message += f"┃ 📅 Uploaded: {res.get('uploaded', 'N/A')}\n"
                output_message += f"┃ ⏱️ Duration: {res.get('duration', 'N/A')}\n"
                output_message += f"┃ 📝 Description: {res.get('description', 'N/A')[:100]}...\n"
                output_message += f"┃ 📢 Channel: {res.get('channel', 'N/A')}\n"
                output_message += f"┃ 🔗 Link: {res.get('url', 'N/A')}\n"
                output_message += "┃\n"
            
            # Get creator and log for debugging
            creator = data.get('creator', 'Unknown')
            logger.info(f"Raw creator value: {creator}")
            # Replace the creator with the new text
            creator = "𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸"
            output_message += f"┗━━━ {creator} ━━━┛"
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
        
        # Box design matching /yts
        output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        output_message += f"┃ 🌐 IP Information for '{ip_address}' ┃\n"
        output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
        output_message += f"┃ 📍 IP: {data.get('ip', 'N/A')}\n"
        output_message += f"┃ 🖥️ Hostname: {data.get('hostname', 'N/A')}\n"
        output_message += f"┃ 🏙️ City: {data.get('city', 'N/A')}\n"
        output_message += f"┃ 🌍 Region: {data.get('region', 'N/A')}\n"
        output_message += f"┃ 🇺🇳 Country: {data.get('country', 'N/A')}\n"
        output_message += f"┃ 📌 Location: {data.get('loc', 'N/A')}\n"
        output_message += f"┃ 🏢 Organization: {data.get('org', 'N/A')}\n"
        output_message += "┃\n"
        output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
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
            # Handle currency dynamically
            currency_info = "N/A"
            if 'currencies' in country and country['currencies']:
                first_currency = next(iter(country['currencies']))
                currency_name = country['currencies'][first_currency].get('name', 'N/A')
                currency_symbol = country['currencies'][first_currency].get('symbol', '')
                currency_info = f"{currency_name} ({currency_symbol})"
            
            # Handle capital as a list or string
            capital = country.get('capital', ['N/A'])[0] if isinstance(country.get('capital'), list) else country.get('capital', 'N/A')
            
            # Format output with box design
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ 🌍 Country Information for '{country_name.title()}' ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            output_message += f"┃ 🏳️ Name: {country.get('name', {}).get('common', 'N/A')}\n"
            output_message += f"┃ 🏛️ Capital: {capital}\n"
            output_message += f"┃ 👨‍👩‍👧‍👦 Population: {country.get('population', 'N/A')}\n"
            output_message += f"┃ 📏 Area: {country.get('area', 'N/A')} km²\n"
            output_message += f"┃ 🗣️ Languages: {', '.join(country.get('languages', {}).values()) if country.get('languages') else 'N/A'}\n"
            output_message += f"┃ 🚩 Flag: {country.get('flag', 'N/A')}\n"
            output_message += f"┃ 💰 Currency: {currency_info}\n"
            output_message += f"┃ 🌐 Region: {country.get('region', 'N/A')}\n"
            output_message += f"┃ 🗺️ Subregion: {country.get('subregion', 'N/A')}\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
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
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ ☁ Weather Information for '{location.title()}' ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            output_message += f"┃ 🌡️ Temperature: {current_weather.get('temperature', 'N/A')}°C\n"
            output_message += f"┃ ☁ Weather: {current_weather.get('weather_descriptions', ['N/A'])[0]}\n"
            output_message += f"┃ 💧 Humidity: {current_weather.get('humidity', 'N/A')}% \n"
            output_message += f"┃ 💨 Wind Speed: {current_weather.get('wind_speed', 'N/A')} km/h\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
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

async def get_gemini_trading_pairs():
    """
    Fetch available trading pairs from Gemini API
    :return: Formatted response string with box design
    """
    url = "https://api.gemini.com/v1/symbols"
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            symbols = response.json()
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += "┃ 💹 Available Trading Pairs on Gemini ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            for i, symbol in enumerate(symbols[:10], 1):  # Limit to 10 pairs for brevity
                output_message += f"┃ 💱 Pair {i}: {symbol.upper()}\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
            return output_message
        else:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            return f"❌ Error fetching trading pairs: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Gemini trading pairs: {e}")
        return f"❌ Error fetching trading pairs: {str(e)}"

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
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ 💹 24hr Ticker Data for {data['symbol']} ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            output_message += f"┃ 💰 Last Price: {data.get('lastPrice', 'N/A')}\n"
            output_message += f"┃ 📈 Price Change (24h): {data.get('priceChange', 'N/A')}\n"
            output_message += f"┃ 📊 Price Change Percent: {data.get('priceChangePercent', 'N/A')}% \n"
            output_message += f"┃ 🔺 24h High Price: {data.get('highPrice', 'N/A')}\n"
            output_message += f"┃ 🔻 24h Low Price: {data.get('lowPrice', 'N/A')}\n"
            output_message += f"┃ 📉 24h Volume: {data.get('volume', 'N/A')}\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 �𝗙𝗮𝗿𝘂𝗸 ━━━┛"
            return output_message
        else:
            logger.error(f"Binance API error: {response.status_code} - {response.text}")
            return f"❌ Error fetching ticker data: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Binance ticker data: {e}")
        return f"❌ Error fetching ticker data: {str(e)}"

async def send_like(uid: str, server_name: str = "BD"):
    """
    Send likes to a Free Fire UID
    :param uid: Free Fire user ID
    :param server_name: Server name (default: BD)
    :return: Formatted response string with box design
    """
    api_url = f"https://free-like-api-aditya-ffm.vercel.app/like?uid={uid}&server_name={server_name}&key=@adityaapis"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            before = data.get("LikesbeforeCommand", 0)
            after = data.get("LikesafterCommand", 0)
            added = after - before
            level = data.get("PlayerLevel", "N/A")
            region = data.get("PlayerRegion", "N/A")
            nickname = data.get("PlayerNickname", "N/A")
            
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ ✅ Likes Sent to Free Fire UID {uid} ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            output_message += f"┃ 👤 Player Nickname: {nickname}\n"
            output_message += f"┃ 🏆 Player Level: {level}\n"
            output_message += f"┃ 🌍 Player Region: {region}\n"
            output_message += f"┃ ❤️ Likes Before: {before}\n"
            output_message += f"┃ ❤️ Likes After: {after}\n"
            output_message += f"┃ ➕ Likes Added: {added}\n"
            output_message += f"┃ 🟢 Status: Success ✅\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
            return output_message
        else:
            logger.error(f"Free Fire Like API error: {response.status_code} - {response.text}")
            return f"❌ Failed to send like.\nStatus: Error {response.status_code}"
    except Exception as e:
        logger.error(f"Error sending Free Fire like: {e}")
        return f"❌ Failed to send like.\nStatus: Error: {str(e)}"

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
        self.application.add_handler(CommandHandler("gemini", self.gemini_command))
        self.application.add_handler(CommandHandler("binance", self.binance_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
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
- /validatebin <bin_number]: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
- /weather <location>: Fetch current weather information
- /removebg: Remove the background from an uploaded image
- /gemini: List available trading pairs on Gemini exchange
- /binance <symbol>: Fetch 24hr ticker data for a Binance trading pair
- /like <uid>: Send likes to a Free Fire UID
{'' if user_id != ADMIN_USER_ID else '- /api <key>: Set Gemini AI API key (admin only)\n- /setadmin: Set yourself as admin (first-time only)\n- /setmodel: Choose a different model (admin only)'}

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
- /clear: Clear your conversation history
- /status: Check bot status
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number]: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
- /weather <location>: Fetch current weather information
- /removebg: Remove the background from an uploaded image
- /gemini: List available trading pairs on Gemini exchange
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
        """Handle /api command to set Gemini AI API key"""
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

To get a Gemini AI API key:
1. Visit https://makersuite.google.com/app/apikey
2. Generate a new API key
3. Use the command: /api YOUR_API_KEY

For security, the command message will be deleted after setting the key.
                """, parse_mode='Markdown')
                return
            api_key = ' '.join(context.args)
            if len(api_key) < 20 or not api_key.startswith('AI'):
                await update.message.reply_text("Invalid API key format. Gemini AI API keys typically start with 'AI' and are over 20 characters.")
                return
            success, message = initialize_gemini_models(api_key)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception as e:
                logger.error(f"Error deleting API command