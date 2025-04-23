from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from database.mongo_db import MongoDB
import re

register_bp = Blueprint('register', __name__)

@register_bp.route('/register', methods=['GET', 'POST'])


def handle_register():
    # Initialize MongoDB connection
    mongo_db = MongoDB()
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate form data
        if not all([username, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if "@" not in email or "gmail.com" not in email:
            flash('Email must be a valid Gmail address', 'error')
            return render_template('register.html')
        
        password_pattern = re.compile(
        r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{7,}$'
)

        if not password_pattern.match(password):
            flash('Password must be more than 6 characters and contain at least one uppercase letter, one lowercase letter, one digit, and one special character.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        mongo_db = MongoDB()
        existing_user = mongo_db.find_user_by_email(email)
        if existing_user:
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        mongo_db = MongoDB()
        # Create new user
        user = {
            'username': username,
            'email': email,
            'password': hashed_password
        }
        
        # Insert user into database
        mongo_db.create_user(username,email,password)
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login.handle_login'))
    
    # GET request - display the registration form
    return render_template('register.html')