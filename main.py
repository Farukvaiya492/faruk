
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
import time

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
API_URL = "https://free-like-api-aditya-ffm.vercel.app/like"

# User Likes Tracking Database or Dictionary
user_likes = {}

# ===========================
# Function to Send Likes
# ===========================
def send_like(uid: str, server_name: str = "BD"):
    api_url = f"{API_URL}?uid={uid}&server_name={server_name}&key=@adityaapis"
    
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
        return {"status": f"Error: {e}"}

# ===========================
# একাউন্ট স্ট্যাটাস দেখানোর ফাংশন
# ===========================
def get_account_status(uid: str, server_name: str = "BD"):
    api_url = f"{API_URL}?uid={uid}&server_name={server_name}&key=@adityaapis"
    
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
        return {"status": f"Error: {e}"}

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

async def get_ip_info2(ip_address: str):
    """
    Fetch IP information using ip2location.io
    :param ip_address: IP address to look up
    :return: Formatted response string
    """
    url = f"https://api.ip2location.io/?ip={ip_address}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            output_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            output_message += f"┃ 🌐 IP Location Information for '{ip_address}' ┃\n"
            output_message += "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            output_message += f"┃ 📍 IP: {data.get('ip', 'N/A')}\n"
            output_message += f"┃ 🇺🇳 Country: {data.get('country_name', 'N/A')}\n"
            output_message += f"┃ 🌍 Region: {data.get('region_name', 'N/A')}\n"
            output_message += f"┃ 🏙️ City: {data.get('city', 'N/A')}\n"
            output_message += f"┃ 📌 Latitude: {data.get('latitude', 'N/A')}\n"
            output_message += f"┃ 📌 Longitude: {data.get('longitude', 'N/A')}\n"
            output_message += f"┃ 🏢 ISP: {data.get('isp', 'N/A')}\n"
            output_message += "┃\n"
            output_message += "┗━━━ 𝗖𝗿𝗲𝗮𝘁𝗲 𝗕𝘆 𝗙𝗮𝗿𝘂𝗸 ━━━┛"
            return output_message
        else:
            return "Failed to fetch data"
    except Exception as e:
        logger.error(f"Error fetching IP info from ip2location.io: {e}")
        return f"Error fetching data: {str(e)}"

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
        self.application.add_handler(CommandHandler("ipinfo2", self.ipinfo2_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(CommandHandler("ban", self.ban_user))
        self.application.add_handler(CommandHandler("unban", self.unban_user))
        self.application.add_handler(CommandHandler("countryinfo", self.countryinfo_command))
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
- /clear: Clear conversation history
- /status <UID>: Check Free Fire account status (admin only)
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number]: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /ipinfo2 <ip_address>: Fetch IP address information (IP2Location)
- /like <UID>: Send likes to a Free Fire UID
- /ban <USER_ID>: Ban a user (admin only)
- /unban <USER_ID>: Unban a user (admin only)
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
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
- /clear: Clear your conversation history
- /status <UID>: Check Free Fire account status (admin only)
- /checkmail: Check temporary email inbox
- /info: Show user profile information
- /validatephone <number> [country_code]: Validate a phone number
- /validatebin <bin_number]: Validate a BIN number
- /yts <query> [limit]: Search YouTube videos
- /ipinfo <ip_address>: Fetch IP address information
- /ipinfo2 <ip_address>: Fetch IP address information (IP2Location)
- /like <UID>: Send likes to a Free Fire UID
- /ban <USER_ID>: Ban a user (admin only)
- /unban <USER_ID>: Unban a user (admin only)
- /countryinfo <country_name>: Fetch country information (use English names, e.g., 'Bangladesh')
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
            return

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
        """Handle /status command to check Free Fire account status"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if str(user_id) == str(ADMIN_USER_ID):
            if len(context.args) != 1:
                await update.message.reply_text("Usage: /status <UID>")
                return
            uid = context.args[0]
            result = get_account_status(uid)
            
            if "added" in result:
                message = (
                    f"✅ Account Status:\n\n"
                    f"UID: {result['uid']}\n"
                    f"Player Level: {result['level']}\n"
                    f"Player Region: {result['region']}\n"
                    f"Player Nickname: {result['nickname']}\n"
                    f"Likes Before: {result['before']}\n"
                    f"Likes After: {result['after']}\n"
                    f"Likes Added: {result['added']}"
                )
            else:
                message = f"Failed to retrieve account status.\nStatus: {result.get('status', 'Unknown Error')}"
            
            await context.bot.send_message(chat_id="@VPSHUB_BD_CHAT", text=message)
        else:
            await update.message.reply_text("You are not authorized to use this command.")

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

    async def validatephone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validatephone command to validate a phone number"""
        user_id = update.effective_user.id
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
            await update.message.reply_text("Usage: /validatebin <bin_number]\nExample: /validatebin 324000")
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
            await update.message.reply_text("Usage: /yts <query> [limit]\nExample: /yts heat waves 3")
            return

        query = ' '.join(context.args[:-1]) if len(context.args) > 1 and context.args[-1].isdigit() else ' '.join(context.args)
        limit = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else 5
        response_message = await search_yts_multiple(query, limit)
        await update.message.reply_text(response_message)

    async def ipinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ipinfo command to fetch IP address information"""
        user_id = update.effective_user.id
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
        await update.message.reply_text(response_message)

    async def ipinfo2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ipinfo2 command to fetch IP address information using ip2location.io"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /ipinfo2 <ip_address>\nExample: /ipinfo2 8.8.8.8")
            return

        ip_address = context.args[0]
        response_message = await get_ip_info2(ip_address)
        await update.message.reply_text(response_message)

    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command to send likes to a Free Fire UID"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        current_time = time.time()
        
        # If user has previous like data
        if user_id in user_likes:
            last_time, likes_count = user_likes[user_id]
            time_diff = current_time - last_time
            
            # If the user tries to send more than 2 likes within 24 hours
            if likes_count >= 2 and time_diff < 86400:  # 86400 seconds = 24 hours
                await update.message.reply_text("You have already sent two likes in the last 24 hours. Please try again after 24 hours.")
                return

        if len(context.args) != 1:
            await update.message.reply_text("Usage: /like <UID>")
            return
        
        uid = context.args[0]
        result = send_like(uid)
        
        if "added" in result:
            message = (
                f"✅ Like Sent!\n\n"
                f"UID: {result['uid']}\n"
                f"Player Level: {result['level']}\n"
                f"Player Region: {result['region']}\n"
                f"Player Nickname: {result['nickname']}\n"
                f"Likes Before: {result['before']}\n"
                f"Likes After: {result['after']}\n"
                f"Likes Added: {result['added']}"
            )
            # Update user data
            user_likes[user_id] = (current_time, user_likes.get(user_id, (0, 0))[1] + 1)
        else:
            message = f"Failed to send like.\nStatus: {result.get('status', 'Unknown Error')}"
        
        await update.message.reply_text(message)

    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ban command to ban a user"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("Sorry, you do not have permission to use this command.")
            return

        if len(context.args) != 1:
            await update.message.reply_text("Usage: /ban <USER_ID>")
            return

        try:
            banned_user_id = int(context.args[0])
            await update.message.reply_text(f"User {banned_user_id} has been banned.")
            # You can add logic to store or act upon banning the user
        except ValueError:
            await update.message.reply_text("Invalid USER_ID. Please provide a numeric user ID.")

    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unban command to unban a user"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("Sorry, you do not have permission to use this command.")
            return

        if len(context.args) != 1:
            await update.message.reply_text("Usage: /unban <USER_ID>")
            return

        try:
            unbanned_user_id = int(context.args[0])
            await update.message.reply_text(f"User {unbanned_user_id} has been unbanned.")
            # You can add logic to restore access for the unbanned user
        except ValueError:
            await update.message.reply_text("Invalid USER_ID. Please provide a numeric user ID.")

    async def countryinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /countryinfo command to fetch country information"""
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type

        if chat_type == 'private' and user_id != ADMIN_USER_ID:
            response, reply_markup = await self.get_private_chat_redirect()
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        if not context.args:
            await update.message.reply_text("Usage: /countryinfo <country_name>\nExample: /countryinfo bangladesh")
            return

        country_name = ' '.join(context.args)
        # Check for non-ASCII characters
        if not re.match(r'^[\x00-\x7F]*$', country_name):
            await update.message.reply_text("Please enter the country name in English. For example, use 'Bangladesh' instead of 'বাংলাদেশ'.")
            return

        response_message = await get_country_info(country_name)
        await update.message.reply_text(response_message)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        chat_type = update.effective_chat.type
        if chat_type not in ['group', 'supergroup']:
            return

        message = update.message.text.lower()
        
        # Responding to specific messages
        if 'hello' in message:
            await update.message.reply_text("Hello, welcome to the group! 😊")
        elif 'help' in message:
            await update.message.reply_text("Here are some commands:\n- /like <UID> : Send a like to a player.\n- /ban <USER_ID> : Ban a user.\n- /unban <USER_ID> : Unban a user.")
        else:
            await update.message.reply_text("I am here to help! Type 'help' to see the available commands.")

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