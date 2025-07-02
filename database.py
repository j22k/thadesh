from pymongo import MongoClient, errors
import os

# Global database variables
mongo_client = None
db = None
users_collection = None
sessions_collection = None
audio_logs_collection = None
chat_history_collection = None

def init_db(app):
    """Initialize MongoDB connection and collections"""
    global mongo_client, db, users_collection, sessions_collection, audio_logs_collection, chat_history_collection
    
    try:
        mongo_client = MongoClient(app.config['MONGO_URI'])
        db = mongo_client.get_database()
        
        # Initialize collections
        users_collection = db['users']
        sessions_collection = db['user_sessions']
        audio_logs_collection = db['audio_logs']
        chat_history_collection = db['chat_history']
        
        # Create indexes for better performance
        create_indexes()
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        print("Database initialized successfully")
        
    except errors.PyMongoError as e:
        print(f"MongoDB connection error: {e}")
        users_collection = None
        sessions_collection = None
        audio_logs_collection = None
        chat_history_collection = None

def create_indexes():
    """Create database indexes for better performance"""
    try:
        if users_collection is not None:
            users_collection.create_index([("username", 1)], unique=True)
            users_collection.create_index([("mobile", 1)], unique=True)
            
        if sessions_collection is not None:
            sessions_collection.create_index([("session_id", 1)], unique=True)
            sessions_collection.create_index([("user_id", 1)])
            sessions_collection.create_index([("created_at", 1)])
            
        if chat_history_collection is not None:
            chat_history_collection.create_index([("session_id", 1)])
            chat_history_collection.create_index([("user_id", 1)])
            chat_history_collection.create_index([("timestamp", 1)])
            
        if audio_logs_collection is not None:
            audio_logs_collection.create_index([("session_id", 1)])
            audio_logs_collection.create_index([("user_id", 1)])
            audio_logs_collection.create_index([("timestamp", 1)])
            
    except errors.PyMongoError as e:
        print(f"Error creating indexes: {e}")

def get_db_collections():
    """Get all database collections"""
    return {
        'users': users_collection,
        'sessions': sessions_collection,
        'audio_logs': audio_logs_collection,
        'chat_history': chat_history_collection
    }

def check_db_connection():
    """Check if database connection is healthy"""
    try:
        if users_collection is None:
            return False, "MongoDB connection not established"
        # Try a simple query
        users_collection.find_one()
        return True, "Database connection successful"
    except Exception as e:
        return False, str(e)