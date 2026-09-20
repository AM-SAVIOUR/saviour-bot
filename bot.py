import os
import telebot
from telebot import types
import edge_tts
import asyncio
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(m):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎙 Voice", callback_data="voice"),
        types.InlineKeyboardButton("📝 Lyrics", callback_data="lyrics"),
        types.InlineKeyboardButton("💬 Auto-Reply", callback_data="reply"),
        types.InlineKeyboardButton("💎 Premium", callback_data="upgrade"),
    )
    bot.send_message(m.chat.id,
        "🌑 *Welcome to SAVIOUR*\n━━━━━━━━━━━━━━━━━━━━\n\nYour all-in-one assistant.",
        reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['say'])
def say(m):
    text = m.text.replace('/say', '', 1).strip()
    if not text:
        bot.reply_to(m, "Usage: /say your text here")
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

@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.reply_to(m, "Type /start to see the menu.")

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
    try:
        asyncio.run(make_voice())
        with open("voice.mp3", "rb") as f:
            bot.send_voice(m.chat.id, f)
    except Exception as e:
        bot.reply_to(m, f"⚠️ Error: {e}")

@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.reply_to(m, "Type /start to see the menu.")

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
