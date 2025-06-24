from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random
import os
import time
import sqlite3
import requests
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Maintenance mode check
@app.before_request
def check_maintenance():
    if os.environ.get('MAINTENANCE_MODE') == 'on':
        return render_template('maintenance.html'), 503

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') or 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') or 'your_app_password'
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# DB init
def init_db():
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                last_login TIMESTAMP,
                profile_pic TEXT
            )
        ''')
        conn.commit()

init_db()

def get_user_info(email):
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT last_login, profile_pic FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        if row:
            return row[0], row[1]
        return None, None

def update_user(email, profile_pic=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        if profile_pic:
            c.execute("INSERT OR REPLACE INTO users (email, last_login, profile_pic) VALUES (?, ?, ?)", (email, now, profile_pic))
        else:
            c.execute("INSERT OR REPLACE INTO users (email, last_login, profile_pic) VALUES (?, ?, COALESCE((SELECT profile_pic FROM users WHERE email = ?), ''))", (email, now, email))
        conn.commit()

def send_to_google_script(email, status):
    url = "https://script.google.com/macros/s/AKfycbwAD7PDD28MAsqRYiQIJZdSW4NqgGa78KLbMZvI1MoS7mLQozQIFPqdwcrtTTP8aYWP/exec"
    login_time = session.get('login_time')
    data = {
        "email": email,
        "time": (login_time or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    }
    try:
        requests.post(url, json=data)
    except Exception as e:
        print("❌ Failed to log to Google Sheet:", e)

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
    <html><body>
      <div style="font-family: Arial;">
        <h2>🔐 Login Verification By JAIMIN</h2>
        <p>Your OTP is:</p>
        <h1 style="background:#222;color:#fff;padding:10px">{otp}</h1>
        <p>Valid for 5 minutes</p>
      </div>
    </body></html>"""

    try:
        mail.send(msg)
        print(f"✅ OTP sent to {email}: {otp}")
    except Exception as e:
        print("❌ Failed to send email:", e)
        raise e

@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            email = request.form['email'].strip()
            if not email:
                return render_template('login.html', error="Please enter an email.")
            session['email'] = email

            if session.get('verified') and session.get('email') == email:
                session['logged_in'] = True
                return redirect(url_for('dashboard'))
            else:
                send_otp(email)
                return redirect(url_for('verify'))
        except Exception as e:
            return render_template('login.html', error=f"Error: {str(e)}")

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
            session['verified'] = True
            session['logged_in'] = True
            session['login_time'] = datetime.now()
            session['ip'] = request.remote_addr
            session['browser'] = request.user_agent.string

            # Profile image handling
            file = request.files.get('profile_pic')
            filename = None
            if file and file.filename:
                filename = secure_filename(f"{session['email']}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            update_user(session['email'], filename)
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard') + "?status=success")
        else:
            return render_template('verify.html', error="Invalid OTP.")

    return render_template('verify.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    last_login, profile_pic = get_user_info(session['email'])
    profile_url = url_for('static', filename='uploads/' + (profile_pic or 'default.png'))
    return render_template('dashboard.html', email=session['email'], last_login=last_login, profile_pic=profile_url)

@app.route('/logout')
def logout():
    email = session.get('email', 'Unknown')
    send_to_google_script(email, "Logout")
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
