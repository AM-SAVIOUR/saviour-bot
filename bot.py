import os
import telebot
from telebot import types
import edge_tts
import asyncio
import requests
import io
import sqlite3
import datetime
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

user_mode = {}

# ---------- BUSINESS: who connected ----------
business_owner = {}  # {business_connection_id: owner_user_id}

# ---------- AUTO SET WEBHOOK ----------
def set_webhook():
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={
                "url": f"{RENDER_URL}/{BOT_TOKEN}",
                "allowed_updates": '["message","callback_query","business_connection","business_message"]'
            },
            timeout=10
        )
        print("Webhook set:", r.json())
    except Exception as e:
        print("Webhook error:", e)

set_webhook()

# ---------- MAIN MENU ----------
def main_menu(chat_id, message_id=None):
    user_mode[chat_id] = None
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎙 Voice", callback_data="voice"),
        types.InlineKeyboardButton("📝 Lyrics", callback_data="lyrics"),
        types.InlineKeyboardButton("💬 Auto-Reply", callback_data="reply"),
        types.InlineKeyboardButton("💎 Premium", callback_data="upgrade"),
    )
    text = ("🌑 *Welcome to SAVIOUR*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your all-in-one assistant.\n\n"
            "Tap a tool, then just type your message.")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m):
    main_menu(m.chat.id)

# ---------- BUTTON HANDLER ----------
@bot.callback_query_handler(func=lambda c: True)
def handle(c):
    bot.answer_callback_query(c.id)
    chat_id = c.message.chat.id
    msg_id = c.message.message_id

    if c.data == "menu":
        main_menu(chat_id, msg_id)
    elif c.data == "voice":
        user_mode[chat_id] = "voice"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text("🎙 *Voice Mode ON*\n\nType your message.",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "lyrics":
        user_mode[chat_id] = "lyrics"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text("📝 *Lyrics Mode ON*\n\nType: song - artist",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "reply":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "💬 *Auto-Reply (Business)*\n\n"
            "To use this:\n"
            "1. Go to Telegram Settings\n"
            "2. Telegram Business → Chatbots\n"
            "3. Add this bot\n"
            "4. Set your away message here\n\n"
            "Coming in the next version.",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "upgrade":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text("💎 *Premium*\n\nComing soon...",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

# ---------- VOICE ----------
def make_voice_note(chat_id, text):
    bot.send_message(chat_id, "🎙 Generating voice...")
    async def _make():
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        await communicate.save("voice.mp3")
    try:
        asyncio.run(_make())
        with open("voice.mp3", "rb") as f:
            bot.send_voice(chat_id, f)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Error: {e}")

# ---------- LYRICS ----------
def send_lrc(chat_id, query):
    bot.send_message(chat_id, "🔎 Searching lyrics...")
    try:
        r = requests.get("https://lrclib.net/api/search", params={"q": query}, timeout=15)
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

# ---------- BUSINESS CONNECTION HANDLER ----------
@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    """Fires when a user connects/disconnects their Business account to the bot"""
    try:
        print(f"Business connection event: {conn}")
        business_owner[conn.id] = conn.user.id
        if conn.is_enabled:
            bot.send_message(conn.user.id,
                "✅ SAVIOUR is now connected to your Telegram Business.\n\n"
                "Set your away message using /setaway on this bot.")
    except Exception as e:
        print("Business connection error:", e)

# ---------- BUSINESS MESSAGE HANDLER ----------
@bot.business_message_handler(func=lambda m: True)
def on_business_message(m):
    """Fires when a customer sends a message to your connected Business account"""
    try:
        connection_id = m.business_connection_id
        # Reply automatically using saved away message
        away = get_away_message(connection_id)
        if away:
            bot.send_message(
                m.chat.id,
                away,
                business_connection_id=connection_id
            )
    except Exception as e:
        print("Business message error:", e)

# ---------- AWAY MESSAGE STORAGE ----------
AWAY_MESSAGES = {}

def set_away_message(connection_id, text):
    AWAY_MESSAGES[connection_id] = text

def get_away_message(connection_id):
    return AWAY_MESSAGES.get(connection_id)

# ---------- /setaway COMMAND (owner only) ----------
@bot.message_handler(commands=['setaway'])
def set_away_cmd(m):
    text = m.text.replace('/setaway', '', 1).strip()
    if not text:
        bot.reply_to(m,
            "Usage: `/setaway Your message here`\n\n"
            "Example: `/setaway Hi, I'm currently away. I'll reply soon.`",
            parse_mode="Markdown")
        return
    # Find owner's connection
    for conn_id, owner_id in business_owner.items():
        if owner_id == m.from_user.id:
            set_away_message(conn_id, text)
            bot.reply_to(m, "✅ Away message set!")
            return
    bot.reply_to(m, "⚠️ No business connection found. Connect the bot to your Telegram Business first.")

# ---------- /say /lrc still work ----------
@bot.message_handler(commands=['say'])
def say_cmd(m):
    text = m.text.replace('/say', '', 1).strip()
    if text:
        make_voice_note(m.chat.id, text)

@bot.message_handler(commands=['lrc'])
def lrc_cmd(m):
    q = m.text.replace('/lrc', '', 1).strip()
    if q:
        send_lrc(m.chat.id, q)

# ---------- MAIN HANDLER ----------
@bot.message_handler(func=lambda m: True)
def handle_message(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    if not text:
        return
    mode = user_mode.get(chat_id)
    if mode == "voice":
        make_voice_note(chat_id, text)
        return
    if mode == "lyrics":
        send_lrc(chat_id, text)
        return
    bot.reply_to(m, "Tap /start to choose a tool.")

# ---------- WEBHOOK ----------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/")
def index():
    return "SAVIOUR is running", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
