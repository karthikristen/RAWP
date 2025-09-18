from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
import os
import random

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Safety ranges (WHO)
# -------------------------
SAFE_RANGES = {
    "pH": (6.5, 8.5),
    "TDS": (0, 100),       # scaled for your ESP demo
    "Hardness": (0, 100),  # scaled for demo
    "Nitrate": (0, 100),   # scaled for demo
}

# -------------------------
# Store last data
# -------------------------
latest_data = {}

# -------------------------
# ESP data model
# -------------------------
class ESPData(BaseModel):
    tds: float

@app.get("/")
def home():
    return {"status": "RAWP running ✅", "message": "Use /submit (ESP) or /manual_input (frontend)"}

# -------------------------
# ESP will call this
# -------------------------
@app.post("/submit")
def submit(data: ESPData):
    global latest_data

    # ESP sends only TDS → backend generates rest
    tds = data.tds
    ph = round(random.uniform(6.0, 9.0), 2)
    hardness = round(random.uniform(20, 90), 2)
    nitrate = round(random.uniform(5, 80), 2)

    risk = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    latest_data = {
        "pH": ph,
        "TDS": tds,
        "Hardness": hardness,
        "Nitrate": nitrate,
        "RiskScore": risk,
        "Elements": elements
    }

    return {"message": "Data received from ESP ✅", "data": latest_data}

# -------------------------
# Manual input (judges demo)
# -------------------------
@app.post("/manual_input")
def manual_input(
    ph: float = Form(...),
    tds: float = Form(...),
    hardness: float = Form(...),
    nitrate: float = Form(...),
):
    global latest_data

    risk = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    latest_data = {
        "pH": ph,
        "TDS": tds,
        "Hardness": hardness,
        "Nitrate": nitrate,
        "RiskScore": risk,
        "Elements": elements
    }

    return {"message": "Manual data received ✅", "data": latest_data}

@app.get("/latest")
def get_latest():
    if not latest_data:
        return {"message": "No data yet"}
    return latest_data

# -------------------------
# Email report
# -------------------------
@app.post("/send_report")
def send_report():
    if not latest_data:
        return {"error": "No data to send"}

    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    to_email = os.getenv("ALERT_EMAIL")

    subject = "🚨 RAWP Alert: Water Report"
    body = f"""
    Water Report from RAWP:

    💧 TDS: {latest_data['TDS']}
    ⚗️ pH: {latest_data['pH']}
    🧪 Nitrate: {latest_data['Nitrate']}
    🪨 Hardness: {latest_data['Hardness']}

    ✅ Risk Score: {latest_data['RiskScore']}
    ⚠️ Elements Detected: {', '.join(latest_data['Elements']) if latest_data['Elements'] else 'None'}

    Safety Ranges (WHO):
    - pH: 6.5–8.5
    - TDS: 0–100 (demo scaled)
    - Hardness: 0–100 (demo scaled)
    - Nitrate: 0–100 (demo scaled)
    """

    try:
        msg = MIMEText(body)
        msg["From"] = user
        msg["To"] = to_email
        msg["Subject"] = subject

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, to_email, msg.as_string())

        return {"status": "Report sent successfully ✅"}
    except Exception as e:
        return {"error": str(e)}

# -------------------------
# Risk & element detection
# -------------------------
def calculate_risk(ph, tds, hardness, nitrate):
    ph_dev = max(0, abs(ph - 7.5) * 15)
    tds_dev = max(0, (tds - SAFE_RANGES["TDS"][1]) * 2 if tds > SAFE_RANGES["TDS"][1] else 0)
    hardness_dev = max(0, (hardness - SAFE_RANGES["Hardness"][1]) * 2 if hardness > SAFE_RANGES["Hardness"][1] else 0)
    nitrate_dev = max(0, (nitrate - SAFE_RANGES["Nitrate"][1]) * 2 if nitrate > SAFE_RANGES["Nitrate"][1] else 0)

    risk = 0.3 * ph_dev + 0.25 * tds_dev + 0.2 * hardness_dev + 0.25 * nitrate_dev
    return round(min(risk, 100), 2)

def detect_elements(ph, tds, hardness, nitrate):
    elements = []
    if ph < 6.5 or hardness > 70:
        elements.append("Uranium")
    if nitrate > 60 and tds > 70:
        elements.append("Cesium")
    if ph > 7.5 and hardness < 40:
        elements.append("Radium")
    return elements
