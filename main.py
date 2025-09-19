# main.py
from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os, ssl, smtplib, datetime, random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

app = FastAPI(title="RAWP Backend (Software Demo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for demo; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

WHO_RANGES = {
    "pH": "6.5 – 8.5",
    "TDS": "≤ 500 mg/L",
    "Hardness": "≤ 200 mg/L",
    "Nitrate": "≤ 45 mg/L"
}

# in-memory storage (demo)
history = []
last_report_text: Optional[str] = None

# ---------------- helpers ----------------
def generate_from_tds(tds: float):
    """Generate realistic pH/hardness/nitrate from TDS (heuristic)."""
    # pH: decreases slightly with higher TDS, clamped
    ph = round(max(6.0, min(8.5, 8.5 - (tds / 2000.0) * 2.0)), 2)
    # hardness correlated with dissolved solids
    hardness = round(min(2000.0, tds * 0.5), 1)
    # nitrate roughly scales; clamp
    nitrate = round(min(500.0, (tds / 2000.0) * 500.0), 1)
    return ph, hardness, nitrate

def calculate_risk(scaled):
    score = 0
    if scaled["ph"] < 6.5 or scaled["ph"] > 8.5: score += 30
    if scaled["tds"] > 500: score += 25
    if scaled["hardness"] > 200: score += 20
    if scaled["nitrate"] > 45: score += 25
    return round(score, 2)

def detect_elements(scaled):
    elements = []
    ph, tds, hardness, nitrate = scaled["ph"], scaled["tds"], scaled["hardness"], scaled["nitrate"]
    if ph < 6.5 or hardness > 200:
        elements.append("Uranium (possible)")
    if nitrate > 45 and tds > 500:
        elements.append("Cesium (possible)")
    if ph > 7.5 and hardness < 150:
        elements.append("Radium (possible)")
    return elements

def prepare_report(payload, location="Unknown", notes=""):
    scaled = payload["scaled_inputs"]
    report = f"""
RAWP Water Contamination Report
Location: {location}
Time (UTC): {datetime.datetime.utcnow().isoformat()}

Parameters:
- pH: {scaled['ph']}    (WHO safe: {WHO_RANGES['pH']})
- TDS: {scaled['tds']} mg/L    (WHO safe: {WHO_RANGES['TDS']})
- Hardness: {scaled['hardness']} mg/L    (WHO safe: {WHO_RANGES['Hardness']})
- Nitrate: {scaled['nitrate']} mg/L    (WHO safe: {WHO_RANGES['Nitrate']})

Risk Score: {payload['risk_score']} ({payload['status']})
Detected Elements (predicted): {', '.join(payload['detected_elements']) if payload['detected_elements'] else 'None'}
Suggested Treatment: {', '.join(payload['treatments'])}

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
        return {"status": "error", "message": "Email vars not set (EMAIL_USER, EMAIL_PASS, ALERT_EMAIL)."}

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = "RAWP Water Contamination Report"
        msg.attach(MIMEText(report_text, "plain"))
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as s:
            s.login(EMAIL_USER, EMAIL_PASS)
            s.sendmail(EMAIL_USER, ALERT_EMAIL, msg.as_string())
        return {"status": "success", "message": "Report sent via email ✅"}
    except Exception as e:
        return {"status": "error", "message": f"Email failed: {str(e)}"}

# ---------------- endpoints ----------------
@app.get("/")
def root():
    return {"status": "RAWP (software demo) running ✅", "message": "POST /submit to add reading, POST /simulate to create demo reading, GET /history to view"}

@app.get("/history")
def get_history():
    return {"history": history[-200:]}

@app.post("/clear")
def clear_history():
    history.clear()
    return {"status": "ok", "message": "History cleared"}

@app.post("/submit")
async def submit(request: Request):
    """
    Accepts form or JSON with:
    - tds (required)
    - ph, hardness, nitrate (optional)
    - location, notes (optional)
    """
    form = await request.form()
    data = {}
    if form:
        def g(k): return form.get(k)
        tds = g("tds")
        ph = g("ph")
        hardness = g("hardness")
        nitrate = g("nitrate")
        location = g("location") or "Unknown"
        notes = g("notes") or ""
        try:
            tds = float(tds)
            ph = float(ph) if ph not in (None, "") else None
            hardness = float(hardness) if hardness not in (None, "") else None
            nitrate = float(nitrate) if nitrate not in (None, "") else None
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid numeric inputs."})
    else:
        body = await request.json()
        tds = body.get("tds")
        ph = body.get("ph")
        hardness = body.get("hardness")
        nitrate = body.get("nitrate")
        location = body.get("location", "Unknown")
        notes = body.get("notes", "")

    if tds is None:
        return JSONResponse(status_code=400, content={"error": "tds is required."})

    if ph is None or hardness is None or nitrate is None:
        gen_ph, gen_hardness, gen_nitrate = generate_from_tds(float(tds))
        ph = ph if ph is not None else gen_ph
        hardness = hardness if hardness is not None else gen_hardness
        nitrate = nitrate if nitrate is not None else gen_nitrate

    scaled = {"ph": round(float(ph), 2), "tds": round(float(tds), 1),
              "hardness": round(float(hardness), 1), "nitrate": round(float(nitrate), 1)}

    risk = calculate_risk(scaled)
    status = "✅ Safe" if risk < 30 else ("⚠️ Moderate Risk" if risk < 60 else "☢️ High Risk")
    elements = detect_elements(scaled)
    treatments = []
    if any("Uranium" in e for e in elements): treatments.append("Reverse osmosis / activated alumina")
    if any("Cesium" in e for e in elements): treatments.append("Ion exchange / RO")
    if any("Radium" in e for e in elements): treatments.append("Lime softening / ion exchange")
    if not treatments: treatments = ["No specific treatment required (lab confirmation recommended)"]

    payload = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "location": location,
        "scaled_inputs": scaled,
        "risk_score": risk,
        "status": status,
        "detected_elements": elements,
        "treatments": treatments,
        "notes": notes
    }

    history.append(payload)
    if len(history) > 500: history.pop(0)

    global last_report_text
    last_report_text = prepare_report(payload, location=location, notes=notes)

    # return payload and status (email not automatically sent so you can control send)
    return {"result": payload, "email_status": {"status": "idle", "message": "Use POST /report to send the saved report via email."}}

@app.post("/simulate")
def simulate(location: Optional[str] = Form("Simulated Site"), severity: Optional[str] = Form("moderate")):
    """
    Create a simulated realistic reading.
    severity: 'low', 'moderate', 'high' -> affects TDS level
    """
    seed = random.randint(1, 1_000_000)
    if severity == "low":
        tds = round(random.uniform(50, 250), 1)
    elif severity == "high":
        tds = round(random.uniform(600, 1200), 1)
    else:  # moderate
        tds = round(random.uniform(250, 600), 1)

    ph, hardness, nitrate = generate_from_tds(tds)
    scaled = {"ph": ph, "tds": tds, "hardness": hardness, "nitrate": nitrate}
    risk = calculate_risk(scaled)
    status = "✅ Safe" if risk < 30 else ("⚠️ Moderate Risk" if risk < 60 else "☢️ High Risk")
    elements = detect_elements(scaled)
    treatments = []
    if any("Uranium" in e for e in elements): treatments.append("Reverse osmosis / activated alumina")
    if any("Cesium" in e for e in elements): treatments.append("Ion exchange / RO")
    if any("Radium" in e for e in elements): treatments.append("Lime softening / ion exchange")
    if not treatments: treatments = ["No specific treatment required (lab confirmation recommended)"]

    payload = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "location": location,
        "scaled_inputs": scaled,
        "risk_score": risk,
        "status": status,
        "detected_elements": elements,
        "treatments": treatments,
        "notes": "Simulated reading (software demo)"
    }
    history.append(payload)
    if len(history) > 500: history.pop(0)

    global last_report_text
    last_report_text = prepare_report(payload, location=location, notes=payload["notes"])

    return {"result": payload, "email_status": {"status": "idle", "message": "Use POST /report to send the saved report via email."}}

@app.post("/report")
def report_send():
    global last_report_text
    if not last_report_text:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No saved report; submit/simulate first."})
    res = send_email(last_report_text)
    return res
