import os
import tempfile
import yt_dlp
import asyncio
import re
from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # replace with your Telegram user ID

application = (
    Application.builder()
    .token(TOKEN)
    .updater(None)
    .build()
)

# In-memory user session
user_languages = {}
active_users = set()  # tracks users for admin broadcast

# Supported languages
LANGUAGES = {
    "en": "English 🇬🇧",
    "es": "Spanish 🇪🇸",
    "fr": "French 🇫🇷",
    "ar": "Arabic 🇸🇦",
    "ru": "Russian 🇷🇺"
}

# Translations
MESSAGES = {
    "welcome": {
        "en": "Yo! 🚀 Send me any video link (TikTok, Insta, Threads, Facebook, X, VK, ok.ru) 😏 (Up to 50MB for now)",
        "es": "¡Hola! 🚀 Envíame cualquier enlace de video (TikTok, Insta, Threads, Facebook, X, VK, ok.ru) 😏 (Hasta 50MB por ahora)",
        "fr": "Yo! 🚀 Envoyez-moi n'importe quel lien vidéo (TikTok, Insta, Threads, Facebook, X, VK, ok.ru) 😏 (Jusqu'à 50 Mo pour l'instant)",
        "ar": "مرحبًا! 🚀 أرسل لي أي رابط فيديو (TikTok، إنستاجرام، Threads، Facebook، X، VK، ok.ru) 😏 (حتى 50 ميغابايت الآن)",
        "ru": "Привет! 🚀 Отправь мне любую ссылку на видео (TikTok, Insta, Threads, Facebook, X, VK, ok.ru) 😏 (до 50 МБ)"
    },
    "invalid_url": {
        "en": "⚠️ That doesn’t look like a valid link.",
        "es": "⚠️ Eso no parece un enlace válido.",
        "fr": "⚠️ Cela ne ressemble pas à un lien valide.",
        "ar": "⚠️ هذا الرابط يبدو غير صالح.",
        "ru": "⚠️ Это не похоже на действительную ссылку."
    },
    "processing": {
        "en": "⏳ Got it! Working on your link...",
        "es": "⏳ ¡Recibido! Procesando tu enlace...",
        "fr": "⏳ Reçu ! Traitement de votre lien...",
        "ar": "⏳ تم الاستلام! جاري معالجة الرابط...",
        "ru": "⏳ Понял! Обрабатываю ссылку..."
    },
    "download_error_instagram": {
        "en": "📸 This post can’t be downloaded 😕 It may be private or restricted.",
        "es": "📸 Este post no se puede descargar 😕 Puede ser privado o restringido.",
        "fr": "📸 Ce post ne peut pas être téléchargé 😕 Il peut être privé ou restreint.",
        "ar": "📸 لا يمكن تنزيل هذا المنشور 😕 قد يكون خاصًا أو مقيدًا.",
        "ru": "📸 Этот пост нельзя скачать 😕 Возможно, он приватный или ограниченный."
    },
    "download_error_twitter": {
        "en": "🐦 X is acting weird right now 😕 Please try again later.",
        "es": "🐦 X está fallando 😕 Por favor, inténtalo más tarde.",
        "fr": "🐦 X rencontre des problèmes 😕 Veuillez réessayer plus tard.",
        "ar": "🐦 X لا يعمل بشكل صحيح 😕 حاول لاحقًا.",
        "ru": "🐦 X сейчас ведет себя странно 😕 Пожалуйста, попробуйте позже."
    },
    "download_error_okru": {
        "en": "🟠 This video couldn’t be processed 😕 Please try another link.",
        "es": "🟠 Este video no se pudo procesar 😕 Intenta con otro enlace.",
        "fr": "🟠 Cette vidéo n'a pas pu être traitée 😕 Veuillez essayer un autre lien.",
        "ar": "🟠 لم يتمكن من معالجة هذا الفيديو 😕 حاول رابطًا آخر.",
        "ru": "🟠 Это видео не удалось обработать 😕 Попробуйте другую ссылку."
    },
    "download_error_generic": {
        "en": "⚠️ Something went wrong 😕 Please try a different link.",
        "es": "⚠️ Algo salió mal 😕 Por favor, intenta otro enlace.",
        "fr": "⚠️ Quelque chose a mal tourné 😕 Veuillez essayer un autre lien.",
        "ar": "⚠️ حدث خطأ 😕 حاول رابطًا مختلفًا.",
        "ru": "⚠️ Что-то пошло не так 😕 Попробуйте другую ссылку."
    },
    "download_too_big": {
        "en": "🚨 This video is too big right now 😬 (Max 50MB)",
        "es": "🚨 ¡Este video es demasiado grande 😬 (Máx 50MB)!",
        "fr": "🚨 Cette vidéo est trop volumineuse 😬 (Max 50 Mo)",
        "ar": "🚨 هذا الفيديو كبير جدًا الآن 😬 (الحد الأقصى 50 ميغابايت)",
        "ru": "🚨 Это видео слишком большое 😬 (Макс 50 МБ)"
    },
    "download_done": {
        "en": "✅ Done! Enjoy 🎉",
        "es": "✅ ¡Listo! Disfruta 🎉",
        "fr": "✅ Terminé ! Profitez 🎉",
        "ar": "✅ تم! استمتع 🎉",
        "ru": "✅ Готово! Наслаждайся 🎉"
    },
    "timeout": {
        "en": "⏱ This site took too long 😕 Please try another link.",
        "es": "⏱ Este sitio tardó demasiado 😕 Intenta con otro enlace.",
        "fr": "⏱ Ce site a mis trop de temps 😕 Veuillez essayer un autre lien.",
        "ar": "⏱ استغرق هذا الموقع وقتًا طويلاً 😕 حاول رابطًا آخر.",
        "ru": "⏱ Этот сайт слишком долго отвечает 😕 Попробуйте другую ссылку."
    }
}

# ---------- UTILITIES ----------

def normalize_url(url: str) -> str:
    if "threads.net" in url or "threads.com" in url:
        match = re.search(r"/post/([A-Za-z0-9_-]+)", url)
        if match:
            return f"https://www.instagram.com/p/{match.group(1)}/"
    return url

def detect_platform(url: str) -> str:
    url = url.lower()
    if "tiktok" in url:
        return "tiktok"
    if "instagram" in url or "threads" in url:
        return "instagram"
    if "facebook" in url:
        return "facebook"
    if "twitter" in url or "x.com" in url:
        return "twitter"
    if "vk.com" in url:
        return "vk"
    if "ok.ru" in url or "odnoklassniki" in url:
        return "okru"
    return "generic"

def platform_emoji(platform: str) -> str:
    return {
        "tiktok": "🎵",
        "instagram": "📸",
        "facebook": "📘",
        "twitter": "🐦",
        "vk": "🧊",
        "okru": "🟠",
        "generic": "👍",
    }.get(platform, "👍")

# ---------- DOWNLOAD LOGIC ----------

def download_video(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return info, filename

async def process_download(chat_id, url, bot, lang):
    platform = detect_platform(url)
    emoji = platform_emoji(platform)

    url = normalize_url(url)
    is_okru = platform == "okru"
    timeout = 45 if is_okru else 120

    ydl_opts = {
        "format": "best[filesize<48M]/bestvideo+bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        try:
            try:
                info, filename = await asyncio.wait_for(
                    asyncio.to_thread(download_video, url, ydl_opts),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                await bot.send_message(
                    chat_id=chat_id,
                    text=MESSAGES["timeout"][lang]
                )
                return

            file_size = os.path.getsize(filename) / (1024 * 1024)
            if file_size > 50:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{emoji} {MESSAGES['download_too_big'][lang]}"
                )
                return

            # Reaction before sending video
            try:
                await update.get_bot().set_message_reaction(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    reaction=[{"type": "emoji", "emoji": emoji}],
                )
            except Exception:
                pass  # Fail silently

            with open(filename, "rb") as video:
                await bot.send_video(
                    chat_id=chat_id,
                    video=video,
                    caption=f"{emoji} {info.get('title', 'Your video!')}"
                )

            await bot.send_message(
                chat_id=chat_id,
                text=f"{emoji} {MESSAGES['download_done'][lang]}"
            )

        except Exception as e:
            if platform == "instagram":
                msg = MESSAGES["download_error_instagram"][lang]
            elif platform == "twitter":
                msg = MESSAGES["download_error_twitter"][lang]
            elif platform == "okru":
                msg = MESSAGES["download_error_okru"][lang]
            else:
                msg = MESSAGES["download_error_generic"][lang]
            await bot.send_message(chat_id=chat_id, text=msg)
            print("DOWNLOAD ERROR:", e)

# ---------- HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(LANGUAGES[code], callback_data=code)] for code in LANGUAGES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose your language / اختر لغتك / Выберите язык:", reply_markup=reply_markup)

async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data
    user_languages[query.from_user.id] = lang
    active_users.add(query.from_user.id)

    # Menu buttons with broadcast for admin
    menu_buttons = [["📥 My Downloads", "🌐 Visit Website"], ["🔧 Help / Commands", "🎉 Fun Stuff"]]
    if query.from_user.id == ADMIN_ID:
        menu_buttons.append(["📣 Broadcast"])
    menu_buttons.append(["🛠️ Settings"])

    await query.message.reply_text(MESSAGES["welcome"][lang], reply_markup=ReplyKeyboardMarkup(
        menu_buttons,
        resize_keyboard=True
    ))

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, "en")

    if not url.startswith("http"):
        await update.message.reply_text(MESSAGES["invalid_url"][lang])
        return

    emoji = platform_emoji(detect_platform(url))
    await update.message.reply_text(f"{emoji} {MESSAGES['processing'][lang]}")

    asyncio.create_task(process_download(chat_id, url, context.bot, lang))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📣 Send the broadcast message now:")
    context.user_data["broadcasting"] = True

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("broadcasting"):
        msg = update.message.text
        for user_id in active_users:
            try:
                await context.bot.send_message(user_id, f"📣 Broadcast from admin:\n{msg}")
            except:
                pass
        context.user_data["broadcasting"] = False
        await update.message.reply_text("✅ Broadcast sent!")

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(language_selected))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(".*"), handle_broadcast_message))
application.add_handler(CommandHandler("broadcast", broadcast))

# ---------- FASTAPI ----------

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await application.start()

@app.get("/")
async def root():
    return {"message": "Bot is alive! 🎉"}

@app.post("/webhook")
async def webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)
    await application.process_update(update)
    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
