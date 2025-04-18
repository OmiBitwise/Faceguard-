from flask import Blueprint,render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from database.mongo_db import MongoDB

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['GET', 'POST'])


def handle_login():
    # Initialize MongoDB connection
    mongo_db = MongoDB()
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate form data
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')
        
        # Find user by email
        mongo_db = MongoDB()
        user = mongo_db.find_user_by_email(email)
        
        # Check if user exists and password is correct
        if not user or not check_password_hash(user['password'], password):
            flash('Invalid email or password', 'error')
            return render_template('login.html')

        if user:  
        # Set session variables
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['email'] = user['email']
            
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('homepage'))
        else:
            flash('Invalid email or password','error')
    
    # GET request - display the login form
    return render_template('login.html')