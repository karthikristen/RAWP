from fastapi import FastAPI, Request
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

# ====== EMAIL CONFIG ======
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")   # your Gmail
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # Gmail App Password
NGO_EMAIL = os.getenv("NGO_EMAIL")           # NGO Email

# ====== Function to send email ======
def send_email_alert(subject, body):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not NGO_EMAIL:
        print("⚠️ Email not configured. Skipping alert.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = NGO_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent to NGO")
    except Exception as e:
        print("❌ Email failed:", e)

# ====== Function to calculate risk ======
def predict_contamination(ph: float, tds: float):
    score = 0
    if ph < 6.5 or ph > 8.5: score += 30
    if tds > 500: score += 25
    return score

# ====== Home Route ======
@app.get("/")
def home():
    return {"status": "RAWP is running ✅", "message": "Send water data to /submit"}

# ====== Data Submit Route ======
@app.post("/submit")
async def submit_data(request: Request):
    data = await request.json()
    ph = data.get("ph", 7.0)
    tds = data.get("tds", 300.0)
    location = data.get("location", "Unknown")

    # Calculate risk
    risk_score = predict_contamination(ph, tds)
    risk_level = "✅ Safe" if risk_score < 30 else "⚠️ Moderate Risk" if risk_score < 60 else "☢️ High Risk"

    # Prepare email message
    subject = f"RAWP Alert: {risk_level}"
    body = f"""
    Location: {location}
    pH: {ph}
    TDS: {tds}
    Risk Score: {risk_score}
    Risk Level: {risk_level}
    """

    # Send Email
    send_email_alert(subject, body)

    return {
        "ph": ph,
        "tds": tds,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "message": "Analysis complete ✅ Email alert sent (if configured)"
    }
