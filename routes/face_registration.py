from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
import os , cv2 , numpy as np
import face_recognition
import time
from werkzeug.utils import secure_filename
from database.mongo_db import MongoDB

register_face_bp = Blueprint('register_face', __name__)

@register_face_bp.route('/register_face', methods=['GET', 'POST'])
def register_face():
    if 'user_id' not in session:
        return redirect(url_for('register_face.register_face'))
        
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
            
        # Save the image
        filename = secure_filename(f"{name}_{int(time.time())}.jpg")
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_FOLDER'])
            
        file.save(image_path)
        
        # Generate face encoding
        face_data_list = extract_faces_and_encodings(image_path)

        if not face_data_list:
            flash('No faces detected in the image', 'error')
            os.remove(image_path)
            return redirect(request.url)

        for name, encoding, cropped_img in face_data_list:
            cropped_filename = secure_filename(f"{name}_{int(time.time())}.jpg")
            cropped_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cropped_filename)
            cv2.imwrite(cropped_path, cropped_img)
            mongo_db.register_face(name, encoding, session['user_id'],cropped_path)

        flash(f'Successfully registered {len(face_data_list)} face(s)', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('register_face.html')

def extract_faces_and_encodings(image_path):
    #alg = "C:\\Users\\admin\\Desktop\\TyProject\\haarcascade_frontalface_alt.xml" 
    alg = os.path.join(current_app.root_path, "static", "haarcascade_frontalface_alt.xml")
    har_cas = cv2.CascadeClassifier(alg)

    img = cv2.imread(image_path)
    if img is None:
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    faces = har_cas.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    face_data = []

    for i, (x, y, w, h) in enumerate(faces):
        crop_img = img_rgb[y:y+h, x:x+w]
        crop_img_bgr = cv2.cvtColor(crop_img, cv2.COLOR_RGB2BGR)
        crop_img = np.ascontiguousarray(crop_img, dtype=np.uint8)

        cv2.imshow(f"Face {i+1}", crop_img)
        cv2.waitKey(1)
        name = input(f"Enter name for face {i+1}: ")
        cv2.destroyWindow(f"Face {i+1}")

        encodings = face_recognition.face_encodings(crop_img)
        if encodings:
            face_data.append((name, encodings[0], crop_img_bgr))

    cv2.destroyAllWindows()
    return face_data
