from flask import Blueprint, render_template, current_app

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page"""
    services = current_app.config.get('SAMPLE_SERVICES', [])
    return render_template('index.html', services=services)

@main_bp.route('/signup')
def signup():
    """Signup page"""
    return render_template('signup.html')

@main_bp.route('/login')
def login():
    """Login page"""
    return render_template('login.html')