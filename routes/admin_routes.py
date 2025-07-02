from flask import Blueprint, render_template, request, session, redirect, url_for, current_app
from functools import wraps
from models import UserModel, ChatModel, AudioModel, SessionModel

admin_bp = Blueprint('admin', __name__)

# Simple HTTP Basic Auth for admin
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'me'

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD):
            return ("Unauthorized", 401, {'WWW-Authenticate': 'Basic realm=\"Login Required\"'})
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    users = UserModel.get_all_users()
    chat_logs = ChatModel.get_all_chats()
    audio_logs = AudioModel.get_all_audio_logs()
    sessions = SessionModel.get_all_sessions() if hasattr(SessionModel, 'get_all_sessions') else []
    return render_template('admin.html', users=users, chat_logs=chat_logs, audio_logs=audio_logs, sessions=sessions)

# Optionally, add more admin routes for user/session management, analytics, etc.
