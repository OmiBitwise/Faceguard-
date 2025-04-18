from flask import Blueprint, current_app
import time
import base64
import cv2
import threading

from models.camera1 import Camera
from models.face_detector import FaceRecognition
from models.alert_system import AlertSystem
from database.mongo_db import MongoDB

monitoring_bp = Blueprint('monitoring', __name__)

# Global variables
camera = None
face_recognition_thread = None
is_monitoring = False

def process_frames(socketio):
    """Process frames and detect faces"""
    global camera, is_monitoring
    
    # Initialize components
    mongo_db = MongoDB()
    
    # Load known faces
    known_face_encodings, known_face_names = mongo_db.get_face_encodings_and_names()
    face_detector = FaceRecognition(known_face_encodings, known_face_names)
    alert_system = AlertSystem(mongo_db)
    
    while is_monitoring and camera:
        # Get frame from camera
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        
        # Detect faces
        detected_faces = face_detector.detect_faces(frame)
        
        # Process each face
        current_time = time.time()
        for face in detected_faces:
            location = face['location']
            name = face['name']
            is_known = face['is_known']
            
            # Draw box
            top, right, bottom, left = location
            color = (0, 255, 0) if is_known else (255, 0, 0)  # Green for known, Blue for unknown
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
            
            # Handle unknown faces
            if not is_known:
                alert_system.handle_unknown_face(frame, location)
            else:
                alert_system.stats['authorized_count'] += 1
        
        # Update recordings
        alert_system.update_recordings(frame, current_time)
        
        # Convert frame to JPEG and emit to client
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = base64.b64encode(buffer).decode('utf-8')
        
        socketio.emit('video_frame', {'frame': frame_bytes})
        
        # Update stats
        socketio.emit('stats_update', alert_system.get_stats())
        
        # Sleep briefly to reduce CPU usage
        time.sleep(0.03)
    
    # Clean up
    if camera:
        camera.release()

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