import os
import telebot
from telebot import types
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
            "More powerful tools for daily use.\n\n"
            "Tap one to begin.")
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
            "🎙 *Voice Tool*\n"
            "1. Tap Voice → pick a country → pick a voice\n"
            "2. Type your message → get MP3\n\n"
            "📝 *Lyrics Tool*\n"
            "1. Tap Lyrics\n"
            "2. Type: song name - artist\n"
            "3. Get a synced .lrc file\n\n"
            "🌍 *Translator*\n"
            "1. Tap Tools → Translate\n"
            "2. Pick language, then type text\n\n"
            "📄 *PDF Suite*\n"
            "Merge, split, compress, rotate PDFs\n\n"
            "🖼 *Image Tools*\n"
            "Compress, resize, convert images\n\n"
            "💬 *Auto-Reply*\n"
            "Set with: /setaway your message\n\n"
            "💎 *Premium*\n"
            f"Unlock unlimited — {PRICE}\n\n"
            "*Free Limits:*\n"
            f"🎙 Voice: {FREE_VOICE_LIMIT}/day\n"
            f"📝 Lyrics: {FREE_LYRICS_LIMIT}/day\n"
            f"🌍 Translate: {FREE_TRANSLATE_LIMIT}/day\n"
            f"📄 PDF: {FREE_PDF_LIMIT}/day\n"
            f"🖼 Image: {FREE_IMAGE_LIMIT}/day\n\n"
            f"👑 Created by: @{CREATOR}")

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
            "Pick target language.\n"
            "Then type text to translate.\n\n"
            "I auto-detect the source language.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- PDF PAGE ----------
def pdf_page(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🖼 Images → PDF", callback_data="pdf_img2pdf"),
        types.InlineKeyboardButton("🔗 Merge PDFs", callback_data="pdf_merge"),
        types.InlineKeyboardButton("✂️ Split PDF", callback_data="pdf_split"),
        types.InlineKeyboardButton("🗜 Compress PDF", callback_data="pdf_compress"),
        types.InlineKeyboardButton("🔄 Rotate PDF", callback_data="pdf_rotate"),
        types.InlineKeyboardButton("📸 PDF → Images", callback_data="pdf_pdf2img"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("📄 *PDF Suite*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pick an action.\n"
            "Max file size: 20 MB\n\n"
            "1. Tap an action\n"
            "2. Send your file(s)\n"
            "3. Get the result")
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
            "Pick an action.\n"
            "Max file size: 20 MB\n\n"
            "1. Tap an action\n"
            "2. Send your image\n"
            "3. Get the result")
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
        bot.edit_message_text(
            "💬 *Auto-Reply (Business)*\n\nSet with: /setaway your message",
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
                f"Now type your text to translate.",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "pdf":
        pdf_page(chat_id, msg_id)
    elif c.data == "image":
        image_page(chat_id, msg_id)
    elif c.data.startswith("pdf_") or c.data.startswith("img_"):
        set_mode(uid, c.data)
        instruction = {
            "pdf_img2pdf": "Send images to combine into a PDF",
            "pdf_merge": "Send PDFs to merge",
            "pdf_split": "Send a PDF to split",
            "pdf_compress": "Send a PDF to compress",
            "pdf_rotate": "Send a PDF to rotate",
            "pdf_pdf2img": "Send a PDF to convert to images",
            "img_compress": "Send an image to compress",
            "img_resize": "Send an image to resize",
            "img_convert": "Send an image to convert format",
            "img_rotate": "Send an image to rotate/flip",
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

        # Upload to Cloudinary
        cloud_url = upload_to_cloud("voice.mp3", resource_type="video", folder="saviour/voice")

        # Send to user
        with open("voice.mp3", "rb") as f:
            bot.send_document(chat_id, f,
                visible_file_name=filename,
                caption="🎙 Tap to play, long-press to save")

        # Save record
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

    # Send to user
    bot.send_document(chat_id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}")

    # Upload to Cloudinary (raw type for text files)
    try:
        with open("temp_lrc.lrc", "w", encoding="utf-8") as f:
            f.write(lrc)
        cloud_url = upload_to_cloud("temp_lrc.lrc", resource_type="raw", folder="saviour/lyrics")
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

# ---------- BUSINESS ----------
BUSINESS_OWNERS = {}

@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    try:
        if conn.is_enabled:
            BUSINESS_OWNERS[conn.id] = conn.user.id
            bot.send_message(conn.user.id,
                "✅ SAVIOUR connected to your Telegram Business.\n"
                "Use /setaway to set your auto-reply.")
        else:
            BUSINESS_OWNERS.pop(conn.id, None)
    except Exception as e:
        print("Business conn error:", e, flush=True)

@bot.business_message_handler(func=lambda m: True)
def on_business_message(m):
    try:
        for owner_uid in list(BUSINESS_OWNERS.values()):
            away = get_away_msg(owner_uid)
            if away:
                bot.send_message(m.chat.id, away,
                    business_connection_id=m.business_connection_id)
                return
    except Exception as e:
        print("Business msg error:", e, flush=True)

# ---------- /setaway ----------
@bot.message_handler(commands=['setaway'])
def set_away_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    text = m.text.replace('/setaway', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: /setaway Your message here")
        return
    set_away_msg(uid, text)
    bot.reply_to(m, "✅ Away message set!")

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
            f"📊 *Stats*\n\n👥 Users: {total}\n💎 Paid: {paid}\n"
            f"🚫 Banned: {banned}\n📁 Files stored: {files}",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['admin'])
def admin_cmd(m):
    if not admin_only(m):
        return
    bot.reply_to(m,
        "🛡️ *ADMIN PANEL*\n\n"
        "/users — recent users\n"
        "/stats — overview\n"
        "/addpaid <id> — unlock\n"
        "/removepaid <id> — lock\n"
        "/ban <id> — ban\n"
        "/unban <id> — unban",
        parse_mode="Markdown")

# ---------- /say /lrc ----------
@bot.message_handler(commands=['say'])
def say_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    text = m.text.replace('/say', '', 1).strip()
    if text:
        make_voice_note(uid, m.chat.id, text)

@bot.message_handler(commands=['lrc'])
def lrc_cmd(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    q = m.text.replace('/lrc', '', 1).strip()
    if q:
        send_lrc(uid, m.chat.id, q)

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
    text = (m.text or "").strip()
    if not text:
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

