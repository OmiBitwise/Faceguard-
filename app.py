#project
from flask import Flask, render_template, session, redirect, url_for, flash , request , Response
from flask_socketio import SocketIO
import secrets
import os , cv2, time , threading
from database.mongo_db import MongoDB
from config import Config
from models.camera1 import Camera


camera_thread = None
camera_active = False

# Import route handlers
from routes.face_registration import register_face_bp
from routes.settings import settings_bp
from routes.registration import register_bp
from routes.login import login_bp
from utils.monitoring import monitoring_bp



# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app)

# Register blueprints
app.register_blueprint(register_face_bp)
app.register_blueprint(monitoring_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(register_bp)
app.register_blueprint(login_bp)

# Main routes
@app.route('/')
def index():
    return render_template('landing.html')
@app.route('/index')
def homepage():
    return render_template('index.html')
@app.route('/login')
def landing():
    return render_template('register.handle_register')

@app.route('/dashboard')
def dashboard():


    mongo_db = MongoDB()
    authorized_faces = mongo_db.get_authorized_faces()
    # Other dashboard data...
    return render_template('dashboard.html',
                            authorized_faces=authorized_faces,
                        )
    
    mongo_db = MongoDB()
    authorized_faces = mongo_db.get_authorized_faces()
    recent_alerts = mongo_db.get_recent_alerts()
    stats = mongo_db.get_stats()
    
    return render_template('dashboard.html', 
                         authorized_faces=authorized_faces, 
                         recent_alerts=recent_alerts,
                         **stats)   

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    def gen(camera):
        try:
            while True:
                frame, _, _ = camera.process_frame()
                if frame is None:
                    break
                    
                # Resize frame to reduce bandwidth
                frame = cv2.resize(frame, (640, 480))
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                # Add a small delay to reduce CPU usage
                time.sleep(0.05)
        except Exception as e:
            print(f"Error in video stream: {e}")
        finally:
            camera.release()
    
    try:
        camera = Camera()
        return Response(gen(camera),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"Could not initialize camera: {e}")
        return "Video feed unavailable", 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login.handle_login'))



# Socket event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# Socket event handlers for monitoring
@socketio.on('start_monitoring')
def handle_start_monitoring():
    global camera_thread, camera_active
    
    if camera_thread is None or not camera_active:
        camera_active = True
        camera_thread = threading.Thread(target=monitoring_task, args=(socketio,))
        camera_thread.daemon = True
        camera_thread.start()
        print("[INFO] Monitoring started")

@app.route('/start_camera')
def start_camera():
    global is_monitoring, monitoring_thread, camera
    if not is_monitoring:
        camera = Camera()
        is_monitoring = True
        monitoring_thread = threading.Thread(target=monitoring_task)
        monitoring_thread.daemon = True
        monitoring_thread.start()
    return 'Camera started', 200

@app.route('/stop_camera')
def stop_camera():
    global camera_active, camera_thread
    
    # Signal to stop monitoring
    camera_active = False
    
    # Wait for thread to terminate
    if camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=1.0)
        
    # Return success response
    return {"status": "success", "message": "Camera stopped"}, 200


@socketio.on('stop_monitoring')
def handle_stop_monitoring():
    global camera_active
    camera_active = False
    print("[INFO] Monitoring stopped")

    if camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=1.0)
        camera_thread = None


def monitoring_task(socketio):
    """Background task for monitoring"""
    global camera_active
    camera = Camera()

    from database.mongo_db import MongoDB
    mongo_db = MongoDB()
    from models.alert_system import AlertSystem
    alert_system = AlertSystem(mongo_db)
    
    last_update_time = time.time()
    
    try:
        while camera_active:
            # Process frame
            frame, auth_count, unauth_count = camera.process_frame()
            
            if frame is None:
                break
                
            # Update status every second
            current_time = time.time()
            if current_time - last_update_time >= 1:
                # Update stats only every second
                stats = alert_system.get_stats()
                stats['authorized_count'] = auth_count
                stats['unauthorized_count'] = unauth_count
                
                socketio.emit('status_update', stats)
                last_update_time = current_time
                
                # Send a detection event (simulate for testing)
                if auth_count > last_stats_update:
                    socketio.emit('detection_event', {
                        'authorized': True,
                        'name': 'Authorized Person',
                        'time': time.strftime('%H:%M:%S')
                    })
                    last_stats_update = auth_count
            
            # Sleep to reduce CPU usage
            time.sleep(0.03)
    except Exception as e:
        print(f"[ERROR] Monitoring task error: {e}")
    finally:
        print("[INFO] Monitoring task stopped")
        if camera:
            camera.release()

if __name__=="__main__":
    socketio.run(app, debug=True , host='127.0.0.1', port=8000) 