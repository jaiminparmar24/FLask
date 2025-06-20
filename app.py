from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random
import os
import time
import sqlite3
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 📧 Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# 📦 Init SQLite DB
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

# 🔐 Update last login
def update_last_login(email):
    now = datetime.now().isoformat()
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (email, last_login) VALUES (?, ?)", (email, now))
        conn.commit()

# 🌍 Send login/logout details to Google Sheet
def send_to_google_script(email, status, logout=False):
    url = "https://script.google.com/macros/s/AKfycbwAD7PDD28MAsqRYiQIJZdSW4NqgGa78KLbMZvI1MoS7mLQozQIFPqdwcrtTTP8aYWP/exec"
    login_time = session.get('login_time')
    logout_time = datetime.now() if logout else None
    duration = ""

    if login_time and logout_time:
        duration = str(logout_time - login_time).split('.')[0]

    ip = session.get('ip', request.remote_addr)
    browser = session.get('browser', request.user_agent.string)
    city = country = "Unknown"

    try:
        geo = requests.get(f"http://ip-api.com/json/{ip}").json()
        city = geo.get("city", "Unknown")
        country = geo.get("country", "Unknown")
    except:
        pass

    data = {
        "email": email,
        "time": (login_time or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "ip": ip,
        "browser": browser,
        "city": city,
        "country": country,
        "duration": duration
    }

    try:
        requests.post(url, json=data)
    except Exception as e:
        print("❌ Failed to log to Google Sheet:", e)

# 📤 Send OTP
def send_otp(email):
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = time.time()
    session['email'] = email
    session['otp_attempts'] = 0

    msg = Message(
        subject="🔐 Your OTP for JAIMIN's Login",
        recipients=[email],
        reply_to="noreply@example.com"
    )

    msg.body = f"Your OTP is: {otp}"
    msg.html = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2>🔐 Login Verification by JAIMIN</h2>
        <p>Your OTP is:</p>
        <h1>{otp}</h1>
        <p>Expires in 5 minutes.</p>
      </body>
    </html>
    """

    mail.send(msg)

# 📥 Login
@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        session['email'] = email
        send_otp(email)
        return redirect(url_for('verify'))

    return render_template('login.html')

# ✅ OTP Verify
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if 'resend' in request.form:
            send_otp(session.get('email'))
            return redirect(url_for('verify'))

        user_otp = request.form['otp']
        otp_time = session.get('otp_time')

        if not session.get('otp') or time.time() - otp_time > 300:
            session.pop('otp', None)
            return render_template('verify.html', error="⏰ OTP expired!")

        if user_otp == session.get('otp'):
            session['verified'] = True
            session['logged_in'] = True
            session['login_time'] = datetime.now()
            session['ip'] = request.remote_addr
            session['browser'] = request.user_agent.string

            update_last_login(session['email'])
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard'))

        return render_template('verify.html', error="❌ Invalid OTP")

    return render_template('verify.html')

# 🖥️ Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html', email=session['email'], last_login=session.get('login_time'))

# 🚪 Logout
@app.route('/logout')
def logout():
    email = session.get('email', 'Unknown')
    send_to_google_script(email, "Logout", logout=True)
    session.clear()
    return redirect(url_for('login'))

# 🚀 Start
if __name__ == '__main__':
    app.run(debug=True)
