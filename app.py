from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from pytz import timezone
import random
import os
import time
import sqlite3
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 🔐 Gmail Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# 🛢️ Initialize DB
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

# ⏱️ Get last login
def get_last_login(email):
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT last_login FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

# 🔄 Update last login
def update_last_login(email):
    now = datetime.now().isoformat()
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (email, last_login) VALUES (?, ?)", (email, now))
        conn.commit()

# 🌍 Send to Google Sheet (with IST Time)
def send_to_google_script(email, status, logout=False):
    url = "https://script.google.com/macros/s/AKfycbwAD7PDD28MAsqRYiQIJZdSW4NqgGa78KLbMZvI1MoS7mLQozQIFPqdwcrtTTP8aYWP/exec"  # Replace with actual deployed script URL
    
    ist = timezone('Asia/Kolkata')
    login_time = session.get('login_time')
    if not login_time:
        login_time = datetime.now(ist)
    else:
        login_time = login_time.astimezone(ist)

    data = {
        "email": email,
        "time": login_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    }

    try:
        requests.post(url, json=data)
    except Exception as e:
        print("❌ Failed to log to Google Sheet:", e)


# ✉️ Send OTP
def send_otp(email):
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = time.time()
    session['email'] = email
    session['otp_attempts'] = 0

    msg = Message(
        subject="🔐 Your OTP for JAIMIN's Login",
        recipients=[email],
        reply_to="noreply@example.com",
        extra_headers={"X-Priority": "1", "X-MSMail-Priority": "High"}
    )

    msg.body = f"Your OTP is: {otp}"
    msg.html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 10px;">
          <h2 style="color: #4CAF50;">🔐 Login Verification By JAIMIN</h2>
          <p>Hi there 👋,</p>
          <p>You requested a One-Time Password (OTP) to log in.</p>
          <h1 style="background: #222; color: #fff; padding: 10px 20px; border-radius: 8px; display: inline-block;">{otp}</h1>
          <p>This OTP will expire in <strong>5 minutes</strong> and can only be used once.</p>
          <p>If you didn’t request this, you can safely ignore this email.</p>
          <br>
          <p style="color: #888;">— JAIMIN's Secure Login Team 🚀</p>
        </div>
      </body>
    </html>
    """

    mail.send(msg)

# 📨 Login route
@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        session['email'] = email

        if session.get('verified') and session.get('email') == email:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            send_otp(email)
            return redirect(url_for('verify'))

    return render_template('login.html')

# 🔐 OTP Verify route
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
            return render_template('verify.html', error="⏰ OTP expired. Please login again.")

        if user_otp == session.get('otp'):
            session['verified'] = True
            session['logged_in'] = True
            session['login_time'] = datetime.now()
            session['ip'] = request.remote_addr
            session['browser'] = request.user_agent.string
            update_last_login(session['email'])
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard') + "?status=success")
        else:
            return render_template('verify.html', error="Invalid OTP. Please try again! 🔐")

    return render_template('verify.html')

# 📋 Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    last_login = get_last_login(session['email'])
    return render_template('dashboard.html', email=session['email'], last_login=last_login)

# 🚪 Logout
@app.route('/logout')
def logout():
    email = session.get('email', 'Unknown')
    try:
        send_to_google_script(email, "Logout", logout=True)
    except:
        send_to_google_script(email, "Logout", logout=False)
    session.clear()
    return redirect(url_for('login'))

# 🚀 Start server
if __name__ == '__main__':
    app.run(debug=True)
