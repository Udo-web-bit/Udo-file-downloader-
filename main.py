import os
import tempfile
import yt_dlp
import asyncio
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

application = (
    Application.builder()
    .token(TOKEN)
    .updater(None)  # Keeps the polling crash away!
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yo fam! 🚀 Drop any video link (TikTok, Insta, X, Facebook Reels, ok.ru) and I'll fetch it for you! "
        "(Up to 50MB for now, bigger ones coming soon 😏)"
    )

def download_video(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return info, filename

async def process_download_independent(chat_id, url, bot):
    """Runs a single download task fully isolated from other requests."""
    ydl_opts = {
        "format": "best[filesize<48M]/bestvideo+bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        try:
            try:
                info, filename = await asyncio.wait_for(
                    asyncio.to_thread(download_video, url, ydl_opts),
                    timeout=120
                )
            except asyncio.TimeoutError:
                await bot.send_message(
                    chat_id=chat_id,
                    text="This site is taking too long 😕 I stopped it to keep the bot alive."
                )
                return

            file_size = os.path.getsize(filename) / (1024 * 1024)
            if file_size > 50:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Oof, this video is {file_size:.1f}MB – too big right now! (Max 50MB)"
                )
                return

            with open(filename, "rb") as video:
                await bot.send_video(
                    chat_id=chat_id,
                    video=video,
                    caption=info.get("title", "Your video!")
                )

            await bot.send_message(chat_id=chat_id, text="Boom! Video delivered 🎉")
        except Exception as e:
            await bot.send_message(chat_id=chat_id, text=f"Something went wrong 😢 Error: {str(e)}")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Immediately responds and launches a fully isolated background task."""
    url = update.message.text.strip()
    chat_id = update.effective_chat.id

    if not url.startswith("http"):
        await update.message.reply_text("Hey, that doesn't look like a link! Try a real URL.")
        return

    # Immediate response so the user knows their request is accepted
    await update.message.reply_text("Got your link! Downloading in the background... ⏳")

    # Launch fully isolated task
    asyncio.create_task(process_download_independent(chat_id, url, context.bot))

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

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
