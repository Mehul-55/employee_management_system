"""
Shared MongoDB configuration for the Employee Management System.

Works with both local MongoDB and MongoDB Atlas connection strings.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = (os.getenv("MONGO_URI") or "").strip().strip('"').strip("'")
DB_NAME = os.getenv("MONGO_DB_NAME") or "employee_attendance"
CONNECT_TIMEOUT_MS = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS") or "5000")

if not MONGO_URI:
    raise EnvironmentError(
        "MONGO_URI is not configured. Copy .env.example to .env and "
        "set your MongoDB connection string."
    )

if not MONGO_URI.startswith(("mongodb://", "mongodb+srv://")):
    raise EnvironmentError(
        "MONGO_URI must start with mongodb:// for local MongoDB or "
        "mongodb+srv:// for MongoDB Atlas."
    )


def using_atlas():
    return MONGO_URI.startswith("mongodb+srv://") or ".mongodb.net" in MONGO_URI


def connection_label():
    return "MongoDB Atlas" if using_atlas() else "local MongoDB"


client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
    connectTimeoutMS=CONNECT_TIMEOUT_MS,
    appname="EmployeeManagementSystem",
)
db = client[DB_NAME]

employees_col = db["employees"]
