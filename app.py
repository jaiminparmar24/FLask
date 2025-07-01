from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
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

# ✅ Flask App Setup
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.permanent_session_lifetime = timedelta(days=365 * 100)

# ✅ Mail Configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', 'your_app_password'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
)
mail = Mail(app)

# ✅ SQLite DB Init
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

# ✅ Telegram Bot Functions
BOT_TOKEN = "7694345842:AAEtJ8ympGE8EYX_LwPAgwBoypvpbcuG22I"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\ud83c\udfa5 Send me any video URL and I'll download it!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("\u23f3 Processing your request...")

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

        await update.message.reply_video(video=open(video_file, 'rb'), caption="\u2705 Here's your video!")
        await msg.delete()

        try:
            os.remove(video_file)
        except Exception as cleanup_error:
            print(f"\u26a0\ufe0f File not removed: {cleanup_error}")

    except Exception as e:
        await msg.edit_text(f"\u274c Failed to download video.\n\nError: `{str(e)}`", parse_mode="Markdown")

def run_telegram_bot():
    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    print("\u2705 Telegram bot is running...")
    tg_app.run_polling()

# ✅ Basic Routes
@app.route("/")
def home():
    return "<h1>Welcome to JAIMIN's Flask App with Telegram Bot</h1>"

@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")

@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml")

# ✅ Main Runner
if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot).start()
    app.run(debug=False)

# ✅ App Setup
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.permanent_session_lifetime = timedelta(days=365 * 100)  # ≈ 100 years

# ✅ (Optional) Flask-Session Setup
# from flask_session import Session
# app.config['SESSION_TYPE'] = 'filesystem'
# Session(app)

# ✅ Static robots.txt and sitemap.xml
@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")

@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml")

# ✅ Maintenance Mode
@app.before_request
def check_maintenance():
    if os.environ.get('MAINTENANCE_MODE') == 'on' and request.endpoint != 'maintenance':
        return render_template('maintenance.html'), 503

# ✅ Mail Configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', 'your_app_password'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
)
mail = Mail(app)

# ✅ SQLite Setup
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

# ✅ Google Sheet Logger
def send_to_google_script(email, status):
    try:
        url = "https://script.google.com/macros/s/AKfycbye0Ky4KMKw1O3oQj3ctxqpDPyIZu8PyEn8mt7pQOUiLkqvSZ4OUi-oshm2XEUs8PdMjw/exec"
        login_time = session.get('login_time') or datetime.now(pytz.timezone("Asia/Kolkata"))
        data = {
            "email": email,
            "time": login_time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status
        }
        requests.post(url, json=data)
    except Exception as e:
        print("❌ Google Sheet log failed:", e)

# ✅ OTP Sender
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

    time_now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %B %Y, %I:%M %p")
    subject = f"🔐 Your OTP for JAIMIN's Login – {time_now}"

    msg = Message(
        subject=subject,
        recipients=[email],
        reply_to="noreply@example.com",
        extra_headers={"X-Priority": "1", "X-MSMail-Priority": "High"}
    )

    msg.body = f"Your OTP is: {otp}"
    msg.html = f"""<!DOCTYPE html>
    <html><head><style>
    body {{ font-family: 'Segoe UI'; background: #f4f4f4; margin: 0; padding: 0; }}
    .container {{
      background: #fff; padding: 30px; max-width: 600px; margin: 30px auto;
      border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1);
    }}
    .otp-box {{
      font-size: 26px; letter-spacing: 8px; background: #222; color: #fff;
      padding: 15px; border-radius: 10px; text-align: center; margin: 20px 0;
    }}
    .footer {{ font-size: 13px; color: #888; text-align: center; margin-top: 30px; }}
    </style></head>
    <body>
    <div class="container">
      <h2 style="color:#20B2AA;">🔐 JAIMIN Login OTP</h2>
      <p>Hello,</p>
      <p>We received a login request for: <b>{email}</b></p>
      <p>Enter this OTP to continue:</p>
      <div class="otp-box">{otp}</div>
      <p>This OTP is valid for 5 minutes.Please do not share it with anyone</p>
      <p>If you didn't request this,simply ignore this email.</P>
      <div class="footer">Securely sent by JAIMIN 🚀</div>
    </div></body></html>"""

    try:
        mail.send(msg)
        print(f"✅ OTP sent to {email}: {otp}")
    except Exception as e:
        print("❌ Email failed:", e)
        raise e

# ✅ Routes

@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            return render_template('login.html', error="Please enter a valid email.")
        
        session.permanent = True  # ✅ Added for session stability
        session['email'] = email

        if session.get('verified') and session['email'] == email:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            send_otp(email)
            return redirect(url_for('verify'))

    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if 'resend' in request.form:
            send_otp(session.get('email'))
            return redirect(url_for('verify'))

        user_otp = request.form.get('otp', '').strip()
        otp_time = session.get('otp_time')

        if not session.get('otp') or not otp_time or (time.time() - otp_time > 300):
            session.pop('otp', None)
            return render_template('verify.html', error="⏰ OTP expired. Please login again.")

        if user_otp == session.get('otp'):
            session.update({
                'verified': True,
                'logged_in': True,
                'login_time': datetime.now(pytz.timezone("Asia/Kolkata")),
                'ip': request.remote_addr,
                'browser': request.user_agent.string
            })
            update_last_login(session['email'])
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard'))
        else:
            return render_template('verify.html', error="Invalid OTP. Try again!")

    return render_template('verify.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    last_login = get_last_login(session['email'])
    return render_template('dashboard.html', email=session['email'], last_login=last_login)

@app.route('/logout')
def logout():
    email = session.get('email', 'Unknown')
    session['login_time'] = datetime.now(pytz.timezone("Asia/Kolkata"))
    send_to_google_script(email, "Logout")
    session.clear()
    return redirect(url_for('login'))

@app.route('/maintenance')
def maintenance():
    return render_template("maintenance.html"), 503

@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    url = request.form.get('url')
    if not url:
        return "No URL provided", 400

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    try:
        requests.post(
            "https://script.google.com/macros/s/YOUR_SECOND_SCRIPT_ID/exec",
            json={"url": url, "ip": request.remote_addr}
        )
    except Exception as e:
        print("QR log failed:", e)

    return send_file(buf, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=False)  # ✅ Debug mode disabled to prevent auto restart
