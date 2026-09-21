import os
import telebot
from telebot import types
import edge_tts
import asyncio
import requests
import io
import json
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")
CREATOR 👑 = "I_AM_SAVIOUR_1"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

user_mode = {}
business_owner = {}
AWAY_MESSAGES = {}

# ---------- AUTO SET WEBHOOK ----------
def set_webhook():
    try:
        allowed = json.dumps([
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages"
        ])
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            data={
                "url": f"{RENDER_URL}/{BOT_TOKEN}",
                "allowed_updates": allowed
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
        types.InlineKeyboardButton("❓ Help", callback_data="help"),
    )
    text = ("🌑 *Welcome to SAVIOUR*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your all-in-one assistant.\n\n"
            "Tap a tool, then just type your message.\n\n"
            f"👑 *Creator:* @{CREATOR}")
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m):
    main_menu(m.chat.id)

# ---------- HELP PAGE ----------
def help_text():
    return ("❓ *SAVIOUR — Help Guide*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎙 *Voice Tool*\n"
            "Turn any text into a voice note.\n"
            "→ Tap Voice, then type your message\n"
            "→ Or use `/say your text`\n\n"
            "📝 *Lyrics Tool*\n"
            "Get a synced `.lrc` file for any song.\n"
            "→ Tap Lyrics, then type: song - artist\n"
            "→ Or use `/lrc song - artist`\n"
            "→ Opens in Poweramp, Musicolet, etc.\n\n"
            "💬 *Auto-Reply (Business)*\n"
            "Replies to your Telegram Business DMs when you're away.\n"
            "→ Connect the bot in Settings → Telegram Business\n"
            "→ Set your message: `/setaway your text`\n\n"
            "💎 *Premium*\n"
            "Unlimited use of all tools. Coming soon.\n\n"
            "❓ *Need more help?*\n"
            f"Contact the creator: @{CREATOR}\n\n"
            f"👑 *Created by:* @{CREATOR}")

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
            "Set your away message with:\n"
            "`/setaway your message`\n\n"
            "When someone DMs your connected Business account, "
            "the bot replies for you.",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "upgrade":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text("💎 *Premium*\n\nComing soon...",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    elif c.data == "help":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(help_text(), chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")

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

# ---------- BUSINESS CONNECTION ----------
@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(conn):
    try:
        print(f"BUSINESS CONNECTION: id={conn.id} user={conn.user.id} enabled={conn.is_enabled}")
        if conn.is_enabled:
            business_owner[conn.id] = conn.user.id
            bot.send_message(conn.user.id,
                "✅ SAVIOUR connected to your Telegram Business.\n"
                "Use /setaway to set your auto-reply message.")
        else:
            business_owner.pop(conn.id, None)
    except Exception as e:
        print("Business connection error:", e)

# ---------- BUSINESS MESSAGE ----------
@bot.business_message_handler(func=lambda m: True)
def on_business_message(m):
    try:
        connection_id = m.business_connection_id
        print(f"BUSINESS MESSAGE: from={m.chat.id} text={m.text}")
        away = AWAY_MESSAGES.get(connection_id)
        if away:
            bot.send_message(m.chat.id, away, business_connection_id=connection_id)
            print("Auto-reply sent.")
    except Exception as e:
        print("Business message error:", e)

# ---------- /setaway ----------
@bot.message_handler(commands=['setaway'])
def set_away_cmd(m):
    text = m.text.replace('/setaway', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: `/setaway Your message here`", parse_mode="Markdown")
        return
    if not business_owner:
        bot.reply_to(m, "⚠️ No business connection found. Connect the bot to your Telegram Business first.")
        return
    for conn_id in business_owner:
        AWAY_MESSAGES[conn_id] = text
    bot.reply_to(m, "✅ Away message set!")

# ---------- /say /lrc ----------
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
