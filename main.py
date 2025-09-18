from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

app = FastAPI()

# Enable CORS for frontend + ESP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for testing, restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Email Config (set in Render Environment Variables)
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASS = "your_app_password"
RECEIVER_EMAIL = "ngo_email@example.com"  # NGO or recipient

# Input Data Model
class WaterData(BaseModel):
    location: str
    ph: float
    tds: float
    hardness: float
    nitrate: float

# Function: Calculate Risk Score
def calculate_risk(data: WaterData):
    # Normalized deviations (0–100 scale)
    ph_dev = 0 if 6.5 <= data.ph <= 8.5 else min(100, abs(data.ph - 7.5) * 20)
    tds_dev = min(100, max(0, data.tds - 500) / 5)
    hard_dev = min(100, max(0, data.hardness - 200) / 2)
    nit_dev = min(100, max(0, data.nitrate - 45) * 2)

    # Weighted risk formula
    risk_score = (
        0.3 * ph_dev +
        0.25 * tds_dev +
        0.2 * hard_dev +
        0.25 * nit_dev
    )

    # Element detection
    element = "None"
    if data.ph < 6.5 or data.hardness > 200:
        element = "Uranium"
    elif data.nitrate > 40 and data.tds > 600:
        element = "Cesium"
    elif data.ph > 7.5 and data.hardness < 150:
        element = "Radium"

    status = "⚠️ Unsafe" if risk_score > 50 else "✅ Safe"

    return round(risk_score, 2), status, element

# Function: Send Email
def send_alert_email(location, risk_score, report):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = f"Water Quality Report - {location}"

        msg.attach(MIMEText(report, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.send_message(msg)

        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# Routes
@app.get("/")
def home():
    return {"status": "RAWP is running ✅", "message": "Send water data to /submit or /esp-submit"}

@app.post("/submit")
def submit(data: WaterData):
    risk_score, status, element = calculate_risk(data)
    return {
        "location": data.location,
        "ph": data.ph,
        "tds": data.tds,
        "hardness": data.hardness,
        "nitrate": data.nitrate,
        "risk_score": risk_score,
        "status": status,
        "element_detected": element
    }

@app.post("/send-report")
def send_report(data: dict):
    notes = data.get("notes", "")
    report = f"""
📄 Water Quality Report
----------------------------
Location: {data.get('location')}
pH: {data.get('ph')}
TDS: {data.get('tds')} mg/L
Hardness: {data.get('hardness')} mg/L
Nitrate: {data.get('nitrate')} mg/L
Risk Score: {data.get('risk_score')}
Status: {data.get('status')}
Element Detected: {data.get('element_detected')}

Notes: {notes}
    """

    send_alert_email(data.get("location", "Unknown"), data.get("risk_score", 0), report)
    return {"message": "Report sent"}

# New ESP route (sends only TDS, backend mimics rest)
@app.post("/esp-submit")
def esp_submit(data: dict):
    location = data.get("location", "Unknown")
    tds = float(data.get("tds", 0))

    # Mimic missing values
    ph = round(random.uniform(6.0, 8.5), 2)
    hardness = round(random.uniform(100, 250), 2)
    nitrate = round(random.uniform(20, 60), 2)

    fake_data = WaterData(
        location=location,
        ph=ph,
        tds=tds,
        hardness=hardness,
        nitrate=nitrate
    )

    risk_score, status, element = calculate_risk(fake_data)

    return {
        "location": location,
        "ph": ph,
        "tds": tds,
        "hardness": hardness,
        "nitrate": nitrate,
        "risk_score": risk_score,
        "status": status,
        "element_detected": element
    }
