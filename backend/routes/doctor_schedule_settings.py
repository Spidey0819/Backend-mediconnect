from flask import Blueprint, request, jsonify, current_app
from models.doctor_schedule_settings import DoctorScheduleSettingsSchema
from bson import ObjectId
import traceback

schedule_settings = Blueprint("schedule_settings", __name__)

@schedule_settings.route("/doctor/schedule-settings", methods=["GET"])
def get_schedule_settings():
    try:
        doctor_id = request.args.get("doctorId")
        if not doctor_id:
            return jsonify({"error": "Missing doctorId"}), 400

        db = current_app.db
        settings = db.doctor_schedule_settings.find_one({"doctorId": ObjectId(doctor_id)})

        if settings:
            settings["_id"] = str(settings["_id"])
            settings["doctorId"] = str(settings["doctorId"])
            return jsonify(settings), 200
        else:
            return jsonify({"message": "No settings found"}), 404

    except Exception as e:
        print("GET /doctor/schedule-settings Error:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@schedule_settings.route("/doctor/schedule-settings", methods=["POST"])
def update_schedule_settings():
    try:
        data = DoctorScheduleSettingsSchema(**request.get_json()).dict()
        data["doctorId"] = ObjectId(data["doctorId"])

        db = current_app.db
        db.doctor_schedule_settings.update_one(
            {"doctorId": data["doctorId"]},
            {"$set": data},
            upsert=True
        )

        return jsonify({"message": "Schedule settings saved successfully"}), 200

    except Exception as e:
        print("POST /doctor/schedule-settings Error:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500
