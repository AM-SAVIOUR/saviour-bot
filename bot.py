import os
import telebot
from telebot import types
import edge_tts
import asyncio
import requests
import io
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)

# ---------- MAIN MENU ----------
def main_menu(chat_id, message_id=None):
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
            "Choose a tool below:")
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
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "🎙 *Voice Tool*\n\nType:\n`/say your text here`\n\n"
            "Example: `/say Hello world`",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif c.data == "lyrics":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu"))
        bot.edit_message_text(
            "📝 *Lyrics Tool*\n\nType:\n`/lrc song name - artist`\n\n"
            "Example: `/lrc Shape of You - Ed Sheeran`\n\n"
            "You'll get back a `.lrc` file with timestamps.",
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

# ---------- VOICE TOOL ----------
@bot.message_handler(commands=['say'])
def say(m):
    text = m.text.replace('/say', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: `/say your text here`", parse_mode="Markdown")
        return
    bot.reply_to(m, "🎙 Generating voice...")

    async def make_voice():
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        await communicate.save("voice.mp3")

    try:
        asyncio.run(make_voice())
        with open("voice.mp3", "rb") as f:
            bot.send_voice(m.chat.id, f)
    except Exception as e:
        bot.reply_to(m, f"⚠️ Error: {e}")

# ---------- LYRICS TOOL ----------
@bot.message_handler(commands=['lrc'])
def lrc_cmd(m):
    query = m.text.replace('/lrc', '', 1).strip()
    if not query:
        bot.reply_to(m, "Usage: `/lrc song name - artist`", parse_mode="Markdown")
        return

    bot.reply_to(m, "🔎 Searching lyrics...")

    try:
        r = requests.get("https://lrclib.net/api/search",
                         params={"q": query}, timeout=15)
        data = r.json()
    except Exception as e:
        bot.reply_to(m, f"⚠️ Search error: {e}")
        return

    if not data:
        bot.reply_to(m, "❌ No lyrics found. Try `song name - artist`.",
                     parse_mode="Markdown")
        return

    song = None
    for item in data:
        if item.get("syncedLyrics"):
            song = item
            break

    if not song:
        bot.reply_to(m, "⚠️ Found the song but no synced (timestamped) lyrics available.")
        return

    filename = f"{song['artistName']} - {song['trackName']}.lrc"
    filename = filename.replace("/", "-").replace("\\", "-")

    file_bytes = io.BytesIO(song["syncedLyrics"].encode("utf-8"))
    file_bytes.name = filename

    bot.send_document(m.chat.id, file_bytes,
        caption=f"🎤 {song['trackName']} — {song['artistName']}\n⏱ Timestamps included")

# ---------- FALLBACK ----------
@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.reply_to(m, "Type /start to see the menu.")

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
