from flask import Blueprint, render_template, current_app
from utils import require_login
from models import SessionModel

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
@require_login
def chat_page():
    """Chat page - main application interface"""
    from flask import session
    
    # Update session activity
    session_id = session.get('session_id')
    if session_id:
        SessionModel.update_session_activity(session_id)
    
    services = current_app.config.get('SAMPLE_SERVICES', [])
    return render_template('chat.html', services=services)