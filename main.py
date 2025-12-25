import os
import tempfile
import yt_dlp
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv('BOT_TOKEN')
app = Flask(__name__)

# Build the application
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Yo! 🚀 Send me any video link (YouTube, TikTok, Insta, etc.), and I\'ll grab it for you! '
        '(Up to 50MB for now – bigger ones soon 😏)'
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text('Hey, that doesn\'t look like a link! Try a real URL.')
        return

    await update.message.reply_text('Downloading your video... Hang tight! ⏳')

    ydl_opts = {
        'format': 'best[filesize<48M]/bestvideo+bestaudio/best',  # Safe under 50MB
        'outtmpl': '%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts['outtmpl'] = os.path.join(tmpdir, '%(title)s.%(ext)s')
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            file_size = os.path.getsize(filename) / (1024 * 1024)  # In MB
            if file_size > 50:
                await update.message.reply_text(
                    f'Oof, this video is {file_size:.1f}MB – too big right now! (Max 50MB)'
                )
                return

            with open(filename, 'rb') as video:
                await update.message.reply_video(video=video, caption=info.get('title', 'Your video!'))

            await update.message.reply_text('Boom! Video delivered 🎉')
        except Exception as e:
            await update.message.reply_text(f'Something went wrong 😢 Error: {str(e)}')

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

# Webhook endpoint
@app.post('/webhook')
async def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_data = request.get_json()
        update = Update.de_json(json_data, application.bot)
        await application.process_update(update)
        return 'OK', 200
    abort(403)

# Home page (optional, just for health check)
@app.get('/')
def index():
    return 'Bot is alive! 🎉'

# Run the app with built-in webhook support
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Render uses $PORT
    # Set webhook automatically on startup
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_URL')}/webhook"
    application.run_webhook(
        listen='0.0.0.0',
        port=port,
        url_path='/webhook',
        webhook_url=webhook_url
    )
