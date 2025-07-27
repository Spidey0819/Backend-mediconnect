from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import jwt
from pymongo import MongoClient
from bson import ObjectId
import bcrypt
from dotenv import load_dotenv
import os
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta, timezone
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import io
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from routes.db import doctor_profiles_collection, doctor_availability_collection
from routes.doctor_schedule_settings import schedule_settings
from routes.doctor_schedule import doctor_schedule
from routes.google_calendar import google_calendar
from routes.doctor_public_route import doctor_routes
from webrtc_signaling import init_webrtc_signaling, get_active_rooms

load_dotenv()
app = Flask(__name__)

# CORS Configuration
CORS(app, 
     origins=[
         "https://web-frontend-mediconnect.onrender.com",
         "https://*.onrender.com",
         "http://localhost:3000",
         "http://127.0.0.1:3000"
     ],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True,
     expose_headers=["Content-Range", "X-Content-Range"]
)

# App Configuration
secret_key = os.getenv('SECRET_KEY')
app.config['SECRET_KEY'] = secret_key
app.secret_key = secret_key
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('SENDER_EMAIL')
app.config['MAIL_PASSWORD'] = os.getenv('SENDER_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('SENDER_EMAIL')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

mail = Mail(app)

# File Upload Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_file):
    try:
        image = Image.open(image_file)
        
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        if max(image.size) > 1600:
            ratio = 1600 / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            return output, 'jpg'
            
        if max(image.size) > 1280:
            ratio = 1280 / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=60, optimize=True)
            output.seek(0)
            return output, 'jpg'
        
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=30, optimize=True)
        output.seek(0)
        return output, 'jpg'
        
    except Exception as e:
        print(f"Error compressing image: {e}")
        image_file.seek(0)
        original_extension = image_file.filename.rsplit('.', 1)[1].lower()
        return image_file, original_extension

# Database Configuration
MONGO_URI = os.getenv('MONGO_URI')
try:
    client = MongoClient(MONGO_URI)
    result = client.admin.command('ping')
    print("MongoDB Connection Success:", result)
except Exception as e:
    print("MongoDB Connection Error:", e)

db = client.mediconnect
app.db = db
users_collection = db.users
appointments_collection = db.appointment
messages_collection = db.messages
conversations_collection = db.conversations
doctor_profiles_collection = db.doctor_profiles
patient_profiles_collection = db.patient_profiles
video_sessions_collection = db.video_sessions
doctor_availability_collection = db.doctor_availability

# Initialize WebRTC Signaling
print("Initializing WebRTC signaling...")
socketio = init_webrtc_signaling(app)

# Register Blueprints
app.register_blueprint(doctor_schedule)
app.register_blueprint(google_calendar)
app.register_blueprint(schedule_settings)
app.register_blueprint(doctor_routes)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "https://web-frontend-mediconnect.onrender.com")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        return response

# Token Authentication Decorator
def token_required(f):
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401
        except Exception as e:
            return jsonify({'message': 'Token verification failed!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

# Authentication Routes
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")

    if users_collection.find_one({"email": email}):
        return jsonify({"message": "User already exists!"}), 400

    hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt())
    
    user_doc = {
        "firstName": data.get("firstName"),
        "lastName": data.get("lastName"),
        "email": email,
        "password": hashed_password,
        "role": data.get("role"),
        "created_at": datetime.now(timezone.utc)
    }
    
    result = users_collection.insert_one(user_doc)
    
    if data.get("role") == "doctor":
        doctor_profile = {
            "userId": str(result.inserted_id),
            "firstName": data.get("firstName"),
            "lastName": data.get("lastName"),
            "email": email,
            "specialization": data.get("specialization", ""),
            "experience": data.get("experience", ""),
            "bio": data.get("bio", ""),
            "location": data.get("location", ""),
            "consultationFee": data.get("consultationFee", 0),
            "education": data.get("education", ""),
            "languages": data.get("languages", []),
            "profileImage": "",
            "isVerified": False,
            "rating": 0,
            "totalReviews": 0,
            "created_at": datetime.now(timezone.utc)
        }
        doctor_profiles_collection.insert_one(doctor_profile)
    
    return jsonify({"message": "User created successfully!"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = users_collection.find_one({"email": email})
    
    if not user:
        return jsonify({"message": "Invalid credentials!"}), 401

    if bcrypt.checkpw(password.encode('utf-8'), user['password']):
        token = jwt.encode({
            'user_id': str(user['_id']),
            'exp': datetime.now(timezone.utc) + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        response_data = {
            "message": "Login successful!",
            "token": token,
            "user": {
                "id": str(user['_id']),
                "firstName": user.get('firstName'),
                "lastName": user.get('lastName'),
                "email": user['email'],
                "role": user['role']
            }
        }
        
        return jsonify(response_data), 200
    else:
        return jsonify({"message": "Invalid credentials!"}), 401

# WebRTC Video Session Routes
@app.route("/api/video/session/create", methods=["POST"])
@token_required
def create_video_session(current_user):
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        
        if not appointment_id:
            return jsonify({"error": "Appointment ID is required"}), 400
        
        appointment = appointments_collection.find_one({"_id": ObjectId(appointment_id)})
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404
        
        user_email = current_user.get('email')
        user_role = current_user.get('role')
        
        has_access = False
        if user_role == 'patient' and appointment.get('patientEmail') == user_email:
            has_access = True
        elif user_role == 'doctor':
            has_access = True
        
        if not has_access:
            return jsonify({"error": "Access denied to this appointment"}), 403
        
        existing_session = video_sessions_collection.find_one({"appointment_id": appointment_id})
        if existing_session and existing_session.get('status') == 'active':
            return jsonify({
                "session_id": str(existing_session['_id']),
                "room_id": existing_session['room_id'],
                "status": existing_session['status']
            }), 200
        
        room_id = f"appointment_{appointment_id}"
        session_doc = {
            "appointment_id": appointment_id,
            "room_id": room_id,
            "status": "active",
            "created_by": user_email,
            "created_at": datetime.now(timezone.utc),
            "participants": [],
            "peers": []
        }
        
        result = video_sessions_collection.insert_one(session_doc)
        
        return jsonify({
            "session_id": str(result.inserted_id),
            "room_id": room_id,
            "status": "active"
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/video/session/<session_id>/end", methods=["POST"])
@token_required
def end_video_session(current_user, session_id):
    try:
        video_sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "status": "ended",
                    "ended_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return jsonify({"message": "Video session ended successfully"}), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to end video session"}), 500

@app.route('/api/appointments/<appointment_id>/video-session', methods=['GET'])
@token_required
def get_appointment_video_session(current_user, appointment_id):
    try:
        appointment = appointments_collection.find_one({"_id": ObjectId(appointment_id)})
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404
        
        user_email = current_user.get('email')
        user_role = current_user.get('role')
        
        has_access = False
        if user_role == 'patient' and appointment.get('patientEmail') == user_email:
            has_access = True
        elif user_role == 'doctor':
            has_access = True
        
        if not has_access:
            return jsonify({"error": "Access denied"}), 403
        
        session = video_sessions_collection.find_one({
            "appointment_id": appointment_id,
            "status": "active"
        })
        
        if session:
            return jsonify({
                "exists": True,
                "session_id": str(session['_id']),
                "room_id": session['room_id'],
                "status": session['status'],
                "participants": session.get('participants', [])
            }), 200
        else:
            return jsonify({"exists": False}), 200
            
    except Exception as e:
        return jsonify({"error": "Failed to get video session"}), 500

# WebRTC Monitoring Routes
@app.route("/api/webrtc/rooms", methods=["GET"])
def get_webrtc_rooms():
    try:
        rooms_info = get_active_rooms()
        return jsonify({
            "success": True,
            "data": rooms_info
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/webrtc/health", methods=["GET"])
def webrtc_health_check():
    return jsonify({
        "status": "healthy",
        "service": "WebRTC Signaling",
        "timestamp": datetime.now().isoformat()
    }), 200

# Doctor Appointments Route
@app.route("/api/doctor/appointments", methods=["GET"])
@token_required
def get_doctor_appointments(current_user):
    if current_user.get("role") != "doctor":
        return jsonify({"message": "Access denied"}), 403
    
    try:
        doctor_profile = doctor_profiles_collection.find_one({"userId": str(current_user["_id"])})
        if not doctor_profile:
            return jsonify({"message": "Doctor profile not found"}), 404
        
        doctor_name = f"{doctor_profile.get('firstName', '')} {doctor_profile.get('lastName', '')}".strip()
        
        name_patterns = [
            doctor_name, 
            f"Dr. {doctor_name}",
            f"{doctor_profile.get('firstName', '')} {doctor_profile.get('lastName', '')}"
        ]
        
        appointments = list(appointments_collection.find({
            "doctorName": {"$in": name_patterns}
        }).sort("appointmentDate", 1))
        
        for appointment in appointments:
            appointment["_id"] = str(appointment["_id"])
            
            if appointment.get("appointmentDate"):
                if isinstance(appointment["appointmentDate"], str):
                    try:
                        appointment_dt = datetime.fromisoformat(appointment["appointmentDate"].replace('Z', '+00:00'))
                        appointment["appointmentDate"] = appointment_dt.isoformat()
                    except:
                        pass
        
        return jsonify({"appointments": appointments}), 200
        
    except Exception as e:
        return jsonify({"message": f"Error fetching appointments: {str(e)}"}), 500

# Appointment Status Update Route
@app.route("/api/appointments/<appointment_id>/status", methods=["PUT"])
@token_required
def update_appointment_status(current_user, appointment_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({"error": "Status is required"}), 400
        
        appointment = appointments_collection.find_one({"_id": ObjectId(appointment_id)})
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404
        
        result = appointments_collection.update_one(
            {"_id": ObjectId(appointment_id)},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({"message": "Status updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to update status"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Image Upload Route
@app.route('/api/upload-image', methods=['POST'])
@token_required
def upload_image(current_user):
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            compressed_file, extension = compress_image(file)
            filename = secure_filename(f"{uuid.uuid4().hex}.{extension}")
            
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            if hasattr(compressed_file, 'save'):
                with open(filepath, 'wb') as f:
                    compressed_file.seek(0)
                    f.write(compressed_file.read())
            else:
                compressed_file.save(filepath)
            
            file_url = f"/api/uploads/{filename}"
            return jsonify({'imageUrl': file_url}), 200
        else:
            return jsonify({'error': 'Invalid file type'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

# Health Check Route
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200

# Password Reset Routes
@app.route("/api/request-password-reset", methods=["POST"])
def request_password_reset():
    try:
        data = request.json
        email = data.get("email")
        
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"message": "If this email exists, a reset link has been sent."}), 200
        
        token = serializer.dumps(email, salt='password-reset-salt')
        reset_url = f"https://web-frontend-mediconnect.onrender.com/reset-password?token={token}"
        
        msg = Message(
            'Password Reset Request',
            recipients=[email]
        )
        msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.
'''
        
        mail.send(msg)
        return jsonify({"message": "If this email exists, a reset link has been sent."}), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to send reset email"}), 500

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    try:
        data = request.json
        token = data.get("token")
        new_password = data.get("password")
        
        try:
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        except:
            return jsonify({"error": "Invalid or expired token"}), 400
        
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        result = users_collection.update_one(
            {"email": email},
            {"$set": {"password": hashed_password}}
        )
        
        if result.modified_count > 0:
            return jsonify({"message": "Password updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to update password"}), 500
            
    except Exception as e:
        return jsonify({"error": "Password reset failed"}), 500

# Run Application
if __name__ == '__main__':
    socketio.run(
        app, 
        debug=True, 
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000)),
        allow_unsafe_werkzeug=True
    )