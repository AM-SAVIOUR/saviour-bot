import os
import telebot
from telebot import types
from telebot.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
import edge_tts
import asyncio
import requests
import io
import json
import time
import datetime
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
import cloudinary
import cloudinary.uploader
from deep_translator import GoogleTranslator
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageDraw, ImageFont
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

AUTO_REPLY_TRIAL_HOURS = 48

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

# ---------- COMMAND MENU (FIXED) ----------
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

def register_commands():
    try:
        # Delete all existing scopes
        for scope in [None, BotCommandScopeDefault(),
                      BotCommandScopeAllPrivateChats(),
                      BotCommandScopeAllGroupChats()]:
            try:
                if scope is None:
                    bot.delete_my_commands()
                else:
                    bot.delete_my_commands(scope=scope)
            except:
                pass

        # Set public commands for everyone
        bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
        bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeAllPrivateChats())

        # Set admin commands for admin only
        bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

        print("Commands registered", flush=True)
    except Exception as e:
        print("Command register error:", e, flush=True)

register_commands()

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
                auto_reply_enabled INTEGER DEFAULT 1,
                auto_reply_trial_start TIMESTAMP,
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
                cv_data TEXT,
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

        # Games tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id SERIAL PRIMARY KEY,
                game_id TEXT UNIQUE,
                player1_id BIGINT,
                player2_id BIGINT,
                board TEXT DEFAULT '---------',
                turn BIGINT,
                status TEXT DEFAULT 'waiting',
                winner BIGINT,
                difficulty TEXT DEFAULT 'medium',
                vs_bot INTEGER DEFAULT 0,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_move TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                user_id BIGINT PRIMARY KEY,
                sp INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_played DATE DEFAULT CURRENT_DATE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_trivia (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                play_date DATE DEFAULT CURRENT_DATE,
                score INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                sessions_used INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_wordle (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                play_date DATE DEFAULT CURRENT_DATE,
                word TEXT,
                guesses TEXT DEFAULT '',
                solved INTEGER DEFAULT 0,
                tries_used INTEGER DEFAULT 0,
                sessions_used INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sp_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                reason TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_photos (
                user_id BIGINT PRIMARY KEY,
                cloud_url TEXT,
                uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

# ---------- AUTO REPLY PREMIUM GATE ----------
def can_use_auto_reply(uid):
    if uid == ADMIN_ID:
        return True, "admin"
    if is_paid(uid):
        return True, "premium"
    u = get_user(uid)
    if not u:
        return False, "no_user"
    trial_start = u.get("auto_reply_trial_start")
    if not trial_start:
        try:
            conn = db()
            cur = conn.cursor()
            cur.execute("""UPDATE users SET auto_reply_trial_start=NOW()
                           WHERE user_id=%s AND auto_reply_trial_start IS NULL""",
                        (uid,))
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass
        return True, "trial"
    elapsed = datetime.datetime.now() - trial_start
    if elapsed.total_seconds() < AUTO_REPLY_TRIAL_HOURS * 3600:
        hours_left = AUTO_REPLY_TRIAL_HOURS - (elapsed.total_seconds() / 3600)
        return True, f"trial_{int(hours_left)}h_left"
    return False, "trial_expired"

def toggle_auto_reply(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE users SET auto_reply_enabled =
                       CASE WHEN auto_reply_enabled=1 THEN 0 ELSE 1 END
                       WHERE user_id=%s RETURNING auto_reply_enabled""", (uid,))
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result["auto_reply_enabled"] if result else 0
    except Exception as e:
        print("toggle_auto_reply error:", e, flush=True)
        return 0

def is_auto_reply_enabled(uid):
    u = get_user(uid)
    return bool(u and u.get("auto_reply_enabled") == 1)

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
        print("save_business_connection error:", e, flush=True)

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
            ("Fake Investment", "Anyone promising 50%+ returns in days is running a Ponzi scheme."),
            ("Lottery/Promo Win", "You did not win a lottery you never entered. Delete such messages."),
            ("Fake Customs Officer", "Fake customs asking you to pay for parcel clearance. Verify with the real customs office."),
            ("Romance Scam", "Strangers on dating apps asking for money after a few chats."),
            ("Fake Loan App", "Loan apps that ask for your contacts and photos. Use only CBN-licensed lenders."),
            ("Fake Crypto Giveaway", "Fake Elon Musk or Binance giveaways asking you to send crypto first."),
            ("WhatsApp Account Theft", "Fake messages asking for your WhatsApp verification code."),
            ("Fake Telegram Premium", "Fake bots offering free Telegram Premium. They steal your account."),
            ("Fake POS Reversal", "Scammers claim they sent money to your POS and want a reversal."),
            ("Fake Delivery Fee", "Fake courier messages asking for delivery fees for packages you didn't order."),
            ("Fake School Fees", "Fake messages pretending to be from your child's school."),
            ("Fake Recruitment", "Fake military or police recruitment scams."),
            ("Fake Giveaway", "Social media giveaways asking for your bank details."),
            ("SIM Swap Fraud", "Fraudsters port your number to access your bank."),
            ("Fake Charity", "Fake charities asking for donations for fake causes."),
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

# ---------- TRIVIA API ----------
TRIVIA_FALLBACK = [
    {"q": "What is the capital of Nigeria?", "a": "Abuja",
     "options": ["Lagos", "Abuja", "Kano", "Ibadan"]},
    {"q": "Who was Nigeria's first president?", "a": "Nnamdi Azikiwe",
     "options": ["Nnamdi Azikiwe", "Olusegun Obasanjo", "Yakubu Gowon", "Sani Abacha"]},
    {"q": "What is the largest ocean?", "a": "Pacific",
     "options": ["Atlantic", "Indian", "Pacific", "Arctic"]},
    {"q": "How many continents are there?", "a": "7",
     "options": ["5", "6", "7", "8"]},
    {"q": "What year did Nigeria gain independence?", "a": "1960",
     "options": ["1957", "1960", "1963", "1970"]},
]

def fetch_trivia_questions():
    try:
        r = requests.get(
            "https://opentdb.com/api.php",
            params={"amount": 5, "type": "multiple"},
            timeout=10
        )
        data = r.json()
        if data.get("response_code") == 0:
            questions = []
            for item in data["results"]:
                correct = item["correct_answer"]
                incorrect = item["incorrect_answers"]
                options = [correct] + incorrect
                random.shuffle(options)
                questions.append({
                    "q": item["question"],
                    "a": correct,
                    "options": options
                })
            return questions
    except Exception as e:
        print("Trivia API error:", e, flush=True)

    # Fallback
    return random.sample(TRIVIA_FALLBACK, min(5, len(TRIVIA_FALLBACK)))

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

# ---------- GAME STATS ----------
def get_game_stats(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM game_stats WHERE user_id=%s", (uid,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO game_stats (user_id) VALUES (%s)", (uid,))
            conn.commit()
            cur.execute("SELECT * FROM game_stats WHERE user_id=%s", (uid,))
            row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print("get_game_stats error:", e, flush=True)
        return None

def add_sp(uid, amount, reason):
    if amount <= 0:
        return
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO game_stats (user_id, sp) VALUES (%s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET sp = game_stats.sp + %s""",
                    (uid, amount, amount))
        cur.execute("""INSERT INTO sp_log (user_id, amount, reason)
                       VALUES (%s, %s, %s)""",
                    (uid, amount, reason))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("add_sp error:", e, flush=True)

def record_game_result(uid, result, difficulty="medium"):
    try:
        conn = db()
        cur = conn.cursor()
        if result == "win":
            sp = {"easy": 1, "medium": 3, "hard": 5}.get(difficulty, 3)
            cur.execute("""INSERT INTO game_stats (user_id, wins, streak)
                           VALUES (%s, 1, 1)
                           ON CONFLICT (user_id) DO UPDATE SET
                           wins = game_stats.wins + 1,
                           streak = game_stats.streak + 1""", (uid,))
        elif result == "loss":
            cur.execute("""INSERT INTO game_stats (user_id, losses, streak)
                           VALUES (%s, 1, 0)
                           ON CONFLICT (user_id) DO UPDATE SET
                           losses = game_stats.losses + 1,
                           streak = 0""", (uid,))
        elif result == "draw":
            cur.execute("""INSERT INTO game_stats (user_id, draws)
                           VALUES (%s, 1)
                           ON CONFLICT (user_id) DO UPDATE SET
                           draws = game_stats.draws + 1""", (uid,))
        conn.commit()
        cur.close()
        conn.close()

        if result == "win":
            add_sp(uid, sp, f"tic_tac_toe_{difficulty}_win")
    except Exception as e:
        print("record_game_result error:", e, flush=True)

def get_leaderboard(limit=10):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT g.user_id, g.sp, u.first_name, u.username
                       FROM game_stats g
                       LEFT JOIN users u ON u.user_id = g.user_id
                       WHERE g.sp > 0
                       ORDER BY g.sp DESC LIMIT %s""", (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("get_leaderboard error:", e, flush=True)
        return []

# ---------- TRIVIA SESSIONS ----------
def get_trivia_sessions_today(uid):
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT sessions_used FROM daily_trivia
                       WHERE user_id=%s AND play_date=%s""",
                    (uid, today))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row["sessions_used"] if row else 0
    except:
        return 0

def increment_trivia_session(uid):
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO daily_trivia (user_id, play_date, sessions_used)
                       VALUES (%s, %s, 1)
                       ON CONFLICT DO NOTHING""", (uid, today))
        cur.execute("""UPDATE daily_trivia SET sessions_used = sessions_used + 1
                       WHERE user_id=%s AND play_date=%s""", (uid, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("increment_trivia error:", e, flush=True)

# ---------- TRIVIA ACTIVE SESSION (database) ----------
def save_trivia_session(uid, questions, current, score):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE daily_trivia SET
                       questions = %s,
                       current_q = %s,
                       score = %s,
                       in_progress = 1
                       WHERE user_id=%s AND play_date=%s""",
                    (json.dumps(questions), current, score, uid, datetime.date.today()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("save_trivia_session error:", e, flush=True)

def get_active_trivia(uid):
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT questions, current_q, score, in_progress
                       FROM daily_trivia
                       WHERE user_id=%s AND play_date=%s AND in_progress=1""",
                    (uid, today))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row["questions"]:
            return {
                "questions": json.loads(row["questions"]),
                "current": row["current_q"] or 0,
                "score": row["score"] or 0,
            }
        return None
    except Exception as e:
        print("get_active_trivia error:", e, flush=True)
        return None

def clear_active_trivia(uid):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE daily_trivia SET in_progress = 0
                       WHERE user_id=%s AND play_date=%s""",
                    (uid, datetime.date.today()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("clear_active_trivia error:", e, flush=True)

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
                "✅ Unlimited QR codes\n"
                "✅ Unlimited Auto-Reply\n\n"
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
            "✅ Unlimited QR codes\n"
            "✅ Unlimited Auto-Reply\n\n"
            "📋 *How to pay:*\n"
            f"1. Transfer {PRICE} to:\n"
            f"   🏦 {PAY_BANK}\n"
            f"   🔢 {PAY_ACCOUNT}\n"
            f"   👤 {PAY_NAME}\n\n"
            f"2. Send receipt to @{CREATOR}\n"
            "3. Wait for approval")

# ---------- MAIN MENU ----------
def main_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎙 Voice", callback_data="voice"),
        types.InlineKeyboardButton("📝 Lyrics", callback_data="lyrics"),
        types.InlineKeyboardButton("🔧 Tools", callback_data="tools"),
        types.InlineKeyboardButton("🎮 Games", callback_data="games"),
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
            "🛡️ Security — check suspicious links\n"
            "🎮 Games — play and earn SP\n\n"
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

def games_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("❌ Tic Tac Toe", callback_data="game_ttt"),
        types.InlineKeyboardButton("🎯 Daily Trivia", callback_data="game_trivia"),
        types.InlineKeyboardButton("🏆 Leaderboard", callback_data="game_lb"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="menu"),
    )
    text = ("🎮 *SAVIOUR Games*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Play, earn SP (SAVIOUR Points), climb the leaderboard.\n\n"
            "*Games:*\n"
            "❌ Tic Tac Toe — vs SAVIOUR\n"
            "🎯 Daily Trivia — 3 sessions/day\n\n"
            "*Earn SP:*\n"
            "❌ Easy win: +1 SP\n"
            "❌ Medium win: +3 SP\n"
            "❌ Hard win: +5 SP\n"
            "🎯 Correct answer: +2 SP\n"
            "🎯 Perfect 5/5: +5 bonus\n\n"
            "Tap a game to play 👇")
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
            "Turn text into voice notes in 32 voices.\n\n"
            "📝 *Lyrics Finder*\n"
            "Get synced lyrics for any song.\n\n"
            "🌍 *Translator*\n"
            "Translate between 24 languages.\n\n"
            "📄 *PDF Suite*\n"
            "Merge, split, compress, rotate PDFs.\n\n"
            "🖼 *Image Tools*\n"
            "Compress, resize, convert images.\n\n"
            "🛡️ *Security Center*\n"
            "Check links, screenshots, and learn about scams.\n\n"
            "📝 *CV Builder*\n"
            "Create professional CVs with your photo.\n\n"
            "🎙 *Voice Translator*\n"
            "Translate voice messages between languages.\n\n"
            "🔲 *QR Code*\n"
            "Generate QR codes for links, WiFi, contacts.\n\n"
            "🎮 *Games*\n"
            "Tic Tac Toe and Daily Trivia. Earn SP.\n\n"
            "📚 *My Files*\n"
            "Access all your past files anytime.\n\n"
            "💎 *Premium* — " + PRICE + "\n"
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
    markup.add(types.InlineKeyboardButton("📢 Add to Group/Channel", callback_data="setup_guide"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
    bot.send_message(m.chat.id, help_text(), reply_markup=markup, parse_mode="Markdown")

# ---------- PRIVACY ----------
@bot.message_handler(commands=['privacy'])
def privacy_cmd(m):
    bot.reply_to(m,
        "📜 *SAVIOUR Privacy Policy*\n\n"
        f"Read it here:\n{PRIVACY_URL}",
        parse_mode="Markdown")

# ---------- CHANNEL/GROUP SETUP GUIDE ----------
def setup_guide_text():
    return ("📢 *Add SAVIOUR to Your Group or Channel*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*👥 FOR GROUPS:*\n\n"
            "1. Open your group\n"
            "2. Tap \"Add Members\"\n"
            "3. Search: @" + bot.get_me().username + "\n"
            "4. Add it\n"
            "5. Make it admin (recommended)\n\n"
            "Then in the group:\n"
            "→ `/addkeyword word | reply` — add auto-reply\n"
            "→ `/listkeywords` — see all\n"
            "→ `/delkeyword word` — remove one\n\n"
            "*📢 FOR CHANNELS:*\n\n"
            "1. Open your channel\n"
            "2. Administrators → Add Admin\n"
            "3. Search: @" + bot.get_me().username + "\n"
            "4. Grant \"Post Messages\" permission\n\n"
            "✅ *That's it!* SAVIOUR will confirm automatically.\n\n"
            "Then use:\n"
            "→ `/post Your message` — post now\n"
            "→ `/schedule 09:00 | Daily post` — schedule\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *No channel ID needed.*\n"
            "SAVIOUR detects your channel when you add it.")

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
            "Test any suspicious link before you click.\n\n"
            "📸 *Check Screenshot*\n"
            "Analyze payment screenshots for red flags.\n\n"
            "📚 *Scam Alerts*\n"
            "See the latest Nigerian scams.\n\n"
            "⚠️ *Important:*\n"
            "No tool catches every scam. Always verify "
            "in your bank app before releasing goods.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

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
            "Test any suspicious link before you click.\n\n"
            "📸 *Check Screenshot*\n"
            "Analyze payment screenshots for red flags.\n\n"
            "📚 *Scam Alerts*\n"
            "See the latest Nigerian scams.\n\n"
            "⚠️ *Important:*\n"
            "No tool catches every scam. Always verify "
            "in your bank app before releasing goods.")
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
            "✅ Sorted by type")
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
            "• Your photo (optional)\n"
            "• Full name, phone, email\n"
            "• Location, experience, education\n"
            "• Skills, certifications\n\n"
            "*Features:*\n"
            "✅ ATS-friendly format\n"
            "✅ Add your photo\n"
            "✅ Download as PDF\n\n"
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
            "→ English voice → French voice\n\n"
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

# ---------- TIC TAC TOE PAGE ----------
def ttt_page(chat_id, uid, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 Play vs SAVIOUR", callback_data="ttt_bot_menu"),
        types.InlineKeyboardButton("📊 My Stats", callback_data="ttt_stats"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="games"),
    )
    stats = get_game_stats(uid)
    sp = stats["sp"] if stats else 0
    wins = stats["wins"] if stats else 0
    losses = stats["losses"] if stats else 0

    text = ("❌ *Tic Tac Toe* ⭕\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Play against SAVIOUR.\n\n"
            f"*Your Stats:*\n"
            f"🏅 SP: {sp}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {losses}\n\n"
            "*SP Rewards:*\n"
            "Easy win: +1 SP\n"
            "Medium win: +3 SP\n"
            "Hard win: +5 SP\n"
            "Draw: +1 SP")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def ttt_bot_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🟢 Easy (+1 SP)", callback_data="ttt_new_bot_easy"),
        types.InlineKeyboardButton("🟡 Medium (+3 SP)", callback_data="ttt_new_bot_medium"),
        types.InlineKeyboardButton("🔴 Hard (+5 SP)", callback_data="ttt_new_bot_hard"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="game_ttt"),
    )
    text = ("🤖 *Play vs SAVIOUR*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose difficulty:\n\n"
            "🟢 *Easy* — Random moves, easy to win\n"
            "🟡 *Medium* — Blocks your wins sometimes\n"
            "🔴 *Hard* — Nearly unbeatable\n\n"
            "More SP for harder difficulty!")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- TRIVIA PAGE ----------
def trivia_page(chat_id, uid, message_id=None):
    used = get_trivia_sessions_today(uid)
    remaining = max(0, 3 - used)

    # Check if there's an active session
    active = get_active_trivia(uid)

    markup = types.InlineKeyboardMarkup(row_width=1)
    if active:
        markup.add(types.InlineKeyboardButton("▶️ Continue Trivia",
            callback_data="trivia_continue"))
    elif remaining > 0:
        markup.add(types.InlineKeyboardButton("▶️ Start Trivia",
            callback_data="trivia_start"))
    else:
        markup.add(types.InlineKeyboardButton("❌ No sessions left today",
            callback_data="games"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="games"))

    text = ("🎯 *Daily Trivia*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Answer 5 questions per session.\n\n"
            "*Rewards:*\n"
            "✅ Correct answer: +2 SP\n"
            "🎉 Perfect 5/5: +5 SP bonus\n\n"
            f"*Sessions left today:* {remaining}/3\n\n"
            "New sessions reset at midnight.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- LEADERBOARD ----------
def leaderboard_page(chat_id, uid, message_id=None):
    rows = get_leaderboard(10)
    if not rows:
        text = ("🏆 *Leaderboard*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "No players yet.\n"
                "Play a game to appear here!")
    else:
        text = ("🏆 *Leaderboard — All Time*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n")
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            pos = medals[i] if i < 3 else f"{i+1}."
            name = r["first_name"] or r["username"] or f"User{r['user_id']}"
            sp = r["sp"]
            you = " ← you" if r["user_id"] == uid else ""
            text += f"{pos} {name} — {sp} SP{you}\n"

        text += "\n*Daily rewards:*\n"
        text += "🥇 3 free Premium days\n"
        text += "🥈 2 free Premium days\n"
        text += "🥉 1 free Premium day"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="game_lb"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="games"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------- TIC TAC TOE LOGIC ----------
def ttt_board_keyboard(board, game_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i, cell in enumerate(board):
        if cell == "X":
            label = "❌"
        elif cell == "O":
            label = "⭕"
        else:
            label = "⬜"
        row.append(types.InlineKeyboardButton(label, callback_data=f"ttt_move_{game_id}_{i}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    markup.row(types.InlineKeyboardButton("🏳️ Forfeit", callback_data=f"ttt_forfeit_{game_id}"))
    return markup

def ttt_check_winner(board):
    lines = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for a,b,c in lines:
        if board[a] != "-" and board[a] == board[b] == board[c]:
            return board[a]
    if "-" not in board:
        return "draw"
    return None

def ttt_bot_move(board, difficulty):
    empty = [i for i, c in enumerate(board) if c == "-"]
    if not empty:
        return None

    if difficulty == "easy":
        return random.choice(empty)

    # Medium/Hard: check if bot can win
    def find_winning_move(symbol):
        for i in empty:
            test = list(board)
            test[i] = symbol
            if ttt_check_winner(test) == symbol:
                return i
        return None

    # Win move
    win = find_winning_move("O")
    if win is not None:
        return win

    # Block player win
    block = find_winning_move("X")
    if block is not None:
        return block

    if difficulty == "medium":
        if random.random() < 0.5:
            return random.choice(empty)

    # Hard: take center or corner
    if 4 in empty:
        return 4
    corners = [i for i in [0,2,6,8] if i in empty]
    if corners:
        return random.choice(corners)
    return random.choice(empty)

def create_ttt_game(uid, vs_bot, difficulty):
    game_id = f"{uid}_{int(time.time())}"
    board = "---------"
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO games (game_id, player1_id, board, turn,
                       status, vs_bot, difficulty)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (game_id, uid, board, uid, "playing" if vs_bot else "waiting",
                     1 if vs_bot else 0, difficulty))
        conn.commit()
        cur.close()
        conn.close()
        return game_id
    except Exception as e:
        print("create_ttt_game error:", e, flush=True)
        return None

def get_ttt_game(game_id):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM games WHERE game_id=%s", (game_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except:
        return None

def update_ttt_game(game_id, board, turn, status, winner=None):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE games SET board=%s, turn=%s, status=%s,
                       winner=%s, last_move=NOW() WHERE game_id=%s""",
                    (board, turn, status, winner, game_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("update_ttt_game error:", e, flush=True)

def render_ttt(chat_id, game, message_id=None):
    board = game["board"]
    winner = ttt_check_winner(board)

    if winner == "X":
        text = "🎉 *You win!* 🎉"
        status = "won"
    elif winner == "O":
        text = "😢 *SAVIOUR wins!*"
        status = "lost"
    elif winner == "draw":
        text = "🤝 *It's a draw!*"
        status = "draw"
    else:
        turn = "Your turn" if game["turn"] == game["player1_id"] else "Opponent's turn"
        text = f"❌ *Tic Tac Toe* ⭕\n\n{turn}"

    markup = ttt_board_keyboard(board, game["game_id"])
    if winner:
        markup.add(types.InlineKeyboardButton("🔄 Play again",
            callback_data=f"ttt_again_{game['difficulty']}"))
        markup.add(types.InlineKeyboardButton("⬅️ Games menu", callback_data="games"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id,
                reply_markup=markup, parse_mode="Markdown")
        except:
            pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    return winner

def process_ttt_move(uid, chat_id, game_id, position, message_id):
    game = get_ttt_game(game_id)
    if not game:
        bot.send_message(chat_id, "⚠️ Game not found.")
        return

    if game["status"] not in ["playing", "waiting"]:
        return

    board = list(game["board"])
    if board[position] != "-":
        return

    # Player move (X)
    board[position] = "X"
    winner = ttt_check_winner(board)

    if winner == "X":
        update_ttt_game(game_id, "".join(board), game["turn"], "won", uid)
        record_game_result(uid, "win", game["difficulty"])
        game = get_ttt_game(game_id)
        render_ttt(chat_id, game, message_id)
        return
    elif winner == "draw":
        update_ttt_game(game_id, "".join(board), game["turn"], "draw")
        record_game_result(uid, "draw", game["difficulty"])
        game = get_ttt_game(game_id)
        render_ttt(chat_id, game, message_id)
        return

    # Bot move if vs_bot
    if game["vs_bot"]:
        bot_pos = ttt_bot_move(board, game["difficulty"])
        if bot_pos is not None:
            board[bot_pos] = "O"

        winner = ttt_check_winner(board)
        if winner == "O":
            update_ttt_game(game_id, "".join(board), game["turn"], "lost")
            record_game_result(uid, "loss", game["difficulty"])
        elif winner == "draw":
            update_ttt_game(game_id, "".join(board), game["turn"], "draw")
            record_game_result(uid, "draw", game["difficulty"])
        else:
            update_ttt_game(game_id, "".join(board), game["turn"], "playing")

        game = get_ttt_game(game_id)
        render_ttt(chat_id, game, message_id)

# ---------- TRIVIA LOGIC (database-based) ----------
def start_trivia(uid, chat_id, message_id=None):
    used = get_trivia_sessions_today(uid)
    if used >= 3:
        bot.send_message(chat_id, "❌ No trivia sessions left today. Come back tomorrow!")
        return

    questions = fetch_trivia_questions()
    if not questions:
        bot.send_message(chat_id, "⚠️ Could not load questions. Try again later.")
        return

    # Save session to database
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO daily_trivia
                       (user_id, play_date, sessions_used, questions, current_q, score, total, in_progress)
                       VALUES (%s, %s, 1, %s, 0, 0, %s, 1)
                       ON CONFLICT DO NOTHING""",
                    (uid, today, json.dumps(questions), len(questions)))
        cur.execute("""UPDATE daily_trivia SET
                       questions = %s,
                       current_q = 0,
                       score = 0,
                       total = %s,
                       in_progress = 1
                       WHERE user_id=%s AND play_date=%s""",
                    (json.dumps(questions), len(questions), uid, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("start_trivia save error:", e, flush=True)

    send_trivia_question(uid, chat_id)

def send_trivia_question(uid, chat_id):
    active = get_active_trivia(uid)
    if not active:
        return

    questions = active["questions"]
    idx = active["current"]
    score = active["score"]

    if idx >= len(questions):
        finish_trivia(uid, chat_id)
        return

    q = questions[idx]
    options = q["options"][:4]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(options):
        markup.add(types.InlineKeyboardButton(
            opt[:60], callback_data=f"triv_ans_{i}"))

    text = (f"🎯 *Question {idx+1}/5*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{q['q'][:300]}\n\n"
            f"Score: {score}/{idx}")

    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text, reply_markup=markup)

def answer_trivia(uid, chat_id, answer_index, message_id):
    active = get_active_trivia(uid)
    if not active:
        bot.edit_message_text("⚠️ Session expired.", chat_id, message_id)
        return

    questions = active["questions"]
    idx = active["current"]
    score = active["score"]

    if idx >= len(questions):
        return

    q = questions[idx]
    correct_answer = q["a"]
    given = q["options"][answer_index] if answer_index < len(q["options"]) else ""

    if given == correct_answer:
        score += 1
        add_sp(uid, 2, "trivia_correct")
        result = f"✅ *Correct!*\n\nThe answer is: {correct_answer}"
    else:
        result = f"❌ *Wrong!*\n\nCorrect answer: {correct_answer}"

    try:
        bot.edit_message_text(result, chat_id, message_id, parse_mode="Markdown")
    except:
        try:
            bot.edit_message_text(result, chat_id, message_id)
        except:
            pass

    # Update database with new progress
    idx += 1
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE daily_trivia SET current_q=%s, score=%s
                       WHERE user_id=%s AND play_date=%s""",
                    (idx, score, uid, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("answer_trivia update error:", e, flush=True)

    time.sleep(1)
    send_trivia_question(uid, chat_id)

def finish_trivia(uid, chat_id):
    active = get_active_trivia(uid)
    if not active:
        return

    questions = active["questions"]
    score = active["score"]
    total = len(questions)

    if score == total:
        add_sp(uid, 5, "trivia_perfect")

    increment_trivia_session(uid)
    clear_active_trivia(uid)

    text = (f"🎉 *Trivia Complete!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Score: {score}/{total}\n"
            f"SP earned: {score * 2}")

    if score == total:
        text += " + 5 bonus"

    text += "\n\n"

    if score == total:
        text += "🏆 *PERFECT SCORE!* +5 bonus SP\n\n"
    text += "Come back tomorrow for more!"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏆 Leaderboard", callback_data="game_lb"))
    markup.add(types.InlineKeyboardButton("⬅️ Games", callback_data="games"))

    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text, reply_markup=markup)

# ---------- TRIVIA LOGIC (database-based) ----------
def start_trivia(uid, chat_id, message_id=None):
    used = get_trivia_sessions_today(uid)
    if used >= 3:
        bot.send_message(chat_id, "❌ No trivia sessions left today. Come back tomorrow!")
        return

    questions = fetch_trivia_questions()
    if not questions:
        bot.send_message(chat_id, "⚠️ Could not load questions. Try again later.")
        return

    # Save session to database
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO daily_trivia
                       (user_id, play_date, sessions_used, questions, current_q, score, total, in_progress)
                       VALUES (%s, %s, 1, %s, 0, 0, %s, 1)
                       ON CONFLICT DO NOTHING""",
                    (uid, today, json.dumps(questions), len(questions)))
        cur.execute("""UPDATE daily_trivia SET
                       questions = %s,
                       current_q = 0,
                       score = 0,
                       total = %s,
                       in_progress = 1
                       WHERE user_id=%s AND play_date=%s""",
                    (json.dumps(questions), len(questions), uid, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("start_trivia save error:", e, flush=True)

    send_trivia_question(uid, chat_id)

def send_trivia_question(uid, chat_id):
    active = get_active_trivia(uid)
    if not active:
        return

    questions = active["questions"]
    idx = active["current"]
    score = active["score"]

    if idx >= len(questions):
        finish_trivia(uid, chat_id)
        return

    q = questions[idx]
    options = q["options"][:4]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(options):
        markup.add(types.InlineKeyboardButton(
            opt[:60], callback_data=f"triv_ans_{i}"))

    text = (f"🎯 *Question {idx+1}/5*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{q['q'][:300]}\n\n"
            f"Score: {score}/{idx}")

    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text, reply_markup=markup)

def answer_trivia(uid, chat_id, answer_index, message_id):
    active = get_active_trivia(uid)
    if not active:
        bot.edit_message_text("⚠️ Session expired.", chat_id, message_id)
        return

    questions = active["questions"]
    idx = active["current"]
    score = active["score"]

    if idx >= len(questions):
        return

    q = questions[idx]
    correct_answer = q["a"]
    given = q["options"][answer_index] if answer_index < len(q["options"]) else ""

    if given == correct_answer:
        score += 1
        add_sp(uid, 2, "trivia_correct")
        result = f"✅ *Correct!*\n\nThe answer is: {correct_answer}"
    else:
        result = f"❌ *Wrong!*\n\nCorrect answer: {correct_answer}"

    try:
        bot.edit_message_text(result, chat_id, message_id, parse_mode="Markdown")
    except:
        try:
            bot.edit_message_text(result, chat_id, message_id)
        except:
            pass

    # Update database with new progress
    idx += 1
    today = datetime.date.today()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE daily_trivia SET current_q=%s, score=%s
                       WHERE user_id=%s AND play_date=%s""",
                    (idx, score, uid, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("answer_trivia update error:", e, flush=True)

    time.sleep(1)
    send_trivia_question(uid, chat_id)

def finish_trivia(uid, chat_id):
    active = get_active_trivia(uid)
    if not active:
        return

    questions = active["questions"]
    score = active["score"]
    total = len(questions)

    if score == total:
        add_sp(uid, 5, "trivia_perfect")

    increment_trivia_session(uid)
    clear_active_trivia(uid)

    text = (f"🎉 *Trivia Complete!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Score: {score}/{total}\n"
            f"SP earned: {score * 2}")

    if score == total:
        text += " + 5 bonus"

    text += "\n\n"

    if score == total:
        text += "🏆 *PERFECT SCORE!* +5 bonus SP\n\n"
    text += "Come back tomorrow for more!"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏆 Leaderboard", callback_data="game_lb"))
    markup.add(types.InlineKeyboardButton("⬅️ Games", callback_data="games"))

    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text, reply_markup=markup)

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

    data = c.data

    # Menu navigation
    if data == "menu":
        main_menu(chat_id, msg_id)
    elif data == "tools":
        tools_menu(chat_id, msg_id)
    elif data == "games":
        games_menu(chat_id, msg_id)
    elif data == "voice":
        set_mode(uid, "voice")
        voice_countries_page(chat_id, uid, msg_id)
    elif data.startswith("vc_"):
        ck = data.replace("vc_", "")
        if ck in COUNTRIES:
            voice_list_page(chat_id, uid, ck, msg_id)
    elif data.startswith("setvoice_"):
        key = data.replace("setvoice_", "")
        if key in VOICES:
            set_voice_key(uid, key)
            voice_list_page(chat_id, uid, VOICES[key]["country"], msg_id)
    elif data == "lyrics":
        set_mode(uid, "lyrics")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "📝 *Lyrics Finder*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Get synced lyrics with timestamps.\n\n"
            "*How to use:*\n"
            "Type the song name and artist, separated by a dash.\n\n"
            "*Examples:*\n"
            "→ `Shape of You - Ed Sheeran`\n"
            "→ `Blinding Lights - The Weeknd`\n"
            "→ `Essence - Wizkid`\n\n"
            "*What you get:*\n"
            "A `.lrc` file with timestamps — works with Lark Player, "
            "Poweramp, Musicolet, and more.\n\n"
            "*Type your song now:*",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "reply":
        set_mode(uid, "reply")
        show_auto_reply_page(chat_id, uid, msg_id)
    elif data == "upgrade":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(premium_text(uid), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif data == "help":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Add to Group/Channel", callback_data="setup_guide"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(help_text(), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif data == "setup_guide":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="help"))
        bot.edit_message_text(setup_guide_text(), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif data == "translate":
        set_mode(uid, "translate")
        translate_lang_page(chat_id, uid, msg_id)
    elif data.startswith("tr_"):
        code = data.replace("tr_", "")
        if code in TRANS_LANGS:
            set_mode(uid, f"tr_{code}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="translate"))
            bot.edit_message_text(
                f"🌍 *Translator*\n\n"
                f"Target: {TRANS_LANGS[code]}\n\n"
                f"Type your text to translate 👇",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "pdf":
        pdf_page(chat_id, msg_id)
    elif data == "image":
        image_page(chat_id, msg_id)
    elif data == "security":
        security_page(chat_id, msg_id)
    elif data == "cv":
        cv_page(chat_id, uid, msg_id)
    elif data == "cv_new":
        # Clear any existing CV data
        clear_cv_data(uid)
        set_mode(uid, "cv_photo")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⏭ Skip photo", callback_data="cv_skip_photo"))
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cv"))
        bot.edit_message_text(
            "📝 *CV Builder — Step 1 of 13*\n\n"
            "Send your *profile photo*, or tap Skip.\n\n"
            "📸 Best size: square, clear face",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "cv_skip_photo":
        save_cv_data(uid, {"photo_url": None})
        set_mode(uid, "cv_form")
        bot.edit_message_text(
            CV_PROMPTS["name"], chat_id, msg_id, parse_mode="Markdown")
    elif data == "voicetrans":
        voicetrans_page(chat_id, uid, msg_id)
    elif data.startswith("vt_"):
        code = data.replace("vt_", "")
        if code in TRANS_LANGS:
            set_mode(uid, f"vt_{code}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="voicetrans"))
            bot.edit_message_text(
                f"🎙 *Voice Translator*\n\n"
                f"Target: {TRANS_LANGS[code]}\n\n"
                f"Send a voice note to translate 👇",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "qr":
        qr_page(chat_id, uid, msg_id)
    elif data.startswith("qr_"):
        qrtype = data.replace("qr_", "")
        set_mode(uid, f"qr_{qrtype}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="qr"))
        prompts = {
            "qr_link": "🔗 Send the URL for the QR code.\n\nExample: `https://example.com`",
            "qr_wifi": "📶 Send WiFi details:\n\n`WiFiName | Password`\n\nExample: `MyWiFi | 12345678`",
            "qr_vcard": "👤 Send your details:\n\n`Name | Phone | Email`\n\nExample: `John Doe | 08012345678 | john@example.com`",
            "qr_text": "📝 Send the text to encode.",
        }
        bot.edit_message_text(prompts.get(qrtype, "Send your details"),
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "myfiles":
        my_files_page(chat_id, uid, msg_id)
    elif data.startswith("mf_"):
        ftype = data.replace("mf_", "")
        my_files_list(chat_id, uid, ftype, msg_id)
    elif data == "sec_link":
        set_mode(uid, "sec_link")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="security"))
        bot.edit_message_text(
            "🔗 *Link Checker*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send any link to check if it's safe.\n\n"
            "*I check:*\n"
            "• Phishing databases\n"
            "• Malware databases\n"
            "• Shortened links (followed)\n\n"
            "*Examples:*\n"
            "→ `opay-verify.xyz`\n"
            "→ `bit.ly/abc123`\n\n"
            "Send a link now 👇",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "sec_screenshot":
        set_mode(uid, "sec_screenshot")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="security"))
        bot.edit_message_text(
            "📸 *Screenshot Checker*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send a payment screenshot to check for red flags.\n\n"
            "*What I check:*\n"
            "• Unusual text patterns\n"
            "• 'Pending' status\n"
            "• Common scam phrases\n\n"
            "⚠️ I can only FLAG suspicious signs.\n"
            "Always verify in your bank app.\n\n"
            "Send a screenshot now 👇",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif data == "sec_scams":
        show_scams(chat_id, msg_id)
    elif data.startswith("scampage_"):
        page = int(data.replace("scampage_", ""))
        show_scams(chat_id, msg_id, page)
    elif data.startswith("pdf_") or data.startswith("img_"):
        set_mode(uid, data)
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
        }.get(data, "Send your file")
        markup = types.InlineKeyboardMarkup()
        back_target = "pdf" if data.startswith("pdf_") else "image"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_target))
        bot.edit_message_text(
            f"✅ *Ready*\n\n{instruction}",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    # Games
    elif data == "game_ttt":
        ttt_page(chat_id, uid, msg_id)
    elif data == "ttt_bot_menu":
        ttt_bot_menu(chat_id, msg_id)
    elif data.startswith("ttt_new_bot_"):
        difficulty = data.replace("ttt_new_bot_", "")
        game_id = create_ttt_game(uid, True, difficulty)
        if not game_id:
            bot.send_message(chat_id, "⚠️ Could not create game.")
            return
        game = get_ttt_game(game_id)
        render_ttt(chat_id, game, msg_id)
    elif data.startswith("ttt_move_"):
        parts = data.replace("ttt_move_", "").split("_")
        game_id = parts[0] + "_" + parts[1]
        pos = int(parts[2])
        process_ttt_move(uid, chat_id, game_id, pos, msg_id)
    elif data.startswith("ttt_forfeit_"):
        game_id = data.replace("ttt_forfeit_", "")
        game = get_ttt_game(game_id)
        if game:
            update_ttt_game(game_id, game["board"], game["turn"], "forfeit", 0)
            record_game_result(uid, "loss", game["difficulty"])
            bot.edit_message_text("🏳️ You forfeited.", chat_id, msg_id)
    elif data.startswith("ttt_again_"):
        difficulty = data.replace("ttt_again_", "")
        game_id = create_ttt_game(uid, True, difficulty)
        game = get_ttt_game(game_id)
        render_ttt(chat_id, game, msg_id)
    elif data == "ttt_stats":
        stats = get_game_stats(uid)
        text = (f"📊 *Your Tic Tac Toe Stats*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏅 SP: {stats['sp']}\n"
                f"✅ Wins: {stats['wins']}\n"
                f"❌ Losses: {stats['losses']}\n"
                f"🤝 Draws: {stats['draws']}\n"
                f"🔥 Current Streak: {stats['streak']}\n"
                f"⭐ Best Streak: {stats['best_streak']}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="game_ttt"))
        bot.edit_message_text(text, chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
    elif data == "game_trivia":
        trivia_page(chat_id, uid, msg_id)
    elif data == "trivia_start":
        start_trivia(uid, chat_id, msg_id)
    elif data == "trivia_continue":
        send_trivia_question(uid, chat_id)
    elif data.startswith("triv_ans_"):
        idx = int(data.replace("triv_ans_", ""))
        answer_trivia(uid, chat_id, idx, msg_id)
    elif data == "game_lb":
        leaderboard_page(chat_id, uid, msg_id)
    # Auto-Reply toggle
    elif data == "ar_off":
        set_auto_reply(uid, 0)
        show_auto_reply_page(chat_id, uid, msg_id)
    elif data == "ar_on":
        set_auto_reply(uid, 1)
        show_auto_reply_page(chat_id, uid, msg_id)

def set_auto_reply(uid, value):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET auto_reply_enabled=%s WHERE user_id=%s",
                    (value, uid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("set_auto_reply error:", e, flush=True)

def show_auto_reply_page(chat_id, uid, message_id=None):
    allowed, status = can_use_auto_reply(uid)
    enabled = is_auto_reply_enabled(uid)

    if not allowed:
        text = ("💬 *Auto-Reply (Business)*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔒 *Premium Feature*\n\n"
                "Your 48-hour free trial has ended.\n\n"
                "Upgrade to Premium to continue using Auto-Reply.\n\n"
                f"💎 *{PRICE}*\n"
                f"Pay to: {PAY_ACCOUNT} ({PAY_BANK})\n"
                f"Contact: @{CREATOR}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Upgrade", callback_data="upgrade"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))
    else:
        status_line = ""
        if status == "trial":
            status_line = "🆓 Free trial just started!"
        elif status.startswith("trial_"):
            status_line = f"🆓 Free trial: {status.replace('trial_', '')}"
        elif status == "premium":
            status_line = "💎 Premium user"
        elif status == "admin":
            status_line = "👑 Admin account"

        state_line = "✅ *ON*" if enabled else "❌ *OFF*"

        keywords = get_away_keywords(uid)
        kw_text = "\n".join([f"• `{k['keyword']}` → {k['reply'][:30]}"
                            for k in keywords]) or "_No keywords yet_"

        text = ("💬 *Auto-Reply (Business)*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "When a customer DMs your Telegram Business, "
                "the bot replies automatically.\n\n"
                f"Status: {state_line}\n"
                f"{status_line}\n\n"
                f"*Keywords set:*\n{kw_text}\n\n"
                "*Commands:*\n"
                "`/setaway keyword | reply` — add\n"
                "`/editaway keyword | new reply` — edit\n"
                "`/delaway keyword` — delete one\n"
                "`/awaylist` — list all\n"
                "`/clearaway` — remove all")

        markup = types.InlineKeyboardMarkup(row_width=2)
        if enabled:
            markup.add(types.InlineKeyboardButton("❌ Turn OFF", callback_data="ar_off"))
        else:
            markup.add(types.InlineKeyboardButton("✅ Turn ON", callback_data="ar_on"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="tools"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id,
                reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

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

# ---------- LYRICS (LARK PLAYER FIX) ----------
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

    lrc_lines = []
    lrc_lines.append(f"[ti:{song['trackName']}]")
    lrc_lines.append(f"[ar:{song['artistName']}]")
    if song.get("albumName"):
        lrc_lines.append(f"[al:{song['albumName']}]")
    lrc_lines.append("[by:SAVIOUR Bot]")
    lrc_lines.append("[offset:0]")
    lrc_lines.append("")
    lrc_lines.append(raw)
    lrc_content = "\n".join(lrc_lines)

    filename = f"{song['artistName']} - {song['trackName']}.lrc".replace("/", "-")

    # Plain UTF-8 WITHOUT BOM — fixes Lark Player "invalid" error
    data_bytes = lrc_content.encode("utf-8")
    file_bytes = io.BytesIO(data_bytes)
    file_bytes.name = filename

    bot.send_document(chat_id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}\n\n"
                f"✅ Rename to match your song file\n"
                f"✅ Works with Lark Player, Poweramp, Musicolet")

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

# ---------- TRANSLATE (with retry) ----------
def do_translate(uid, chat_id, text, target_code):
    if not can_use(uid, "translate"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_TRANSLATE_LIMIT} translations/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return
    bot.send_message(chat_id, "🌍 Translating...")

    translated = None
    for attempt in range(3):
        try:
            time.sleep(2)
            translated = GoogleTranslator(source="auto", target=target_code).translate(text)
            break
        except Exception as e:
            err = str(e)
            if "Too many requests" in err or "429" in err:
                if attempt < 2:
                    time.sleep(10)
                    continue
                bot.send_message(chat_id,
                    "⚠️ *Translation service is busy*\n\n"
                    "Please try again in a few minutes.",
                    parse_mode="Markdown")
                return
            else:
                bot.send_message(chat_id, f"⚠️ Translation error: {e}")
                return

    if not translated:
        return

    result = (f"🌍 *Translation*\n"
              f"━━━━━━━━━━━━━━━━━━━━\n\n"
              f"📝 *Original:*\n{text[:500]}\n\n"
              f"✅ *{TRANS_LANGS.get(target_code, target_code)}:*\n{translated[:500]}")
    bot.send_message(chat_id, result, parse_mode="Markdown")
    bump(uid, "translate")

# ---------- SECURITY: LINK CHECKER (FIXED) ----------
def extract_domain(url):
    try:
        if "://" in url:
            domain = url.split("://")[1].split("/")[0]
        else:
            domain = url.split("/")[0]
        return domain.lower()
    except:
        return url.lower()

def follow_redirect(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        return r.url
    except:
        try:
            r = requests.get(url, allow_redirects=True, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"},
                             stream=True)
            return r.url
        except:
            return url

SHORTENERS = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
              "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at"]

def check_link(uid, chat_id, url):
    if not can_use(uid, "security"):
        bot.send_message(chat_id,
            f"🔒 *Free limit reached*\n\n"
            f"Free: {FREE_SECURITY_LIMIT} checks/day\n\n"
            f"💎 Upgrade — {PRICE}\nContact @{CREATOR}",
            parse_mode="Markdown")
        return

    bot.send_message(chat_id, "🔍 Checking link...")

    clean = url.strip()
    if not clean.startswith("http"):
        clean = "http://" + clean

    # Follow shorteners
    real_url = clean
    original_domain = extract_domain(clean)
    if any(s in original_domain for s in SHORTENERS):
        real_url = follow_redirect(clean)

    domain = extract_domain(real_url)
    domain_no_www = domain.replace("www.", "")

    # Check cache
    cached = get_cached_link(real_url)
    if cached:
        bot.send_message(chat_id, cached, parse_mode="Markdown")
        return

    danger_score = 0
    reason = ""

    # PhishStats
    if PHISHSTATS_KEY:
        try:
            r = requests.get(
                "https://api.phishstats.info/api/phishing",
                params={"_where": f"url LIKE '%{domain_no_www}%'", "_size": 1},
                headers={"API-Key": PHISHSTATS_KEY},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data and len(data) > 0:
                    score = data[0].get("score", 0)
                    if score >= 6:
                        danger_score = 10
                        reason = "Phishing database match"
                    elif score >= 4:
                        danger_score = 5
                        reason = "Suspicious pattern"
        except Exception as e:
            print("PhishStats error:", e, flush=True)

    # URLhaus
    if danger_score < 6:
        try:
            r = requests.post(
                "https://urlhaus-api.abuse.ch/v1/url/",
                data={"url": real_url},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("query_status") == "ok":
                    danger_score = 10
                    reason = "Malware detected"
        except Exception as e:
            print("URLhaus error:", e, flush=True)

    # Build response
    if danger_score >= 6:
        verdict = "⚠️ *DANGEROUS*"
        advice = ("Do NOT enter any personal information.\n"
                  "Do NOT send money.\n"
                  "Verify with the official app instead.")
    elif danger_score >= 4:
        verdict = "❓ *SUSPICIOUS*"
        advice = ("Be careful. This link shows some warning signs.\n"
                  "Only proceed if you trust the source.")
    else:
        verdict = "✅ *No threats found*"
        advice = ("Still be careful with:\n"
                  "• Requests for passwords or OTPs\n"
                  "• Urgent payment demands\n"
                  "• Too-good-to-be-true offers")

    result_text = f"🔗 *Link Check Result*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    result_text += f"URL: `{clean[:80]}`\n"
    if real_url != clean:
        result_text += f"→ Redirects to: `{real_url[:80]}`\n"
    result_text += f"Domain: `{domain_no_www}`\n\n"
    result_text += f"{verdict}\n\n{advice}"

    if reason:
        result_text += f"\n\n_Reason: {reason}_"

    bot.send_message(chat_id, result_text, parse_mode="Markdown")
    cache_link(real_url, result_text)
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
            "Try a clearer image.",
            parse_mode="Markdown")
        return

    text_low = text.lower()
    flags = []

    if "pending" in text_low or "processing" in text_low:
        flags.append("⚠️ 'Pending' or 'Processing' status — money not yet received")

    if "initiated" in text_low:
        flags.append("⚠️ 'Initiated' — not yet completed")

    if "reverse" in text_low or "reversal" in text_low:
        flags.append("⚠️ Reversal mentioned — verify in your bank")

    banks = ["opay", "palmpay", "gtbank", "access", "zenith", "uba", "first bank"]
    found_bank = any(b in text_low for b in banks)

    if not found_bank:
        flags.append("⚠️ No recognized bank name found")

    result = "📸 *Screenshot Check*\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if flags:
        result += "*Red flags found:*\n"
        for f in flags:
            result += f"{f}\n"
        result += "\n⚠️ *This could be a fake screenshot.*\n"
        result += "*Verify in your bank app before releasing goods.*"
    else:
        result += "✅ *No obvious red flags found*\n\n"
        result += "⚠️ No tool catches every fake.\n"
        result += "Always verify the money in your bank app."

    result += f"\n\n📝 *Text detected:*\n`{text[:200]}`"

    bot.send_message(chat_id, result, parse_mode="Markdown")
    bump(uid, "security")
