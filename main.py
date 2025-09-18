from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import random, os, smtplib
from email.mime.text import MIMEText

app = FastAPI()

# Enable CORS so frontend can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage for latest readings
latest_data = {
    "tds": 0,
    "ph": 7.0,
    "hardness": 100,
    "nitrate": 10,
    "risk_score": 0,
    "element": "None",
    "status": "Safe",
    "location": "CHENNAI"
}

# WHO safe ranges
SAFE_RANGES = {
    "pH": "6.5 – 8.5",
    "TDS": "< 500 mg/L",
    "Hardness": "< 200 mg/L",
    "Nitrate": "< 45 mg/L"
}

def calculate_risk(ph, tds, hardness, nitrate):
    # Normalize deviations (0-100 scale)
    ph_dev = max(0, abs(ph - 7.5) * 20)  # deviation from neutral
    tds_dev = max(0, (tds - 500) / 5)
    hard_dev = max(0, (hardness - 200) / 2)
    nit_dev = max(0, (nitrate - 45) * 2)

    # Weighted sum
    risk = 0.3 * ph_dev + 0.25 * tds_dev + 0.2 * hard_dev + 0.25 * nit_dev
    risk = min(100, round(risk, 2))

    # Determine element
    element = "None"
    if ph < 6.5 or hardness > 200:
        element = "Uranium"
    elif ph > 7.5 and hardness < 150:
        element = "Radium"
    elif nitrate > 40 and tds > 600:
        element = "Cesium"

    # Risk status
    if risk < 30:
        status = "✅ Safe"
    elif risk < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    return risk, element, status

@app.get("/")
async def root():
    return {"status": "RAWP is running ✅", "message": "Send water data to /submit"}

@app.post("/submit")
async def submit_data(request: Request):
    global latest_data
    data = await request.json()

    # ESP sends only TDS
    tds = float(data.get("tds", random.uniform(50, 700)))

    # Mimic other parameters
    ph = random.uniform(6.0, 9.0)
    hardness = random.uniform(50, 400)
    nitrate = random.uniform(5, 100)

    risk, element, status = calculate_risk(ph, tds, hardness, nitrate)

    latest_data = {
        "tds": round(tds, 2),
        "ph": round(ph, 2),
        "hardness": round(hardness, 2),
        "nitrate": round(nitrate, 2),
        "risk_score": risk,
        "element": element,
        "status": status,
        "location": data.get("location", "CHENNAI")
    }
    return {"message": "Data received", "data": latest_data}

@app.get("/latest")
async def get_latest():
    return latest_data

@app.post("/send_report")
async def send_report(request: Request):
    data = await request.json()
    notes = data.get("notes", "")

    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    recipient = os.getenv("ALERT_EMAIL")

    body = f"""
🚨 RAWP Alert: Water Report for {latest_data['location']}

📍 Location: {latest_data['location']}
💧 TDS: {latest_data['tds']} mg/L
⚗️ pH: {latest_data['ph']}
🧪 Nitrate: {latest_data['nitrate']} mg/L
🪨 Hardness: {latest_data['hardness']} mg/L

✅ Risk Score: {latest_data['risk_score']}
☢️ Detected Element: {latest_data['element']}
⚠️ Status: {latest_data['status']}

📝 Notes: {notes if notes else "No additional notes"}

📖 WHO Safe Ranges:
- pH: {SAFE_RANGES['pH']}
- TDS: {SAFE_RANGES['TDS']}
- Hardness: {SAFE_RANGES['Hardness']}
- Nitrate: {SAFE_RANGES['Nitrate']}
"""

    msg = MIMEText(body)
    msg["Subject"] = f"RAWP – Water Quality Report ({latest_data['location']})"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        return {"message": "✅ Report sent successfully via Email!"}
    except Exception as e:
        return {"message": f"❌ Error sending email: {e}"}
