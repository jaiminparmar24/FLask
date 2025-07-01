from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import yt_dlp
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file


app = Flask(__name__)
app.secret_key = 'supersecretkey'

# ✅ Robots.txt and Sitemap.xml Routes
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

# ✅ SQLite DB Setup
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

# ✅ Google Script Logger
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

# ✅ OTP Email Sender
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
      <p>This OTP is valid for 5 minutes.</p>
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

        if not session.get('otp') or (time.time() - otp_time > 300):
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

# ✅ QR Code Generator Route
@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    url = request.form.get('url')
    if not url:
        return "No URL provided", 400

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to memory buffer
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    # Optional Google Sheet logging (you can use same or separate sheet)
    try:
        requests.post(
            "https://script.google.com/macros/s/YOUR_SECOND_SCRIPT_ID/exec",  # Optional logging
            json={
                "url": url,
                "ip": request.remote_addr
            }
        )
    except Exception as e:
        print("QR log failed:", e)

    return send_file(buf, mimetype='image/png')

# ✅ Telegram Bot Setup
BOT_TOKEN = "7694345842:AAEtJ8ympGE8EYX_LwPAgwBoypvpbcuG22I"  # keep this secure

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("🎥 Send me any video URL and I'll download it!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ Processing your request...")

    output_path = "video.%(ext)s"

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

        await update.message.reply_video(video=open(video_file, 'rb'), caption="✅ Here's your video!")
        await msg.delete()
        os.remove(video_file)

    except Exception as e:
        await msg.edit_text(f"❌ Failed to download video.\n\nError: `{str(e)}`", parse_mode="Markdown")

def run_bot():
    import asyncio
    async def main():
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
        print("✅ Bot is running...")
        await app.run_polling()
    asyncio.run(main())

# ✅ Final Execution Block
if __name__ == '__main__':
    import threading
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(debug=True)
