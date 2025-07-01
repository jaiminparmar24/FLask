from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import threading
import yt_dlp
import pytz
import random
import os
import time
import sqlite3
import requests
import qrcode
import io

# === Flask Setup ===
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.permanent_session_lifetime = timedelta(days=365 * 100)

# === Flask Mail Setup ===
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', 'your_app_password'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
)
mail = Mail(app)

# === SQLite Setup ===
def init_db():
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                last_login TIMESTAMP
            )
        ''')
        conn.commit()
init_db()

def get_last_login(email):
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT last_login FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        if row and row[0]:
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return None

def update_last_login(email):
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (email, last_login) VALUES (?, ?)", (email, now))
        conn.commit()

# === Google Sheet Logger ===
def send_to_google_script(email, status):
    try:
        url = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
        login_time = session.get('login_time') or datetime.now(pytz.timezone("Asia/Kolkata"))
        data = {
            "email": email,
            "time": login_time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status
        }
        requests.post(url, json=data)
    except Exception as e:
        print("❌ Google Sheet log failed:", e)

# === OTP Email Sender ===
def send_otp(email):
    session.pop('otp', None)
    session.pop('otp_time', None)
    
    otp = str(random.randint(1000, 9999))
    session.update({
        'otp': otp,
        'otp_time': time.time(),
        'email': email,
        'otp_attempts': 0
    })

    msg = Message(
        subject=f"🔐 Your OTP for JAIMIN's Login",
        recipients=[email]
    )
    msg.body = f"Your OTP is: {otp}"
    msg.html = f"""
    <html><body>
    <h2>JAIMIN Login OTP</h2>
    <p>We received a login request for: <b>{email}</b></p>
    <p>Enter this OTP to continue:</p>
    <div style='font-size:24px;font-weight:bold;'>{otp}</div>
    <p>This OTP is valid for 5 minutes. Do not share it.</p>
    </body></html>
    """
    try:
        mail.send(msg)
        print(f"✅ OTP sent to {email}: {otp}")
    except Exception as e:
        print("❌ Failed to send email:", e)

# === Telegram Bot ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Best practice: use env var

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎥 Send me a video URL to download!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ Downloading...")
    try:
        ydl_opts = {
            'outtmpl': 'downloaded.%(ext)s',
            'format': 'best[ext=mp4]',
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)
        await update.message.reply_video(video=open(video_file, 'rb'), caption="✅ Here's your video!")
        await msg.delete()
        os.remove(video_file)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown")


def run_telegram_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    print("✅ Telegram Bot running...")
    app.run_polling()

# === Flask Routes ===
@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            return render_template('login.html', error="Enter a valid email")
        session['email'] = email
        send_otp(email)
        return redirect(url_for('verify'))
    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()
        if not session.get('otp') or (time.time() - session['otp_time'] > 300):
            return render_template('verify.html', error="OTP expired. Please login again.")
        if user_otp == session['otp']:
            session.update({
                'verified': True,
                'logged_in': True,
                'login_time': datetime.now(pytz.timezone("Asia/Kolkata"))
            })
            update_last_login(session['email'])
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard'))
        else:
            return render_template('verify.html', error="Invalid OTP")
    return render_template('verify.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    last_login = get_last_login(session['email'])
    return render_template('dashboard.html', email=session['email'], last_login=last_login)

@app.route('/logout')
def logout():
    send_to_google_script(session.get('email'), "Logout")
    session.clear()
    return redirect(url_for('login'))

@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    url = request.form.get('url')
    if not url:
        return "Missing URL", 400
    qr = qrcode.make(url)
    buf = io.BytesIO()
    qr.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/robots.txt')
def robots():
    return send_from_directory("static", "robots.txt")

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory("static", "sitemap.xml")

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html'), 503

# === Run Both Flask + Telegram Bot ===
if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot).start()
    app.run(debug=False, use_reloader=False)
