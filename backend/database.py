import os
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://suryamsaini3_db_user:DziKLc2JFeoaX4dK@cluster0.yfd6kld.mongodb.net/?appName=Cluster0"

client = MongoClient(MONGO_URI)

db = client["classroom_engagement"]
users = db["users"]

print("MongoDB connected successfully!")
