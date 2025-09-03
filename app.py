from flask import Flask, request, render_template
from openai import OpenAI
import base64, json, gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


# Google Sheets environment variables
private_key = os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n")
client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
private_key_id = os.getenv("GOOGLE_PRIVATE_KEY_ID")
project_id = os.getenv("GOOGLE_PROJECT_ID")
client_id = os.getenv("GOOGLE_CLIENT_ID")

# Construct service account dictionary
service_account_info = {
    "type": "service_account",
    "project_id": project_id,
    "private_key_id": private_key_id,
    "private_key": private_key,
    "client_email": client_email,
    "client_id": client_id,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@','%40')}",
    "universe_domain": "googleapis.com"
}

# OpenAI client
openaikey = os.getenv("OPENAI_API_KEY")
oa_client = OpenAI(api_key=openaikey)
#GC = os.getenv("GOOGLE_CREDENTIALS")

# Convert string to JSON object
#service_account_info = json.loads(GC)

# Google Sheets config

SHEET_ID = os.getenv("SHEET_ID")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key(SHEET_ID).sheet1

@app.route("/", methods=["GET", "POST"])
def upload_file():
    extracted = None
    if request.method == "POST":
        file = request.files["receipt"]
        if file:
            image_bytes = file.read()
            img_type = file.mimetype.split("/")[-1]  # "jpeg" / "png"
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:image/{img_type};base64,{b64_image}"

            # OpenAI OCR
            response = oa_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an OCR assistant for diesel fuel receipts."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract station name, address, date, time, diesel gallons, price per gallon, total diesel cost, other purchases, tax, and total amount paid. Return JSON only."},
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        ]
                    }
                ]
            )

            text_output = response.choices[0].message.content
            clean_text = text_output.strip().strip("`")
            if clean_text.startswith("json"):
                clean_text = clean_text[4:].strip()

            try:
                extracted = json.loads(clean_text)
            except:
                extracted = {"raw_response": text_output}

            # Save to Google Sheet
            row = [str(extracted.get(field, "")) for field in [
                "station_name", "address", "date", "time",
                "diesel_gallons", "price_per_gallon", "total_diesel_cost",
                "other_purchases", "tax", "total_amount_paid"
            ]]
            sheet.append_row(row)

    return render_template("index.html", extracted=extracted)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
