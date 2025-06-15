from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'jaiminparmar94081@gmail.com'
app.config['MAIL_PASSWORD'] = 'qxpdnrlabhtkwqjp'
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

        msg = Message('Your OTP Code', sender='youremail@gmail.com', recipients=[email])
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

