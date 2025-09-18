from fastapi import FastAPI
from pydantic import BaseModel
import datetime, random
from fastapi_utils.tasks import repeat_every

app = FastAPI()

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
    return {"risk_score": risk, "elements": elements}

@app.on_event("startup")
@repeat_every(seconds=10)  # generate new sample every 10s
def generate_fake_data():
    global latest_data
    ph = round(random.uniform(6.0, 8.5), 2)
    tds = round(random.uniform(50, 150), 1)
    hardness = round(random.uniform(30, 100), 1)
    nitrate = round(random.uniform(10, 80), 1)

    fake_sample = WaterSample(
        location="Demo Lab",
        ph=ph,
        tds=tds,
        hardness=hardness,
        nitrate=nitrate
    )
    risk_info = calculate_risk(fake_sample)
    latest_data = {
        "location": fake_sample.location,
        "ph": fake_sample.ph,
        "tds": fake_sample.tds,
        "hardness": fake_sample.hardness,
        "nitrate": fake_sample.nitrate,
        "risk_score": risk_info["risk_score"],
        "elements": risk_info["elements"],
        "timestamp": datetime.datetime.now().isoformat()
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
    return {"status": "Report generated", "report": latest_data}
