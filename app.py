import os
import json
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(override=False)

app = Flask(__name__)

# Configure CORS
allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins_str == '*':
    CORS(app)
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()]
    CORS(app, origins=allowed_origins)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

MAIL_TO = os.environ.get('MAIL_TO')

mail = Mail(app)

def get_request_data():
    if request.is_json:
        return request.get_json() or {}
    return request.form

@app.route('/', methods=['GET'])
def index():
    return "Tattle Tale backend is running"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/booking', methods=['POST'])
def booking():
    print("[Booking] Received request")
    data = get_request_data()
    
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    name = data.get('name', f"{first_name} {last_name}".strip())
    email = data.get('email', '')
    phone = data.get('phone', '')
    
    # Read any extra fields that might be passed from the frontend form
    message = data.get('message', '')
    
    if not name or not email:
        print("[Booking Error] Missing name or email")
        return jsonify({"success": False, "message": "Missing name or email"}), 400

    admin_body = f"New Booking:\n\nName: {name}\nEmail: {email}\nPhone: {phone}\n"
    if message:
        admin_body += f"Message: {message}\n"
    for key, val in data.items():
        if key not in ['name', 'first_name', 'last_name', 'email', 'phone', 'message']:
            admin_body += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            # Admin Email
            admin_msg = Message(subject='New Workshop Booking', recipients=[MAIL_TO])
            admin_msg.body = admin_body
            mail.send(admin_msg)
            print("[Booking] Admin email sent")
            
            # User Confirmation
            user_msg = Message(subject='Your Seat is Confirmed', recipients=[email])
            user_msg.body = f"Dear {name},\n\nThank you for booking. Your seat is confirmed."
            mail.send(user_msg)
            print("[Booking] User confirmation sent")

        return jsonify({"success": True, "message": "Booking submitted successfully"})
    except Exception as e:
        print(f"[Booking Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/survey', methods=['POST'])
def survey():
    print("[Survey] Received request")
    data = get_request_data()
    
    body_content = "New Community Survey Response\n\n"
    
    # Depending on form data (MultiDict) vs JSON (Dict)
    # Form data may have multiple values for same key: request.form.getlist(key)
    if not request.is_json and hasattr(request.form, 'getlist'):
        # unique keys
        keys = set(request.form.keys())
        for key in keys:
            val_list = request.form.getlist(key)
            if len(val_list) > 1:
                body_content += f"{key}: {', '.join(val_list)}\n"
            else:
                body_content += f"{key}: {val_list[0]}\n"
    else:
        for key, val in data.items():
            if isinstance(val, list):
                body_content += f"{key}: {', '.join(str(v) for v in val)}\n"
            else:
                body_content += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject='New Community Survey Response', recipients=[MAIL_TO])
            msg.body = body_content
            mail.send(msg)
            print("[Survey] Admin email sent")
        return jsonify({"success": True, "message": "Survey submitted successfully"})
    except Exception as e:
        print(f"[Survey Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/api/feedback', methods=['POST'])
def feedback():
    print("[Feedback] Received request")
    data = get_request_data()
    
    body_content = "New Feedback:\n\n"
    for key, val in data.items():
        body_content += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject='New Homepage Feedback', recipients=[MAIL_TO])
            msg.body = body_content
            # optionally reply_to
            email = data.get('email')
            if email:
                msg.reply_to = email
            mail.send(msg)
            print("[Feedback] Admin email sent")
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
    except Exception as e:
        print(f"[Feedback Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/api/contact', methods=['POST'])
def contact():
    print("[Contact] Received request")
    data = get_request_data()
    
    name = data.get('name', '')
    email = data.get('email', '')
    message = data.get('message', '')

    body_content = f"New Contact Submission:\n\nName: {name}\nEmail: {email}\nMessage: {message}\n"
    
    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject=f"New Contact Form Submission from {name}", recipients=[MAIL_TO])
            msg.body = body_content
            if email:
                msg.reply_to = email
            mail.send(msg)
            print("[Contact] Admin email sent")
        return jsonify({"success": True, "message": "Contact submitted successfully"})
    except Exception as e:
        print(f"[Contact Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
