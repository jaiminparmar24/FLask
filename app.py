from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # 🔐 For session handling

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
import os

app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['email'] = email

        msg = Message('Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP is {otp}'
        mail.send(msg)

        return redirect(url_for('verify'))

    return render_template('login.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            return "✅ OTP Verified Successfully!"
        else:
            return "❌ Invalid OTP. Try again."

    return render_template('verify.html')


# This is required for Render to detect the app
# gunicorn will use: app:app
if __name__ == '__main__':
    app.run()
