import os
import tempfile
import yt_dlp
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# Key fix: updater(None) to disable internal Updater/polling
application = (
    Application.builder()
    .token(TOKEN)
    .updater(None)  # <--- THIS LINE FIXES THE ERROR!!!
    .read_timeout(20)
    .get_updates_read_timeout(60)
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yo! 🚀 Send me any video link (YouTube, TikTok, Insta, etc.), and I'll grab it for you! "
        "(Up to 50MB for now – bigger ones soon 😏)"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("Hey, that doesn't look like a link! Try a real URL.")
        return

    await update.message.reply_text("Downloading your video... Hang tight! ⏳")

    ydl_opts = {
        "format": "best[filesize<48M]/bestvideo+bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            file_size = os.path.getsize(filename) / (1024 * 1024)
            if file_size > 50:
                await update.message.reply_text(
                    f"Oof, this video is {file_size:.1f}MB – too big right now! (Max 50MB)"
                )
                return

            with open(filename, "rb") as video:
                await update.message.reply_video(video=video, caption=info.get("title", "Your video!"))

            await update.message.reply_text("Boom! Video delivered 🎉")
        except Exception as e:
            await update.message.reply_text(f"Something went wrong 😢 Error: {str(e)}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Bot is alive! 🎉"}

@app.post("/webhook")
async def webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)
    await application.process_update(update)
    return Response(status_code=200)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set webhook on startup
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL') or os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await application.bot.set_webhook(url=webhook_url)
    await application.initialize()
    await application.start()
    yield
    await application.stop()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
