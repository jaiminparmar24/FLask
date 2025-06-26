from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_mail import Mail, Message
import random, os, time, sqlite3, requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# ✅ Robots & Sitemap routes (for SEO indexing)
@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")

@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml")

# ✅ Maintenance mode check
@app.before_request
def check_maintenance():
    if os.environ.get('MAINTENANCE_MODE') == 'on':
        return render_template('maintenance.html'), 503

# ✅ Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') or 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') or 'your_app_password'
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# ✅ DB init
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
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S') if row and row[0] else None

def update_last_login(email):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (email, last_login) VALUES (?, ?)", (email, now))
        conn.commit()

def send_to_google_script(email, status):
    url = "https://script.google.com/macros/s/AKfycbye0Ky4KMKw1O3oQj3ctxqpDPyIZu8PyEn8mt7pQOUiLkqvSZ4OUi-oshm2XEUs8PdMjw/exec"
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
    otp = str(random.randint(1000, 9999))
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
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>OTP Verification</title>
      <style>
        @keyframes slide-in {{
          from {{ transform: translateY(-50px); opacity: 0; }}
          to {{ transform: translateY(0); opacity: 1; }}
        }}
        body {{
          background-color: #f4f4f4;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          padding: 0;
          margin: 0;
        }}
        .container {{
          background: #ffffff;
          max-width: 600px;
          margin: 30px auto;
          padding: 30px;
          border-radius: 10px;
          box-shadow: 0 10px 20px rgba(0,0,0,0.1);
          animation: slide-in 1s ease;
        }}
        .otp-box {{
          font-size: 28px;
          font-weight: bold;
          letter-spacing: 8px;
          background: #222;
          color: #fff;
          padding: 15px;
          border-radius: 12px;
          text-align: center;
          margin: 20px 0;
        }}
        .header {{
          color: #4CAF50;
          text-align: center;
          font-size: 26px;
          margin-bottom: 10px;
        }}
        .footer {{
          font-size: 13px;
          color: #888;
          text-align: center;
          margin-top: 30px;
        }}
        .highlight {{
          color: #333;
          font-weight: 500;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">🔐 JAIMIN's Secure Login</div>
        <p>Hello 👋,</p>
        <p>We received a login request for your email: <span class="highlight">{email}</span></p>
        <p>Please use the following One-Time Password (OTP) to proceed:</p>
        <div class="otp-box">{otp}</div>
        <p>This OTP is valid for <strong>5 minutes</strong>. Please do not share it with anyone.</p>
        <p>If you didn’t request this, simply ignore this email.</p>
        <div class="footer">Sent securely by JAIMIN 🚀 | Protecting your identity</div>
      </div>
    </body>
    </html>
    """
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
                return render_template('login.html', error="Please enter an email address.")
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
            update_last_login(session['email'])
            send_to_google_script(session['email'], "Login")
            return redirect(url_for('dashboard') + "?status=success")
        else:
            return render_template('verify.html', error="Invalid OTP. Please try again! 🔐")
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
    send_to_google_script(email, "Logout")
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
