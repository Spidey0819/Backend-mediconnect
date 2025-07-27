from flask import Blueprint, request, jsonify, current_app
from models.doctor_availability import DoctorAvailabilitySchema
from models.doctor_busy_time import DoctorBusyTimeSchema
from bson import ObjectId

doctor_schedule = Blueprint('doctor_schedule', __name__)

# --- helper ---
def safe_iso(val):
    return val.isoformat() if hasattr(val, "isoformat") else val


# Availability routes
@doctor_schedule.route('/doctor/availability', methods=['POST'])
def add_doctor_availability():
    try:
        validated = DoctorAvailabilitySchema(**request.get_json())
        data = validated.dict()

        if "doctorId" in data:
            data["doctorId"] = ObjectId(data["doctorId"])

        db = current_app.db
        result = db.doctor_availability.insert_one(data)

        return jsonify({"message": "Availability added", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@doctor_schedule.route('/doctor/availability', methods=['GET'])
def get_doctor_availability():
    try:
        doctor_id_str = request.args.get("doctorId")
        if not doctor_id_str:
            return jsonify({"error": "Missing doctorId parameter"}), 400

        try:
            doctor_id = ObjectId(doctor_id_str)
        except Exception:
            return jsonify({"error": "Invalid doctorId"}), 400

        db = current_app.db
        slots = list(db.doctor_availability.find({"doctorId": doctor_id}))
        for slot in slots:
            slot["_id"] = str(slot["_id"])
            slot["startTime"] = safe_iso(slot["startTime"])
            slot["endTime"] = safe_iso(slot["endTime"])
            slot["createdAt"] = safe_iso(slot["createdAt"])
            slot["updatedAt"] = safe_iso(slot["updatedAt"])

        return jsonify(slots), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@doctor_schedule.route('/doctor/availability/<slot_id>', methods=['DELETE'])
def delete_doctor_availability(slot_id):
    try:
        db = current_app.db
        result = db.doctor_availability.delete_one({"_id": ObjectId(slot_id)})

        if result.deleted_count == 1:
            return jsonify({"message": "Slot deleted"}), 200
        else:
            return jsonify({"error": "Slot not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Busy slot routes
@doctor_schedule.route('/doctor/busy', methods=['POST'])
def add_doctor_busy_time():
    try:
        validated = DoctorBusyTimeSchema(**request.get_json())
        data = validated.dict()

        if "doctorId" in data:
            data["doctorId"] = ObjectId(data["doctorId"])

        db = current_app.db
        result = db.doctor_busy_time.insert_one(data)

        return jsonify({"message": "Busy time added", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@doctor_schedule.route('/doctor/busy', methods=['GET'])
def get_doctor_busy_times():
    try:
        doctor_id_str = request.args.get("doctorId")
        if not doctor_id_str:
            return jsonify({"error": "Missing doctorId parameter"}), 400

        try:
            doctor_id = ObjectId(doctor_id_str)
        except Exception:
            return jsonify({"error": "Invalid doctorId"}), 400

        db = current_app.db
        busy_times = list(db.doctor_busy_time.find({"doctorId": doctor_id}))
        for slot in busy_times:
            slot["_id"] = str(slot["_id"])
            slot["startTime"] = safe_iso(slot["startTime"])
            slot["endTime"] = safe_iso(slot["endTime"])
            slot["createdAt"] = safe_iso(slot["createdAt"])
            slot["updatedAt"] = safe_iso(slot["updatedAt"])

        return jsonify(busy_times), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@doctor_schedule.route('/doctor/busy/<slot_id>', methods=['DELETE'])
def delete_doctor_busy_time(slot_id):
    try:
        db = current_app.db
        result = db.doctor_busy_time.delete_one({"_id": ObjectId(slot_id)})

        if result.deleted_count == 1:
            return jsonify({"message": "Busy time deleted"}), 200
        else:
            return jsonify({"error": "Busy time not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Combined route
@doctor_schedule.route('/doctor/schedule', methods=['GET'])
def get_combined_doctor_schedule():
    from bson import ObjectId
    doctor_id = request.args.get("doctorId")
    if not doctor_id:
        return jsonify({"error": "Missing doctorId parameter"}), 400

    db = current_app.db

    try:
        doctor_oid = ObjectId(doctor_id)
    except Exception:
        doctor_oid = None

    # Match both string and ObjectId versions
    availability = list(db.doctor_availability.find({
        "$or": [
            {"doctorId": doctor_id},
            {"doctorId": doctor_oid} 
        ]
    }))
    for slot in availability:
        slot["_id"] = str(slot["_id"])
        slot["doctorId"] = str(slot["doctorId"])
        slot["startTime"] = safe_iso(slot["startTime"])
        slot["endTime"] = safe_iso(slot["endTime"])
        slot["createdAt"] = safe_iso(slot["createdAt"])
        slot["updatedAt"] = safe_iso(slot["updatedAt"])
        slot["type"] = "available"

    busy = list(db.doctor_busy_time.find({
        "$or": [
            {"doctorId": doctor_id},
            {"doctorId": doctor_oid}
        ]
    }))
    for slot in busy:
        slot["_id"] = str(slot["_id"])
        slot["doctorId"] = str(slot["doctorId"])
        slot["startTime"] = safe_iso(slot["startTime"])
        slot["endTime"] = safe_iso(slot["endTime"])
        slot["createdAt"] = safe_iso(slot["createdAt"])
        slot["updatedAt"] = safe_iso(slot["updatedAt"])
        slot["type"] = "busy"

    return jsonify(availability + busy), 200
