# main.py
from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import os
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime

app = FastAPI(title="RAWP Backend")

# Allow frontend & ESP to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# WHO safe ranges (for display)
WHO_RANGES = {
    "pH": "6.5 – 8.5",
    "TDS": "≤ 500 mg/L",
    "Hardness": "≤ 200 mg/L",
    "Nitrate": "≤ 45 mg/L"
}

# in-memory store (simple, ok for hackathon/demo)
history = []   # list of dict readings (latest appended)
last_report = None  # last generated report text (string) and data container


# ---- helper logic ----
def generate_other_params_from_tds(tds: float):
    """
    Generate realistic pH, hardness, nitrate values from TDS.
    These are heuristic / illustrative, not lab-grade.
    """
    # pH tends to drift slightly with dissolved solids; clamp to safe-ish range
    ph = round(max(6.0, min(8.5, 8.5 - (tds / 2000.0) * 2.0)), 2)

    # hardness correlates with dissolved minerals; scale
    hardness = round(min(2000.0, tds * 0.5), 1)  # up to 1000+ possible

    # nitrate roughly scales with contamination sources; clamp
    nitrate = round(min(500.0, (tds / 2000.0) * 500.0), 1)

    return ph, hardness, nitrate


def calculate_risk(scaled: dict):
    score = 0
    ph = scaled["ph"]
    tds = scaled["tds"]
    hardness = scaled["hardness"]
    nitrate = scaled["nitrate"]
    if ph < 6.5 or ph > 8.5:
        score += 30
    if tds > 500:
        score += 25
    if hardness > 200:
        score += 20
    if nitrate > 45:
        score += 25
    return round(score, 2)


def detect_elements(scaled: dict):
    elements = []
    ph = scaled["ph"]
    tds = scaled["tds"]
    hardness = scaled["hardness"]
    nitrate = scaled["nitrate"]
    # heuristic flags
    if ph < 6.5 or hardness > 200:
        elements.append("Uranium (possible)")
    if nitrate > 45 and tds > 500:
        elements.append("Cesium (possible)")
    if ph > 7.5 and hardness < 150:
        elements.append("Radium (possible)")
    return elements


def prepare_report_text(data: dict, location: str = "Unknown", notes: str = ""):
    # data contains scaled_inputs, risk_score, status, elements, treatments
    scaled = data["scaled_inputs"]
    report = f"""
RAWP Water Contamination Report
Location: {location}
Time: {datetime.datetime.utcnow().isoformat()} UTC

Parameters:
- pH: {scaled['ph']}  (WHO safe: {WHO_RANGES['pH']})
- TDS: {scaled['tds']} mg/L  (WHO safe: {WHO_RANGES['TDS']})
- Hardness: {scaled['hardness']} mg/L  (WHO safe: {WHO_RANGES['Hardness']})
- Nitrate: {scaled['nitrate']} mg/L  (WHO safe: {WHO_RANGES['Nitrate']})

Risk Score: {data['risk_score']} ({data['status']})
Detected Elements (predicted): {', '.join(data['detected_elements']) if data['detected_elements'] else 'None'}
Suggested Treatment: {', '.join(data['treatments']) if data['treatments'] else 'No specific treatment required'}

Notes:
{notes}

-- End of report
    """
    return report.strip()


def send_email(report_text: str):
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")
    ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")

    if not EMAIL_USER or not EMAIL_PASS or not ALERT_EMAIL:
        return {"status": "error", "message": "Email environment variables not set on server."}

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = "RAWP Water Contamination Report"

        msg.attach(MIMEText(report_text, "plain"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, ALERT_EMAIL, msg.as_string())

        return {"status": "success", "message": "Report sent via email ✅"}
    except Exception as e:
        return {"status": "error", "message": f"Email sending failed: {str(e)}"}


# ---- endpoints ----
@app.get("/")
async def root():
    return {"status": "RAWP running ✅", "message": "Use POST /submit to submit readings, GET /history to fetch history, POST /report to send last report via email."}


@app.get("/history")
async def get_history():
    # return last N readings (keep small)
    return {"history": history[-50:]}  # last up to 50


@app.post("/submit")
async def submit(request: Request):
    """
    Accepts either form-encoded or JSON:
      - If JSON: { "tds": 123.4, "ph": .. optional, "hardness": .. optional, "nitrate": .. optional, "location": "...", "notes": "..." }
      - If form: tds, ph, hardness, nitrate, location, notes
    Backend will prefer provided values; if only TDS provided, we will generate other params.
    """
    form = await request.form()
    data = {}
    # try form fields first
    if form:
        # read keys safely
        def getf(k):
            v = form.get(k)
            return None if v is None or v == "" else v
        tds = getf("tds")
        ph = getf("ph")
        hardness = getf("hardness")
        nitrate = getf("nitrate")
        location = getf("location") or "Unknown"
        notes = getf("notes") or ""
        # convert
        try:
            tds = float(tds) if tds is not None else None
            ph = float(ph) if ph is not None else None
            hardness = float(hardness) if hardness is not None else None
            nitrate = float(nitrate) if nitrate is not None else None
        except:
            return JSONResponse(status_code=400, content={"error": "Invalid numeric values in form."})
    else:
        body = await request.json()
        tds = body.get("tds")
        ph = body.get("ph")
        hardness = body.get("hardness")
        nitrate = body.get("nitrate")
        location = body.get("location", "Unknown")
        notes = body.get("notes", "")

    # require tds at least
    if tds is None:
        return JSONResponse(status_code=400, content={"error": "tds is required (float)"})

    # if other params missing, generate from tds
    if ph is None or hardness is None or nitrate is None:
        gen_ph, gen_hardness, gen_nitrate = generate_other_params_from_tds(float(tds))
        ph = ph if ph is not None else gen_ph
        hardness = hardness if hardness is not None else gen_hardness
        nitrate = nitrate if nitrate is not None else gen_nitrate

    scaled = {"ph": round(float(ph), 2), "tds": round(float(tds), 1), "hardness": round(float(hardness), 1), "nitrate": round(float(nitrate), 1)}
    risk_score = calculate_risk(scaled)
    if risk_score < 30:
        status = "✅ Safe"
    elif risk_score < 60:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    elements = detect_elements(scaled)
    treatments = []
    if "Uranium" in " ".join(elements):
        treatments.append("Reverse osmosis or activated alumina")
    if "Cesium" in " ".join(elements):
        treatments.append("Ion exchange or reverse osmosis")
    if "Radium" in " ".join(elements):
        treatments.append("Lime softening / ion exchange")
    if not treatments:
        treatments = ["No specific treatment required (lab confirmation recommended)"]

    payload = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "location": location,
        "scaled_inputs": scaled,
        "risk_score": risk_score,
        "status": status,
        "detected_elements": elements,
        "treatments": treatments,
        "notes": notes
    }

    # append to history (keep size small)
    history.append(payload)
    if len(history) > 200:
        history.pop(0)

    # store last_report text
    global last_report
    last_report = prepare_report_text(payload, location=location, notes=notes)

    # send immediate email optionally? we return email_status but do not auto-send every reading to avoid spam.
    # For demo, do not auto send; use /report to send.
    email_status = {"status": "idle", "message": "Use /report to send the saved report via email."}

    return {"result": payload, "email_status": email_status}


@app.post("/report")
async def send_last_report():
    global last_report
    if not last_report:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No report available. Submit data first."})
    res = send_email(last_report)
    return res
