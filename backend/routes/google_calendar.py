import datetime
from flask import Blueprint, jsonify, redirect, request, current_app
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import os
from bson import ObjectId
import jwt
from dateutil.parser import isoparse
import base64
import json
import traceback

load_dotenv()
google_calendar = Blueprint("google_calendar", __name__)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = "http://localhost:5000/google/callback"


# Login 
@google_calendar.route("/google/login")
def google_login():
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "Missing JWT token"}), 400

    decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"], options={"verify_exp": False})
    doctor_id = decoded.get("doctorId")

    state_payload = base64.urlsafe_b64encode(json.dumps({
        "token": token,
        "doctorId": doctor_id
    }).encode()).decode()

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state_payload
    )

    return redirect(authorization_url)


# Callback
@google_calendar.route("/google/callback")
def google_callback():
    try:
        state_encoded = request.args.get("state")
        state_json = json.loads(base64.urlsafe_b64decode(state_encoded).decode())
        jwt_token = state_json["token"]
        doctor_id = state_json["doctorId"]

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state_encoded
        )
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        token_data = credentials_to_dict(credentials)

        db = current_app.db
        db.users.update_one(
            {"_id": ObjectId(doctor_id)},
            {"$set": {"googleToken": token_data}}
        )

        return redirect(f"http://localhost:3000/oauth-success?token={jwt_token}&doctorId={doctor_id}")

    except Exception as e:
        print("OAuth callback failed:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 400


# Sync calendar
@google_calendar.route("/google/sync-busy", methods=["GET"])
def sync_google_busy():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing"}), 401

    jwt_token = auth_header.split(" ")[1]

    try:
        decoded = jwt.decode(jwt_token, current_app.config['SECRET_KEY'], algorithms=["HS256"], options={"verify_exp": False})
        doctor_id = decoded.get("doctorId")
        print("Syncing busy slots for doctorId:", doctor_id)

        db = current_app.db
        user = db.users.find_one({"_id": ObjectId(doctor_id)})

        if not user or "googleToken" not in user:
            return jsonify({"error": "No Google Calendar token found."}), 403

        creds = dict_to_credentials(user["googleToken"])
        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        print(f"Fetched {len(events)} Google Calendar events")

        busy_slots = []
        for event in events:
            start = event['start'].get('dateTime') or event['start'].get('date')
            end = event['end'].get('dateTime') or event['end'].get('date')

            if not start or not end:
                continue

            busy_slot = {
                "doctorId": doctor_id,
                "startTime": isoparse(start).astimezone().isoformat(),
                "endTime": isoparse(end).astimezone().isoformat(),
                "reason": event.get("summary", "Google Calendar Event"),
                "createdAt": datetime.datetime.now(datetime.timezone.utc),
                "updatedAt": datetime.datetime.now(datetime.timezone.utc)
            }

            # Avoid duplicates
            if not db.doctor_busy_time.find_one({
                "doctorId": doctor_id,
                "startTime": busy_slot["startTime"],
                "endTime": busy_slot["endTime"]
            }):
                busy_slots.append(busy_slot)

        if busy_slots:
            db.doctor_busy_time.insert_many(busy_slots)

        return jsonify({"message": f"{len(busy_slots)} busy slots synced."}), 200

    except Exception as e:
        print("Google Sync Failed:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


def credentials_to_dict(creds):
    return {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

def dict_to_credentials(data):
    creds = Credentials(
        token=data['token'],
        refresh_token=data.get('refresh_token'),
        token_uri=data['token_uri'],
        client_id=data['client_id'],
        client_secret=data['client_secret'],
        scopes=data['scopes']
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())  

        # Save the new access token back to DB
        current_app.db.users.update_one(
            {"_id": ObjectId(data["doctorId"])},
            {"$set": {"googleToken.token": creds.token}}
        )
    return creds
