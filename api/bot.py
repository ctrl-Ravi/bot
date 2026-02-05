import os
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler,
    CommandHandler, ConversationHandler
)

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


# ========== APPLICATION ==========
app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_message))

app.add_handler(CallbackQueryHandler(again_callback, pattern="again"))
app.add_handler(CallbackQueryHandler(short_callback, pattern="short"))
app.add_handler(CallbackQueryHandler(copy_title, pattern="copy_title"))
app.add_handler(CallbackQueryHandler(copy_body, pattern="copy_body"))

app.add_handler(CommandHandler("settings", settings))
app.add_handler(CommandHandler("clearprompt", clear_prompt))

conv = ConversationHandler(
    entry_points=[CommandHandler("setprompt", ask_prompt)],
    states={SET_PROMPT: [MessageHandler(filters.TEXT, save_prompt)]},
    fallbacks=[]
)

app.add_handler(conv)


# ========== 🔥 VERCEL ENTRY 🔥 ==========
async def handler(request):

    if request.method == "POST":
        data = await request.json()

        update = Update.de_json(data, app.bot)
        await app.process_update(update)

        return {"status": "ok"}

    return {"status": "running"}
