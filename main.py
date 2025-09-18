from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from twilio.rest import Client
import os

app = FastAPI(title="Radioactive Water Predicter API")

# ====== DATA STORAGE ======
latest_data = {}

# ====== Twilio Config (set as env variables before running) ======
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
TWILIO_TO = os.getenv("TWILIO_TO")

# ====== Risk Score Logic ======
def predict_contamination(ph, tds, hardness, nitrate):
    score = 0
    if ph < 6.5 or ph > 8.5: score += 30
    if tds > 500: score += 25
    if hardness > 200: score += 20
    if nitrate > 45: score += 25
    return min(score, 100)

def treatment_recommendation(score):
    if score < 30:
        return "✅ Safe: No treatment needed."
    elif score < 60:
        return "⚠️ Moderate: Consider filtration before drinking."
    else:
        return "☢️ High Risk: Avoid consumption. Send for lab testing."

# ====== Data Model ======
class Reading(BaseModel):
    device_id: str
    ph: float
    tds: float
    hardness: float
    nitrate: float
    location: str = "Unknown"

# ====== API Endpoints ======
@app.post("/api/readings")
async def receive_reading(reading: Reading):
    global latest_data
    risk_score = predict_contamination(reading.ph, reading.tds, reading.hardness, reading.nitrate)
    recommendation = treatment_recommendation(risk_score)

    latest_data = {
        "device_id": reading.device_id,
        "ph": reading.ph,
        "tds": reading.tds,
        "hardness": reading.hardness,
        "nitrate": reading.nitrate,
        "location": reading.location,
        "risk_score": risk_score,
        "recommendation": recommendation
    }

    # ===== Send SMS if high risk =====
    if risk_score >= 60 and TWILIO_SID and TWILIO_TOKEN:
        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            msg = f"[Radioactive Water Predicter Alert]\nDevice: {reading.device_id}\nRisk Score: {risk_score}\nLocation: {reading.location}\nRecommendation: {recommendation}"
            client.messages.create(body=msg, from_=TWILIO_FROM, to=TWILIO_TO)
        except Exception as e:
            print("SMS failed:", e)

    return {"status": "success", "data": latest_data}

@app.get("/api/latest")
async def get_latest():
    return latest_data if latest_data else {"message": "No data yet"}

# ====== Serve Frontend ======
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return FileResponse("static/index.html")
