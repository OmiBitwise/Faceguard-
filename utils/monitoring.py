
import cv2 , threading
from flask_socketio import emit 
from flask import Blueprint, render_template, session, redirect, url_for, Response
from models.camera1 import Camera
from models.face_detector import FaceRecognition
from models.alert_system import AlertSystem
from database.mongo_db import MongoDB

monitoring_bp = Blueprint('monitoring', __name__)

camera = None
face_recognition_thread = None
is_monitoring = False

@monitoring_bp.route('/start_monitoring')
def start_monitoring():
    """Start the monitoring process"""
    """if 'user_id' not in session:
        return redirect(url_for('login.handle_login'))
    """
    return render_template('monitoring.html')

def emit_status_update(socketio, stats):
    socketio.emit('status_update', stats)

@monitoring_bp.route('/start_camera')
def start_camera():
    """Start the camera and begin monitoring"""
    socketio = current_app.extensions['socketio']
    start_monitoring(socketio)
    return {'status': 'success'}

@monitoring_bp.route('/stop_camera')
def stop_camera():
    """Stop the camera and monitoring"""
    socketio = current_app.extensions['socketio']
    stop_monitoring(socketio)
    return {'status': 'success'}



def stop_monitoring(socketio):
    """Stop face recognition monitoring"""
    global camera, is_monitoring
    
    if is_monitoring:
        is_monitoring = False
        
        # Wait for thread to terminate
        if face_recognition_thread and face_recognition_thread.is_alive():
            face_recognition_thread.join(timeout=1.0)
        
        # Release camera
        if camera:
            camera.release()
            camera = None
        
        socketio.emit('monitoring_status', {'status': 'stopped'})
        print("[INFO] Monitoring stopped")

def start_monitoring(socketio):
    """Start face recognition monitoring"""
    global camera, face_recognition_thread, is_monitoring
    
    if not is_monitoring:
        # Initialize camera
        camera = Camera()
        
        # Start face recognition thread
        is_monitoring = True
        face_recognition_thread = threading.Thread(target=process_frames, args=(socketio,))
        face_recognition_thread.daemon = True
        face_recognition_thread.start()
        
        socketio.emit('monitoring_status', {'status': 'started'})
        print("[INFO] Monitoring started")