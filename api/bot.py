import os
import re
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from http.server import BaseHTTPRequestHandler
import json

print("FILE LOADED 🔥")

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')

USER_TEXT = {}
LAST_TITLE = {}
LAST_BODY = {}
USER_SETTINGS = {}

SET_PROMPT = 1

# -------- DEFAULT PROMPT --------
DEFAULT_PROMPT = """
You are STRICTLY a DEAL POST REWRITER.

TASK:
Rewrite the given text ONLY. Treat input as a deal/offer post.

FORMAT:
- FIRST LINE = TITLE  
- REMAINING = BODY

RULES:
- You MUST paraphrase – change sentence structure & wording  
- Keep meaning, price, coupon, and ALL links EXACTLY same  
- Same language as original (Hindi/Hinglish/English)  
- add some Light emojis allowed  
- Keep {length_rule}

DO NOT:
- Add any new information  
- Add benefits, CTA, or marketing claims  
- Ask questions or suggestions  
- Write help/tutorial/community text  
- Act like an assistant  
- Use words like "Part 1/Title/Body"  
- Repeat sentences from original as-is

If input is non-deal content, still rewrite it as neutral text without adding opinions.

Rewrite ONLY the provided content.
"""


# ================= AI CALL =================

async def call_ai(text, user_id, mode="normal"):

    links = re.findall(r'https?://\S+', text)

    setting = USER_SETTINGS.get(user_id, {})
    custom_prompt = setting.get("prompt", DEFAULT_PROMPT)

    length_rule = "normal length"
    if mode == "short":
        length_rule = "very short"

    prompt = f"""
{custom_prompt}

Extra Rule: {length_rule}

ORIGINAL POST:
{text}
"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",

            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },

            json={
                "model": "openai/gpt-4o-mini",

                "messages": [
                    {"role": "user", "content": prompt}
                ],

                "temperature": 0.7
            },

            timeout=60
        )

        data = response.json()

        output = data["choices"][0]["message"]["content"]

        if not output:
            return "AI empty response"

        # ---- Link Protection ----
        for link in links:
            output = re.sub(r'https?://\S+', link, output, count=1)

        return output

    except Exception as e:
        return f"Rewrite error: {str(e)}"


# ================= BUTTONS =================

def buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔁 Another Style", callback_data="again"),
            InlineKeyboardButton("🩳 Short", callback_data="short")
        ],
        [
            InlineKeyboardButton("📋 Copy Title", callback_data="copy_title"),
            InlineKeyboardButton("📋 Copy Body", callback_data="copy_body")
        ]
    ])


# ================= HANDLERS =================

async def handle_message(update, context):

    message = update.message
    text = message.text or message.caption

    user_id = message.from_user.id

    new_text = await call_ai(text, user_id)

    parts = new_text.split("\n", 1)

    title = parts[0].strip()
    body = parts[1].strip()

    LAST_TITLE[user_id] = title
    LAST_BODY[user_id] = body
    USER_TEXT[user_id] = text

    await message.reply_text(
        f"TITLE:\n{title}\n\nBODY:\n{body}",
        reply_markup=buttons()
    )


# ===== SETTINGS SYSTEM =====

async def settings(update, context):

    await update.message.reply_text("""
⚙️ COMMANDS

/setprompt – Custom prompt  
/clearprompt – Default
""")


async def ask_prompt(update, context):
    await update.message.reply_text("Apna custom prompt likho 👇")
    return SET_PROMPT


async def save_prompt(update, context):

    user_id = update.message.from_user.id
    text = update.message.text

    USER_SETTINGS.setdefault(user_id, {})
    USER_SETTINGS[user_id]["prompt"] = text

    await update.message.reply_text("✅ Custom prompt saved!")
    return ConversationHandler.END


async def clear_prompt(update, context):

    user_id = update.message.from_user.id

    USER_SETTINGS.setdefault(user_id, {})
    USER_SETTINGS[user_id]["prompt"] = DEFAULT_PROMPT

    await update.message.reply_text("Default prompt restore ho gaya")


# ===== CALLBACKS =====

async def again_callback(update, context):
    await handle_message(update, context)

async def short_callback(update, context):
    await handle_message(update, context)

async def copy_title(update, context):

    user_id = update.callback_query.from_user.id
    await update.callback_query.message.reply_text(
        LAST_TITLE.get(user_id, "")
    )

async def copy_body(update, context):

    user_id = update.callback_query.from_user.id
    await update.callback_query.message.reply_text(
        LAST_BODY.get(user_id, "")
    )


# ========== HANDLER REGISTRATION FUNCTION ==========
bot = Bot(token=TELEGRAM_TOKEN)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):

    try:
        print("👉 POST RECEIVED")

        content_length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(content_length)

        print("RAW BODY:", body)

        data = json.loads(body)

        print("JSON:", data)

        update = Update.de_json(data, bot)

        # ----- HANDLE MESSAGE -----
        if update.message:
            text = update.message.text or ""
            chat_id = update.message.chat_id

            print("TEXT:", text)

            new = call_ai(text)

            parts = new.split("\n", 1)

            title = parts[0]
            body = parts[1] if len(parts) > 1 else ""

            bot.send_message(
                chat_id=chat_id,
                text=f"TITLE:\n{title}\n\nBODY:\n{body}"
            )

        # ----- HANDLE CALLBACK -----
        elif update.callback_query:
            chat_id = update.callback_query.message.chat_id

            bot.send_message(
                chat_id=chat_id,
                text="Button clicked 👍"
            )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    except Exception as e:

        print("❌ ERROR:", e)

        # Telegram ko hamesha 200 do
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


    # def do_POST(self):

    #     print("👉 POST RECEIVED FROM TELEGRAM")

    #     content_length = int(self.headers.get('content-length', 0))
    #     body = self.rfile.read(content_length)

    #     data = json.loads(body)

    #     update = Update.de_json(data, bot)

    #     text = update.message.text
    #     chat_id = update.message.chat_id

    #     try:
    #         new = call_ai(text, chat_id)

    #         parts = new.split("\n", 1)

    #         title = parts[0]
    #         body = parts[1] if len(parts) > 1 else ""

    #         bot.send_message(
    #             chat_id=chat_id,
    #             text=f"TITLE:\n{title}\n\nBODY:\n{body}"
    #         )

    #     except Exception as e:
    #         bot.send_message(chat_id=chat_id, text=str(e))

    #     self.send_response(200)
    #     self.end_headers()
    #     self.wfile.write(b'{"ok":true}')


    # def do_GET(self):

    #     self.send_response(200)
    #     self.end_headers()
    #     self.wfile.write(b'{"status":"running"}')


