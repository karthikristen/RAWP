from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

# --------------------
# Global storage
# --------------------
latest_data = {
    "location": "CHENNAI",
    "tds": 50,
    "ph": 7.0,
    "hardness": 120,
    "nitrate": 30,
    "risk_score": 0,
    "element": "Safe"
}

# --------------------
# WHO Safe Ranges
# --------------------
SAFE_LIMITS = {
    "ph": (6.5, 8.5),
    "tds": (0, 500),
    "hardness": (0, 200),
    "nitrate": (0, 45)
}

# --------------------
# Email Config
# --------------------
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")


def calculate_risk(data):
    """Calculate risk score and detected element"""
    score = 0
    element = "Safe"

    if not SAFE_LIMITS["ph"][0] <= data["ph"] <= SAFE_LIMITS["ph"][1]:
        score += 15
    if data["tds"] > SAFE_LIMITS["tds"][1]:
        score += 10
        element = "Cesium"
    if data["hardness"] > SAFE_LIMITS["hardness"][1]:
        score += 10
        element = "Uranium"
    if data["nitrate"] > SAFE_LIMITS["nitrate"][1]:
        score += 10
        element = "Cesium"

    data["risk_score"] = score
    data["element"] = element
    return data


def send_email_report(data, notes=""):
    """Send email with latest report"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = f"🚨 RAWP Alert: Water Report for {data['location']}"

        body = f"""
        Water Report from RAWP:

        📍 Location: {data['location']}
        💧 TDS: {data['tds']}
        ⚗️ pH: {data['ph']}
        🧪 Nitrate: {data['nitrate']}
        🪨 Hardness: {data['hardness']}

        ✅ Risk Score: {data['risk_score']}
        ⚠️ Status: {data['element']}

        Notes: {notes}
        """

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, ALERT_EMAIL, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("❌ Email error:", e)
        return False


# --------------------
# Routes
# --------------------

@app.route("/latest", methods=["GET"])
def get_latest():
    return jsonify(latest_data)


@app.route("/esp", methods=["POST"])
def from_esp():
    """ESP sends only TDS, backend generates others"""
    global latest_data
    content = request.json
    tds_value = float(content.get("tds", 50))

    latest_data["tds"] = tds_value
    latest_data["ph"] = round(random.uniform(6.0, 9.0), 2)
    latest_data["hardness"] = random.randint(50, 300)
    latest_data["nitrate"] = random.randint(10, 100)

    latest_data = calculate_risk(latest_data)
    return jsonify({"message": "ESP data updated", "data": latest_data})


@app.route("/manual_input", methods=["POST"])
def manual_input():
    """Manual data entry (used in frontend tab)"""
    global latest_data
    content = request.json
    latest_data["tds"] = float(content.get("tds", latest_data["tds"]))
    latest_data["ph"] = float(content.get("ph", latest_data["ph"]))
    latest_data["hardness"] = float(content.get("hardness", latest_data["hardness"]))
    latest_data["nitrate"] = float(content.get("nitrate", latest_data["nitrate"]))
    latest_data["location"] = content.get("location", latest_data["location"])

    latest_data = calculate_risk(latest_data)
    return jsonify({"message": "Manual input updated", "data": latest_data})


@app.route("/send_report", methods=["POST"])
def send_report():
    global latest_data
    content = request.json
    notes = content.get("notes", "")
    success = send_email_report(latest_data, notes)
    return jsonify({"message": "✅ Report sent!" if success else "❌ Failed to send"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
