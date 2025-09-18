from fastapi import FastAPI
from pydantic import BaseModel
import math

app = FastAPI()

class WaterData(BaseModel):
    ph: float
    tds: float
    hardness: float
    nitrate: float
    location: str

def calculate_risk(ph, tds, hardness, nitrate):
    # --- Normalize each parameter deviation ---
    # pH deviation (6.5–8.5 safe range)
    if 6.5 <= ph <= 8.5:
        ph_dev = 0
    else:
        ph_dev = abs(ph - 7.5) * 10  # exaggerated scale
    ph_dev = min(ph_dev, 100)

    # TDS deviation (safe < 500)
    tds_dev = max(0, (tds - 500) / 5)
    tds_dev = min(tds_dev, 100)

    # Hardness deviation (safe < 200)
    hard_dev = max(0, (hardness - 200) / 2)
    hard_dev = min(hard_dev, 100)

    # Nitrate deviation (safe < 45)
    nit_dev = max(0, (nitrate - 45) * 2)
    nit_dev = min(nit_dev, 100)

    # --- Weighted risk score ---
    score = (
        0.3 * ph_dev +
        0.25 * tds_dev +
        0.2 * hard_dev +
        0.25 * nit_dev
    )

    return round(min(score, 100), 2)

def detect_element(ph, tds, hardness, nitrate):
    """
    Based on correlations from WHO + UNSCEAR reports
    """
    if ph < 6.5 or hardness > 200:
        return "Uranium"
    elif nitrate > 40 and tds > 600:
        return "Cesium"
    elif ph > 7.5 and hardness < 150:
        return "Radium"
    elif nitrate > 50 and hardness > 180:
        return "Strontium"
    else:
        return "None"

@app.get("/")
def root():
    return {"status": "RAWP backend running ✅", "message": "Send POST to /submit"}

@app.post("/submit")
def submit(data: WaterData):
    # Step 1: Calculate risk score
    risk_score = calculate_risk(data.ph, data.tds, data.hardness, data.nitrate)

    # Step 2: Define risk status
    if risk_score < 30:
        status = "✅ Safe"
    elif risk_score < 70:
        status = "⚠️ Moderate Risk"
    else:
        status = "☢️ High Risk"

    # Step 3: Predict radioactive element
    element = detect_element(data.ph, data.tds, data.hardness, data.nitrate)

    # Step 4: Treatment suggestions
    treatment = "None"
    if element == "Uranium":
        treatment = "Reverse Osmosis, Activated Alumina"
    elif element == "Cesium":
        treatment = "Reverse Osmosis + Special Ion Exchange Resins"
    elif element == "Radium":
        treatment = "Ion Exchange, Reverse Osmosis"
    elif element == "Strontium":
        treatment = "Lime Softening, Reverse Osmosis"

    return {
        "location": data.location,
        "ph": data.ph,
        "tds": data.tds,
        "hardness": data.hardness,
        "nitrate": data.nitrate,
        "risk_score": risk_score,
        "status": status,
        "element_detected": element,
        "treatment": treatment
    }
