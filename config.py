import os
from datetime import timedelta

class Config:
    """Application configuration class"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Database settings
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/thadhesh-app')
    
    # File upload settings
    UPLOAD_FOLDER = 'uploads/audio'
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'ogg', 'webm', 'm4a'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Admin credentials
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'me')
    
    # Sample services data
    SAMPLE_SERVICES = [
        "What are the Kerala Building Rules for a residential construction?",
        "How can I find information about the Panchayath Raj Act?",
        "What are the procedures for obtaining a building permit from the municipality?",
        "Can you explain the Municipality Act regarding property taxes?",
        "What are the zoning regulations for commercial properties in my area?",
        "What are the functions of a Grama Panchayat as per the Panchayath Raj Act?"
    ]