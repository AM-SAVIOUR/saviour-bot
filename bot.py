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

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")
CREATOR = "IAMSAVIOUR1"
ADMIN_ID = 8872791323

PRICE = "₦1,500/month"
PAY_NAME = "CHINAZAEKPERE SAVIOUR MBAEBIE"
PAY_ACCOUNT = "9038530721"
PAY_BANK = "Opay"

FREE_VOICE_LIMIT = 3
FREE_LYRICS_LIMIT = 3

print("=" * 50, flush=True)
print("STARTUP", flush=True)
print("BOT_TOKEN:", "YES" if BOT_TOKEN else "MISSING!", flush=True)
print("DATABASE_URL:", "YES" if DATABASE_URL else "MISSING!", flush=True)
print("=" * 50, flush=True)

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN missing")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL missing")

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
                mode TEXT DEFAULT 'voice',
                last_reset DATE,
                joined DATE DEFAULT CURRENT_DATE,
                last_seen DATE DEFAULT CURRENT_DATE
            )
        """)
        # Add mode column if table already existed without it
        cur.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'voice'
        """)
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
    if kind == "voice":
        return u["voice_count"] < FREE_VOICE_LIMIT
    if kind == "lyrics":
        return u["lyrics_count"] < FREE_LYRICS_LIMIT
    return True

def bump(uid, kind):
    col = "voice_count" if kind == "voice" else "lyrics_count"
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

# ---------- PREMIUM ----------
def premium_text(uid):
    if is_paid(uid):
        return ("💎 *PREMIUM ACTIVE*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ Unlimited voice notes\n"
                "✅ Unlimited lyrics\n"
                "✅ Priority speed\n\n"
                "Thank you for supporting SAVIOUR!")
    return (f"💎 *UPGRADE TO PREMIUM*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Price: *{PRICE}*\n\n"
            "🎁 *You get:*\n"
            "✅ Unlimited voice notes\n"
            "✅ Unlimited lyrics\n"
            "✅ Priority speed\n\n"
            "📋 *How to pay:*\n"
            f"1. Transfer {PRICE} to:\n"
            f"   🏦 {PAY_BANK}\n"
            f"   🔢 {PAY_ACCOUNT}\n"
            f"   👤 {PAY_NAME}\n\n"
            f"2. Send receipt to @{CREATOR}\n"
            "3. Wait for approval\n\n"
            "⚠️ Free: 3 voice + 3 lyrics per day")

# ---------- MAIN MENU ----------
def main_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎙 Voice", callback_data="voice"),
        types.InlineKeyboardButton("📝 Lyrics", callback_data="lyrics"),
        types.InlineKeyboardButton("💬 Auto-Reply", callback_data="reply"),
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
            "1. Tap Voice\n"
            "2. Choose a country\n"
            "3. Pick a voice\n"
            "4. Type your message → MP3\n\n"
            "📝 *Lyrics Tool*\n"
            "1. Tap Lyrics\n"
            "2. Type: song name - artist\n"
            "3. Get a synced .lrc file\n\n"
            "💬 *Auto-Reply*\n"
            "Set with: /setaway your message\n\n"
            "💎 *Premium*\n"
            f"Unlock unlimited — {PRICE}\n\n"
            "*Free Limits:*\n"
            f"🎙 Voice: {FREE_VOICE_LIMIT}/day\n"
            f"📝 Lyrics: {FREE_LYRICS_LIMIT}/day\n\n"
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

# ---------- BUTTONS ----------
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
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
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
        with open("voice.mp3", "rb") as f:
            bot.send_document(chat_id, f,
                visible_file_name=filename,
                caption="🎙 Tap to play, long-press to save")
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
    bump(uid, "lyrics")
# ---------- BUSINESS ----------
BUSINESS_OWNERS = {}

@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    try:
        print(f"BUSINESS: id={conn.id} enabled={conn.is_enabled}", flush=True)
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
                print("Auto-reply sent", flush=True)
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
            bot.send_message(uid, "🎉 You are now Premium! Unlimited access unlocked.")
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
        cur.close()
        conn.close()
        bot.reply_to(m,
            f"📊 *Stats*\n\n"
            f"👥 Users: {total}\n"
            f"💎 Paid: {paid}\n"
            f"🚫 Banned: {banned}",
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
