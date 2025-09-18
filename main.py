from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import smtplib, ssl, os
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

# ===== Convert scaled (0–100) inputs into real-world units =====
def scale_inputs(ph_in, tds_in, hardness_in, nitrate_in):
    return {
        "ph": round(ph_in, 2),
        "tds": round(tds_in, 1),
        "hardness": round(hardness_in, 1),
        "nitrate": round(nitrate_in, 1)
    }

# ===== Calculate Risk Score =====
def calculate_risk(scaled):
    score = 0
    ph, tds, hardness, nitrate = scaled["ph"], scaled["tds"], scaled["hardness"], scaled["nitrate"]

    if ph < 6.5 or ph > 8.5: score += 30
    if tds > 500: score += 25
    if hardness > 200: score += 20
    if nitrate > 45: score += 25

    return score

# ===== Detect Radioactive Elements =====
def detect_elements(scaled):
    elements = []
    ph, tds, hardness, nitrate = scaled["ph"], scaled["tds"], scaled["hardness"], scaled["nitrate"]

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

# ===== Global last report (for /report endpoint) =====
last_report = None

# ===== Routes =====
@app.get("/")
def home():
    return {"status": "RAWP is running ✅", "message": "Send water data to /submit"}

@app.post("/submit")
def submit_data(
    ph: float = Form(...),
    tds: float = Form(...),
    hardness: float = Form(...),
    nitrate: float = Form(...),
    location: str = Form("Unknown"),
    notes: str = Form("")
):
    global last_report

    scaled = scale_inputs(ph, tds, hardness, nitrate)
    risk = calculate_risk(scaled)
    elements = detect_elements(scaled)

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

    # Save last report for /report
    last_report = report

    return {
        "risk_score": risk,
        "status": status,
        "scaled_inputs": scaled,
        "who_safe_ranges": WHO_RANGES,
        "detected_elements": elements,
        "treatments": treatments,
        "email_status": email_status
    }

@app.post("/report")
def send_last_report():
    global last_report
    if not last_report:
        return {"status": "error", "message": "No report available. Please submit data first."}
    
    email_status = send_email(last_report)
    return {"status": email_status["status"], "message": email_status["message"]}

