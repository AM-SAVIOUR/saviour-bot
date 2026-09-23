import os
import telebot
from telebot import types
from telebot.types import BotCommand, BotCommandScopeChat
import edge_tts
import asyncio
import requests
import io
import json
import time
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
import cloudinary
import cloudinary.uploader
from deep_translator import GoogleTranslator
from pypdf import PdfReader, PdfWriter
from PIL import Image

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")
CREATOR = "IAMSAVIOUR1"
ADMIN_ID = 8872791323

CLOUDINARY_CLOUD = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

PRIVACY_URL = "https://telegra.ph/SAVIOUR-privacy-policy-09-23"

PRICE = "₦1,500/month"
PAY_NAME = "CHINAZAEKPERE SAVIOUR MBAEBIE"
PAY_ACCOUNT = "9038530721"
PAY_BANK = "Opay"

FREE_VOICE_LIMIT = 3
FREE_LYRICS_LIMIT = 3
FREE_TRANSLATE_LIMIT = 3
FREE_PDF_LIMIT = 3
FREE_IMAGE_LIMIT = 3

print("=" * 50, flush=True)
print("STARTUP", flush=True)
print("BOT_TOKEN:", "YES" if BOT_TOKEN else "MISSING", flush=True)
print("DATABASE_URL:", "YES" if DATABASE_URL else "MISSING", flush=True)
print("CLOUDINARY:", "YES" if CLOUDINARY_CLOUD else "MISSING", flush=True)
print("=" * 50, flush=True)

if not BOT_TOKEN or not DATABASE_URL:
    raise SystemExit("Missing env vars")

if CLOUDINARY_CLOUD and CLOUDINARY_KEY and CLOUDINARY_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD,
        api_key=CLOUDINARY_KEY,
        api_secret=CLOUDINARY_SECRET,
        secure=True
    )

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------- COMMAND MENU ----------
PUBLIC_COMMANDS = [
    BotCommand("start", "Open main menu"),
    BotCommand("say", "Voice from text"),
    BotCommand("lrc", "Lyrics file"),
    BotCommand("setaway", "Away message for Business"),
    BotCommand("privacy", "Privacy policy"),
    BotCommand("help", "How to use"),
]

ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand("admin", "Admin panel"),
    BotCommand("addpaid", "Unlock a user"),
    BotCommand("removepaid", "Remove premium"),
    BotCommand("ban", "Ban a user"),
    BotCommand("unban", "Unban a user"),
    BotCommand("users", "Recent users"),
    BotCommand("stats", "Bot statistics"),
    BotCommand("maintenance", "Toggle maintenance mode"),
]

try:
    bot.set_my_commands(PUBLIC_COMMANDS)
    bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    print("Commands menu set", flush=True)
except Exception as e:
    print("Command set error:", e, flush=True)

# ---------- DATABASE ----------
def db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                paid INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                voice_key TEXT DEFAULT 'ng_male',
                away_message TEXT,
                voice_count INTEGER DEFAULT 0,
                lyrics_count INTEGER DEFAULT 0,
                translate_count INTEGER DEFAULT 0,
                pdf_count INTEGER DEFAULT 0,
                image_count INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'voice',
                last_reset DATE,
                joined DATE DEFAULT CURRENT_DATE,
                last_seen DATE DEFAULT CURRENT_DATE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                file_type TEXT,
                file_name TEXT,
                cloud_url TEXT,
                created DATE DEFAULT CURRENT_DATE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS away_keywords (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                keyword TEXT,
                reply TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_keywords (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                owner_id BIGINT,
                keyword TEXT,
                reply TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                channel_id TEXT,
                channel_name TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled (
                id SERIAL PRIMARY KEY,
                channel_id TEXT,
                post_time TEXT,
                message TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        for col in ["translate_count INTEGER DEFAULT 0",
                    "pdf_count INTEGER DEFAULT 0",
                    "image_count INTEGER DEFAULT 0",
                    "mode TEXT DEFAULT 'voice'"]:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col}")
            except:
                pass
        conn.commit()
        cur.close()
        conn.close()
        print("DB init OK", flush=True)
    except Exception as e:
        print("DB INIT ERROR:", e, flush=True)

init_db()

def get_user(uid):
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO users (user_id, last_reset) VALUES (%s, %s)",
                        (uid, today))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
        elif row["last_reset"] != today:
            cur.execute("""UPDATE users SET voice_count=0, lyrics_count=0,
                           translate_count=0, pdf_count=0, image_count=0,
                           last_reset=%s, last_seen=%s WHERE user_id=%s""",
                        (today, today, uid))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print("get_user error:", e, flush=True)
        return None

def save_user_meta(uid, username, first_name):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE users SET username=%s, first_name=%s, last_seen=%s
                       WHERE user_id=%s""",
                    (username, first_name, datetime.date.today(), uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("save_user_meta error:", e, flush=True)

def is_paid(uid):
    u = get_user(uid)
    return bool(u and u["paid"] == 1)

def is_banned(uid):
    u = get_user(uid)
    return bool(u and u["banned"] == 1)

def can_use(uid, kind):
    if uid == ADMIN_ID:
        return True
    if is_paid(uid):
        return True
    u = get_user(uid)
    if not u:
        return False
    limits = {
        "voice": (u["voice_count"], FREE_VOICE_LIMIT),
        "lyrics": (u["lyrics_count"], FREE_LYRICS_LIMIT),
        "translate": (u["translate_count"], FREE_TRANSLATE_LIMIT),
        "pdf": (u["pdf_count"], FREE_PDF_LIMIT),
        "image": (u["image_count"], FREE_IMAGE_LIMIT),
    }
    if kind in limits:
        used, maxv = limits[kind]
        return used < maxv
    return True

def bump(uid, kind):
    cols = {"voice": "voice_count", "lyrics": "lyrics_count",
            "translate": "translate_count", "pdf": "pdf_count",
            "image": "image_count"}
    col = cols.get(kind)
    if not col:
        return
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET {col}={col}+1 WHERE user_id=%s", (uid,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("bump error:", e, flush=True)

def set_paid(uid, value):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET paid=%s WHERE user_id=%s", (value, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_paid error:", e, flush=True)

def set_banned(uid, value):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET banned=%s WHERE user_id=%s", (value, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_banned error:", e, flush=True)

def set_voice_key(uid, key):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET voice_key=%s WHERE user_id=%s", (key, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_voice_key error:", e, flush=True)

def get_voice_key(uid):
    u = get_user(uid)
    return u["voice_key"] if u and u["voice_key"] else "ng_male"

def set_mode(uid, mode):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET mode=%s WHERE user_id=%s", (mode, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_mode error:", e, flush=True)

def get_mode(uid):
    u = get_user(uid)
    return u["mode"] if u and u["mode"] else "voice"

def set_away_msg(uid, text):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET away_message=%s WHERE user_id=%s", (text, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_away error:", e, flush=True)

def get_away_msg(uid):
    u = get_user(uid)
    return u["away_message"] if u else None

def save_file_record(uid, file_type, file_name, cloud_url):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO files (user_id, file_type, file_name, cloud_url)
                       VALUES (%s, %s, %s, %s)""",
                    (uid, file_type, file_name, cloud_url))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("save_file_record error:", e, flush=True)

def get_user_files(uid, file_type):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT file_name, cloud_url, created FROM files
                       WHERE user_id=%s AND file_type=%s
                       ORDER BY id DESC LIMIT 10""", (uid, file_type))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("get_user_files error:", e, flush=True)
        return []

def get_file_counts(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT file_type, COUNT(*) as c FROM files
                       WHERE user_id=%s GROUP BY file_type""", (uid,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {r["file_type"]: r["c"] for r in rows}
    except:
        return {}

# ---------- MAINTENANCE ----------
def get_maintenance():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key='maintenance'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return bool(row and row["value"] == "true")
    except:
        return False

def set_maintenance(value):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO settings (key, value) VALUES ('maintenance', %s)
                       ON CONFLICT (key) DO UPDATE SET value=%s""",
                    (str(value).lower(), str(value).lower()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_maintenance error:", e, flush=True)

# ---------- AWAY KEYWORDS ----------
def add_away_keyword(uid, keyword, reply):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM away_keywords WHERE user_id=%s AND keyword=%s",
                    (uid, keyword.lower()))
        cur.execute("""INSERT INTO away_keywords (user_id, keyword, reply)
                       VALUES (%s, %s, %s)""", (uid, keyword.lower(), reply))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("add_away_keyword error:", e, flush=True)

def get_away_keywords(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT keyword, reply FROM away_keywords WHERE user_id=%s", (uid,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except:
        return []

def find_away_reply(uid, text):
    text_low = text.lower()
    for row in get_away_keywords(uid):
        if row["keyword"] in text_low:
            return row["reply"]
    return None

# ---------- GROUP KEYWORDS ----------
def add_group_keyword(chat_id, owner_id, keyword, reply):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""DELETE FROM group_keywords WHERE chat_id=%s AND keyword=%s""",
                    (chat_id, keyword.lower()))
        cur.execute("""INSERT INTO group_keywords (chat_id, owner_id, keyword, reply)
                       VALUES (%s, %s, %s, %s)""",
                    (chat_id, owner_id, keyword.lower(), reply))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("add_group_keyword error:", e, flush=True)

def get_group_keywords(chat_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT keyword, reply FROM group_keywords WHERE chat_id=%s",
                    (chat_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except:
        return []

def find_group_reply(chat_id, text):
    text_low = text.lower()
    for row in get_group_keywords(chat_id):
        if row["keyword"] in text_low:
            return row["reply"]
    return None

# ---------- CHANNELS ----------
def add_channel(uid, channel_id, channel_name):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO channels (user_id, channel_id, channel_name)
                       VALUES (%s, %s, %s)""",
                    (uid, channel_id, channel_name))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("add_channel error:", e, flush=True)

def get_channels(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT channel_id, channel_name FROM channels WHERE user_id=%s",
                    (uid,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except:
        return []

def add_scheduled(channel_id, post_time, message):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO scheduled (channel_id, post_time, message)
                       VALUES (%s, %s, %s)""",
                    (channel_id, post_time, message))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("add_scheduled error:", e, flush=True)

# ---------- CLOUDINARY ----------
def upload_to_cloud(file_path_or_bytes, resource_type="auto", folder="saviour"):
    if not CLOUDINARY_CLOUD:
        return None
    try:
        result = cloudinary.uploader.upload(
            file_path_or_bytes,
            resource_type=resource_type,
            folder=folder
        )
        return result.get("secure_url")
    except Exception as e:
        print("Cloudinary error:", e, flush=True)
        return None

# ---------- VOICES ----------
COUNTRIES = {
    "ng": {"flag": "🇳🇬", "name": "Nigeria"},
    "us": {"flag": "🇺🇸", "name": "USA"},
    "uk": {"flag": "🇬🇧", "name": "UK"},
    "au": {"flag": "🇦🇺", "name": "Australia"},
    "in": {"flag": "🇮🇳", "name": "India"},
    "sa": {"flag": "🇸🇦", "name": "Arabic"},
    "fr": {"flag": "🇫🇷", "name": "French"},
    "es": {"flag": "🇪🇸", "name": "Spanish"},
    "za": {"flag": "🇿🇦", "name": "S. Africa"},
    "ph": {"flag": "🇵🇭", "name": "Philippines"},
}

VOICES = {
    "ng_male":   {"country": "ng", "label": "Abeo (M)",  "voice": "en-NG-AbeoNeural"},
    "ng_female": {"country": "ng", "label": "Ezinne (F)", "voice": "en-NG-EzinneNeural"},
    "us_aria":   {"country": "us", "label": "Aria (F)",   "voice": "en-US-AriaNeural"},
    "us_guy":    {"country": "us", "label": "Guy (M)",    "voice": "en-US-GuyNeural"},
    "us_jenny":  {"country": "us", "label": "Jenny (F)",  "voice": "en-US-JennyNeural"},
    "us_michelle":{"country": "us","label": "Michelle (F)","voice": "en-US-MichelleNeural"},
    "us_eric":   {"country": "us", "label": "Eric (M)",   "voice": "en-US-EricNeural"},
    "us_ana":    {"country": "us", "label": "Ana (F)",    "voice": "en-US-AnaNeural"},
    "uk_sonia":  {"country": "uk", "label": "Sonia (F)",  "voice": "en-GB-SoniaNeural"},
    "uk_ryan":   {"country": "uk", "label": "Ryan (M)",   "voice": "en-GB-RyanNeural"},
    "uk_libby":  {"country": "uk", "label": "Libby (F)",  "voice": "en-GB-LibbyNeural"},
    "uk_thomas": {"country": "uk", "label": "Thomas (M)", "voice": "en-GB-ThomasNeural"},
    "au_william":{"country": "au", "label": "William (M)","voice": "en-AU-WilliamNeural"},
    "au_natasha":{"country": "au", "label": "Natasha (F)","voice": "en-AU-NatashaNeural"},
    "in_neerja": {"country": "in", "label": "Neerja (F)", "voice": "en-IN-NeerjaNeural"},
    "in_prabhat":{"country": "in", "label": "Prabhat (M)","voice": "en-IN-PrabhatNeural"},
    "in_swara":  {"country": "in", "label": "Swara (F)",  "voice": "en-IN-SwaraNeural"},
    "in_madhur": {"country": "in", "label": "Madhur (M)", "voice": "en-IN-MadhurNeural"},
    "sa_salma":  {"country": "sa", "label": "Salma (F)",  "voice": "ar-SA-SalmaNeural"},
    "sa_zariyah":{"country": "sa", "label": "Zariyah (F)","voice": "ar-SA-ZariyahNeural"},
    "sa_hamed":  {"country": "sa", "label": "Hamed (M)",  "voice": "ar-SA-HamedNeural"},
    "fr_denise": {"country": "fr", "label": "Denise (F)", "voice": "fr-FR-DeniseNeural"},
    "fr_henri":  {"country": "fr", "label": "Henri (M)",  "voice": "fr-FR-HenriNeural"},
    "fr_eloise": {"country": "fr", "label": "Eloise (F)", "voice": "fr-FR-EloiseNeural"},
    "es_elvira": {"country": "es", "label": "Elvira (F)", "voice": "es-ES-ElviraNeural"},
    "es_alvaro": {"country": "es", "label": "Alvaro (M)", "voice": "es-ES-AlvaroNeural"},
    "es_lucia":  {"country": "es", "label": "Lucia (F)",  "voice": "es-ES-LuciaNeural"},
    "za_leah":   {"country": "za", "label": "Leah (F)",   "voice": "en-ZA-LeahNeural"},
    "za_luke":   {"country": "za", "label": "Luke (M)",   "voice": "en-ZA-LukeNeural"},
    "ph_rosa":   {"country": "ph", "label": "Rosa (F)",   "voice": "fil-PH-RosaNeural"},
    "ph_angelo": {"country": "ph", "label": "Angelo (M)", "voice": "fil-PH-AngeloNeural"},
    "ph_blessica":{"country":"ph", "label": "Blessica (F)","voice":"fil-PH-BlessicaNeural"},
}

def get_voice(uid):
    key = get_voice_key(uid)
    if key not in VOICES:
        key = "ng_male"
    return VOICES[key]["voice"]

# ---------- TRANSLATOR LANGUAGES ----------
TRANS_LANGS = {
    "en": "🇬🇧 English", "fr": "🇫🇷 French", "es": "🇪🇸 Spanish",
    "de": "🇩🇪 German", "it": "🇮🇹 Italian", "pt": "🇵🇹 Portuguese",
    "ru": "🇷🇺 Russian", "ar": "🇸🇦 Arabic", "zh-CN": "🇨🇳 Chinese",
    "ja": "🇯🇵 Japanese", "ko": "🇰🇷 Korean", "hi": "🇮🇳 Hindi",
    "yo": "🇳🇬 Yoruba", "ig": "🇳🇬 Igbo", "ha": "🇳🇬 Hausa",
    "sw": "🇰🇪 Swahili", "tr": "🇹🇷 Turkish", "nl": "🇳🇱 Dutch",
    "pl": "🇵🇱 Polish", "sv": "🇸🇪 Swedish", "id": "🇮🇩 Indonesian",
    "vi": "🇻🇳 Vietnamese", "th": "🇹🇭 Thai", "fa": "🇮🇷 Persian",
}

# ---------- AUTO SET WEBHOOK ----------
def set_webhook():
    try:
        allowed = json.dumps([
            "message", "callback_query",
            "business_connection", "business_message",
            "edited_business_message", "deleted_business_messages"
        ])
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            data={"url": f"{RENDER_URL}/{BOT_TOKEN}", "allowed_updates": allowed},
            timeout=10
        )
        print("Webhook:", r.json(), flush=True)
    except Exception as e:
        print("Webhook error:", e, flush=True)

set_webhook()

# ---------- PREMIUM TEXT ----------
def premium_text(uid):
    if uid == ADMIN_ID:
        return ("👑 *ADMIN ACCOUNT*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "You are the creator of SAVIOUR.\n\n"
                "✅ Unlimited access to everything\n"
                "✅ Full admin panel\n\n"
                "Thank you for building SAVIOUR! 🚀")
    if is_paid(uid):
        return ("💎 *PREMIUM ACTIVE*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ Unlimited voice notes\n"
                "✅ Unlimited lyrics\n"
                "✅ Unlimited translation\n"
                "✅ Unlimited PDF tools\n"
                "✅ Unlimited image tools\n\n"
                "Thank you for supporting SAVIOUR!")
    return (f"💎 *UPGRADE TO PREMIUM*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Price: *{PRICE}*\n\n"
            "🎁 *You get:*\n"
            "✅ Unlimited voice notes\n"
            "✅ Unlimited lyrics\n"
            "✅ Unlimited translation\n"
            "✅ Unlimited PDF tools\n"
            "✅ Unlimited image tools\n\n"
            "📋 *How to pay:*\n"
            f"1. Transfer {PRICE} to:\n"
            f"   🏦 {PAY_BANK}\n"
            f"   🔢 {PAY_ACCOUNT}\n"
            f"   👤 {PAY_NAME}\n\n"
            f"2. Send receipt to @{CREATOR}\n"
            "3. Wait for approval\n\n"
            "⚠️ Free: 3 uses/day per tool")

# ---------- MAIN MENU ----------
def main_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎙 Voice", callback_data="voice"),
        types.InlineKeyboardButton("📝 Lyrics", callback_data="lyrics"),
        types.InlineKeyboardButton("🔧 Tools", callback_data="tools"),
        types.InlineKeyboardButton("📚 My Files", callback_data="myfiles"),
        types.InlineKeyboardButton("💎 Premium", callback_data="upgrade"),
        types.InlineKeyboardButton("❓ Help", callback_data="help"),
    )
    text = ("🌑 *Welcome to SAVIOUR*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your all-in-one assistant.\n\n"
            "Tap a tool, then just type your message.\n\n"
            f"👑 Creator: @{CREATOR}")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def tools_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🌍 Translate", callback_data="translate"),
        types.InlineKeyboardButton("📄 PDF Suite", callback_data="pdf"),
        types.InlineKeyboardButton("🖼 Image Tools", callback_data="image"),
        types.InlineKeyboardButton("💬 Auto-Reply", callback_data="reply"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="menu"),
    )
    text = ("🔧 *Tools*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "More powerful tools for daily use.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m):
    if is_banned(m.from_user.id):
        bot.send_message(m.chat.id, "🚫 You are banned.")
        return
    save_user_meta(m.from_user.id, m.from_user.username, m.from_user.first_name)
    main_menu(m.chat.id)

# ---------- HELP ----------
def help_text():
    return ("❓ *SAVIOUR — Help Guide*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎙 *Voice* — Tap Voice → country → voice → type text\n"
            "📝 *Lyrics* — Tap Lyrics → type: song - artist\n"
            "🌍 *Translate* — Tools → Translate → pick language\n"
            "📄 *PDF* — Tools → PDF → merge/split/compress\n"
            "🖼 *Image* — Tools → Image → compress/resize/convert\n"
            "📚 *My Files* — See all your past files\n"
            "💬 *Auto-Reply* — /setaway keyword | reply\n\n"
            "💎 *Premium* — " + PRICE + "\n\n"
            "*Commands:*\n"
            "/say — voice from text\n"
            "/lrc — lyrics file\n"
            "/privacy — privacy policy\n"
            "/setaway — away message\n\n"
            f"👑 Created by: @{CREATOR}")

@bot.message_handler(commands=['help'])
def help_cmd(m):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
    bot.send_message(m.chat.id, help_text(), reply_markup=markup, parse_mode="Markdown")

# ---------- PRIVACY ----------
@bot.message_handler(commands=['privacy'])
def privacy_cmd(m):
    bot.reply_to(m,
        "📜 *SAVIOUR Privacy Policy*\n\n"
        f"Read it here:\n{PRIVACY_URL}",
        parse_mode="Markdown")

# ---------- VOICE PAGES ----------
def voice_countries_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    for ckey, cinfo in COUNTRIES.items():
        count = sum(1 for v in VOICES.values() if v["country"] == ckey)
        if count > 0:
            btns.append(types.InlineKeyboardButton(
                f"{cinfo['flag']} {cinfo['name']}",
                callback_data=f"vc_{ckey}"))
    for i in range(0, len(btns), 3):
        markup.row(*btns[i:i+3])
    markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))

    current = get_voice_key(uid)
    if current not in VOICES:
        current = "ng_male"
    cur_name = VOICES[current]["label"]
    cur_country = COUNTRIES[VOICES[current]["country"]]

    text = ("🎙 *Voice Tool*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose a country.\n\n"
            f"Current: {cur_country['flag']} *{cur_name}*")

    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def voice_list_page(chat_id, uid, country_key, message_id=None):
    current = get_voice_key(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for key, info in VOICES.items():
        if info["country"] == country_key:
            label = f"✅ {info['label']}" if key == current else info['label']
            btns.append(types.InlineKeyboardButton(label, callback_data=f"setvoice_{key}"))
    for i in range(0, len(btns), 2):
        markup.row(*btns[i:i+2])
    markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="voice"))

    c = COUNTRIES[country_key]
    text = (f"🎙 *{c['flag']} {c['name']} Voices*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\nTap one.")

    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- TRANSLATOR PAGE ----------
def translate_lang_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for code, name in TRANS_LANGS.items():
        btns.append(types.InlineKeyboardButton(name, callback_data=f"tr_{code}"))
    for i in range(0, len(btns), 2):
        markup.row(*btns[i:i+2])
    markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))

    text = ("🌍 *Translator*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pick target language.\nThen type text.\n\n"
            "I auto-detect source language.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- PDF PAGE ----------
def pdf_page(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 Merge PDFs", callback_data="pdf_merge"),
        types.InlineKeyboardButton("✂️ Split PDF", callback_data="pdf_split"),
        types.InlineKeyboardButton("🗜 Compress PDF", callback_data="pdf_compress"),
        types.InlineKeyboardButton("🔄 Rotate PDF", callback_data="pdf_rotate"),
        types.InlineKeyboardButton("📸 PDF → Images", callback_data="pdf_pdf2img"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("📄 *PDF Suite*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Max file size: 20 MB\n\n"
            "Tap an action, then send your file.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- IMAGE PAGE ----------
def image_page(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🗜 Compress", callback_data="img_compress"),
        types.InlineKeyboardButton("📐 Resize", callback_data="img_resize"),
        types.InlineKeyboardButton("🔄 Convert", callback_data="img_convert"),
        types.InlineKeyboardButton("↩️ Rotate/Flip", callback_data="img_rotate"),
        types.InlineKeyboardButton("📄 Image → PDF", callback_data="img_pdf"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("🖼 *Image Tools*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Max file size: 20 MB\n\n"
            "Tap an action, then send your image.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- MY FILES PAGE ----------
def my_files_page(chat_id, uid, message_id=None):
    counts = get_file_counts(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"🎙 Voice ({counts.get('voice', 0)})",
            callback_data="mf_voice"),
        types.InlineKeyboardButton(f"📝 Lyrics ({counts.get('lyrics', 0)})",
            callback_data="mf_lyrics"),
        types.InlineKeyboardButton(f"📄 PDF ({counts.get('pdf', 0)})",
            callback_data="mf_pdf"),
        types.InlineKeyboardButton(f"🖼 Image ({counts.get('image', 0)})",
            callback_data="mf_image"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="menu"),
    )
    text = ("📚 *My Files*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "All files you've generated.\n"
            "They stay here even if you change phones.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def my_files_list(chat_id, uid, file_type, message_id=None):
    files = get_user_files(uid, file_type)
    if not files:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="myfiles"))
        text = f"📁 *No {file_type} files yet.*"
        if message_id:
            bot.edit_message_text(text, chat_id, message_id,
                reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, f in enumerate(files):
        label = f"{f['file_name'][:40]} ({f['created']})"
        markup.add(types.InlineKeyboardButton(label, url=f["cloud_url"]))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="myfiles"))

    text = (f"📁 *Your {file_type} files*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Tap any file to open/download it.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- BUTTON HANDLER ----------
@bot.callback_query_handler(func=lambda c: True)
def handle(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    chat_id = c.message.chat.id
    msg_id = c.message.message_id

    if is_banned(uid):
        return

    if get_maintenance() and uid != ADMIN_ID:
        bot.send_message(chat_id,
            "🛠 *SAVIOUR is under maintenance*\n\n"
            "We're making improvements.\n"
            "Please try again in a few minutes.",
            parse_mode="Markdown")
        return

    if c.data == "menu":
        main_menu(chat_id, msg_id)
    elif c.data == "tools":
        tools_menu(chat_id, msg_id)
    elif c.data == "voice":
        set_mode(uid, "voice")
        voice_countries_page(chat_id, uid, msg_id)
    elif c.data.startswith("vc_"):
        ck = c.data.replace("vc_", "")
        if ck in COUNTRIES:
            voice_list_page(chat_id, uid, ck, msg_id)
    elif c.data.startswith("setvoice_"):
        key = c.data.replace("setvoice_", "")
        if key in VOICES:
            set_voice_key(uid, key)
            voice_list_page(chat_id, uid, VOICES[key]["country"], msg_id)
    elif c.data == "lyrics":
        set_mode(uid, "lyrics")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "📝 *Lyrics Mode ON*\n\n"
            "Type: song name - artist\n"
            "Example: Shape of You - Ed Sheeran",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "reply":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))
        keywords = get_away_keywords(uid)
        kw_text = "\n".join([f"• `{k['keyword']}` → {k['reply'][:30]}" for k in keywords]) or "_No keywords yet_"
        bot.edit_message_text(
            "💬 *Auto-Reply (Business)*\n\n"
            "Set keyword replies for your Business DMs.\n\n"
            "*Current keywords:*\n" + kw_text + "\n\n"
            "*Commands:*\n"
            "`/setaway keyword | reply` — add keyword\n"
            "`/clearaway` — remove all keywords\n"
            "`/awaylist` — list keywords",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "upgrade":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(premium_text(uid), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif c.data == "help":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(help_text(), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif c.data == "translate":
        set_mode(uid, "translate")
        translate_lang_page(chat_id, uid, msg_id)
    elif c.data.startswith("tr_"):
        code = c.data.replace("tr_", "")
        if code in TRANS_LANGS:
            set_mode(uid, f"tr_{code}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="translate"))
            bot.edit_message_text(
                f"🌍 *Translator*\n\n"
                f"Target: {TRANS_LANGS[code]}\n\n"
                f"Type your text to translate.",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "pdf":
        pdf_page(chat_id, msg_id)
    elif c.data == "image":
        image_page(chat_id, msg_id)
    elif c.data == "myfiles":
        my_files_page(chat_id, uid, msg_id)
    elif c.data.startswith("mf_"):
        ftype = c.data.replace("mf_", "")
        my_files_list(chat_id, uid, ftype, msg_id)
    elif c.data.startswith("pdf_") or c.data.startswith("img_"):
        set_mode(uid, c.data)
        instruction = {
            "pdf_merge": "Send PDFs one by one. Only the first will be processed for now.",
            "pdf_split": "Send a PDF to split into pages",
            "pdf_compress": "Send a PDF to compress",
            "pdf_rotate": "Send a PDF to rotate 90°",
            "pdf_pdf2img": "Send a PDF to extract images",
            "img_compress": "Send an image to compress",
            "img_resize": "Send an image to resize to 50%",
            "img_convert": "Send an image to convert to JPG",
            "img_rotate": "Send an image to rotate 90°",
            "img_pdf": "Send an image to convert to PDF",
        }.get(c.data, "Send your file")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))
        bot.edit_message_text(
            f"✅ *Ready*\n\n{instruction}",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

# ---------- VOICE ----------
def make_voice_note(uid, chat_id, text):
    if not can_use(uid, "voice"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_VOICE_LIMIT} voice notes/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return
    voice = get_voice(uid)
    bot.send_message(chat_id, "🎙 Generating voice...")

    async def _make():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save("voice.mp3")

    try:
        asyncio.run(_make())
        filename = f"voice_{int(time.time())}.mp3"

        cloud_url = upload_to_cloud("voice.mp3",
            resource_type="video", folder="saviour/voice")

        with open("voice.mp3", "rb") as f:
            bot.send_document(chat_id, f,
                visible_file_name=filename,
                caption="🎙 Tap to play, long-press to save")

        if cloud_url:
            save_file_record(uid, "voice", filename, cloud_url)

        bump(uid, "voice")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Error: {e}")

# ---------- LYRICS ----------
def send_lrc(uid, chat_id, query):
    if not can_use(uid, "lyrics"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_LYRICS_LIMIT} lyrics/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return
    bot.send_message(chat_id, "🔎 Searching lyrics...")
    try:
        r = requests.get("https://lrclib.net/api/search",
                         params={"q": query}, timeout=15)
        data = r.json()
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Search error: {e}")
        return
    if not data:
        bot.send_message(chat_id, "❌ No lyrics found.")
        return
    song = None
    for item in data:
        if item.get("syncedLyrics"):
            song = item
            break
    if not song:
        bot.send_message(chat_id, "⚠️ No synced lyrics available.")
        return
    raw = song["syncedLyrics"].strip()
    lrc = f"[ti:{song['trackName']}]\n[ar:{song['artistName']}]\n"
    lrc += f"[al:{song.get('albumName', '')}]\n[by:SAVIOUR Bot]\n\n"
    lrc += raw
    filename = f"{song['artistName']} - {song['trackName']}.lrc".replace("/", "-")
    file_bytes = io.BytesIO(lrc.encode("utf-8"))
    file_bytes.name = filename

    bot.send_document(chat_id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}")

    try:
        with open("temp_lrc.lrc", "w", encoding="utf-8") as f:
            f.write(lrc)
        cloud_url = upload_to_cloud("temp_lrc.lrc",
            resource_type="raw", folder="saviour/lyrics")
        if cloud_url:
            save_file_record(uid, "lyrics", filename, cloud_url)
    except Exception as e:
        print("Lyrics upload error:", e, flush=True)

    bump(uid, "lyrics")

# ---------- TRANSLATE ----------
def do_translate(uid, chat_id, text, target_code):
    if not can_use(uid, "translate"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_TRANSLATE_LIMIT} translations/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return
    bot.send_message(chat_id, "🌍 Translating...")
    try:
        time.sleep(1)
        translated = GoogleTranslator(source="auto", target=target_code).translate(text)
        result = (f"🌍 *Translation*\n"
                  f"━━━━━━━━━━━━━━━━━━━━\n\n"
                  f"📝 *Original:*\n{text[:500]}\n\n"
                  f"✅ *{TRANS_LANGS.get(target_code, target_code)}:*\n{translated[:500]}")
        bot.send_message(chat_id, result, parse_mode="Markdown")
        bump(uid, "translate")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Translation error: {e}")

# ---------- PDF & IMAGE PROCESSOR ----------
def handle_pdf_image(uid, chat_id, mode, file_id, file_name):
    try:
        info = bot.get_file(file_id)
        downloaded = bot.download_file(info.file_path)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Download failed: {e}")
        return

    try:
        if mode == "pdf_pdf2img":
            if not can_use(uid, "pdf"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            reader = PdfReader(io.BytesIO(downloaded))
            pages = len(reader.pages)
            bot.send_message(chat_id, f"📸 Converting {pages} pages...")
            for i, page in enumerate(reader.pages):
                for img in page.images:
                    bio = io.BytesIO(img.data)
                    bio.name = f"page_{i+1}.png"
                    bot.send_document(chat_id, bio, caption=f"Page {i+1}")
            bump(uid, "pdf")
            return

        if mode == "pdf_compress":
            if not can_use(uid, "pdf"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            reader = PdfReader(io.BytesIO(downloaded))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            out.seek(0)
            out.name = f"compressed_{file_name}"
            bot.send_document(chat_id, out, caption="🗜 Compressed PDF")

            try:
                out.seek(0)
                with open("temp.pdf", "wb") as f:
                    f.write(out.read())
                cloud_url = upload_to_cloud("temp.pdf",
                    resource_type="raw", folder="saviour/pdf")
                if cloud_url:
                    save_file_record(uid, "pdf", out.name, cloud_url)
            except:
                pass
            bump(uid, "pdf")
            return

        if mode == "pdf_split":
            if not can_use(uid, "pdf"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            reader = PdfReader(io.BytesIO(downloaded))
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                out = io.BytesIO()
                writer.write(out)
                out.seek(0)
                out.name = f"page_{i+1}.pdf"
                bot.send_document(chat_id, out, caption=f"Page {i+1}")
            bump(uid, "pdf")
            return

        if mode == "pdf_rotate":
            if not can_use(uid, "pdf"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            reader = PdfReader(io.BytesIO(downloaded))
            writer = PdfWriter()
            for page in reader.pages:
                page.rotate(90)
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            out.seek(0)
            out.name = f"rotated_{file_name}"
            bot.send_document(chat_id, out, caption="🔄 Rotated 90°")
            bump(uid, "pdf")
            return

        if mode == "pdf_merge":
            if not can_use(uid, "pdf"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            bot.send_message(chat_id,
                "🔗 PDF merge: please send PDFs one at a time.\n"
                "Currently limited to single-file operations.")
            return

        if mode == "img_compress":
            if not can_use(uid, "image"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            img = Image.open(io.BytesIO(downloaded))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=60, optimize=True)
            out.seek(0)
            out.name = f"compressed_{file_name}"
            bot.send_document(chat_id, out, caption="🗜 Compressed image")

            try:
                out.seek(0)
                with open("temp.jpg", "wb") as f:
                    f.write(out.read())
                cloud_url = upload_to_cloud("temp.jpg",
                    resource_type="image", folder="saviour/image")
                if cloud_url:
                    save_file_record(uid, "image", out.name, cloud_url)
            except:
                pass
            bump(uid, "image")
            return

        if mode == "img_resize":
            if not can_use(uid, "image"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            img = Image.open(io.BytesIO(downloaded))
            w, h = img.size
            img = img.resize((w // 2, h // 2))
            out = io.BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            out.name = f"resized_{file_name}"
            bot.send_document(chat_id, out, caption="📐 Resized to 50%")
            bump(uid, "image")
            return

        if mode == "img_convert":
            if not can_use(uid, "image"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            img = Image.open(io.BytesIO(downloaded)).convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            out.name = f"converted_{file_name.rsplit('.', 1)[0]}.jpg"
            bot.send_document(chat_id, out, caption="🔄 Converted to JPG")
            bump(uid, "image")
            return

        if mode == "img_rotate":
            if not can_use(uid, "image"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            img = Image.open(io.BytesIO(downloaded))
            img = img.rotate(-90, expand=True)
            out = io.BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            out.name = f"rotated_{file_name}"
            bot.send_document(chat_id, out, caption="↩️ Rotated 90°")
            bump(uid, "image")
            return

        if mode == "img_pdf":
            if not can_use(uid, "image"):
                bot.send_message(chat_id, "🔒 Free limit reached")
                return
            img = Image.open(io.BytesIO(downloaded)).convert("RGB")
            out = io.BytesIO()
            img.save(out, format="PDF")
            out.seek(0)
            out.name = f"image_{int(time.time())}.pdf"
            bot.send_document(chat_id, out, caption="📄 Image → PDF")
            bump(uid, "image")
            return

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Processing error: {e}")

# ---------- GROUP AUTO-REPLY ----------
@bot.message_handler(content_types=['text'],
                     func=lambda m: m.chat.type in ['group', 'supergroup'])
def group_handler(m):
    if not m.text:
        return
    text = m.text.strip()

    if text.startswith("/addkeyword"):
        if m.from_user.id != ADMIN_ID and not is_group_admin(m.chat.id, m.from_user.id):
            bot.reply_to(m, "⛔ Only group admins can add keywords.")
            return
        parts = text.replace("/addkeyword", "", 1).strip()
        if "|" not in parts:
            bot.reply_to(m, "Usage: `/addkeyword word | reply`", parse_mode="Markdown")
            return
        keyword, reply = parts.split("|", 1)
        add_group_keyword(m.chat.id, m.from_user.id, keyword.strip(), reply.strip())
        bot.reply_to(m, f"✅ Keyword `{keyword.strip()}` added.", parse_mode="Markdown")
        return

    if text.startswith("/listkeywords"):
        kws = get_group_keywords(m.chat.id)
        if not kws:
            bot.reply_to(m, "No keywords set.")
            return
        out = "📋 *Keywords:*\n\n"
        for k in kws:
            out += f"• `{k['keyword']}` → {k['reply'][:50]}\n"
        bot.reply_to(m, out, parse_mode="Markdown")
        return

    if text.startswith("/"):
        return

    reply = find_group_reply(m.chat.id, text)
    if reply:
        bot.reply_to(m, reply)

def is_group_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False

# ---------- BUSINESS ----------
BUSINESS_OWNERS = {}

@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    try:
        if conn.is_enabled:
            BUSINESS_OWNERS[conn.id] = conn.user.id
            bot.send_message(conn.user.id,
                "✅ SAVIOUR connected to your Telegram Business.\n"
                "Use /setaway keyword | reply to set auto-replies.")
        else:
            BUSINESS_OWNERS.pop(conn.id, None)
    except Exception as e:
        print("Business conn error:", e, flush=True)

@bot.business_message_handler(func=lambda m: True)
def on_business_message(m):
    try:
        for owner_uid in list(BUSINESS_OWNERS.values()):
            if m.text:
                reply = find_away_reply(owner_uid, m.text)
                if reply:
                    bot.send_message(m.chat.id, reply,
                        business_connection_id=m.business_connection_id)
                    return
            away = get_away_msg(owner_uid)
            if away:
                bot.send_message(m.chat.id, away,
                    business_connection_id=m.business_connection_id)
                return
    except Exception as e:
        print("Business msg error:", e, flush=True)

# ---------- /setaway (upgraded) ----------
@bot.message_handler(commands=['setaway'])
def set_away_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    text = m.text.replace('/setaway', '', 1).strip()
    if not text:
        bot.reply_to(m,
            "💬 *Auto-Reply for Business*\n\n"
            "*Commands:*\n"
            "`/setaway keyword | reply` — add keyword reply\n"
            "`/setaway default text` — set fallback reply\n"
            "`/awaylist` — see all keywords\n"
            "`/clearaway` — remove all\n\n"
            "*Examples:*\n"
            "`/setaway price | Our prices start at ₦5000`\n"
            "`/setaway hours | We are open 9am-6pm`",
            parse_mode="Markdown")
        return

    if "|" in text:
        keyword, reply = text.split("|", 1)
        add_away_keyword(uid, keyword.strip(), reply.strip())
        bot.reply_to(m, f"✅ Keyword `{keyword.strip()}` added.", parse_mode="Markdown")
    else:
        set_away_msg(uid, text)
        bot.reply_to(m, "✅ Default away message set!")

@bot.message_handler(commands=['awaylist'])
def awaylist_cmd(m):
    uid = m.from_user.id
    kws = get_away_keywords(uid)
    default = get_away_msg(uid)
    out = "📋 *Your Away Replies*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if default:
        out += f"*Default:* {default}\n\n"
    if kws:
        out += "*Keywords:*\n"
        for k in kws:
            out += f"• `{k['keyword']}` → {k['reply'][:50]}\n"
    else:
        out += "_No keywords yet._"
    bot.reply_to(m, out, parse_mode="Markdown")

@bot.message_handler(commands=['clearaway'])
def clearaway_cmd(m):
    uid = m.from_user.id
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM away_keywords WHERE user_id=%s", (uid,))
        cur.execute("UPDATE users SET away_message=NULL WHERE user_id=%s", (uid,))
        conn.commit()
        cur.close()
        conn.close()
        bot.reply_to(m, "✅ All away replies cleared.")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

# ---------- CHANNEL POSTER ----------
@bot.message_handler(commands=['setchannel'])
def setchannel_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    parts = m.text.replace('/setchannel', '', 1).strip().split()
    if not parts:
        bot.reply_to(m,
            "📢 *Set Channel*\n\n"
            "Usage: `/setchannel <channel_id>`\n"
            "Example: `/setchannel -1001234567890`\n\n"
            "Add SAVIOUR as admin to your channel first.",
            parse_mode="Markdown")
        return
    channel_id = parts[0]
    add_channel(uid, channel_id, parts[1] if len(parts) > 1 else channel_id)
    bot.reply_to(m, f"✅ Channel `{channel_id}` linked.", parse_mode="Markdown")

@bot.message_handler(commands=['post'])
def post_cmd(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    text = m.text.replace('/post', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: `/post your message`", parse_mode="Markdown")
        return
    channels = get_channels(uid)
    if not channels:
        bot.reply_to(m, "⚠️ No channel linked. Use /setchannel first.")
        return
    for ch in channels:
        try:
            bot.send_message(ch["channel_id"], text)
            bot.reply_to(m, f"✅ Posted to {ch['channel_name']}")
        except Exception as e:
            bot.reply_to(m, f"❌ Failed: {e}")

@bot.message_handler(commands=['schedule'])
def schedule_cmd(m):
    if m.from_user.id != ADMIN_ID:
        return
    text = m.text.replace('/schedule', '', 1).strip()
    if "|" not in text:
        bot.reply_to(m,
            "Usage: `/schedule HH:MM | message`\n"
            "Example: `/schedule 09:00 | Good morning!`",
            parse_mode="Markdown")
        return
    time_part, msg = text.split("|", 1)
    channels = get_channels(ADMIN_ID)
    if not channels:
        bot.reply_to(m, "⚠️ No channel linked. Use /setchannel first.")
        return
    for ch in channels:
        add_scheduled(ch["channel_id"], time_part.strip(), msg.strip())
    bot.reply_to(m,
        f"✅ Scheduled for {time_part.strip()} daily.",
        parse_mode="Markdown")

# ---------- /say /lrc (fixed) ----------
@bot.message_handler(commands=['say'])
def say_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    text = m.text.replace('/say', '', 1).strip()
    if not text:
        bot.reply_to(m,
            "🎙 *Voice from Text*\n\n"
            "Usage: `/say your text here`\n"
            "Example: `/say Good morning everyone`",
            parse_mode="Markdown")
        return
    make_voice_note(uid, m.chat.id, text)

@bot.message_handler(commands=['lrc'])
def lrc_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    q = m.text.replace('/lrc', '', 1).strip()
    if not q:
        bot.reply_to(m,
            "📝 *Lyrics Search*\n\n"
            "Usage: `/lrc song name - artist`\n"
            "Example: `/lrc Shape of You - Ed Sheeran`",
            parse_mode="Markdown")
        return
    send_lrc(uid, m.chat.id, q)

# ---------- ADMIN ----------
def admin_only(m):
    return m.from_user.id == ADMIN_ID

@bot.message_handler(commands=['addpaid'])
def addpaid_cmd(m):
    if not admin_only(m):
        return
    try:
        uid = int(m.text.split()[1])
        set_paid(uid, 1)
        bot.reply_to(m, f"✅ {uid} is now Premium")
        try:
            bot.send_message(uid, "🎉 You are now Premium!")
        except:
            pass
    except:
        bot.reply_to(m, "Usage: /addpaid user_id")

@bot.message_handler(commands=['removepaid'])
def removepaid_cmd(m):
    if not admin_only(m):
        return
    try:
        uid = int(m.text.split()[1])
        set_paid(uid, 0)
        bot.reply_to(m, f"👤 {uid} removed from Premium")
    except:
        bot.reply_to(m, "Usage: /removepaid user_id")

@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not admin_only(m):
        return
    try:
        uid = int(m.text.split()[1])
        set_banned(uid, 1)
        bot.reply_to(m, f"🚫 {uid} banned")
    except:
        bot.reply_to(m, "Usage: /ban user_id")

@bot.message_handler(commands=['unban'])
def unban_cmd(m):
    if not admin_only(m):
        return
    try:
        uid = int(m.text.split()[1])
        set_banned(uid, 0)
        bot.reply_to(m, f"✅ {uid} unbanned")
    except:
        bot.reply_to(m, "Usage: /unban user_id")

@bot.message_handler(commands=['users'])
def users_cmd(m):
    if not admin_only(m):
        return
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT user_id, username, paid, banned
                       FROM users ORDER BY last_seen DESC LIMIT 20""")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = "👥 *Recent Users:*\n\n"
        for r in rows:
            tag = "💎" if r["paid"] else "👤"
            bn = "🚫" if r["banned"] else ""
            out += f"{tag}{bn} `{r['user_id']}` @{r['username'] or '—'}\n"
        bot.reply_to(m, out, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if not admin_only(m):
        return
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM users")
        total = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as p FROM users WHERE paid=1")
        paid = cur.fetchone()["p"]
        cur.execute("SELECT COUNT(*) as b FROM users WHERE banned=1")
        banned = cur.fetchone()["b"]
        cur.execute("SELECT COUNT(*) as f FROM files")
        files = cur.fetchone()["f"]
        cur.close()
        conn.close()
        bot.reply_to(m,
            f"📊 *Stats*\n\n"
            f"👥 Users: {total}\n"
            f"💎 Paid: {paid}\n"
            f"🚫 Banned: {banned}\n"
            f"📁 Files: {files}",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['admin'])
def admin_cmd(m):
    if not admin_only(m):
        return
    bot.reply_to(m,
        "🛡️ *ADMIN PANEL*\n\n"
        "*Users:*\n"
        "/users — recent users\n"
        "/stats — overview\n"
        "/addpaid <id> — unlock\n"
        "/removepaid <id> — lock\n"
        "/ban <id> — ban\n"
        "/unban <id> — unban\n\n"
        "*Channel:*\n"
        "/setchannel <id> — link channel\n"
        "/post <message> — post now\n"
        "/schedule HH:MM | message\n\n"
        "*System:*\n"
        "/maintenance on|off — toggle maintenance",
        parse_mode="Markdown")

@bot.message_handler(commands=['maintenance'])
def maintenance_cmd(m):
    if not admin_only(m):
        return
    arg = m.text.replace('/maintenance', '', 1).strip().lower()
    if arg == "on":
        set_maintenance(True)
        bot.reply_to(m, "🛠 Maintenance mode ON\n\nUsers will see a maintenance message.")
    elif arg == "off":
        set_maintenance(False)
        bot.reply_to(m, "✅ Maintenance mode OFF\n\nUsers can use the bot now.")
    else:
        status = "ON" if get_maintenance() else "OFF"
        bot.reply_to(m,
            f"🛠 *Maintenance Mode*\n\n"
            f"Status: *{status}*\n\n"
            f"Commands:\n"
            f"`/maintenance on`\n"
            f"`/maintenance off`",
            parse_mode="Markdown")

# ---------- FILE HANDLER ----------
@bot.message_handler(content_types=['document', 'photo'])
def handle_file(m):
    uid = m.from_user.id
    if is_banned(uid):
        return

    mode = get_mode(uid)

    if m.content_type == 'document':
        file_id = m.document.file_id
        file_name = m.document.file_name or "file"
    else:
        file_id = m.photo[-1].file_id
        file_name = f"photo_{int(time.time())}.jpg"

    if mode.startswith("pdf_") or mode.startswith("img_"):
        handle_pdf_image(uid, m.chat.id, mode, file_id, file_name)
    else:
        bot.reply_to(m, "Tap /start → Tools → PDF or Image to use this file.")

# ---------- MAIN HANDLER ----------
@bot.message_handler(func=lambda m: True)
def handle_message(m):
    uid = m.from_user.id
    if is_banned(uid):
        return

    if get_maintenance() and uid != ADMIN_ID:
        bot.reply_to(m,
            "🛠 *SAVIOUR is under maintenance*\n\n"
            "We're making improvements.\n"
            "Please try again in a few minutes.",
            parse_mode="Markdown")
        return

    if m.chat.type in ['group', 'supergroup']:
        return

    text = (m.text or "").strip()
    if not text:
        return

    if text.startswith("/"):
        return

    save_user_meta(uid, m.from_user.username, m.from_user.first_name)

    mode = get_mode(uid)

    if mode == "lyrics":
        send_lrc(uid, m.chat.id, text)
    elif mode.startswith("tr_"):
        target = mode.replace("tr_", "")
        do_translate(uid, m.chat.id, text, target)
    elif mode == "translate":
        bot.reply_to(m, "Pick a language first from the Translator menu.")
    elif mode == "voice":
        make_voice_note(uid, m.chat.id, text)
    else:
        make_voice_note(uid, m.chat.id, text)

# ---------- WEBHOOK ----------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook error:", e, flush=True)
    return "ok", 200

@app.route("/")
def index():
    return "SAVIOUR is running", 200

if __name__ == "__main__":
    print("Starting...", flush=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
