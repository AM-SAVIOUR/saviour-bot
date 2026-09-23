import os
import telebot
from telebot import types
from telebot.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
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
import qrcode

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")
CREATOR = "IAMSAVIOUR1"
ADMIN_ID = 8872791323

CLOUDINARY_CLOUD = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
PHISHSTATS_KEY = os.environ.get("PHISHSTATS_KEY")

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
FREE_SECURITY_LIMIT = 5
FREE_CV_LIMIT = 1
FREE_VOICETRANS_LIMIT = 2
FREE_QR_LIMIT = 5

print("=" * 50, flush=True)
print("STARTUP", flush=True)
print("BOT_TOKEN:", "YES" if BOT_TOKEN else "MISSING", flush=True)
print("DATABASE_URL:", "YES" if DATABASE_URL else "MISSING", flush=True)
print("CLOUDINARY:", "YES" if CLOUDINARY_CLOUD else "MISSING", flush=True)
print("PHISHSTATS:", "YES" if PHISHSTATS_KEY else "MISSING", flush=True)
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
    BotCommand("addscam", "Add a scam alert"),
    BotCommand("editaway", "Edit away keyword"),
    BotCommand("delaway", "Delete away keyword"),
    BotCommand("synccommands", "Re-register commands"),
]

try:
    try:
        bot.delete_my_commands()
    except:
        pass
    try:
        bot.delete_my_commands(scope=BotCommandScopeDefault())
    except:
        pass

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
                security_count INTEGER DEFAULT 0,
                cv_count INTEGER DEFAULT 0,
                voicetrans_count INTEGER DEFAULT 0,
                qr_count INTEGER DEFAULT 0,
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
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id BIGINT PRIMARY KEY,
                welcome_enabled INTEGER DEFAULT 0,
                welcome_text TEXT
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                connection_id TEXT PRIMARY KEY,
                owner_id BIGINT,
                enabled INTEGER DEFAULT 1,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scam_alerts (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                created DATE DEFAULT CURRENT_DATE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS link_cache (
                url TEXT PRIMARY KEY,
                result TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for col in ["security_count INTEGER DEFAULT 0",
                    "cv_count INTEGER DEFAULT 0",
                    "voicetrans_count INTEGER DEFAULT 0",
                    "qr_count INTEGER DEFAULT 0"]:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col}")
            except:
                pass

        conn.commit()
        cur.close()
        conn.close()
        print("DB init OK", flush=True)

        load_default_scams()

    except Exception as e:
        print("DB INIT ERROR:", e, flush=True)

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
                           security_count=0, cv_count=0, voicetrans_count=0,
                           qr_count=0,
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
        "security": (u["security_count"], FREE_SECURITY_LIMIT),
        "cv": (u["cv_count"], FREE_CV_LIMIT),
        "voicetrans": (u["voicetrans_count"], FREE_VOICETRANS_LIMIT),
        "qr": (u["qr_count"], FREE_QR_LIMIT),
    }
    if kind in limits:
        used, maxv = limits[kind]
        return used < maxv
    return True

def bump(uid, kind):
    cols = {"voice": "voice_count", "lyrics": "lyrics_count",
            "translate": "translate_count", "pdf": "pdf_count",
            "image": "image_count", "security": "security_count",
            "cv": "cv_count", "voicetrans": "voicetrans_count",
            "qr": "qr_count"}
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

def delete_away_keyword(uid, keyword):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM away_keywords WHERE user_id=%s AND keyword=%s",
                    (uid, keyword.lower()))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except:
        return False

# ---------- GROUP KEYWORDS ----------
def add_group_keyword(chat_id, owner_id, keyword, reply):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM group_keywords WHERE chat_id=%s AND keyword=%s",
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

def delete_group_keyword(chat_id, keyword):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM group_keywords WHERE chat_id=%s AND keyword=%s",
                    (chat_id, keyword.lower()))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except:
        return False

def find_group_reply(chat_id, text):
    text_low = text.lower()
    for row in get_group_keywords(chat_id):
        if row["keyword"] in text_low:
            return row["reply"]
    return None

# ---------- GROUP SETTINGS ----------
def get_group_settings(chat_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM group_settings WHERE chat_id=%s", (chat_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO group_settings (chat_id) VALUES (%s)", (chat_id,))
            conn.commit()
            cur.close()
            conn.close()
            return {"welcome_enabled": 0, "welcome_text": None}
        cur.close()
        conn.close()
        return row
    except:
        return {"welcome_enabled": 0, "welcome_text": None}

def set_group_welcome(chat_id, enabled, text=None):
    try:
        conn = db()
        cur = conn.cursor()
        if text:
            cur.execute("""INSERT INTO group_settings (chat_id, welcome_enabled, welcome_text)
                           VALUES (%s, %s, %s)
                           ON CONFLICT (chat_id) DO UPDATE SET
                           welcome_enabled=%s, welcome_text=%s""",
                        (chat_id, enabled, text, enabled, text))
        else:
            cur.execute("""INSERT INTO group_settings (chat_id, welcome_enabled)
                           VALUES (%s, %s)
                           ON CONFLICT (chat_id) DO UPDATE SET welcome_enabled=%s""",
                        (chat_id, enabled, enabled))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_group_welcome error:", e, flush=True)

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

# ---------- BUSINESS CONNECTIONS ----------
def save_business_connection(connection_id, owner_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO business_connections (connection_id, owner_id)
                       VALUES (%s, %s)
                       ON CONFLICT (connection_id) DO UPDATE SET
                       owner_id=%s, enabled=1""",
                    (connection_id, owner_id, owner_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("save_businss_connection error:", e, flush=True)

def get_business_owner(connection_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT owner_id FROM business_connections
                       WHERE connection_id=%s AND enabled=1""", (connection_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row["owner_id"] if row else None
    except:
        return None

def remove_business_connection(connection_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE business_connections SET enabled=0 WHERE connection_id=%s",
                    (connection_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("remove_business_connection error:", e, flush=True)

# ---------- SCAM ALERTS ----------
def load_default_scams():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scam_alerts")
        if cur.fetchone()["c"] > 0:
            cur.close()
            conn.close()
            return

        scams = [
            ("Fake Bank Alert", "Scammers send fake credit alerts to sellers. Always check your bank app for real balance before releasing goods."),
            ("Fake BVN Request", "No bank or government agency asks for your BVN via SMS, WhatsApp, or Telegram. Never share it."),
            ("Fake OPay/Palmpay Alert", "Fake alerts that look exactly like real Opay notifications. Check the app directly."),
            ("NIN Update Scam", "Fake messages asking you to pay for NIN update. NIN updates are free at NIMC offices."),
            ("Fake Job Offer", "Jobs that ask for registration fees, training fees, or upfront payments are scams. Real jobs pay you."),
            ("Fake Investment", "Anyone promising 50%+ returns in days is running a Ponzi scheme. Real investments don't guarantee huge returns."),
            ("Lottery/Promo Win", "You did not win a lottery you never entered. Delete such messages."),
            ("Fake Customs Officer", "Fake customs asking you to pay for parcel clearance. Verify with the real customs office."),
            ("Romance Scam", "Strangers on dating apps asking for money after a few chats. Never send money to someone you haven't met."),
            ("Fake Loan App", "Loan apps that ask for your contacts and photos. They use them to harass you. Use only CBN-licensed lenders."),
            ("Fake Crypto Giveaway", "Fake Elon Musk or Binance giveaways asking you to send crypto first. Always a scam."),
            ("WhatsApp Account Theft", "Fake messages asking for your WhatsApp verification code. Never share it with anyone."),
            ("Fake Telegram Premium", "Fake bots offering free Telegram Premium. They steal your account or money."),
            ("Fake POS Reversal", "Scammers claim they sent money to your POS and want a reversal. Confirm with your bank first."),
            ("Fake Delivery Fee", "Fake courier messages asking for delivery fees for packages you didn't order."),
            ("Fake School Fees", "Fake messages pretending to be from your child's school. Call the school to verify."),
            ("Fake Recruitment", "Fake military or police recruitment scams. Real recruitment doesn't ask for payment."),
            ("Fake Giveaway", "Social media giveaways asking for your bank details. Never share."),
            ("SIM Swap Fraud", "Fraudsters port your number to access your bank. Watch for sudden network loss."),
            ("Fake Charity", "Fake charities asking for donations for fake causes. Verify before donating."),
        ]
        for title, desc in scams:
            cur.execute("INSERT INTO scam_alerts (title, description) VALUES (%s, %s)",
                        (title, desc))
        conn.commit()
        cur.close()
        conn.close()
        print("Loaded 20 default scams", flush=True)
    except Exception as e:
        print("load_default_scams error:", e, flush=True)

def get_scam_alerts():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, title, description FROM scam_alerts ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except:
        return []

def add_scam_alert(title, description):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO scam_alerts (title, description) VALUES (%s, %s)",
                    (title, description))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except:
        return False

# ---------- LINK CACHE ----------
def get_cached_link(url):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT result FROM link_cache
                       WHERE url=%s AND cached_at > NOW() - INTERVAL '24 hours'""",
                    (url,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row["result"] if row else None
    except:
        return None

def cache_link(url, result):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO link_cache (url, result) VALUES (%s, %s)
                       ON CONFLICT (url) DO UPDATE SET
                       result=%s, cached_at=NOW()""",
                    (url, result, result))
        conn.commit()
        cur.close()
        conn.close()
    except:
        pass

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

init_db()

# ---------- AUTO SET WEBHOOK ----------
def set_webhook():
    try:
        allowed = json.dumps([
            "message", "callback_query",
            "business_connection", "business_message",
            "edited_business_message", "deleted_business_messages",
            "chat_member", "my_chat_member"
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
                "✅ Unlimited image tools\n"
                "✅ Unlimited security checks\n"
                "✅ Unlimited CV Builder\n"
                "✅ Unlimited Voice Translator\n"
                "✅ Unlimited QR codes\n\n"
                "Thank you for supporting SAVIOUR!")
    return (f"💎 *UPGRADE TO PREMIUM*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Price: *{PRICE}*\n\n"
            "🎁 *You get:*\n"
            "✅ Unlimited voice notes\n"
            "✅ Unlimited lyrics\n"
            "✅ Unlimited translation\n"
            "✅ Unlimited PDF tools\n"
            "✅ Unlimited image tools\n"
            "✅ Unlimited security checks\n"
            "✅ Unlimited CV Builder\n"
            "✅ Unlimited Voice Translator\n"
            "✅ Unlimited QR codes\n\n"
            "📋 *How to pay:*\n"
            f"1. Transfer {PRICE} to:\n"
            f"   🏦 {PAY_BANK}\n"
            f"   🔢 {PAY_ACCOUNT}\n"
            f"   👤 {PAY_NAME}\n\n"
            f"2. Send receipt to @{CREATOR}\n"
            "3. Wait for approval\n\n"
            "⚠️ Free limits apply per tool")

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
    text = ("👋 *Welcome to SAVIOUR!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your everyday helper on Telegram.\n\n"
            "*What I can do for you:*\n\n"
            "🎙 Voice notes — turn text into speech\n"
            "📝 Lyrics — get song lyrics with timestamps\n"
            "🌍 Translate — 24 languages\n"
            "📄 PDF — merge, split, compress\n"
            "🖼 Images — compress, resize, convert\n"
            "🛡️ Security — check suspicious links\n\n"
            "Tap any button to start 👇\n\n"
            f"👑 Creator: @{CREATOR}")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def tools_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛡️ Security Center", callback_data="security"),
    )
    markup.add(
        types.InlineKeyboardButton("🌍 Translate", callback_data="translate"),
        types.InlineKeyboardButton("📄 PDF Suite", callback_data="pdf"),
        types.InlineKeyboardButton("🖼 Image Tools", callback_data="image"),
        types.InlineKeyboardButton("💬 Auto-Reply", callback_data="reply"),
        types.InlineKeyboardButton("📝 CV Builder", callback_data="cv"),
        types.InlineKeyboardButton("🎙 Voice Translate", callback_data="voicetrans"),
        types.InlineKeyboardButton("🔲 QR Code", callback_data="qr"),
    )
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
    text = ("🔧 *Tools*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "More powerful tools for daily use.\n\n"
            "Tap one to begin 👇")
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
    return ("❓ *SAVIOUR Help Guide*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*What is SAVIOUR?*\n"
            "An all-in-one Telegram assistant that saves you time.\n\n"
            "*Available Tools:*\n\n"
            "🎙 *Voice Generator*\n"
            "Turn text into voice notes in 32 voices.\n"
            "Example: Type \"Hello world\" → get voice note\n\n"
            "📝 *Lyrics Finder*\n"
            "Get synced lyrics for any song.\n"
            "Example: Type \"Shape of You - Ed Sheeran\"\n\n"
            "🌍 *Translator*\n"
            "Translate between 24 languages.\n"
            "Example: Pick French → type \"Good morning\"\n\n"
            "📄 *PDF Suite*\n"
            "Merge, split, compress, rotate PDFs.\n\n"
            "🖼 *Image Tools*\n"
            "Compress, resize, convert images.\n\n"
            "🛡️ *Security Center*\n"
            "Check links, screenshots, and learn about scams.\n\n"
            "📝 *CV Builder*\n"
            "Create professional CVs in minutes.\n\n"
            "🎙 *Voice Translator*\n"
            "Translate voice messages between languages.\n\n"
            "🔲 *QR Code*\n"
            "Generate QR codes for links, WiFi, contacts.\n\n"
            "📚 *My Files*\n"
            "Access all your past files anytime.\n\n"
            "💎 *Premium* — " + PRICE + "\n"
            "Free limits apply per tool.\n"
            "Pay to: " + PAY_ACCOUNT + " (" + PAY_BANK + ")\n"
            "Contact: @" + CREATOR + "\n\n"
            "*Commands:*\n"
            "/start — Open main menu\n"
            "/say text — Generate voice\n"
            "/lrc song - artist — Get lyrics\n"
            "/setaway keyword | reply — Auto-reply\n"
            "/privacy — Privacy policy\n\n"
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

    text = ("🎙 *Voice Generator*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Turn any text into natural speech.\n\n"
            "*How to use:*\n"
            "1. Pick a country below\n"
            "2. Choose a voice\n"
            "3. Type your message\n"
            "4. Get a downloadable MP3\n\n"
            "*Examples:*\n"
            "→ \"Good morning everyone\"\n"
            "→ \"Happy birthday my dear sister\"\n"
            "→ \"The meeting is at 3pm tomorrow\"\n\n"
            f"*Current voice:* {cur_country['flag']} *{cur_name}*")

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
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Tap one to select it.\n"
            "The ✅ shows your current voice.")

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
            "Translate text between 24 languages.\n\n"
            "*How to use:*\n"
            "1. Pick target language below\n"
            "2. Type your text\n"
            "3. Get instant translation\n\n"
            "*Examples:*\n"
            "→ \"Good morning\" → French = \"Bonjour\"\n"
            "→ \"How are you?\" → Yoruba = \"Báwo ni?\"\n"
            "→ \"Thank you\" → Hausa = \"Na gode\"")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- PDF PAGE ----------
def pdf_page(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✂️ Split PDF", callback_data="pdf_split"),
        types.InlineKeyboardButton("🗜 Compress PDF", callback_data="pdf_compress"),
        types.InlineKeyboardButton("🔄 Rotate PDF", callback_data="pdf_rotate"),
        types.InlineKeyboardButton("📸 PDF → Images", callback_data="pdf_pdf2img"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("📄 *PDF Suite*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Work with PDF files quickly.\n\n"
            "*Available actions:*\n"
            "✂️ Split — break into pages\n"
            "🗜 Compress — reduce file size\n"
            "🔄 Rotate — turn 90°\n"
            "📸 Convert — extract images\n\n"
            "⚠️ Max file size: 20 MB\n\n"
            "Tap an action, then send your PDF.")
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
            "Edit images quickly on Telegram.\n\n"
            "*Available actions:*\n"
            "🗜 Compress — smaller file\n"
            "📐 Resize — 50% smaller\n"
            "🔄 Convert — to JPG\n"
            "↩️ Rotate — turn 90°\n"
            "📄 Convert — Image to PDF\n\n"
            "⚠️ Max file size: 20 MB\n\n"
            "Tap an action, then send your image.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- SECURITY PAGE ----------
def security_page(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 Check Link", callback_data="sec_link"),
        types.InlineKeyboardButton("📸 Check Screenshot", callback_data="sec_screenshot"),
        types.InlineKeyboardButton("📚 Scam Alerts", callback_data="sec_scams"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("🛡️ *SAVIOUR Security Center*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Protect yourself from scams and fraud.\n\n"
            "🔗 *Check Link*\n"
            "Test any suspicious link before you click.\n"
            "Detects phishing sites, fake bank pages, "
            "and dangerous URLs.\n\n"
            "📸 *Check Screenshot*\n"
            "Analyze payment screenshots for red flags.\n"
            "Spots edited text, fake alerts, and common "
            "scam patterns.\n\n"
            "📚 *Scam Alerts*\n"
            "See the latest Nigerian scams and how to "
            "avoid them. Updated regularly.\n\n"
            "⚠️ *Important:*\n"
            "No tool catches every scam. Always verify "
            "in your bank app before releasing goods.\n\n"
            "Tap an option below 👇")
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
            "All files you've generated.\n\n"
            "✅ Stay here even if you change phones\n"
            "✅ Re-download anytime\n"
            "✅ Sorted by type\n\n"
            "Tap a category to see your files 👇")
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
        text = (f"📁 *No {file_type} files yet*\n\n"
                "Generate some and they'll show up here.")
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
            "Tap any file to open or download it.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- CV PAGE ----------
def cv_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 Create New CV", callback_data="cv_new"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("📝 *CV Builder*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Create a professional CV in minutes.\n\n"
            "*What you'll need:*\n"
            "• Your full name\n"
            "• Phone and email\n"
            "• Location (city, state)\n"
            "• Work experience\n"
            "• Education\n"
            "• Skills\n\n"
            "*Features:*\n"
            "✅ ATS-friendly format\n"
            "✅ Professional templates\n"
            "✅ Download as PDF\n"
            "✅ Ready in 5 minutes\n\n"
            "Tap below to start 👇")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- VOICE TRANSLATOR PAGE ----------
def voicetrans_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    langs = ["en", "fr", "es", "yo", "ig", "ha", "ar"]
    for code in langs:
        if code in TRANS_LANGS:
            markup.add(types.InlineKeyboardButton(
                TRANS_LANGS[code], callback_data=f"vt_{code}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))

    text = ("🎙 *Voice Translator*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Translate voice messages between languages.\n\n"
            "*How it works:*\n"
            "1. Pick target language\n"
            "2. Send a voice note\n"
            "3. Get translated voice back\n\n"
            "*Examples:*\n"
            "→ Yoruba voice → English voice\n"
            "→ English voice → French voice\n"
            "→ Hausa voice → Arabic voice\n\n"
            "Tap a target language 👇")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- QR CODE PAGE ----------
def qr_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 Link QR", callback_data="qr_link"),
        types.InlineKeyboardButton("📶 WiFi QR", callback_data="qr_wifi"),
        types.InlineKeyboardButton("👤 Contact QR", callback_data="qr_vcard"),
        types.InlineKeyboardButton("📝 Text QR", callback_data="qr_text"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="tools"),
    )
    text = ("🔲 *QR Code Studio*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Generate QR codes for anything.\n\n"
            "*Types:*\n"
            "🔗 Link — website, YouTube, etc.\n"
            "📶 WiFi — auto-connect to your WiFi\n"
            "👤 Contact — save your details\n"
            "📝 Text — any text\n\n"
            "Tap a type to start 👇")
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
            "📝 *Lyrics Finder*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Get synced lyrics with timestamps.\n\n"
            "*How to use:*\n"
            "Type the song name and artist,\n"
            "separated by a dash.\n\n"
            "*Examples:*\n"
            "→ `Shape of You - Ed Sheeran`\n"
            "→ `Blinding Lights - The Weeknd`\n"
            "→ `Essence - Wizkid`\n\n"
            "*What you get:*\n"
            "A `.lrc` file with timestamps — opens in "
            "Poweramp, Musicolet, and other players.\n\n"
            "*Type your song now:*",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "reply":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))
        keywords = get_away_keywords(uid)
        kw_text = "\n".join([f"• `{k['keyword']}` → {k['reply'][:30]}" for k in keywords]) or "_No keywords yet_"
        bot.edit_message_text(
            "💬 *Auto-Reply (Business)*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Set keyword replies for your Business DMs.\n"
            "When a customer messages you, the bot replies.\n\n"
            "*Current keywords:*\n" + kw_text + "\n\n"
            "*Commands:*\n"
            "`/setaway keyword | reply` — add\n"
            "`/editaway keyword | new reply` — edit\n"
            "`/delaway keyword` — delete one\n"
            "`/awaylist` — list all\n"
            "`/clearaway` — remove all",
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
                f"Type your text to translate 👇",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "pdf":
        pdf_page(chat_id, msg_id)
    elif c.data == "image":
        image_page(chat_id, msg_id)
    elif c.data == "security":
        security_page(chat_id, msg_id)
    elif c.data == "cv":
        cv_page(chat_id, uid, msg_id)
    elif c.data == "cv_new":
        set_mode(uid, "cv_form")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cv"))
        bot.edit_message_text(
            "📝 *CV Builder — Step 1 of 8*\n\n"
            "Type your *full name*:\n\n"
            "*Example:* John Doe Okonkwo",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "voicetrans":
        voicetrans_page(chat_id, uid, msg_id)
    elif c.data.startswith("vt_"):
        code = c.data.replace("vt_", "")
        if code in TRANS_LANGS:
            set_mode(uid, f"vt_{code}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="voicetrans"))
            bot.edit_message_text(
                f"🎙 *Voice Translator*\n\n"
                f"Target: {TRANS_LANGS[code]}\n\n"
                f"Send a voice note to translate 👇",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "qr":
        qr_page(chat_id, uid, msg_id)
    elif c.data.startswith("qr_"):
        qrtype = c.data.replace("qr_", "")
        set_mode(uid, f"qr_{qrtype}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="qr"))
        prompts = {
            "qr_link": "🔗 Send the URL to create a QR code for.\n\nExample: `https://example.com`",
            "qr_wifi": "📶 Send WiFi details in this format:\n\n`WiFiName | Password`\n\nExample: `MyWiFi | 12345678`",
            "qr_vcard": "👤 Send your details in this format:\n\n`Name | Phone | Email`\n\nExample: `John Doe | 08012345678 | john@example.com`",
            "qr_text": "📝 Send the text to encode in QR.",
        }
        bot.edit_message_text(
            prompts.get(qrtype, "Send your details"),
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "myfiles":
        my_files_page(chat_id, uid, msg_id)
    elif c.data.startswith("mf_"):
        ftype = c.data.replace("mf_", "")
        my_files_list(chat_id, uid, ftype, msg_id)
    elif c.data == "sec_link":
        set_mode(uid, "sec_link")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="security"))
        bot.edit_message_text(
            "🔗 *Link Checker*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send any link to check if it's safe.\n\n"
            "*How it works:*\n"
            "I compare the link against known\n"
            "phishing and malware databases.\n\n"
            "*Examples:*\n"
            "→ `opay-verify.xyz`\n"
            "→ `bvn-update.site`\n"
            "→ `https://example.com`\n\n"
            "Send a link now 👇",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "sec_screenshot":
        set_mode(uid, "sec_screenshot")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="security"))
        bot.edit_message_text(
            "📸 *Screenshot Checker*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send a payment screenshot to check\n"
            "for signs of editing or fraud.\n\n"
            "*What I check:*\n"
            "• Unusual text patterns\n"
            "• Wrong bank/app words\n"
            "• 'Pending' status warnings\n"
            "• Common scam phrases\n\n"
            "⚠️ I can only FLAG suspicious signs.\n"
            "Always verify in your bank app.\n\n"
            "Send a screenshot now 👇",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "sec_scams":
        show_scams(chat_id, msg_id)
    elif c.data.startswith("scampage_"):
        page = int(c.data.replace("scampage_", ""))
        show_scams(chat_id, msg_id, page)
    elif c.data.startswith("pdf_") or c.data.startswith("img_"):
        set_mode(uid, c.data)
        instruction = {
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
        back_target = "pdf" if c.data.startswith("pdf_") else "image"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_target))
        bot.edit_message_text(
            f"✅ *Ready*\n\n{instruction}",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

# ---------- SHOW SCAMS ----------
def show_scams(chat_id, message_id=None, page=0):
    scams = get_scam_alerts()
    if not scams:
        text = "📚 No scam alerts yet."
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, parse_mode="Markdown")
        return

    per_page = 3
    total_pages = (len(scams) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    page_items = scams[start:end]

    text = f"📚 *Scam Alerts* ({page+1}/{total_pages})\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for s in page_items:
        text += f"⚠️ *{s['title']}*\n{s['description']}\n\n"

    markup = types.InlineKeyboardMarkup(row_width=3)
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"scampage_{page-1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"scampage_{page+1}"))
    if nav:
        markup.row(*nav)
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="security"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

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

        # Clean filename from text
        safe_text = text[:40].strip()
        for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n']:
            safe_text = safe_text.replace(ch, '_')
        if not safe_text:
            safe_text = f"voice_{int(time.time())}"
        filename = f"{safe_text}.mp3"

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

# ---------- LYRICS (FIXED .LRC) ----------
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

    # Build clean LRC with proper metadata
    lrc_lines = []
    lrc_lines.append(f"[ti:{song['trackName']}]")
    lrc_lines.append(f"[ar:{song['artistName']}]")
    if song.get("albumName"):
        lrc_lines.append(f"[al:{song['albumName']}]")
    lrc_lines.append("[by:SAVIOUR Bot]")
    lrc_lines.append(f"[offset:0]")
    lrc_lines.append("")
    lrc_lines.append(raw)
    lrc_content = "\n".join(lrc_lines)

    filename = f"{song['artistName']} - {song['trackName']}.lrc".replace("/", "-")

    # UTF-8 with BOM — some players require this
    data_bytes = lrc_content.encode("utf-8-sig")
    file_bytes = io.BytesIO(data_bytes)
    file_bytes.name = filename

    bot.send_document(chat_id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}\n\n"
                f"✅ Rename to match your song file if needed\n"
                f"✅ Open in Poweramp, Musicolet, etc.")

    try:
        with open("temp_lrc.lrc", "wb") as f:
            f.write(data_bytes)
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
        error_msg = str(e)
        if "Too many requests" in error_msg or "429" in error_msg:
            bot.send_message(chat_id,
                "⚠️ *Translation service is busy*\n\n"
                "Google is temporarily limiting requests.\n"
                "Please try again in a few minutes.",
                parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"⚠️ Translation error: {e}")

# ---------- SECURITY: LINK CHECKER ----------
def check_link(uid, chat_id, url):
    if not can_use(uid, "security"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_SECURITY_LIMIT} checks/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return

    bot.send_message(chat_id, "🔍 Checking link...")

    # Check cache first
    cached = get_cached_link(url)
    if cached:
        bot.send_message(chat_id, cached, parse_mode="Markdown")
        return

    # Clean URL
    clean = url.strip()
    if not clean.startswith("http"):
        clean = "http://" + clean

    result_text = ""
    danger = False

    # 1. PhishStats
    if PHISHSTATS_KEY:
        try:
            r = requests.get(
                f"https://api.phishstats.info/api/phishing",
                params={"_where": f"url LIKE '%{clean}%'", "_size": 1},
                headers={"API-Key": PHISHSTATS_KEY},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data and len(data) > 0:
                    danger = True
                    result_text = "⚠️ *DANGEROUS*\n\nThis link matches known phishing patterns."
        except Exception as e:
            print("PhishStats error:", e, flush=True)

    # 2. URLhaus
    if not danger:
        try:
            r = requests.post(
                "https://urlhaus-api.abuse.ch/v1/url/",
                data={"url": clean},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("query_status") == "ok":
                    danger = True
                    result_text = "🚨 *DANGEROUS — MALWARE*\n\nThis link is flagged as malware."
        except Exception as e:
            print("URLhaus error:", e, flush=True)

    if not result_text:
        result_text = ("✅ *No threats found*\n\n"
                       "Still be careful with:\n"
                       "• Requests for passwords or OTPs\n"
                       "• Urgent payment demands\n"
                       "• Too-good-to-be-true offers")

    result_text = f"🔗 *Link Check Result*\n━━━━━━━━━━━━━━━━━━━━\n\n`{clean[:80]}`\n\n{result_text}"

    bot.send_message(chat_id, result_text, parse_mode="Markdown")
    cache_link(url, result_text)
    bump(uid, "security")

# ---------- SECURITY: SCREENSHOT CHECKER ----------
def check_screenshot(uid, chat_id, file_id):
    if not can_use(uid, "security"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_SECURITY_LIMIT} checks/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return

    bot.send_message(chat_id, "🔍 Analyzing screenshot...")

    try:
        info = bot.get_file(file_id)
        downloaded = bot.download_file(info.file_path)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Download failed: {e}")
        return

    try:
        img = Image.open(io.BytesIO(downloaded))
        img.save("screenshot.png")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Invalid image: {e}")
        return

    # Extract text using Tesseract
    text = ""
    try:
        import pytesseract
        text = pytesseract.image_to_string(img)
    except Exception as e:
        print("Tesseract error:", e, flush=True)
        bot.send_message(chat_id,
            "⚠️ *Screenshot reader unavailable*\n\n"
            "Please try again later.",
            parse_mode="Markdown")
        return

    if not text.strip():
        bot.send_message(chat_id,
            "🤔 Couldn't read text from this screenshot.\n\n"
            "Try a clearer image or a different screenshot.",
            parse_mode="Markdown")
        return

    text_low = text.lower()
    flags = []

    # Common scam phrases
    if "pending" in text_low or "processing" in text_low:
        flags.append("⚠️ 'Pending' or 'Processing' status — money not yet received")

    if "initiated" in text_low:
        flags.append("⚠️ 'Initiated' — not yet completed")

    if "reverse" in text_low or "reversal" in text_low:
        flags.append("⚠️ Reversal mentioned — verify in your bank")

    # Common bank names — check if suspicious spelling
    banks = ["opay", "palmpay", "gtbank", "access", "zenith", "uba", "first bank"]
    found_bank = False
    for b in banks:
        if b in text_low:
            found_bank = True
            break

    if not found_bank:
        flags.append("⚠️ No recognized bank name found")

    # Check for typos in common words
    if "successfull " in text_low and "successful " not in text_low.replace("successfull ", ""):
        flags.append("⚠️ Spelling error detected (possible fake)")

    result = "📸 *Screenshot Check*\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if flags:
        result += "*Red flags found:*\n"
        for f in flags:
            result += f"{f}\n"
        result += "\n⚠️ *This could be a fake screenshot.*\n"
        result += "*Verify in your bank app before releasing goods.*"
    else:
        result += "✅ *No obvious red flags found*\n\n"
        result += "⚠️ *Important:* No tool catches every fake.\n"
        result += "Always verify the money in your bank app."

    result += f"\n\n📝 *Text detected:*\n`{text[:200]}`"

    bot.send_message(chat_id, result, parse_mode="Markdown")
    bump(uid, "security")

# ---------- CV BUILDER ----------
CV_FIELDS = ["name", "phone", "email", "location", "title", "summary",
             "experience", "education", "skills", "certifications",
             "languages", "referees"]

CV_PROMPTS = {
    "name": ("📝 *CV Builder — Step 1 of 12*\n\n"
             "Type your *full name*:\n\n"
             "*Example:* John Doe Okonkwo"),
    "phone": ("📝 *Step 2 of 12*\n\n"
              "Type your *phone number*:\n\n"
              "*Example:* 08012345678"),
    "email": ("📝 *Step 3 of 12*\n\n"
              "Type your *email address*:\n\n"
              "*Example:* john@example.com"),
    "location": ("📝 *Step 4 of 12*\n\n"
                 "Type your *location*:\n\n"
                 "*Example:* Lagos, Nigeria"),
    "title": ("📝 *Step 5 of 12*\n\n"
              "Type your *professional title*:\n\n"
              "*Example:* Software Developer"),
    "summary": ("📝 *Step 6 of 12*\n\n"
                "Write a short *professional summary* (2-3 sentences):\n\n"
                "*Example:* Experienced software developer with 5 years "
                "building web applications. Skilled in Python and JavaScript."),
    "experience": ("📝 *Step 7 of 12*\n\n"
                   "List your *work experience*:\n\n"
                   "Format: Job Title | Company | Years\n"
                   "Separate multiple with new lines.\n\n"
                   "*Example:*\n"
                   "Sales Rep | XYZ Ltd | 2020-2022\n"
                   "Manager | ABC Corp | 2022-Present"),
    "education": ("📝 *Step 8 of 12*\n\n"
                  "List your *education*:\n\n"
                  "Format: Degree | School | Years\n\n"
                  "*Example:*\n"
                  "BSc Computer Science | University of Lagos | 2015-2019"),
    "skills": ("📝 *Step 9 of 12*\n\n"
               "List your *skills* (comma separated):\n\n"
               "*Example:* Python, Excel, Communication, Teamwork"),
    "certifications": ("📝 *Step 10 of 12*\n\n"
                       "List any *certifications*:\n\n"
                       "*Example:* Google Data Analytics (2023)\n"
                       "Or type `skip` if none"),
    "languages": ("📝 *Step 11 of 12*\n\n"
                  "List *languages* you speak:\n\n"
                  "*Example:* English (fluent), Yoruba (native), French (basic)"),
    "referees": ("📝 *Step 12 of 12*\n\n"
                 "List *referees*:\n\n"
                 "Format: Name | Position | Contact\n\n"
                 "*Example:* Dr. Jane Doe | Professor, UNILAG | jane@unilag.edu\n"
                 "Or type `skip` if none"),
}

# Store CV data temporarily per user
CV_DATA = {}

def start_cv(uid, chat_id):
    CV_DATA[uid] = {}
    set_mode(uid, "cv_form")
    bot.send_message(chat_id, CV_PROMPTS["name"], parse_mode="Markdown")

def handle_cv_step(uid, chat_id, text):
    if uid not in CV_DATA:
        CV_DATA[uid] = {}

    data = CV_DATA[uid]
    filled = len(data)
    if filled >= len(CV_FIELDS):
        # Already completed — restart
        CV_DATA[uid] = {}
        filled = 0

    field = CV_FIELDS[filled]
    data[field] = text.strip()

    next_index = filled + 1
    if next_index < len(CV_FIELDS):
        next_field = CV_FIELDS[next_index]
        bot.send_message(chat_id, CV_PROMPTS[next_field], parse_mode="Markdown")
    else:
        # All fields done — generate PDF
        generate_cv(uid, chat_id, data)

def generate_cv(uid, chat_id, data):
    if not can_use(uid, "cv"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_CV_LIMIT} CV/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        CV_DATA.pop(uid, None)
        return

    bot.send_message(chat_id, "📝 Generating your CV...")

    try:
        # Build PDF using PIL (simple text-based CV)
        from PIL import ImageDraw, ImageFont

        W, H = 1240, 1754  # A4 at 150 DPI
        img = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(img)

        # Try to load fonts, fallback to default
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        y = 60
        margin = 60

        # Name
        draw.text((margin, y), data.get("name", ""), fill="black", font=title_font)
        y += 50

        # Title
        draw.text((margin, y), data.get("title", ""), fill="gray", font=header_font)
        y += 40

        # Contact line
        contact = f"{data.get('phone','')} | {data.get('email','')} | {data.get('location','')}"
        draw.text((margin, y), contact, fill="black", font=body_font)
        y += 40

        # Divider
        draw.line([(margin, y), (W-margin, y)], fill="gray", width=1)
        y += 20

        # Summary
        if data.get("summary"):
            draw.text((margin, y), "PROFESSIONAL SUMMARY", fill="black", font=header_font)
            y += 35
            for line in wrap_text(data["summary"], 70):
                draw.text((margin, y), line, fill="black", font=body_font)
                y += 25
            y += 15

        # Experience
        if data.get("experience"):
            draw.text((margin, y), "WORK EXPERIENCE", fill="black", font=header_font)
            y += 35
            for line in data["experience"].split("\n"):
                if line.strip():
                    for wl in wrap_text(line.strip(), 70):
                        draw.text((margin, y), wl, fill="black", font=body_font)
                        y += 25
            y += 15

        # Education
        if data.get("education"):
            draw.text((margin, y), "EDUCATION", fill="black", font=header_font)
            y += 35
            for line in data["education"].split("\n"):
                if line.strip():
                    for wl in wrap_text(line.strip(), 70):
                        draw.text((margin, y), wl, fill="black", font=body_font)
                        y += 25
            y += 15

        # Skills
        if data.get("skills"):
            draw.text((margin, y), "SKILLS", fill="black", font=header_font)
            y += 35
            for line in wrap_text(data["skills"], 70):
                draw.text((margin, y), line, fill="black", font=body_font)
                y += 25
            y += 15

        # Certifications
        if data.get("certifications") and data["certifications"].lower() != "skip":
            draw.text((margin, y), "CERTIFICATIONS", fill="black", font=header_font)
            y += 35
            for line in wrap_text(data["certifications"], 70):
                draw.text((margin, y), line, fill="black", font=body_font)
                y += 25
            y += 15

        # Languages
        if data.get("languages"):
            draw.text((margin, y), "LANGUAGES", fill="black", font=header_font)
            y += 35
            for line in wrap_text(data["languages"], 70):
                draw.text((margin, y), line, fill="black", font=body_font)
                y += 25
            y += 15

        # Referees
        if data.get("referees") and data["referees"].lower() != "skip":
            draw.text((margin, y), "REFEREES", fill="black", font=header_font)
            y += 35
            for line in data["referees"].split("\n"):
                if line.strip():
                    for wl in wrap_text(line.strip(), 70):
                        draw.text((margin, y), wl, fill="black", font=body_font)
                        y += 25

        # Save as PDF
        pdf_name = data.get("name", "CV").replace(" ", "_") + "_CV.pdf"
        img.save("cv.pdf", "PDF", resolution=150.0)

        # Upload to Cloudinary
        cloud_url = upload_to_cloud("cv.pdf", resource_type="raw", folder="saviour/cv")

        with open("cv.pdf", "rb") as f:
            bot.send_document(chat_id, f,
                visible_file_name=pdf_name,
                caption="📝 Your CV is ready!\n\nEdit by sending /start → Tools → CV Builder")

        if cloud_url:
            save_file_record(uid, "cv", pdf_name, cloud_url)

        bump(uid, "cv")
        CV_DATA.pop(uid, None)
        set_mode(uid, "voice")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ CV generation error: {e}")
        CV_DATA.pop(uid, None)
        set_mode(uid, "voice")

def wrap_text(text, max_chars):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars:
            current += (" " if current else "") + w
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines

# ---------- VOICE TRANSLATOR ----------
def handle_voice_translate(uid, chat_id, file_id, target_lang):
    if not can_use(uid, "voicetrans"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_VOICETRANS_LIMIT} voice translations/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return

    bot.send_message(chat_id, "🎙 Processing voice...")

    try:
        info = bot.get_file(file_id)
        downloaded = bot.download_file(info.file_path)
        with open("input_voice.ogg", "wb") as f:
            f.write(downloaded)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Download failed: {e}")
        return

    # Step 1: Transcribe using Google Speech Recognition (via speech_recognition)
    transcript = ""
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
        # Convert OGG to WAV for recognition
        audio = AudioSegment.from_ogg("input_voice.ogg")
        audio.export("input_voice.wav", format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile("input_voice.wav") as source:
            audio_data = recognizer.record(source)
            transcript = recognizer.recognize_google(audio_data)
    except Exception as e:
        print("Transcription error:", e, flush=True)
        bot.send_message(chat_id,
            "⚠️ Could not transcribe this voice note.\n\n"
            "Try a clearer recording, or the language may not be supported.",
            parse_mode="Markdown")
        return

    if not transcript.strip():
        bot.send_message(chat_id, "⚠️ No speech detected.")
        return

    bot.send_message(chat_id, f"📝 Detected: _{transcript[:200]}_", parse_mode="Markdown")

    # Step 2: Translate
    try:
        time.sleep(1)
        translated = GoogleTranslator(source="auto", target=target_lang).translate(transcript)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Translation error: {e}")
        return

    # Step 3: Convert translated text to voice
    async def _make():
        voice_key = "ng_male"
        if target_lang == "fr":
            voice_key = "fr_denise"
        elif target_lang == "ar":
            voice_key = "sa_salma"
        elif target_lang == "es":
            voice_key = "es_elvira"
        elif target_lang == "en":
            voice_key = "us_aria"
        elif target_lang == "yo" or target_lang == "ig" or target_lang == "ha":
            voice_key = "ng_male"

        voice = VOICES.get(voice_key, VOICES["ng_male"])["voice"]
        communicate = edge_tts.Communicate(translated, voice)
        await communicate.save("translated_voice.mp3")

    try:
        asyncio.run(_make())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Voice generation failed: {e}")
        return

    # Send back
    result_text = (f"🎙 *Voice Translation*\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n\n"
                   f"📝 *Original:*\n{transcript[:300]}\n\n"
                   f"✅ *{TRANS_LANGS.get(target_lang, target_lang)}:*\n{translated[:300]}")

    bot.send_message(chat_id, result_text, parse_mode="Markdown")

    filename = f"translated_{int(time.time())}.mp3"
    with open("translated_voice.mp3", "rb") as f:
        bot.send_document(chat_id, f,
            visible_file_name=filename,
            caption="🎧 Translated voice")

    try:
        cloud_url = upload_to_cloud("translated_voice.mp3",
            resource_type="video", folder="saviour/voicetrans")
        if cloud_url:
            save_file_record(uid, "voicetrans", filename, cloud_url)
    except:
        pass

    bump(uid, "voicetrans")

# ---------- QR CODE ----------
def generate_qr(uid, chat_id, mode, content):
    if not can_use(uid, "qr"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_QR_LIMIT} QR codes/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return

    try:
        qr_data = content

        if mode == "qr_wifi":
            parts = content.split("|")
            if len(parts) < 2:
                bot.send_message(chat_id, "⚠️ Format: `WiFiName | Password`", parse_mode="Markdown")
                return
            ssid = parts[0].strip()
            pwd = parts[1].strip()
            qr_data = f"WIFI:T:WPA;S:{ssid};P:{pwd};;"

        elif mode == "qr_vcard":
            parts = content.split("|")
            if len(parts) < 2:
                bot.send_message(chat_id, "⚠️ Format: `Name | Phone | Email`", parse_mode="Markdown")
                return
            name = parts[0].strip()
            phone = parts[1].strip() if len(parts) > 1 else ""
            email = parts[2].strip() if len(parts) > 2 else ""
            qr_data = (f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\n"
                       f"TEL:{phone}\nEMAIL:{email}\nEND:VCARD")

        img = qrcode.make(qr_data)
        img.save("qr.png")

        with open("qr.png", "rb") as f:
            bot.send_photo(chat_id, f, caption="🔲 Your QR code")

        try:
            cloud_url = upload_to_cloud("qr.png",
                resource_type="image", folder="saviour/qr")
            if cloud_url:
                save_file_record(uid, "qr", f"qr_{int(time.time())}.png", cloud_url)
        except:
            pass

        bump(uid, "qr")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ QR error: {e}")

# ---------- PDF/IMAGE PROCESSOR ----------
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

# ---------- BUSINESS ----------
@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    try:
        if conn.is_enabled:
            save_business_connection(conn.id, conn.user.id)
            bot.send_message(conn.user.id,
                "✅ SAVIOUR connected to your Telegram Business.\n"
                "Use /setaway keyword | reply to set auto-replies.")
        else:
            remove_business_connection(conn.id)
    except Exception as e:
        print("Business conn error:", e, flush=True)

@bot.business_message_handler(func=lambda m: True)
def on_business_message(m):
    try:
        connection_id = m.business_connection_id
        owner_uid = get_business_owner(connection_id)
        if not owner_uid:
            print(f"No owner for connection {connection_id}", flush=True)
            return

        if m.text:
            reply = find_away_reply(owner_uid, m.text)
            if reply:
                bot.send_message(m.chat.id, reply,
                    business_connection_id=connection_id)
                return

        away = get_away_msg(owner_uid)
        if away:
            bot.send_message(m.chat.id, away,
                business_connection_id=connection_id)
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
        bot.reply_to(m,
            "💬 *Auto-Reply for Business*\n\n"
            "*Commands:*\n"
            "`/setaway keyword | reply` — add keyword\n"
            "`/setaway default text` — fallback reply\n"
            "`/editaway keyword | new reply` — edit\n"
            "`/delaway keyword` — delete one\n"
            "`/awaylist` — see all\n"
            "`/clearaway` — remove all",
            parse_mode="Markdown")
        return

    if "|" in text:
        keyword, reply = text.split("|", 1)
        add_away_keyword(uid, keyword.strip(), reply.strip())
        bot.reply_to(m, f"✅ Keyword `{keyword.strip()}` added.", parse_mode="Markdown")
    else:
        set_away_msg(uid, text)
        bot.reply_to(m, "✅ Default away message set!")

@bot.message_handler(commands=['editaway'])
def editaway_cmd(m):
    uid = m.from_user.id
    text = m.text.replace('/editaway', '', 1).strip()
    if "|" not in text:
        bot.reply_to(m, "Usage: `/editaway keyword | new reply`", parse_mode="Markdown")
        return
    keyword, reply = text.split("|", 1)
    add_away_keyword(uid, keyword.strip(), reply.strip())
    bot.reply_to(m, f"✅ Keyword `{keyword.strip()}` updated.", parse_mode="Markdown")

@bot.message_handler(commands=['delaway'])
def delaway_cmd(m):
    uid = m.from_user.id
    keyword = m.text.replace('/delaway', '', 1).strip()
    if not keyword:
        bot.reply_to(m, "Usage: `/delaway keyword`", parse_mode="Markdown")
        return
    if delete_away_keyword(uid, keyword):
        bot.reply_to(m, f"✅ Keyword `{keyword}` deleted.", parse_mode="Markdown")
    else:
        bot.reply_to(m, f"⚠️ Keyword `{keyword}` not found.", parse_mode="Markdown")

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

# ---------- /say /lrc ----------
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
        cur.execute("""SELECT user_id, username, first_name, paid, banned, last_seen
                       FROM users ORDER BY last_seen DESC LIMIT 20""")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = "👥 *Recent Users:*\n\n"
        for r in rows:
            tag = "💎" if r["paid"] else "👤"
            bn = "🚫" if r["banned"] else ""
            name = r["first_name"] or "—"
            uname = f"@{r['username']}" if r["username"] else "—"
            out += f"{tag}{bn} `{r['user_id']}`\n   {name} | {uname} | {r['last_seen']}\n\n"
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
        "*Away:*\n"
        "/editaway keyword | reply\n"
        "/delaway keyword\n\n"
        "*Channel:*\n"
        "/setchannel <id>\n"
        "/post <message>\n"
        "/schedule HH:MM | message\n\n"
        "*Scams:*\n"
        "/addscam Title | Description\n\n"
        "*System:*\n"
        "/maintenance on|off\n"
        "/synccommands",
        parse_mode="Markdown")

@bot.message_handler(commands=['maintenance'])
def maintenance_cmd(m):
    if not admin_only(m):
        return
    arg = m.text.replace('/maintenance', '', 1).strip().lower()
    if arg == "on":
        set_maintenance(True)
        bot.reply_to(m, "🛠 Maintenance mode ON")
    elif arg == "off":
        set_maintenance(False)
        bot.reply_to(m, "✅ Maintenance mode OFF")
    else:
        status = "ON" if get_maintenance() else "OFF"
        bot.reply_to(m, f"🛠 Maintenance: *{status}*", parse_mode="Markdown")

@bot.message_handler(commands=['synccommands'])
def synccommands_cmd(m):
    if not admin_only(m):
        return
    try:
        bot.delete_my_commands()
        bot.set_my_commands(PUBLIC_COMMANDS)
        bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        bot.reply_to(m, "✅ Commands synced for all users")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['addscam'])
def addscam_cmd(m):
    if not admin_only(m):
        return
    text = m.text.replace('/addscam', '', 1).strip()
    if "|" not in text:
        bot.reply_to(m, "Usage: `/addscam Title | Description`", parse_mode="Markdown")
        return
    title, desc = text.split("|", 1)
    if add_scam_alert(title.strip(), desc.strip()):
        bot.reply_to(m, "✅ Scam alert added.")
    else:
        bot.reply_to(m, "⚠️ Failed to add.")

# ---------- CHANNEL POSTER ----------
@bot.message_handler(commands=['setchannel'])
def setchannel_cmd(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    parts = m.text.replace('/setchannel', '', 1).strip().split()
    if not parts:
        bot.reply_to(m, "Usage: `/setchannel <channel_id>`", parse_mode="Markdown")
        return
    channel_id = parts[0]
    add_channel(uid, channel_id, parts[1] if len(parts) > 1 else channel_id)
    bot.reply_to(m, f"✅ Channel `{channel_id}` linked.", parse_mode="Markdown")

@bot.message_handler(commands=['post'])
def post_cmd(m):
    if m.from_user.id != ADMIN_ID:
        return
    text = m.text.replace('/post', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: `/post your message`", parse_mode="Markdown")
        return
    channels = get_channels(ADMIN_ID)
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
        bot.reply_to(m, "Usage: `/schedule HH:MM | message`", parse_mode="Markdown")
        return
    time_part, msg = text.split("|", 1)
    channels = get_channels(ADMIN_ID)
    if not channels:
        bot.reply_to(m, "⚠️ No channel linked.")
        return
    for ch in channels:
        add_scheduled(ch["channel_id"], time_part.strip(), msg.strip())
    bot.reply_to(m, f"✅ Scheduled for {time_part.strip()} daily.", parse_mode="Markdown")

# ---------- GROUP HANDLER ----------
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

    if text.startswith("/delkeyword"):
        if m.from_user.id != ADMIN_ID and not is_group_admin(m.chat.id, m.from_user.id):
            bot.reply_to(m, "⛔ Only admins.")
            return
        kw = text.replace("/delkeyword", "", 1).strip()
        if delete_group_keyword(m.chat.id, kw):
            bot.reply_to(m, f"✅ Keyword `{kw}` deleted.", parse_mode="Markdown")
        else:
            bot.reply_to(m, f"⚠️ Not found.", parse_mode="Markdown")
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

# ---------- FILE HANDLER ----------
@bot.message_handler(content_types=['document', 'photo', 'voice'])
def handle_file(m):
    uid = m.from_user.id
    if is_banned(uid):
        return

    mode = get_mode(uid)

    if m.content_type == 'voice':
        if mode.startswith("vt_"):
            target = mode.replace("vt_", "")
            handle_voice_translate(uid, m.chat.id, m.voice.file_id, target)
        return

    if m.content_type == 'document':
        file_id = m.document.file_id
        file_name = m.document.file_name or "file"
    else:
        file_id = m.photo[-1].file_id
        file_name = f"photo_{int(time.time())}.jpg"

    if mode == "sec_screenshot":
        check_screenshot(uid, m.chat.id, file_id)
        return

    if mode.startswith("pdf_") or mode.startswith("img_"):
        handle_pdf_image(uid, m.chat.id, mode, file_id, file_name)
    else:
        bot.reply_to(m, "Tap /start → Tools to use this file.")

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
    elif mode == "cv_form":
        handle_cv_step(uid, m.chat.id, text)
    elif mode == "sec_link":
        check_link(uid, m.chat.id, text)
    elif mode.startswith("qr_"):
        qrtype = mode
        generate_qr(uid, m.chat.id, qrtype, text)
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
