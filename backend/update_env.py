#!/usr/bin/env python3
"""
Script to update the .env file with the correct MongoDB Atlas connection string.
"""
import os

# Your actual MongoDB Atlas credentials
MONGO_URI = "mongodb+srv://namanh14122005:test123@signglove-cluster.2fgsv8h.mongodb.net/sign_glove?retryWrites=true&w=majority"
DB_NAME = "sign_glove"

# Read the current .env file
env_file = ".env"
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update the MONGO_URI and DB_NAME lines
    updated_lines = []
    for line in lines:
        if line.startswith("MONGO_URI="):
            updated_lines.append(f"MONGO_URI={MONGO_URI}\n")
        elif line.startswith("DB_NAME="):
            updated_lines.append(f"DB_NAME={DB_NAME}\n")
        else:
            updated_lines.append(line)
    
    # Write the updated content back
    with open(env_file, 'w') as f:
        f.writelines(updated_lines)
    
    print("✅ .env file updated with MongoDB Atlas credentials!")
    print(f"MONGO_URI: {MONGO_URI}")
    print(f"DB_NAME: {DB_NAME}")
else:
    print("❌ .env file not found!")
