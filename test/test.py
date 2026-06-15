from db_config import employees_collection

data = {
    "employee_id": 1,
    "name": "Rahul"
}

employees_collection.insert_one(data)

print("Inserted Successfully")