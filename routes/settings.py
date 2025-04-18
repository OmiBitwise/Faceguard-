from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.mongo_db import MongoDB
from bson import ObjectId 

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if 'user_id' not in session:
        return redirect(url_for('login.handle_login'))
        
    mongo_db = MongoDB()
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Only update if new values are provided
        result = mongo_db.update_user_credentials(
            ObjectId(session['user_id']),
            email=email if email else None,
            password=password if password else None
        )
        
        if result:
            flash('Settings saved successfully', 'success')
        else:
            flash('No changes were made', 'info')
            
        return redirect(url_for('settings.settings_page'))
    
    # Get current user data
    user_data = mongo_db.find_user_by_id(ObjectId(session['user_id']))
    
    return render_template('settings.html', user=user_data)