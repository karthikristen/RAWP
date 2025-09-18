from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import smtplib, ssl, os, random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

# ===== Allow frontend & ESP to talk to backend =====
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

# ===== Calculate Risk Score =====
def calculate_risk(ph, tds, hardness, nitrate):
    score = 0
    if ph < 6.5 or ph > 8.5:
        score += 30
    if tds > 500:
        score += 25
    if hardness > 200:
        score += 20
    if nitrate > 45:
        score += 25
    return score

# ===== Detect Radioactive Elements =====
def detect_elements(ph, tds, hardness, nitrate):
    elements = []
    if ph < 6.5 or hardness > 200:
        elements.append("Uranium")
    if nitrate > 45 and tds > 500:
        elements.append("Cesium")
    if ph > 7.5 and hardness < 150:
        elements.append("Radium")
    return elements

# ===== Treatment Suggestions =====
TREATMENTS = {
    "Uranium": "Reverse osmosis or activated alumina treatment.",
    "Cesium": "Ion exchange or reverse osmosis filters.",
    "Radium": "Water softening (lime-soda ash) or ion exchange."
}

# ===== Email Function =====
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
    return {"status": "RAWP is running ✅", "message": "Use /submit or /esp_data"}

@app.post("/submit")
def submit_data(
    ph: float = Form(...),
    tds: float = Form(...),
    hardness: float = Form(...),
    nitrate: float = Form(...),
    location: str = Form("Unknown"),
    notes: str = Form("")
):
    risk = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    if risk < 30:
        status = "✅ Safe"
    elif risk < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    treatments = [TREATMENTS[e] for e in elements] if elements else ["No treatment required"]

    return {
        "risk_score": risk,
        "status": status,
        "inputs": {
            "ph": ph,
            "tds": tds,
            "hardness": hardness,
            "nitrate": nitrate
        },
        "who_safe_ranges": WHO_RANGES,
        "detected_elements": elements,
        "treatments": treatments
    }

@app.post("/send_report")
def send_report(
    ph: float = Form(...),
    tds: float = Form(...),
    hardness: float = Form(...),
    nitrate: float = Form(...),
    location: str = Form("Unknown"),
    notes: str = Form("")
):
    risk = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    if risk < 30:
        status = "✅ Safe"
    elif risk < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    treatments = [TREATMENTS[e] for e in elements] if elements else ["No treatment required"]

    # Prepare Report
    report = f"""
    RAWP Water Contamination Report
    Location: {location}

    Parameters:
    pH: {ph} (WHO safe: {WHO_RANGES['ph']})
    TDS: {tds} mg/L (WHO safe: {WHO_RANGES['tds']})
    Hardness: {hardness} mg/L (WHO safe: {WHO_RANGES['hardness']})
    Nitrate: {nitrate} mg/L (WHO safe: {WHO_RANGES['nitrate']})

    Risk Score: {risk} ({status})
    Detected Elements: {", ".join(elements) if elements else "None"}
    Suggested Treatment: {", ".join(treatments)}

    Notes: {notes}
    """

    email_status = send_email(report)

    return {
        "message": "Report generated",
        "email_status": email_status
    }

@app.get("/esp_data")
def esp_data():
    """Return fake ESP32 sensor readings for testing"""
    ph = round(random.uniform(6.0, 9.0), 2)
    tds = round(random.uniform(100, 1200), 1)
    hardness = round(random.uniform(50, 500), 1)
    nitrate = round(random.uniform(10, 100), 1)

    risk = calculate_risk(ph, tds, hardness, nitrate)
    elements = detect_elements(ph, tds, hardness, nitrate)

    if risk < 30:
        status = "✅ Safe"
    elif risk < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    return {
        "risk_score": risk,
        "status": status,
        "inputs": {"ph": ph, "tds": tds, "hardness": hardness, "nitrate": nitrate},
        "who_safe_ranges": WHO_RANGES,
        "detected_elements": elements
    }
