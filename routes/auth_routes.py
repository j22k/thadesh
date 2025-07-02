from flask import Blueprint, render_template, request, redirect, url_for, session
from models import UserModel, SessionModel

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/sign_up', methods=['POST'])
def signup():
    """Handle user signup"""
    username = request.form.get('email')
    mobile = request.form.get('mobile')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Validation
    if not username or not mobile or not password or not confirm_password:
        return render_template('signup.html', 
                             message='All fields are required.',
                             username=username, mobile=mobile)
    
    if password != confirm_password:
        return render_template('signup.html',
                             message='Passwords do not match.',
                             username=username, mobile=mobile)
    
    # Create user
    user_id, message = UserModel.create_user(username, mobile, password)
    
    if user_id:
        return render_template('login.html', message='Sign up successful! Please log in.')
    else:
        return render_template('signup.html',
                             message=message,
                             username=username, mobile=mobile)

@auth_bp.route('/login', methods=['POST'])
def login():
    """Handle user login"""
    username = request.form.get('email_or_mobile')
    password = request.form.get('password')
    
    if not username or not password:
        return render_template('login.html', message='Username and password are required.')
    
    print(f"Attempting login for user: {username}")  # Debugging line
    # Authenticate user
    user, message = UserModel.authenticate_user(username, password)
    print(f"Authentication result: {user}, Message: {message}")  # Debugging line
    
    if user:
        # Create session
        session_id = SessionModel.create_session(user['_id'], user['username'])
        
        # Set Flask session
        session['session_id'] = session_id
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['logged_in'] = True
        session.permanent = True
        
        return redirect(url_for('chat.chat_page'))
    else:
        return render_template('login.html', message=message)

@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    session_id = session.get('session_id')
    
    # Mark session as inactive in database
    if session_id:
        SessionModel.deactivate_session(session_id)
    
    # Clear Flask session
    session.clear()
    return redirect(url_for('main.index'))