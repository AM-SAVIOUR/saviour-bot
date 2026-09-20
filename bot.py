import os
import telebot
from telebot import types
import edge_tts
import asyncio
import requests
import io
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://saviour-bot-014v.onrender.com")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Track which mode each user is in
user_mode = {}  # {chat_id: "voice" | "lyrics" | None}

# ---------- AUTO SET WEBHOOK ----------
def set_webhook():
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={
                "url": f"{RENDER_URL}/{BOT_TOKEN}",
                "allowed_updates": '["message","callback_query"]'
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
            "Tap a tool, then just type your message.\n"
            "No commands needed.")
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
        bot.edit_message_text(
            "🎙 *Voice Mode ON*\n\n"
            "Now just type your message — I'll turn it into a voice note.\n\n"
            "Example: `Good morning everyone`",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif c.data == "lyrics":
        user_mode[chat_id] = "lyrics"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "📝 *Lyrics Mode ON*\n\n"
            "Now just type the song name — I'll send the .lrc file.\n\n"
            "Example: `Shape of You - Ed Sheeran`",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif c.data == "reply":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "💬 *Auto-Reply*\n\nComing soon...",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif c.data == "upgrade":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "💎 *Premium*\n\nComing soon...",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

# ---------- VOICE FUNCTION ----------
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

# ---------- LYRICS FUNCTION ----------
def send_lrc(chat_id, query):
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
    lrc = f"[ti:{song['trackName']}]\n"
    lrc += f"[ar:{song['artistName']}]\n"
    lrc += f"[al:{song.get('albumName', '')}]\n"
    lrc += f"[by:SAVIOUR Bot]\n\n"
    lrc += raw

    filename = f"{song['artistName']} - {song['trackName']}.lrc"
    filename = filename.replace("/", "-").replace("\\", "-")

    # UTF-8 without BOM
    file_bytes = io.BytesIO(lrc.encode("utf-8"))
    file_bytes.name = filename

    bot.send_document(chat_id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}\n⏱ Timestamps included")

# ---------- STILL SUPPORT /say AND /lrc ----------
@bot.message_handler(commands=['say'])
def say_cmd(m):
    text = m.text.replace('/say', '', 1).strip()
    if text:
        make_voice_note(m.chat.id, text)

@bot.message_handler(commands=['lrc'])
def lrc_cmd(m):
    query = m.text.replace('/lrc', '', 1).strip()
    if query:
        send_lrc(m.chat.id, query)

# ---------- MAIN MESSAGE HANDLER ----------
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

    # Fallback — no mode set
    bot.reply_to(m, "Tap /start to choose a tool, or use the menu buttons.")

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
