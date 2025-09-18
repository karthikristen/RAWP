# 💧☢️ Radio Active Water Predicter (R.A.W.P)

A hackathon project to predict water contamination risk using IoT (ESP8266 + sensors) and AI formulas.

## Features
- ESP8266 sends live TDS/pH data
- Dashboard (FastAPI/Streamlit) shows contamination risk
- SMS alerts via Twilio API
- WHO guideline checks for safe water

## Run Locally
```bash
pip install -r requirements.txt
streamlit run main.py
# or for FastAPI
uvicorn main:app --reload
