import os
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "7694345842:AAEtJ8ympGE8EYX_LwPAgwBoypvpbcuG22I"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎥 Send me any video URL and I'll download it!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ Processing your request...")

    output_path = "downloaded_video.%(ext)s"

    try:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4]',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)

        # Send the video
        await update.message.reply_video(video=open(video_file, 'rb'), caption="✅ Here's your video!")
        await msg.delete()

        # Clean up file (safely)
        try:
            os.remove(video_file)
        except Exception as cleanup_error:
            print(f"⚠️ File not removed: {cleanup_error}")

    except Exception as e:
        await msg.edit_text(f"❌ Failed to download video.\n\nError: `{str(e)}`", parse_mode="Markdown")



# Run the bot
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("✅ Bot is running...")
    app.run_polling()
