import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_config

# Step 1: Get the MongoDB collection object from db_config
employees_collection = db_config.db["employees"]  # ← MongoDB collection

# Step 2: Your data goes in a SEPARATE list
employees_data = [
    {"emp_id": 1, "name": "Aman Sharma",  "department": "HR",      "salary": 30000},
    {"emp_id": 2, "name": "Neha Verma",   "department": "IT",      "salary": 50000},
    {"emp_id": 3, "name": "Rohit Meena",  "department": "Finance", "salary": 45000},
    {"emp_id": 4, "name": "Priya Singh",  "department": "IT",      "salary": 55000},
    {"emp_id": 5, "name": "Karan Patel",  "department": "Admin",   "salary": 28000},
    {"emp_id": 6, "name": "Sneha Joshi",  "department": "HR",      "salary": 32000},
    {"emp_id": 7, "name": "Vikram Rao",   "department": "IT",      "salary": 60000},
    {"emp_id": 8, "name": "Anjali Gupta", "department": "Finance", "salary": 47000},
    {"emp_id": 9, "name": "Mohit Jain",   "department": "Support", "salary": 25000},
    {"emp_id": 10, "name": "Pooja Desai", "department": "Admin",   "salary": 30000}
]

# Step 3: Insert the LIST into the MongoDB COLLECTION
result = employees_collection.insert_many(employees_data)  # ✅ correct

print("Employees inserted successfully!")
print("Inserted IDs:", result.inserted_ids)