import os
import logging
import google.generativeai as genai
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime, timedelta
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
GROUP_CHAT_USERNAME = "@VPSHUB_BD_CHAT"  # Group chat username for /like command

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

# Store conversation context, group activity, removebg state, and user likes
conversation_context = {}
group_activity = {}
removebg_state = {}  # To track which chats are expecting an image for /removebg
user_likes = {}  # To track user /like command usage with timestamps

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
    :return: Formatted response string in Bangla with a friendly tone
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
            currency_info = "N/A"
            if 'currencies' in country and country['currencies']:
                first_currency = next(iter(country['currencies']))
                currency_name = country['currencies'][first_currency].get('name', 'N/A')
                currency_symbol = country['currencies'][first_currency].get('symbol', '')
                currency_info = f"{currency_name} ({currency_symbol})"
            
            capital = country.get('capital', ['N/A'])[0] if isinstance(country.get('capital'), list) else country.get('capital', 'N/A')
            
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
            output_message += "┗━━━ 𝗖�_r_e_a_t_e_ _B_y_ _F_a_r_u_k ━━━┛"
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
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
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
    :return: Dictionary with response data
    """
    api_url = f"https://free-like-api-aditya-ffm.vercel.app/like?uid={uid}&server_name={server_name}&key=@adityaapis"
    
    try:
        response = requests.get(api_url, timeout=20)
        
        # Debugging: দেখতে চাইলে রেসপন্সটি প্রিন্ট করুন
        print(response.text)  # রেসপন্স ডেটা দেখতে পারেন

        if response.status_code == 200:
            data = response.json()
            print(f"Received data: {data}")  # ডেটা দেখতে পারেন

            before = data.get("LikesbeforeCommand", 0)
            after = data.get("LikesafterCommand", 0)
            added = after - before
            level = data.get("PlayerLevel", "N/A")
            region = data.get("PlayerRegion", "N/A")
            nickname = data.get("PlayerNickname", "N/A")
            
            return {
                "uid": uid,
                "level": level,
                "region": region,
                "nickname": nickname,
                "before": before,
                "after": after,
                "added": added,
                "status": "Success ✅"
            }
        else:
            return {"status": f"Error: {response.status_code}"}
    except Exception as e:
        return {"status": f"Error: {str(e)}"}

async def download_youtube_video(video_url: str, bot, chat_id):
    """
    Download YouTube video using provided API and send it to Telegram
    :param video_url: YouTube video URL
    :param bot: Telegram bot instance
    :param chat_id: Telegram chat ID
    :return: None (sends video or error message directly)
    """
    api_url = f"https://ytdl.hideme.eu.org/{video_url}"
    
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            video_file = response.content
            # টেলিগ্রামে ভিডিও পাঠানোর আগে ফাইল সাইজ চেক (50 MB লিমিট)
            if len(video_file) > 50 * 1024 * 1024:  # 50 MB in bytes
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ ভিডিওটা অনেক বড়, টেলিগ্রামে পাঠানো যাচ্ছে না। 😅 আরেকটা ভিডিও দিয়ে চেষ্টা করবে?"
                )
                return
            await bot.send_chat_action(chat_id=chat_id, action="upload_video")
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
        self.application.add_handler(CommandHandler("ytdl", self.ytdl_command))
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
হ্যালো, আমার সাথে চ্যাট করতে চাওয়ার জন্য ধন্যবাদ! আমি আই মাস্টার টুলস, তোমার বন্ধুত্বপূর্ণ সঙ্গী। মজার এবং সহায়ক কথোপকথনের জন্য আমাদের অফিসিয়াল গ্রুপে যোগ দাও। নিচের বোতামে ক্লিক করে গ্রুপে যাও এবং @I MasterTools মেনশন করো। আমি সেখানে তোমার জন্য অপেক্ষা করছি!
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
হ্যালো {username}, আই মাস্টার টুলসে স্বাগতম, তোমার বন্ধুত্বপূর্ণ সঙ্গী!

আমার সাথে চ্যাট করতে আমাদের অফিসিয়াল টেলিগ্রাম গ্রুপে যোগ দাও বা গ্রুপে @I MasterTools মেনশন করো। নিচের বোতামে ক্লিক করে গ্রুপে যাও!

উপলব্ধ কমান্ডগুলো:
- /help: সাহায্য এবং ব্যবহারের তথ্য পাও
- /clear: কথোপকথনের ইতিহাস মুছে ফেলো
- /status: বটের স্ট্যাটাস চেক করো
- /checkmail: টেম্পোরারি ইমেইল ইনবক্স চেক করো
- /info: ইউজার প্রোফাইল তথ্য দেখো
- /validatephone <নম্বর> [দেশের_কোড]: ফোন নম্বর যাচাই করো
- /validatebin <বিন_নম্বর>: বিন নম্বর যাচাই করো
- /yts <কুয়েরি> [লিমিট]: ইউটিউব ভিডিও খোঁজো
- /ytdl <ইউআরএল>: ইউটিউব ভিডিও ডাউনলোড করো
- /ipinfo <আইপি_ঠিকানা>: আইপি তথ্য পাও
- /countryinfo <দেশের_নাম>: দেশের তথ্য পাও (ইংরেজিতে নাম দাও, যেমন 'Bangladesh')
- /weather <লোকেশন>: বর্তমান আবহাওয়ার তথ্য পাও
- /removebg: ছবির ব্যাকগ্রাউন্ড মুছে ফেলো
- /gemini: জেমিনি এক্সচেঞ্জে ট্রেডিং পেয়ারের তালিকা দেখো
- /binance <সিম্বল>: বিনান্সে ২৪ ঘণ্টার টিকার ডেটা পাও
- /like <uid>: ফ্রি ফায়ার ইউআইডি-তে লাইক পাঠাও
{'' if user_id != ADMIN_USER_ID else '- /api <key>: জেমিনি এআই API কী সেট করো (শুধুমাত্র অ্যাডমিন)\n- /setadmin: নিজেকে অ্যাডমিন হিসেবে সেট করো (প্রথমবারের জন্য)\n- /setmodel: ভিন্ন মডেল বেছে নাও (শুধুমাত্র অ্যাডমিন)'}

গ্রুপে @I MasterTools মেনশন করো বা আমার মেসেজের রিপ্লাই দাও। তোমার সাথে চ্যাট করতে আমি উত্তেজিত!
            """
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            username = new_member.first_name or "User"
            user_id = new_member.id
            user_mention = f"@{new_member.username}" if new_member.username else username
            welcome_message = f"""
{user_mention}, VPSHUB_BD_CHAT গ্রুপে স্বাগতম! আমি আই মাস্টার টুলস, তোমার বন্ধুত্বপূর্ণ সঙ্গী। এখানে তুমি মজার কথোপকথন, সহায়ক উত্তর এবং আরও অনেক কিছু পাবে। @I MasterTools মেনশন করো বা আমার মেসেজের রিপ্লাই দাও। কী নিয়ে কথা বলতে চাও?
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
হ্যালো {username}! আমি আই মাস্টার টুলস, তোমার বন্ধুত্বপূর্ণ সঙ্গী, যিনি কথোপকথনকে মজাদার এবং আকর্ষণীয় করতে ভালোবাসেন।

আমি কীভাবে কাজ করি:
- গ্রুপে, @I MasterTools মেনশন করো বা আমার মেসেজের রিপ্লাই দাও
- প্রাইভেট চ্যাটে, শুধুমাত্র অ্যাডমিন সব ফিচার ব্যবহার করতে পারবেন; অন্যরা গ্রুপে রিডাইরেক্ট হবেন
- প্রশ্ন করলে, আমি প্রথমে মজার বা চমকপ্রদ কমেন্ট দিয়ে উত্তর দেব
- আমি কথোপকথনের ইতিহাস মনে রাখি যতক্ষণ না তুমি মুছে ফেলো
- আমি কোডিংয়ে (Python, JavaScript, CSS, HTML, ইত্যাদি) বিশেষজ্ঞ এবং সঠিক, নতুনদের জন্য উপযোগী সমাধান দিই
- আমি বন্ধুত্বপূর্ণ, সহায়ক এবং মানুষের মতো আচরণ করি

উপলব্ধ কমান্ডগুলো:
- /start: স্বাগত মেসেজ এবং গ্রুপ লিঙ্ক দেখাও
- /help: এই সাহায্য মেসেজ দেখাও
- /clear: কথোপকথনের ইতিহাস মুছে ফেলো
- /status: বটের স্ট্যাটাস চেক করো
- /checkmail: টেম্পোরারি ইমেইল ইনবক্স চেক করো
- /info: ইউজার প্রোফাইল তথ্য দেখো
- /validatephone <নম্বর> [দেশের_কোড]: ফোন নম্বর যাচাই করো
- /validatebin <বিন_নম্বর>: বিন নম্বর যাচাই করো
- /yts <কুয়েরি> [লিমিট]: ইউটিউব ভিডিও খোঁজো
- /ytdl <ইউআরএল>: ইউটিউব ভিডিও ডাউনলোড করো
- /ipinfo <আইপি_ঠিকানা>: আইপি তথ্য পাও
- /countryinfo <দেশের_নাম>: দেশের তথ্য পাও (ইংরেজিতে নাম দাও, যেমন 'Bangladesh')
- /weather <লোকেশন>: বর্তমান আবহাওয়ার তথ্য পাও
- /removebg: ছবির ব্যাকগ্রাউন্ড মুছে ফেলো
- /gemini: জেমিনি এক্সচেঞ্জে ট্রেডিং পেয়ারের তালিকা দেখো
- /binance <সিম্বল>: বিনান্সে ২৪ ঘণ্টার টিকার ডেটা পাও
- /like <uid>: ফ্রি ফায়ার ইউআইডি-তে লাইক পাঠাও
{'' if user_id != ADMIN_USER_ID else '- /api <key>: জেমিনি এআই API কী সেট করো (শুধুমাত্র অ্যাডমিন)\n- /setadmin: নিজেকে অ্যাডমিন হিসেবে সেট করো (প্রথমবারের জন্য)\n- /setmodel: ভিন্ন মডেল বেছে নাও (শুধুমাত্র অ্যাডমিন)'}

আমার ব্যক্তিত্ব:
- আমি একজন বন্ধুত্বপূর্ণ সঙ্গী, যিনি চ্যাট করতে এবং বন্ধু বানাতে ভালোবাসেন
- আমি কোডিংয়ে বিশেষজ্ঞ এবং সঠিক, ভালোভাবে ব্যাখ্যা করা সমাধান দিই
- আমি তোমার মুডের সাথে মানিয়ে নিই
- আমি প্রাকৃতিক, আকর্ষণীয় ভাষা ব্যবহার করি যেন মনে হয় আমি একজন বাস্তব মানুষ
- আমি রোলপ্লে এবং সৃজনশীল কথোপকথন উপভোগ করি

গুগল জেমিনি দ্বারা চালিত
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
            await update.message.reply_text("কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে। চলো নতুন করে শুরু করি!")

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
                    await update.message.reply_text(f"{email} ইনবক্সে কোনো ইমেইল পাওয়া যায়নি। পরে আরেকবার চেষ্টা করবে? 😊")
                    return
                subjects = [m['subject'] for m in mail_list]
                response_text = f"{email} ইনবক্সে পাওয়া ইমেইলগুলো:\n\n" + "\n".join(subjects)
                await update.message.reply_text(response_text)
            except Exception as e:
                logger.error(f"Error checking email: {e}")
                await update.message.reply_text("ইমেইল চেক করতে গিয়ে একটু সমস্যা হলো। 😅 আবার চেষ্টা করব? আরেকটা ইমেইল দাও!")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            api_status = "সংযুক্ত" if current_gemini_api_key and general_model else "কনফিগার করা হয়নি"
            api_key_display = f"...{current_gemini_api_key[-8:]}" if current_gemini_api_key else "সেট করা হয়নি"
            status_message = f"""
আই মাস্টার টুলসের স্ট্যাটাস রিপোর্ট এখানে:

বটের স্ট্যাটাস: অনলাইন এবং প্রস্তুত
মডেল: {current_model}
API স্ট্যাটাস: {api_status}
API কী: {api_key_display}
গ্রুপে রেসপন্স: শুধুমাত্র মেনশন বা রিপ্লাই
বর্তমান সময়: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
সক্রিয় কথোপকথন: {len(conversation_context)}
অ্যাডমিন আইডি: {ADMIN_USER_ID if ADMIN_USER_ID != 0 else 'সেট করা হয়নি'}

সব সিস্টেম প্রস্তুত! তোমাকে সাহায্য করতে আমি উত্তেজিত!
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
                await update.message.reply_text(f"অভিনন্দন {username}, তুমি এখন বটের অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
                logger.info(f"Admin set to user ID: {user_id}")
            else:
                if user_id == ADMIN_USER_ID:
                    await update.message.reply_text(f"তুমি ইতিমধ্যে অ্যাডমিন! তোমার ইউজার আইডি: {user_id}")
                else:
                    await update.message.reply_text("দুঃখিত, অ্যাডমিন ইতিমধ্যে সেট করা হয়েছে। শুধুমাত্র বর্তমান অ্যাডমিন বট পরিচালনা করতে পারবেন।")

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
                await update.message.reply_text("কোনো অ্যাডমিন সেট করা হয়নি। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("এই কমান্ডটি শুধুমাত্র বটের অ্যাডমিনের জন্য।")
                return
            if not context.args:
                await update.message.reply_text("""
দয়া করে একটি API কী দাও।

ব্যবহার: `/api your_gemini_api_key_here`

জেমিনি এআই API কী পেতে:
1. https://makersuite.google.com/app/apikey এ যাও
2. একটি নতুন API কী তৈরি করো
3. কমান্ডটি ব্যবহার করো: /api YOUR_API_KEY

নিরাপত্তার জন্য, কমান্ড মেসেজটি কী সেট করার পর মুছে ফেলা হবে।
                """, parse_mode='Markdown')
                return
            api_key = ' '.join(context.args)
            if len(api_key) < 20 or not api_key.startswith('AI'):
                await update.message.reply_text("ভুল API কী ফরম্যাট। জেমিনি এআই API কী সাধারণত 'AI' দিয়ে শুরু হয় এবং ২০ অক্ষরের বেশি হয়।")
                return
            success, message = initialize_gemini_models(api_key)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception as e:
                logger.error(f"Error deleting API command message: {e}")
            if success:
                await update.effective_chat.send_message(f"জেমিনি এআই API কী সফলভাবে আপডেট হয়েছে! কী: ...{api_key[-8:]}")
                logger.info(f"Gemini AI API key updated by admin {user_id}")
            else:
                await update.effective_chat.send_message(f"API কী সেট করতে ব্যর্থ: {message}")
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
                await update.message.reply_text("কোনো অ্যাডমিন সেট করা হয়নি। দয়া করে প্রথমে /setadmin ব্যবহার করো।")
                return
            if user_id != ADMIN_USER_ID:
                await update.message.reply_text("এই কমান্ডটি শুধুমাত্র বটের অ্যাডমিনের জন্য।")
                return
            if not context.args:
                models_list = "\n".join([f"- {model}" for model in available_models])
                await update.message.reply_text(f"উপলব্ধ মডেলগুলো:\n{models_list}\n\nব্যবহার: /setmodel <model_name>")
                return
            model_name = context.args[0]
            if model_name not in available_models:
                await update.message.reply_text(f"ভুল মডেল। এগুলো থেকে বেছে নাও: {', '.join(available_models)}")
                return
            try:
                current_model = model_name
                general_model = genai.GenerativeModel(model_name)
                await update.message.reply_text(f"মডেল সফলভাবে {model_name} এ পরিবর্তন করা হয়েছে!")
                logger.info(f"Model switched to {model_name} by admin {user_id}")
            except Exception as e:
                await update.message.reply_text(f"মডেল পরিবর্তন করতে ব্যর্থ: {str(e)}")
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

        is_private = chat_type == "private"
        full_name = user.first_name or "কোনো নাম নেই"
        if user.last_name:
            full_name += f" {user.last_name}"
        username = f"@{user.username}" if user.username else "কোনোটি নেই"
        premium = "হ্যাঁ" if user.is_premium else "না"
        permalink = f"[এখানে ক্লিক করো](tg://user?id={user_id})"
        chat_id_display = f"{chat_id}" if not is_private else "-"
        data_center = "অজানা"
        created_on = "অজানা"
        account_age = "অজানা"
        account_frozen = "না"
        last_seen = "সম্প্রতি"

        status = "প্রাইভেট চ্যাট" if is_private else "অজানা"
        if not is_private:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                status = "অ্যাডমিন" if member.status in ["administrator", "creator"] else "মেম্বার"
            except Exception as e:
                logger.error(f"Error checking group role: {e}")
                status = "অজানা"

        info_text = f"""
🔍 *ইউজারের প্রোফাইল তথ্য দেখাচ্ছি* 📋
━━━━━━━━━━━━━━━━
*পুরো নাম:* {full_name}
*ইউজারনেম:* {username}
*ইউজার আইডি:* `{user_id}`
*চ্যাট আইডি:* {chat_id_display}
*প্রিমিয়াম ইউজার:* {premium}
*ডেটা সেন্টার:* {data_center}
*তৈরি হয়েছে:* {created_on}
*অ্যাকাউন্টের বয়স:* {account_age}
*অ্যাকাউন্ট ফ্রোজেন:* {account_frozen}
*ইউজার শেষ দেখা গেছে:* {last_seen}
*পার্মানেন্ট লিঙ্ক:* {permalink}
━━━━━━━━━━━━━━━━
👁 *আমাদের টুল ব্যবহার করার জন্য ধন্যবাদ* ✅
"""

        keyboard = [[InlineKeyboardButton("প্রোফাইল দেখো", url=f"tg://user?id={user_id}")]] if user.username else []

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

    async def validatebin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatebin command to validate a BIN number"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /validatebin <বিন_নম্বর]\nউদাহরণ: /validatebin 324000")
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
            await update.message.reply_text("ব্যবহার: /yts <কুয়েরি> [লিমিট]\nউদাহরণ: /yts heat waves 3")
            return

        query = ' '.join(context.args[:-1]) if len(context.args) > 1 and context.args[-1].isdigit() else ' '.join(context.args)
        limit = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else 5
        response_message = await search_yts_multiple(query, limit)
        await update.message.reply_text(response_message)

    async def ytdl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ytdl command to download YouTube video"""
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

    async def ipinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ipinfo command to fetch IP address information"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /ipinfo <আইপি_ঠিকানা>\nউদাহরণ: /ipinfo 203.0.113.123")
            return

        ip_address = context.args[0]
        response_message = await get_ip_info(ip_address)
        await update.message.reply_text(response_message)

    async def countryinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /countryinfo command to fetch country information"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /countryinfo <দেশের_নাম>\nউদাহরণ: /countryinfo bangladesh")
            return

        country_name = ' '.join(context.args)
        if not re.match(r'^[\x00-\x7F]*$', country_name):
            await update.message.reply_text("দয়া করে দেশের নাম ইংরেজিতে দাও। যেমন, 'বাংলাদেশ' এর পরিবর্তে 'Bangladesh' ব্যবহার করো।")
            return

        response_message = await get_country_info(country_name)
        await update.message.reply_text(response_message)

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /weather command to fetch current weather information"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /weather <লোকেশন>\nউদাহরণ: /weather Dhaka")
            return

        location = ' '.join(context.args)
        response_message = await get_weather_info(location)
        await update.message.reply_text(response_message)

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
            "একটি ছবি আপলোড করো, আমি এর ব্যাকগ্রাউন্ড মুছে দেব! ফলাফল পাঠিয়ে দেব। 😊"
        )

    async def gemini_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /gemini command to list available trading pairs"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response_message = await get_gemini_trading_pairs()
        await update.message.reply_text(response_message)

    async def binance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /binance command to fetch 24hr ticker data"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("ব্যবহার: /binance <সিম্বল>\nউদাহরণ: /binance BTCUSDT")
            return

        symbol = context.args[0].upper()
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response_message = await get_binance_ticker(symbol)
        await update.message.reply_text(response_message)

    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command to send likes to a Free Fire UID with rate limiting"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        # Check if the command is coming from the correct group
        if chat_type in ['group', 'supergroup'] and update.message.chat.link != 'https://t.me/VPSHUB_BD_CHAT':
            await update.message.reply_text("এই কমান্ডটি শুধুমাত্র @VPSHUB_BD_CHAT গ্রুপে ব্যবহার করা যাবে।")
            return

        if len(context.args) != 1:
            await update.message.reply_text("ব্যবহার: /like <UID>")
            return

        # Rate limiting for non-admin users
        if user_id != ADMIN_USER_ID:
            last_like_time = user_likes.get(user_id)
            current_time = datetime.now()
            if last_like_time and (current_time - last_like_time).total_seconds() < 24 * 60 * 60:
                time_left = 24 * 60 * 60 - (current_time - last_like_time).total_seconds()
                hours_left = int(time_left // 3600)
                minutes_left = int((time_left % 3600) // 60)
                await update.message.reply_text(
                    f"তুমি প্রতি ২৪ ঘণ্টায় একবার /like কমান্ড ব্যবহার করতে পারো। "
                    f"পরবর্তী চেষ্টার জন্য অপেক্ষা করো {hours_left} ঘণ্টা {minutes_left} মিনিট।"
                )
                return

        uid = context.args[0]
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        result = await send_like(uid)
        
        if "added" in result:
            message = (
                "✦───────────────✦\n"
                f"│ 🎉 লাইক পাঠানো সফল! │\n"
                f"│ 🆔 UID: {result['uid']}\n"
                f"│ 🎮 Level: {result['level']}\n"
                f"│ 🌍 Region: {result['region']}\n"
                f"│ 👤 Nickname: {result['nickname']}\n"
                f"│ 📊 Before: {result['before']}\n"
                f"│ 📈 After: {result['after']}\n"
                f"│ ➕ Added: {result['added']}\n"
                "✦──── By Faruk ────✦"
            )
            # Update the user's last like time (only for non-admins)
            if user_id != ADMIN_USER_ID:
                user_likes[user_id] = datetime.now()
        else:
            message = f"লাইক পাঠানোতে ব্যর্থ।\nস্ট্যাটাস: {result.get('status', 'অজানা ত্রুটি')}"
        
        await update.message.reply_text(message)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """