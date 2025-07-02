from flask import Flask
from dotenv import load_dotenv
import os
from datetime import timedelta

from config import Config
from database import init_db
from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp
from routes.main_routes import main_bp

# Load environment variables
load_dotenv()

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)