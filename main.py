from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import os, ssl, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

# ===== Enable CORS (frontend + ESP) =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== WHO Safe Ranges =====
WHO_RANGES = {
    "ph": "6.5 – 8.5",
    "tds": "≤ 500 mg/L",
    "hardness": "≤ 200 mg/L",
    "nitrate": "≤ 45 mg/L"
}

# ===== Storage for latest ESP data =====
latest_reading = {}

# ===== Scientific correlation =====
def generate_values(tds: float):
    # pH decreases with higher TDS
    ph = 8.5 - (tds / 2000 * 2)
    ph = max(6.0, min(8.5, round(ph, 2)))

    # Hardness correlated with TDS
    hardness = min(1000, round(tds * 0.5, 1))

    # Nitrate correlated with TDS
    nitrate = min(500, round((tds / 2000) * 100, 1))

    return {
        "ph": ph,
        "tds": tds,
        "hardness": hardness,
        "nitrate": nitrate
    }

# ===== Risk Score =====
def calculate_risk(scaled):
    score = 0
    if scaled["ph"] < 6.5 or scaled["ph"] > 8.5: score += 30
    if scaled["tds"] > 500: score += 25
    if scaled["hardness"] > 200: score += 20
    if scaled["nitrate"] > 45: score += 25
    return score

# ===== Email Sender =====
def send_email(report):
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")
    ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")

    if not EMAIL_USER or not EMAIL_PASS or not ALERT_EMAIL:
        return {"status": "error", "message": "Email environment variables not set"}

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = "RAWP Water Contamination Report"
        msg.attach(MIMEText(report, "plain"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, ALERT_EMAIL, msg.as_string())

        return {"status": "success", "message": "Report sent via email ✅"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ===== Routes =====
@app.get("/")
def home():
    return {"status": "RAWP is running ✅", "message": "Use /esp-data or /submit"}

# ESP posts TDS data here
@app.post("/esp-data")
def esp_data(tds: float = Form(...)):
    global latest_reading
    values = generate_values(tds)
    risk = calculate_risk(values)

    if risk < 30:
        status = "✅ Safe"
    elif risk < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    latest_reading = {
        "scaled_inputs": values,
        "risk_score": risk,
        "status": status,
        "who_safe_ranges": WHO_RANGES
    }
    return latest_reading

# Frontend fetches latest stable data
@app.get("/esp-data")
def get_esp_data():
    if not latest_reading:
        return {"message": "No ESP data yet"}
    return latest_reading
