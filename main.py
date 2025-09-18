from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import random, smtplib, ssl, os
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

# ===== Risk Calculator =====
def calculate_risk(scaled):
    score = 0
    if scaled["ph"] < 6.5 or scaled["ph"] > 8.5: score += 30
    if scaled["tds"] > 500: score += 25
    if scaled["hardness"] > 200: score += 20
    if scaled["nitrate"] > 45: score += 25
    return score

# ===== Detect Elements =====
def detect_elements(scaled):
    elements = []
    if scaled["ph"] < 6.5 or scaled["hardness"] > 200:
        elements.append("Uranium")
    if scaled["nitrate"] > 45 and scaled["tds"] > 500:
        elements.append("Cesium")
    if scaled["ph"] > 7.5 and scaled["hardness"] < 150:
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
    return {"status": "RAWP running ✅", "message": "Use /submit or /esp"}

# Manual submit
@app.post("/submit")
def submit_data(
    ph: float = Form(...),
    tds: float = Form(...),
    hardness: float = Form(...),
    nitrate: float = Form(...),
    location: str = Form("Unknown"),
    notes: str = Form("")
):
    scaled = {"ph": ph, "tds": tds, "hardness": hardness, "nitrate": nitrate}
    risk = calculate_risk(scaled)
    elements = detect_elements(scaled)

    if risk < 30: status = "✅ Safe"
    elif risk < 60: status = "⚠️ Moderate Risk"
    else: status = "☢️ High Risk"

    treatments = [TREATMENTS[e] for e in elements] if elements else ["No treatment required"]

    report = f"""
    RAWP Water Contamination Report
    Location: {location}

    Parameters:
    pH: {scaled['ph']} (WHO safe: {WHO_RANGES['ph']})
    TDS: {scaled['tds']} mg/L (WHO safe: {WHO_RANGES['tds']})
    Hardness: {scaled['hardness']} mg/L (WHO safe: {WHO_RANGES['hardness']})
    Nitrate: {scaled['nitrate']} mg/L (WHO safe: {WHO_RANGES['nitrate']})

    Risk Score: {risk} ({status})
    Detected Elements: {", ".join(elements) if elements else "None"}
    Suggested Treatment: {", ".join(treatments)}
    Notes: {notes}
    """

    email_status = send_email(report)

    return {
        "risk_score": risk,
        "status": status,
        "scaled_inputs": scaled,
        "who_safe_ranges": WHO_RANGES,
        "detected_elements": elements,
        "treatments": treatments,
        "email_status": email_status
    }

# ESP live data (real TDS + simulated others)
@app.post("/esp")
def esp_data(tds: float = Form(...)):
    # Simulate other values based on TDS
    ph = round(random.uniform(6.5, 8.5), 2)
    hardness = round((tds / 2000) * 1000, 1)
    nitrate = round((tds / 2000) * 500, 1)

    scaled = {"ph": ph, "tds": tds, "hardness": hardness, "nitrate": nitrate}
    risk = calculate_risk(scaled)
    elements = detect_elements(scaled)

    if risk < 30: status = "✅ Safe"
    elif risk < 60: status = "⚠️ Moderate Risk"
    else: status = "☢️ High Risk"

    treatments = [TREATMENTS[e] for e in elements] if elements else ["No treatment required"]

    return {
        "risk_score": risk,
        "status": status,
        "scaled_inputs": scaled,
        "detected_elements": elements,
        "treatments": treatments
    }
