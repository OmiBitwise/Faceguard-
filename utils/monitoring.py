import cv2, threading, time, base64, os
from flask_socketio import emit
from flask import Blueprint, render_template, session, redirect, url_for, Response, current_app

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
    if 'user_id' not in session:
        return redirect(url_for('login.handle_login'))
    
    return render_template('monitoring.html')

def emit_status_update(socketio, stats):
    socketio.emit('status_update', stats)

@monitoring_bp.route('/start_camera')
def start_camera():
    """Start the camera and begin monitoring"""
    socketio = current_app.extensions['socketio']
    start_monitoring_process(socketio)
    return {'status': 'success'}

@monitoring_bp.route('/stop_camera')
def stop_camera():
    """Stop the camera and monitoring"""
    socketio = current_app.extensions['socketio']
    stop_monitoring_process(socketio)
    return {'status': 'success'}

class SimpleAlertSystem:
    def __init__(self, mongo_db, user_id):
        self.mongo_db = mongo_db
        self.user_id = user_id
        self.stats = {
            'authorized_count': 0,
            'unauthorized_count': 0
        }
        self.recording = False
        self.recording_frames = []
        self.recording_start_time = 0
        
    def reset_stats(self):
        """Reset counters for a new monitoring session"""
        self.stats = {
            'authorized_count': 0,
            'unauthorized_count': 0
        }
        db_stats = self.mongo_db.get_user_stats(self.user_id)
        if db_stats:
            self.stats['total_authorized'] = db_stats.get('authorized_count', 0)
            self.stats['total_unauthorized'] = db_stats.get('unauthorized_count', 0)
        
        # Reset database counters if needed
        # self.mongo_db.reset_user_stats(self.user_id)
        
        self.recording = False
        self.recording_frames = []
        
    def handle_unknown_face(self, frame, location):
        """Handle detection of unknown faces"""
        # Save a cropped image of the unknown face
        top, right, bottom, left = location
        face_img = frame[top:bottom, left:right]
        
        # Generate a unique filename for the image
        timestamp = int(time.time())
        image_filename = f"unknown_{timestamp}.jpg"
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], "alerts", image_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        # Save the image
        cv2.imwrite(image_path, face_img)
        
        # Start recording if not already
        if not self.recording:
            self.start_recording()
        
        # Record alert in database
        self.mongo_db.record_alert(
            user_id=self.user_id,
            image_path=image_path
        )
    
    def start_recording(self):
        """Start recording video"""
        self.recording = True
        self.recording_start_time = time.time()
        self.recording_frames = []
    
    def update_recordings(self, frame, current_time):
        """Update video recordings"""
        if self.recording:
            # Add frame to recording
            self.recording_frames.append(frame.copy())
            
            # Stop recording after 15 seconds
            if current_time - self.recording_start_time > 15 or len(self.recording_frames) > 150:  # 15s at 10fps
                self.save_recording()
                self.recording = False
    
    def save_recording(self):
        """Save the current recording"""
        if not self.recording_frames:
            return
            
        # Create a unique filename
        timestamp = int(time.time())
        filename = f"recording_{timestamp}.avi"
        recordings_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], "recordings")
        
        # Ensure directory exists
        os.makedirs(recordings_folder, exist_ok=True)
        
        filepath = os.path.join(recordings_folder, filename)
        
        # Get frame dimensions and FPS
        height, width = self.recording_frames[0].shape[:2]
        fps = 10.0
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
        
        # Write frames
        for frame in self.recording_frames:
            out.write(frame)
            
        # Release writer
        out.release()
        
        # Save recording info to database
        self.mongo_db.record_alert(
            user_id=self.user_id,
            video_path=filepath
        )
        
        # Clear frames
        self.recording_frames = []

    def update_db_stats(self):
        """Update the database with current session stats"""
        if self.stats['authorized_count'] > 0 or self.stats['unauthorized_count'] > 0:
            self.mongo_db.update_user_stats(
                self.user_id,
                authorized_increment=self.stats['authorized_count'],
                unauthorized_increment=self.stats['unauthorized_count']
            )
            # Reset session counters
            self.stats['authorized_count'] = 0
            self.stats['unauthorized_count'] = 0
            
            # Refresh totals
            db_stats = self.mongo_db.get_user_stats(self.user_id)
            if db_stats:
                self.stats['total_authorized'] = db_stats.get('authorized_count', 0)
                self.stats['total_unauthorized'] = db_stats.get('unauthorized_count', 0)
    

def process_frames(socketio):
    """Process frames and detect faces"""
    global camera, is_monitoring
    
    # Get current user_id from session
    user_id = session.get('user_id')
    if not user_id:
        socketio.emit('error', {'message': 'User not logged in'})
        is_monitoring = False
        return
    
    # Initialize components
    mongo_db = MongoDB()
    
    # Load known faces for current user
    known_face_encodings, known_face_names = mongo_db.get_face_encodings_and_names(user_id)
    
    if not known_face_encodings:
        socketio.emit('warning', {'message': 'No authorized faces registered. Unknown faces will not be detected correctly.'})
    
    face_detector = FaceRecognition(known_face_encodings, known_face_names)
    alert_system = SimpleAlertSystem(mongo_db, user_id)
    
    # Reset counters for this monitoring session
    alert_system.reset_stats()
    
    frame_count = 0  # Counter for processing every few frames
    
    while is_monitoring and camera:
        # Get frame from camera
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        
        # Only process every 3rd frame to reduce CPU load
        frame_count += 1
        if frame_count % 3 == 0:
            # Detect faces
            detected_faces = face_detector.detect_faces(frame)
            
            # Update stats counter
            stats_update_counter += 1
            
            # Update database stats every 50 processed frames (150 total frames)
            if stats_update_counter >= 50:
                alert_system.update_db_stats()
                stats_update_counter = 0

            # Process each face
            current_time = time.time()
            for face in detected_faces:
                location = face['location']
                name = face['name']
                is_known = face['is_known']
                
                # Draw box
                top, right, bottom, left = location
                color = (0, 255, 0) if is_known else (0, 0, 255)  # Green for known, Red for unknown
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                
                # Handle unknown faces
                if not is_known:
                    alert_system.handle_unknown_face(frame, location)
                    alert_system.stats['unauthorized_count'] += 1
                else:
                    alert_system.stats['authorized_count'] += 1
            
            # Update recordings
            alert_system.update_recordings(frame, current_time)
            
            # Update stats every 30 frames
            if frame_count % 30 == 0:
                socketio.emit('stats_update', alert_system.get_stats())
        
        # Convert frame to JPEG and emit to client
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = base64.b64encode(buffer).decode('utf-8')
        
        socketio.emit('video_frame', {'frame': frame_bytes})
        
        # Sleep briefly to reduce CPU usage
        time.sleep(0.03)
    
    alert_system.update_db_stats()

    # Clean up
    if camera:
        camera.release()

def stop_monitoring_process(socketio):
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

def start_monitoring_process(socketio):
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