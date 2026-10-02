from pymongo import MongoClient


# MongoDB connection string
MONGO_URI = "mongodb+srv://suryamsaini3_db_user:DziKLc2JFeoaX4dK@cluster0.yfd6kld.mongodb.net/?appName=Cluster0"


# Connect to MongoDB
client = MongoClient(MONGO_URI)

# Select database
db = client["classroom_engagement"]

# Select users collection
users = db["users"]

print("MongoDB connected successfully!")