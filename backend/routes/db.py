from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client.mediconnect

doctor_profiles_collection = db.doctor_profiles
doctor_availability_collection = db.doctor_availability
