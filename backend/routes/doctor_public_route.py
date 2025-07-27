from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from bson import ObjectId
from routes.db import doctor_profiles_collection, doctor_availability_collection  # import your collections

doctor_routes = Blueprint('doctor_routes', __name__)

# Get all doctors for the patient dashboard
@doctor_routes.route('/api/doctors', methods=['GET'])
def get_all_doctors():
    try:
        doctors_cursor = doctor_profiles_collection.find({})
        doctors = []
        for doc in doctors_cursor:
            doctors.append({
                "_id": str(doc.get("_id")),
                "userId": str(doc.get("userId")),
                "name": f"{doc.get('firstName', '')} {doc.get('lastName', '')}".strip(),
                "email": doc.get("email", ""),
                "specialization": doc.get("specialization", ""),
                "experience": doc.get("experience", ""),
                "qualification": doc.get("qualification", ""),
                "profilePhoto": doc.get("profilePhoto", ""),
                "clinicName": doc.get("clinicName", ""),
                "consultationFee": doc.get("consultationFee", ""),
            })
        return jsonify(doctors), 200
    except Exception as e:
        print("Error fetching doctors:", e)
        return jsonify({"error": "Internal server error"}), 500

# Get availability for a particular doctor
@doctor_routes.route('/api/doctors/<doctor_id>/availability', methods=['GET'])
@cross_origin() 
def get_doctor_availability(doctor_id):
    try:
        doctor_profile = doctor_profiles_collection.find_one({"_id": ObjectId(doctor_id)})
        if not doctor_profile:
            return jsonify({"error": "Doctor profile not found"}), 404

        user_id = doctor_profile["userId"]  # This is the one stored in availability
        avail_cursor = doctor_availability_collection.find({
            "doctorId": ObjectId(user_id)
        }).sort("startTime", 1)
        
        availability = [{
            "startTime": slot.get("startTime"),
            "endTime": slot.get("endTime")
        } for slot in avail_cursor]

        return jsonify(availability), 200
    except Exception as e:
        print("Error fetching availability:", e)
        return jsonify({"error": "Internal server error"}), 500