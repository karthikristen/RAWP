from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = FastAPI()

# ✅ Add CORS middleware so frontend can call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all domains (for hackathon demo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================== EMAIL SETTINGS ===================
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
NGO_EMAIL = os.getenv("NGO_EMAIL", "ngo@example.com")

def send_email_report(location, tds, ph, nitrate, hardness, risk_score, status):
    subject = f"🚨 RAWP Alert: Water Report for {location}"
    body = f"""
    Water Report from RAWP:

    📍 Location: {location}
    💧 TDS: {tds}
    ⚗️ pH: {ph}
    🧪 Nitrate: {nitrate}
    🪨 Hardness: {hardness}

    ✅ Risk Score: {risk_score}
    ⚠️ Status: {status}
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = NGO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, NGO_EMAIL, msg.as_string())
        print("📨 Email sent successfully!")
    except Exception as e:
        print("❌ Email failed:", e)


# =================== API ROUTES ===================
@app.get("/")
def home():
    return {"status": "RAWP is running ✅", "message": "Send water data to /submit"}


@app.post("/submit")
async def submit(request: Request):
    try:
        data = await request.json()
        tds = float(data.get("tds", 0))
        ph = float(data.get("ph", 7))
        nitrate = float(data.get("nitrate", 0))
        hardness = float(data.get("hardness", 0))
        location = data.get("location", "Unknown")

        # === Risk Calculation ===
        score = 0
        if ph < 6.5 or ph > 8.5: score += 30
        if tds > 500: score += 25
        if hardness > 200: score += 20
        if nitrate > 45: score += 25

        if score < 30:
            status = "✅ Safe"
        elif score < 60:
            status = "⚠️ Moderate Risk"
        else:
            status = "☢️ High Risk"

        # === Send Email Alert ===
        send_email_report(location, tds, ph, nitrate, hardness, score, status)

        return {
            "location": location,
            "tds": tds,
            "ph": ph,
            "nitrate": nitrate,
            "hardness": hardness,
            "risk_score": score,
            "status": status
        }

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
