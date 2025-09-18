from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

app = Flask(__name__)
CORS(app)

# WHO safety ranges (for display + calculation)
SAFETY_RANGES = {
    "pH": (6.5, 8.5),
    "TDS": (0, 100),       # scaled down from WHO <500
    "Hardness": (0, 100),  # scaled down from WHO <200
    "Nitrate": (0, 100),   # scaled down from WHO <45
}

def calculate_risk(ph, tds, hardness, nitrate):
    # normalize deviation (0–100 scale)
    def deviation(val, low, high):
        if low <= val <= high:
            return 0
        if val < low:
            return min(100, (low - val) * 10)
        return min(100, (val - high) * 10)

    ph_dev = deviation(ph, *SAFETY_RANGES["pH"])
    tds_dev = deviation(tds, *SAFETY_RANGES["TDS"])
    hardness_dev = deviation(hardness, *SAFETY_RANGES["Hardness"])
    nitrate_dev = deviation(nitrate, *SAFETY_RANGES["Nitrate"])

    score = 0.3*ph_dev + 0.25*tds_dev + 0.2*hardness_dev + 0.25*nitrate_dev
    if score < 30:
        status = "✅ Safe"
    elif score < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "🚨 High Risk"
    return round(score, 2), status

def detect_elements(ph, tds, hardness, nitrate):
    elements = []
    if ph < 6.5 or hardness > 80:
        elements.append("Uranium (soluble in acidic / hard water)")
    if nitrate > 40 or tds > 80:
        elements.append("Cesium (mobile with high nitrates & salts)")
    if ph > 7.5 and hardness < 50:
        elements.append("Radium (soluble in alkaline soft water)")
    return elements

def send_email(location, ph, tds, hardness, nitrate, score, status):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    receiver = os.getenv("ALERT_EMAIL")

    subject = f"🚨 RAWP Alert: Water Report for {location}"
    body = f"""
    Water Report from RAWP:

    📍 Location: {location}
    💧 TDS: {tds}
    ⚗️ pH: {ph}
    🧪 Nitrate: {nitrate}
    🪨 Hardness: {hardness}

    ✅ Risk Score: {score}
    ⚠️ Status: {status}
    """

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        return True
    except Exception as e:
        print("❌ Email error:", e)
        return False

@app.route("/")
def home():
    return jsonify({"status": "RAWP running ✅", "message": "Use /submit to send water data"})

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    # ESP sends only TDS → mimic other values
    tds = float(data.get("tds", random.uniform(10, 80)))
    ph = float(data.get("ph", random.uniform(6.0, 9.0)))
    hardness = float(data.get("hardness", random.uniform(10, 90)))
    nitrate = float(data.get("nitrate", random.uniform(5, 90)))
    location = data.get("location", "Unknown")

    score, status = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    send_email(location, ph, tds, hardness, nitrate, score, status)

    return jsonify({
        "location": location,
        "ph": ph,
        "tds": tds,
        "hardness": hardness,
        "nitrate": nitrate,
        "risk_score": score,
        "status": status,
        "elements": elements,
        "safety_ranges": SAFETY_RANGES
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
