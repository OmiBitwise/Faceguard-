from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.mongo_db import MongoDB

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if 'user_id' not in session:
        return redirect(url_for('login.handle_login'))
        
    mongo_db = MongoDB()
    
    if request.method == 'POST':
        email_to = request.form.get('email_to')
        
        # Save settings to MongoDB
        mongo_db.save_settings(email_to)
        mongo_db.save_user_email(session['user_id'],email_to)
        
        flash('Settings saved successfully', 'success')
        return redirect(url_for('settings.settings_page'))
    
    # Get current settings
    settings_data = mongo_db.get_settings(session['user_id'])
    
    return render_template('settings.html', settings=settings_data)