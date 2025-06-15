from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # 🔐 For session handling

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

@app.route('/', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to dashboard directly
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['email'] = email

        msg = Message("JAIMIN'S Login Page", sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'''
Hello 👋,

Welcome to JAIMIN'S secure login page.

Your One-Time Password (OTP) is: 🔐 {otp}

This OTP is valid for only one login attempt.
If you didn’t request this, you can safely ignore this email.

Best regards,  
JAIMIN's Team 🚀
'''
        mail.send(msg)
        return redirect(url_for('verify'))

    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    # If already logged in, skip verify page and go to dashboard
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            session['logged_in'] = True  # Mark user as logged in
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

# 🔁 For local development. Render uses gunicorn with app:app
if __name__ == '__main__':
    app.run()
