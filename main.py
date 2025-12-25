import os
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
from flask import Flask, request, abort

TOKEN = os.getenv('BOT_TOKEN')  # We'll set this secret later

app_flask = Flask(__name__)

@app_flask.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string, application.bot)
        application.process_update(update)
        return 'OK'
    abort(403)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Yo! 🚀 Send me any video link (YouTube, TikTok, Insta, etc.), and I\'ll grab it for you! (Up to 50MB for now – bigger ones soon 😏)')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text('Hey, that doesn\'t look like a link! Try a real URL.')
        return

    await update.message.reply_text('Downloading your video... Hang tight! ⏳')

    ydl_opts = {
        'format': 'best[filesize<48M]/bestvideo+bestaudio/best',  # Keep under 50MB safe
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

            file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
            if file_size > 50:
                await update.message.reply_text(f'Oof, this video is {file_size:.1f}MB – too big for me right now! (Max 50MB) Try a smaller one or wait for my upgrade!')
                return

            with open(filename, 'rb') as video:
                await update.message.reply_video(video=video, caption=info.get('title', 'Your video!'))

            await update.message.reply_text('Boom! Video delivered 🎉')
        except Exception as e:
            await update.message.reply_text(f'Something went wrong 😢 Maybe private video or bad link? Error: {str(e)}')

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

# For Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    application.bot.set_webhook(url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook")
    app_flask.run(host='0.0.0.0', port=port)
