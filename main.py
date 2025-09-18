import os
import random
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# In-memory storage
latest_data = {}

# WHO Safe Ranges
SAFE_LIMITS = {
    "ph": (6.5, 8.5),
    "tds": (0, 500),
    "hardness": (0, 200),
    "nitrate": (0, 45)
}

def calculate_risk(data):
    score = 0
    for key, (low, high) in SAFE_LIMITS.items():
        val = data.get(key, 0)
        if val < low or val > high:
            score += 25
    return score

def detect_element(data):
    ph, tds, hardness, nitrate = data["ph"], data["tds"], data["hardness"], data["nitrate"]
    if ph < 6.5 or hardness > 200:
        return "Uranium"
    elif ph > 7.5 and hardness < 150:
        return "Radium"
    elif nitrate > 40 or tds > 600:
        return "Cesium"
    return "None"

@app.route("/")
def home():
    return jsonify({"status": "RAWP running ✅", "message": "Use /submit to send water data"})

@app.route("/submit", methods=["POST"])
def submit():
    global latest_data
    try:
        req = request.json
        # ESP will send only TDS, so mimic others
        tds = float(req.get("tds", random.uniform(50, 300)))
        data = {
            "tds": tds,
            "ph": random.uniform(6, 9),
            "hardness": random.uniform(50, 300),
            "nitrate": random.uniform(10, 100),
        }
        data["risk_score"] = calculate_risk(data)
        data["element"] = detect_element(data)
        latest_data = data
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/latest", methods=["GET"])
def latest():
    if not latest_data:
        return jsonify({"status": "error", "message": "No data yet"}), 404
    return jsonify(latest_data)

@app.route("/send_report", methods=["POST"])
def send_report():
    try:
        notes = request.json.get("notes", "")
        email_user = os.environ.get("EMAIL_USER")
        email_pass = os.environ.get("EMAIL_PASS")
        alert_email = os.environ.get("ALERT_EMAIL")

        if not latest_data:
            return jsonify({"status": "error", "message": "No data to report"}), 400

        body = f"""🚨 RAWP Water Report 🚨

📍 Location: Chennai
💧 TDS: {latest_data['tds']}
⚗️ pH: {latest_data['ph']}
🧪 Nitrate: {latest_data['nitrate']}
🪨 Hardness: {latest_data['hardness']}

✅ Risk Score: {latest_data['risk_score']}
☢️ Detected Element: {latest_data['element']}

📝 Notes: {notes}
"""
        msg = MIMEText(body)
        msg["Subject"] = "🚨 RAWP Alert: Water Report"
        msg["From"] = email_user
        msg["To"] = alert_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, alert_email, msg.as_string())

        return jsonify({"status": "success", "message": "Report sent via email ✅"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
