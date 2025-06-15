from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random
import os
import time
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

# 📦 DB Setup (Run once to initialize users table)
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

# ⏱️ Check last login
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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        last_login = get_last_login(email)

        if last_login and datetime.now() - last_login < timedelta(days=10):
            # ✅ Allow auto-login without OTP
            session['email'] = email
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            # ✉️ Send OTP if first time or after 10 days
            otp = str(random.randint(100000, 999999))
            session['otp'] = otp
            session['otp_time'] = time.time()
            session['email'] = email

            msg = Message("JAIMIN'S Login Page", sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'''
Hello 👋,

Welcome to JAIMIN'S secure login page.

Your One-Time Password (OTP) is: 🔐 {otp}

This OTP is valid for only one login attempt and expires in 5 minutes.
If you didn’t request this, you can safely ignore this email.

Best regards,  
JAIMIN's Team 🚀
'''
            mail.send(msg)
            return redirect(url_for('verify'))

    return render_template('login.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        user_otp = request.form['otp']
        otp_time = session.get('otp_time')

        if not session.get('otp') or time.time() - otp_time > 300:
            session.pop('otp', None)
            return "⏰ OTP expired. Please login again."

        if user_otp == session.get('otp'):
            session['logged_in'] = True
            update_last_login(session['email'])  # ✅ Update last login
            return redirect(url_for('dashboard'))
        else:
            return "❌ Invalid OTP. Try again."

    return render_template('verify.html')


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
