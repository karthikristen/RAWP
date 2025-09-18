from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import smtplib, ssl, os, random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WHO_RANGES = {
    "ph": "6.5 – 8.5",
    "tds": "≤ 500 mg/L",
    "hardness": "≤ 200 mg/L",
    "nitrate": "≤ 45 mg/L"
}

def calculate_risk(scaled):
    score = 0
    if scaled["ph"] < 6.5 or scaled["ph"] > 8.5: score += 30
    if scaled["tds"] > 500: score += 25
    if scaled["hardness"] > 200: score += 20
    if scaled["nitrate"] > 45: score += 25
    return score

def detect_elements(scaled):
    elements = []
    if scaled["ph"] < 6.5 or scaled["hardness"] > 200: elements.append("Uranium")
    if scaled["nitrate"] > 45 and scaled["tds"] > 500: elements.append("Cesium")
    if scaled["ph"] > 7.5 and scaled["hardness"] < 150: elements.append("Radium")
    return elements

TREATMENTS = {
    "Uranium": "Reverse osmosis or activated alumina treatment.",
    "Cesium": "Ion exchange or reverse osmosis filters.",
    "Radium": "Water softening (lime-soda ash) or ion exchange."
}

# Save last report globally
last_report = {"text": "No data yet."}

def send_email(report):
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")
    ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")

    if not EMAIL_USER or not EMAIL_PASS or not ALERT_EMAIL:
        return {"status": "error", "message": "Email credentials not set"}

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

        return {"status": "success", "message": "Report sent ✅"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def home():
    return {"status": "RAWP running ✅"}

@app.post("/esp")
def esp_data(tds: float = Form(...)):
    global last_report

    # Mimic other values
    ph = random.uniform(6.0, 8.5)
    hardness = random.uniform(100, 400)
    nitrate = random.uniform(10, 80)

    scaled = {
        "ph": round(ph, 2),
        "tds": round(tds, 1),
        "hardness": round(hardness, 1),
        "nitrate": round(nitrate, 1)
    }

    risk = calculate_risk(scaled)
    elements = detect_elements(scaled)
    status = "✅ Safe" if risk < 30 else "⚠️ Moderate Risk" if risk < 60 else "☢️ High Risk"
    treatments = [TREATMENTS[e] for e in elements] if elements else ["No treatment required"]

    report = f"""
    RAWP Water Contamination Report
    pH: {scaled['ph']} (WHO safe: {WHO_RANGES['ph']})
    TDS: {scaled['tds']} mg/L (WHO safe: {WHO_RANGES['tds']})
    Hardness: {scaled['hardness']} mg/L (WHO safe: {WHO_RANGES['hardness']})
    Nitrate: {scaled['nitrate']} mg/L (WHO safe: {WHO_RANGES['nitrate']})
    Risk Score: {risk} ({status})
    Detected Elements: {", ".join(elements) if elements else "None"}
    Suggested Treatment: {", ".join(treatments)}
    """

    last_report = {"text": report}

    return {
        "risk_score": risk,
        "status": status,
        "scaled_inputs": scaled,
        "detected_elements": elements,
        "treatments": treatments,
        "report": report
    }

@app.get("/report")
def get_report():
    return last_report

@app.post("/send_report")
def send_report():
    return send_email(last_report["text"])
