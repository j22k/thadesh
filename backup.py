from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient, errors
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime, timedelta, UTC
import base64
from werkzeug.utils import secure_filename
import json
from functools import wraps


#load text-to-speech module 
try:
    from speech_to_text import transcribe_with_gcp
except ImportError:
    print("speech_to_text module not found. Ensure it is installed and available in the environment.")

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Database Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session expires after 24 hours
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/thadhesh-app')

# File upload configuration
UPLOAD_FOLDER = 'uploads/audio'
ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'ogg', 'webm', 'm4a'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize MongoDB
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client.get_database()
    users_collection = db['users']
    sessions_collection = db['user_sessions']
    audio_logs_collection = db['audio_logs']
    chat_history_collection = db['chat_history']
except errors.PyMongoError as e:
    users_collection = None
    sessions_collection = None
    audio_logs_collection = None
    chat_history_collection = None
    print(f"MongoDB connection error: {e}")

# Sample data for demonstration
SAMPLE_SERVICES = [
    "What are the Kerala Building Rules for a residential construction?",
    "How can I find information about the Panchayath Raj Act?",
    "What are the procedures for obtaining a building permit from the municipality?",
    "Can you explain the Municipality Act regarding property taxes?",
    "What are the zoning regulations for commercial properties in my area?",
    "What are the functions of a Grama Panchayat as per the Panchayath Raj Act?"
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def create_user_session(user_id, username):
    """Create a new user session and store it in database"""
    session_id = str(uuid.uuid4())
    session_data = {
        'session_id': session_id,
        'user_id': user_id,
        'username': username,
        'created_at': datetime.now(UTC),
        'last_activity': datetime.now(UTC),
        'is_active': True,
        'chat_count': 0,
        'audio_interactions': 0
    }
    
    if sessions_collection is not None:
        try:
            sessions_collection.insert_one(session_data)
        except errors.PyMongoError as e:
            print(f"Error creating session: {e}")
    
    # Store session in Flask session
    session['session_id'] = session_id
    session['user_id'] = str(user_id)
    session['username'] = username
    session['logged_in'] = True
    session.permanent = True
    
    return session_id

def update_session_activity(session_id):
    """Update session last activity timestamp"""
    if sessions_collection is not None and session_id:
        try:
            sessions_collection.update_one(
                {'session_id': session_id},
                {'$set': {'last_activity': datetime.now(UTC)}}
            )
        except errors.PyMongoError as e:
            print(f"Error updating session activity: {e}")

def log_audio_interaction(session_id, user_id, audio_data=None, audio_file_path=None, transcript=None, language='english'):
    """Log audio interaction to database"""
    audio_log = {
        'session_id': session_id,
        'user_id': user_id,
        'timestamp': datetime.now(UTC),
        'audio_file_path': audio_file_path,
        'transcript': transcript,
        'language': language,
        'audio_duration': None,  # Can be calculated from audio file
        'processing_status': 'pending'
    }
    
    if audio_logs_collection is not None:
        try:
            result = audio_logs_collection.insert_one(audio_log)
            
            # Update session audio interaction count
            if sessions_collection is not None:
                sessions_collection.update_one(
                    {'session_id': session_id},
                    {'$inc': {'audio_interactions': 1}}
                )
            
            return str(result.inserted_id)
        except errors.PyMongoError as e:
            print(f"Error logging audio interaction: {e}")
    
    return None

def save_chat_message(session_id, user_id, message, message_type, response=None, language='english'):
    """Save chat message to database"""
    chat_data = {
        'session_id': session_id,
        'user_id': user_id,
        'timestamp': datetime.now(UTC),
        'message': message,
        'message_type': message_type,  # 'user' or 'assistant'
        'response': response,
        'language': language
    }
    
    if chat_history_collection is not None:
        try:
            chat_history_collection.insert_one(chat_data)
            
            # Update session chat count
            if sessions_collection is not None and message_type == 'user':
                sessions_collection.update_one(
                    {'session_id': session_id},
                    {'$inc': {'chat_count': 1}}
                )
        except errors.PyMongoError as e:
            print(f"Error saving chat message: {e}")

def require_login(f):
    """Decorator to require user login"""
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == 'admin' and auth.password == 'me'):
            return ("Unauthorized", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html', services=SAMPLE_SERVICES)

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/chat')
@require_login
def chat():
    # Update session activity
    update_session_activity(session.get('session_id'))
    return render_template('chat.html', services=SAMPLE_SERVICES)

@app.route('/logout')
def logout():
    """Handle user logout"""
    session_id = session.get('session_id')
    
    # Mark session as inactive in database
    if sessions_collection is not None and session_id:
        try:
            sessions_collection.update_one(
                {'session_id': session_id},
                {'$set': {'is_active': False, 'logged_out_at': datetime.now(UTC)}}
            )
        except errors.PyMongoError as e:
            print(f"Error updating session on logout: {e}")
    
    # Clear Flask session
    session.clear()
    return redirect(url_for('home'))

@app.route('/auth/sign_up', methods=['POST'])
def signup_auth():
    """Handle user signup - create a new user in the database"""
    username = request.form.get('email')
    mobile = request.form.get('mobile')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if not username or not mobile or not password or not confirm_password:
        return render_template('signup.html', message='All fields are required.', username=username, mobile=mobile)
    if password != confirm_password:
        return render_template('signup.html', message='Passwords do not match.', username=username, mobile=mobile)
    if users_collection is None:
        return render_template('signup.html', message='Database connection error.', username=username, mobile=mobile)
    try:
        # Check for existing user
        if users_collection.find_one({'$or': [{'username': username}, {'mobile': mobile}]}):
            return render_template('signup.html', message='User already exists.', username=username, mobile=mobile)
        
        user_doc = {
            'username': username, 
            'mobile': mobile, 
            'password': password,
            'created_at': datetime.now(UTC),
            'last_login': None
        }
        result = users_collection.insert_one(user_doc)
        if not result.acknowledged:
            return render_template('signup.html', message='Error creating user. Please try again.', username=username, mobile=mobile)
        
        return render_template('login.html', message='Sign up successful! Please log in.')
    except errors.PyMongoError as e:
        return render_template('signup.html', message=f'Error creating user: {e}', username=username, mobile=mobile)

@app.route('/auth/login', methods=['POST'])
def login_auth():
    """Handle user login - verify user credentials"""
    username = request.form.get('email_or_mobile')
    password = request.form.get('password')
    
    if users_collection is None:
        return render_template('login.html', message='Database connection error.')
    
    try:
        user = users_collection.find_one({'$or': [{'username': username}, {'mobile': username}]})
        if user and user.get('password') == password:
            # Update last login
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.now(UTC)}}
            )
            
            # Create user session
            create_user_session(user['_id'], user['username'])
            
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', message='Invalid credentials.')
    except errors.PyMongoError as e:
        return render_template('login.html', message=f'Error during login: {e}')

@app.route('/api/chat', methods=['POST'])
@require_login
def chat_api():
    """API endpoint for chat messages - implement your backend logic here"""
    data = request.get_json()
    user_message = data.get('message', '')
    language = data.get('language', 'english')
    
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    
    # Update session activity
    update_session_activity(session_id)
    
    # TODO: Implement your chat logic here
    # For now, return a simple response
    response_message = f"Hello! I'm Thadhesh, your digital assistant. You asked: '{user_message}'. How can I help you with government services today?"
    
    if language == 'malayalam':
        response_message = f"നമസ്കാരം! ഞാൻ തഢേഷ്, നിങ്ങളുടെ ഡിജിറ്റൽ സഹായിയാണ്. നിങ്ങൾ ചോദിച്ചു: '{user_message}'. സർക്കാർ സേവനങ്ങളിൽ ഞാൻ നിങ്ങളെ എങ്ങനെ സഹായിക്കാം?"
    
    response = {
        'message': response_message,
        'timestamp': datetime.now().strftime('%I:%M %p'),
        'source_reference': 'Kerala Building Rules, Panchayath Raj Act, Municipality Act'
    }
    
    # Save chat messages to database
    save_chat_message(session_id, user_id, user_message, 'user', language=language)
    save_chat_message(session_id, user_id, response_message, 'assistant', language=language)
    
    return jsonify(response)

@app.route('/api/upload_audio', methods=['POST'])
@require_login
def upload_audio():
    """Handle audio file upload and logging"""
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    
    # Update session activity
    update_session_activity(session_id)
    
    # Check if audio data is provided
    if 'audio_data' in request.json:
        # Handle base64 encoded audio data
        audio_data = request.json.get('audio_data')
        language = request.json.get('language', 'english')
        transcript = request.json.get('transcript', '')
        # Print transcript received from frontend
        print(f"Received transcript from frontend: {transcript}")
        
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data.split(',')[1] if ',' in audio_data else audio_data)
            
            # Generate filename
            filename = f"audio_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # Save audio file
            with open(file_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Transcribe audio using GCP
            transcription = transcribe_with_gcp(file_path)
            print(f"Transcription: {transcription}")
            
            # Log audio interaction
            audio_log_id = log_audio_interaction(
                session_id=session_id,
                user_id=user_id,
                audio_file_path=file_path,
                transcript=transcript,
                language=language
            )
            
            
            
            return jsonify({
                'success': True,
                'message': 'Audio uploaded successfully',
                'audio_log_id': audio_log_id,
                'file_path': file_path,
                'transcription': transcription
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error processing audio: {str(e)}'
            }), 500
    
    # Handle file upload
    elif 'audio_file' in request.files:
        file = request.files['audio_file']
        language = request.form.get('language', 'english')
        transcript = request.form.get('transcript', '')
        
        if file and file.filename and allowed_file(file.filename):
            # Print transcript received from frontend (file upload)
            print(f"Received transcript from frontend (file upload): {transcript}")
            filename = secure_filename(f"{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # Log audio interaction
            audio_log_id = log_audio_interaction(
                session_id=session_id,
                user_id=user_id,
                audio_file_path=file_path,
                transcript=transcript,
                language=language
            )
            
            return jsonify({
                'success': True,
                'message': 'Audio file uploaded successfully',
                'audio_log_id': audio_log_id,
                'file_path': file_path
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid file type. Please upload a valid audio file.'
            }), 400
    
    return jsonify({
        'success': False,
        'message': 'No audio data provided'
    }), 400

@app.route('/api/session_info')
@require_login
def session_info():
    """Get current session information"""
    session_id = session.get('session_id')
    
    if sessions_collection is not None and session_id:
        try:
            session_data = sessions_collection.find_one({'session_id': session_id})
            if session_data:
                # Convert ObjectId to string for JSON serialization
                session_data['_id'] = str(session_data['_id'])
                session_data['user_id'] = str(session_data['user_id'])
                return jsonify({
                    'success': True,
                    'session': session_data
                })
        except errors.PyMongoError as e:
            return jsonify({
                'success': False,
                'message': f'Error retrieving session info: {e}'
            }), 500
    
    return jsonify({
        'success': False,
        'message': 'Session not found'
    }), 404

@app.route('/api/chat_history')
@require_login
def get_chat_history():
    """Get chat history for current session"""
    session_id = session.get('session_id')
    
    if chat_history_collection is not None and session_id:
        try:
            messages = list(chat_history_collection.find(
                {'session_id': session_id}
            ).sort('timestamp', 1))
            
            # Convert ObjectId to string for JSON serialization
            for msg in messages:
                msg['_id'] = str(msg['_id'])
                msg['user_id'] = str(msg['user_id'])
            
            return jsonify({
                'success': True,
                'messages': messages
            })
        except errors.PyMongoError as e:
            return jsonify({
                'success': False,
                'message': f'Error retrieving chat history: {e}'
            }), 500
    
    return jsonify({
        'success': False,
        'message': 'No chat history found'
    }), 404

@app.route('/api/audio_logs')
@require_login
def get_audio_logs():
    """Get audio logs for current session"""
    session_id = session.get('session_id')
    
    if audio_logs_collection is not None and session_id:
        try:
            logs = list(audio_logs_collection.find(
                {'session_id': session_id}
            ).sort('timestamp', 1))
            
            # Convert ObjectId to string for JSON serialization
            for log in logs:
                log['_id'] = str(log['_id'])
                log['user_id'] = str(log['user_id'])
            
            return jsonify({
                'success': True,
                'audio_logs': logs
            })
        except errors.PyMongoError as e:
            return jsonify({
                'success': False,
                'message': f'Error retrieving audio logs: {e}'
            }), 500
    
    return jsonify({
        'success': False,
        'message': 'No audio logs found'
    }), 404

@app.route('/admin')
@admin_required
def admin_log():
    users = list(users_collection.find({})) if users_collection is not None else []
    for user in users:
        user['_id'] = str(user['_id'])
    chat_logs = list(chat_history_collection.find({}).sort('timestamp', -1)) if chat_history_collection is not None else []
    for chat in chat_logs:
        chat['_id'] = str(chat['_id'])
        chat['user_id'] = str(chat['user_id'])
    audio_logs = list(audio_logs_collection.find({}).sort('timestamp', -1)) if audio_logs_collection is not None else []
    for log in audio_logs:
        log['_id'] = str(log['_id'])
        log['user_id'] = str(log['user_id'])
    return render_template('admin.html', users=users, chat_logs=chat_logs, audio_logs=audio_logs)

@app.route('/db_status')
def db_status():
    try:
        if users_collection is None:
            raise Exception('MongoDB connection not established.')
        # Try a simple query
        users_collection.find_one()
        return jsonify({'status': 'success', 'message': 'Database connection successful.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)