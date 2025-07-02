from datetime import datetime, UTC
from pymongo import errors
import uuid
from database import get_db_collections

class UserModel:
    """User model for database operations"""
    
    @staticmethod
    def create_user(username, mobile, password):
        """Create a new user"""
        collections = get_db_collections()
        users_collection = collections['users']
        
        if users_collection is None:
            return None, "Database connection error"
        
        try:
            # Check for existing user
            if users_collection.find_one({'$or': [{'username': username}, {'mobile': mobile}]}):
                return None, "User already exists"
            
            user_doc = {
                'username': username,
                'mobile': mobile,
                'password': password,  # In production, hash this password
                'created_at': datetime.now(UTC),
                'last_login': None,
                'is_active': True
            }
            
            result = users_collection.insert_one(user_doc)
            if result.acknowledged:
                return str(result.inserted_id), "User created successfully"
            else:
                return None, "Error creating user"
                
        except errors.PyMongoError as e:
            return None, f"Database error: {e}"
    
    @staticmethod
    def authenticate_user(username, password):
        """Authenticate user credentials"""
        collections = get_db_collections()
        users_collection = collections['users']
        
        if users_collection is None:
            return None, "Database connection error"
        
        try:
            user = users_collection.find_one({
                '$or': [{'username': username}, {'mobile': username}],
                'is_active': True
            })
            
            if user and user.get('password') == password:
                # Update last login
                users_collection.update_one(
                    {'_id': user['_id']},
                    {'$set': {'last_login': datetime.now(UTC)}}
                )
                return user, "Authentication successful"
            else:
                return None, "Invalid credentials"
                
        except errors.PyMongoError as e:
            return None, f"Database error: {e}"
    
    @staticmethod
    def get_all_users():
        """Get all users (admin function)"""
        collections = get_db_collections()
        users_collection = collections['users']
        
        if users_collection is None:
            return []
        
        try:
            users = list(users_collection.find({}))
            for user in users:
                user['_id'] = str(user['_id'])
                # Remove password from response
                user.pop('password', None)
            return users
        except errors.PyMongoError as e:
            print(f"Error getting users: {e}")
            return []

class SessionModel:
    """Session model for database operations"""
    
    @staticmethod
    def create_session(user_id, username):
        """Create a new user session"""
        collections = get_db_collections()
        sessions_collection = collections['sessions']
        
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
        
        return session_id
    
    @staticmethod
    def update_session_activity(session_id):
        """Update session last activity timestamp"""
        collections = get_db_collections()
        sessions_collection = collections['sessions']
        
        if sessions_collection is not None and session_id:
            try:
                sessions_collection.update_one(
                    {'session_id': session_id},
                    {'$set': {'last_activity': datetime.now(UTC)}}
                )
            except errors.PyMongoError as e:
                print(f"Error updating session activity: {e}")
    
    @staticmethod
    def deactivate_session(session_id):
        """Mark session as inactive"""
        collections = get_db_collections()
        sessions_collection = collections['sessions']
        
        if sessions_collection is not None and session_id:
            try:
                sessions_collection.update_one(
                    {'session_id': session_id},
                    {
                        '$set': {
                            'is_active': False,
                            'logged_out_at': datetime.now(UTC)
                        }
                    }
                )
            except errors.PyMongoError as e:
                print(f"Error deactivating session: {e}")
    
    @staticmethod
    def get_session_info(session_id):
        """Get session information"""
        collections = get_db_collections()
        sessions_collection = collections['sessions']
        
        if sessions_collection is not None and session_id:
            try:
                session_data = sessions_collection.find_one({'session_id': session_id})
                if session_data:
                    session_data['_id'] = str(session_data['_id'])
                    session_data['user_id'] = str(session_data['user_id'])
                    return session_data
            except errors.PyMongoError as e:
                print(f"Error retrieving session info: {e}")
        
        return None

class ChatModel:
    """Chat model for database operations"""
    
    @staticmethod
    def save_message(session_id, user_id, message, message_type, response=None, language='english'):
        """Save chat message to database"""
        collections = get_db_collections()
        chat_history_collection = collections['chat_history']
        sessions_collection = collections['sessions']
        
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
                
                # Update session chat count for user messages
                if sessions_collection is not None and message_type == 'user':
                    sessions_collection.update_one(
                        {'session_id': session_id},
                        {'$inc': {'chat_count': 1}}
                    )
            except errors.PyMongoError as e:
                print(f"Error saving chat message: {e}")
    
    @staticmethod
    def get_chat_history(session_id):
        """Get chat history for a session"""
        collections = get_db_collections()
        chat_history_collection = collections['chat_history']
        
        if chat_history_collection is not None and session_id:
            try:
                messages = list(chat_history_collection.find(
                    {'session_id': session_id}
                ).sort('timestamp', 1))
                
                for msg in messages:
                    msg['_id'] = str(msg['_id'])
                    msg['user_id'] = str(msg['user_id'])
                
                return messages
            except errors.PyMongoError as e:
                print(f"Error retrieving chat history: {e}")
        
        return []
    
    @staticmethod
    def get_all_chat_logs():
        """Get all chat logs (admin function)"""
        collections = get_db_collections()
        chat_history_collection = collections['chat_history']
        
        if chat_history_collection is None:
            return []
        
        try:
            chat_logs = list(chat_history_collection.find({}).sort('timestamp', -1))
            for chat in chat_logs:
                chat['_id'] = str(chat['_id'])
                chat['user_id'] = str(chat['user_id'])
            return chat_logs
        except errors.PyMongoError as e:
            print(f"Error getting chat logs: {e}")
            return []

class AudioModel:
    """Audio model for database operations"""
    
    @staticmethod
    def log_audio_interaction(session_id, user_id, audio_file_path=None, transcript=None, language='english'):
        """Log audio interaction to database"""
        collections = get_db_collections()
        audio_logs_collection = collections['audio_logs']
        sessions_collection = collections['sessions']
        
        audio_log = {
            'session_id': session_id,
            'user_id': user_id,
            'timestamp': datetime.now(UTC),
            'audio_file_path': audio_file_path,
            'transcript': transcript,
            'language': language,
            'audio_duration': None,
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
    
    @staticmethod
    def get_audio_logs(session_id):
        """Get audio logs for a session"""
        collections = get_db_collections()
        audio_logs_collection = collections['audio_logs']
        
        if audio_logs_collection is not None and session_id:
            try:
                logs = list(audio_logs_collection.find(
                    {'session_id': session_id}
                ).sort('timestamp', 1))
                
                for log in logs:
                    log['_id'] = str(log['_id'])
                    log['user_id'] = str(log['user_id'])
                
                return logs
            except errors.PyMongoError as e:
                print(f"Error retrieving audio logs: {e}")
        
        return []
    
    @staticmethod
    def get_all_audio_logs():
        """Get all audio logs (admin function)"""
        collections = get_db_collections()
        audio_logs_collection = collections['audio_logs']
        
        if audio_logs_collection is None:
            return []
        
        try:
            audio_logs = list(audio_logs_collection.find({}).sort('timestamp', -1))
            for log in audio_logs:
                log['_id'] = str(log['_id'])
                log['user_id'] = str(log['user_id'])
            return audio_logs
        except errors.PyMongoError as e:
            print(f"Error getting audio logs: {e}")
            return []