# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import datetime

app = FastAPI()

# Fake DB (in-memory for now)
latest_data = {}

class WaterSample(BaseModel):
    location: str
    ph: float
    tds: float
    hardness: float
    nitrate: float

def calculate_risk(data: WaterSample):
    elements = []
    risk = 0

    if data.ph < 6.5:
        elements.append("Uranium")
        risk += 2
    if data.ph > 7.5 and data.hardness < 40:
        elements.append("Radium")
        risk += 2
    if data.nitrate > 60 and data.tds > 70:
        elements.append("Cesium")
        risk += 3

    return {
        "risk_score": risk,
        "elements": elements
    }

@app.get("/latest")
async def get_latest():
    if not latest_data:
        return {"message": "No data yet"}
    return latest_data

@app.post("/submit")
async def submit_data(sample: WaterSample):
    global latest_data
    risk_info = calculate_risk(sample)
    latest_data = {
        "location": sample.location,
        "ph": sample.ph,
        "tds": sample.tds,
        "hardness": sample.hardness,
        "nitrate": sample.nitrate,
        "risk_score": risk_info["risk_score"],
        "elements": risk_info["elements"],
        "timestamp": datetime.datetime.now().isoformat()
    }
    return {"status": "Data submitted", "data": latest_data}

@app.post("/send_report")
async def send_report():
    if not latest_data:
        return {"error": "No data to report"}
    # For now, just return report as JSON (email can be added later)
    return {"status": "Report generated", "report": latest_data}
