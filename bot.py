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
