"""
Shared MongoDB configuration for the Employee Management System.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME") or "employee_attendance"

if not MONGO_URI:
    raise EnvironmentError(
        "MONGO_URI is not configured. Copy .env.example to .env and "
        "set your MongoDB connection string."
    )

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client[DB_NAME]

employees_col = db["employees"]
