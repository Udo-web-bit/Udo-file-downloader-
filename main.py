import os
import tempfile
import yt_dlp
import asyncio
import re
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

application = (
    Application.builder()
    .token(TOKEN)
    .updater(None)
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yo! 🚀 Send me any video link (TikTok, Insta, Threads, Facebook, X, VK, ok.ru) "
        "and I'll grab it for you! (Up to 50MB for now 😏)"
    )

def normalize_url(url: str) -> str:
    # Threads → Instagram conversion
    if "threads.net" in url or "threads.com" in url:
        match = re.search(r"/post/([A-Za-z0-9_-]+)", url)
        if match:
            return f"https://www.instagram.com/p/{match.group(1)}/"
    return url

def download_video(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return info, filename

async def process_download(chat_id, url, bot):
    url = normalize_url(url)

    is_okru = "ok.ru" in url or "odnoklassniki.ru" in url
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
                    text="This site couldn’t respond in time 😕 Please try another link."
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
            await bot.send_message(
                chat_id=chat_id,
                text=f"Something went wrong 😢 Error: {str(e)}"
            )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id

    if not url.startswith("http"):
        await update.message.reply_text("Hey, that doesn't look like a link! Try a real URL.")
        return

    await update.message.reply_text("Got it! Working on your link ⏳")

    asyncio.create_task(process_download(chat_id, url, context.bot))

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
