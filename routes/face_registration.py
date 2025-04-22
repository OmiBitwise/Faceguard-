from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
import os, cv2, numpy as np
import face_recognition
import time
from werkzeug.utils import secure_filename
from database.mongo_db import MongoDB

register_face_bp = Blueprint('register_face', __name__)

@register_face_bp.route('/register_face', methods=['GET', 'POST'])
def register_face():
    if 'user_id' not in session:
        return redirect(url_for('login.handle_login'))  # Redirect to login
        
    mongo_db = MongoDB()
    
    if request.method == 'POST':
        if 'face_image' not in request.files:
            flash('No file provided', 'error')
            return redirect(request.url)
            
        file = request.files['face_image']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
            
        name = request.form.get('name')
        
        if not name:
            flash('Please provide a name', 'error')
            return redirect(request.url)
            
        # Create uploads folder inside static if it doesn't exist
        upload_folder = os.path.join(current_app.static_folder, 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # Save the original image temporarily
        temp_filename = secure_filename(f"temp_{int(time.time())}.jpg")
        temp_path = os.path.join(upload_folder, temp_filename)
        file.save(temp_path)
        
        # Process the image to detect and extract faces
        img = cv2.imread(temp_path)
        if img is None:
            flash('Could not read the uploaded image', 'error')
            return redirect(request.url)
            
        # Convert to RGB for face_recognition
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Use face_recognition to detect faces directly
        face_locations = face_recognition.face_locations(img_rgb)
        
        if not face_locations:
            flash('No faces detected in the image', 'error')
            os.remove(temp_path)  # Clean up temp file
            return redirect(request.url)
            
        user_id = session['user_id']
        registered_count = 0
        
        for i, face_location in enumerate(face_locations):
            top, right, bottom, left = face_location
            
            # Crop the face
            crop_img = img_rgb[top:bottom, left:right]
            crop_img = np.ascontiguousarray(crop_img, dtype=np.uint8)
            
            # Get face encoding
            encodings = face_recognition.face_encodings(crop_img)
            if not encodings:
                continue
                
            # Use the provided name for all faces or add a number if multiple faces
            face_name = name if len(face_locations) == 1 else f"{name}_{i+1}"
            
            # Convert back to BGR for OpenCV save
            crop_img_bgr = cv2.cvtColor(crop_img, cv2.COLOR_RGB2BGR)
            
            # Save the cropped face
            cropped_filename = secure_filename(f"{face_name}_{int(time.time())}.jpg")
            cropped_path = os.path.join(upload_folder, cropped_filename)
            cv2.imwrite(cropped_path, crop_img_bgr)
            
            # Store in database with the correct path (relative to static folder for web access)
            db_path = f"uploads/{cropped_filename}"
            result = mongo_db.register_face(face_name, encodings[0], user_id, db_path)
            
            if result:
                registered_count += 1
                print(f"Successfully registered face: {face_name}, ID: {result}")
            else:
                print(f"Failed to register face: {face_name}")
                
        # Remove the temporary file
        os.remove(temp_path)
        
        if registered_count > 0:
            flash(f'Successfully registered {registered_count} face(s)', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Failed to register any faces', 'error')
            return redirect(request.url)
            
    return render_template('register_face.html')