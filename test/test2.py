from pymongo import MongoClient

try:
    # Connect MongoDB
    client = MongoClient("mongodb://localhost:27017/")

    print("MongoDB Connected")

    # Create Database
    db = client["employee_attendance"]

    print("Database Selected")

    # Create Collection
    attendance_collection = db["attendance"]

    print("Collection Selected")

    # Attendance Data
    attendance_data = {
        "employee_id": 1,
        "name": "Rahul",
        "date": "2026-05-22",
        "status": "Present"
    }

    # Insert Data
    result = attendance_collection.insert_one(attendance_data)

    print("Attendance Inserted Successfully")
    print("Inserted ID:", result.inserted_id)

except Exception as e:
    print("ERROR:", e)