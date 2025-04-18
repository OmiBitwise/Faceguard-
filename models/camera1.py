import cv2
import time
import face_recognition
import pickle
import numpy as np
import os
from utils.email_sender import send_email_alert

class Camera:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()
        self.background = None
        self.video_writer = None
        self.recording = False
        self.last_unknown_detection_time = 0
        self.unknown_detection_cooldown = 60
        self.authorized_count = 0

        self.unauthorized_count = 0

        """# NEW: Set lower resolution for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)"""
        self.cap.set(cv2.CAP_PROP_FPS, 30)

     # NEW: Add frame counter for processing only every N frames
        self.frame_counter = 0
        #self.process_every_n_frames = 3  # Process every 3rd frame


    def load_known_faces(self):
        uploads_dir = "static/uploads"
        for filename in os.listdir(uploads_dir):
            filepath = os.path.join(uploads_dir, filename)
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image = face_recognition.load_image_file(filepath)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    self.known_face_encodings.append(encodings[0])
                    self.known_face_names.append(os.path.splitext(filename)[0])

    def process_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, self.authorized_count, self.unauthorized_count

        # Increment frame counter
        self.frame_counter += 1

        # Init background for motion
        if self.background is None:
            self.background = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self.background = cv2.GaussianBlur(self.background, (21, 21), 0)

        # Resize for face recognition
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Motion detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        diff = cv2.absdiff(self.background, gray_blurred)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_detected = any(cv2.contourArea(c) > 1000 for c in contours)

        if motion_detected:
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.55)
                name = "Unknown"
                color = (255, 0, 0)  # Default Blue

                if self.known_face_encodings:
                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    confidence = 1 - face_distances[best_match_index]

                    if True in matches and confidence > 0.45:
                        name = self.known_face_names[best_match_index]
                        color = (0, 255, 0)  # Green
                        self.authorized_count += 1
                    else:
                        self.unauthorized_count += 1
                        self.handle_unauthorized(frame)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
        
        # Update background every 30 frames for better motion detection
        if self.frame_counter % 30 == 0:
            self.background = gray_blurred

        if self.recording and self.video_writer:
            self.video_writer.write(frame)
            if time.time() - self.last_unknown_detection_time > 10:
                self.stop_recording()

        return frame, self.authorized_count, self.unauthorized_count

    def handle_unauthorized(self):
        current_time = time.time()
        if not self.recording or (current_time - self.last_unknown_detection_time > self.unknown_detection_cooldown):
            self.last_unknown_detection_time = current_time
            filename = f"static/videos/unknown_{int(current_time)}.mp4"

            if self.video_writer:
                self.video_writer.release()

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if actual_fps <= 0 or actual_fps > 30:
                actual_fps = 10.0

            self.video_writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'mp4v'), actual_fps, (width, height))
            self.recording = True
            print(f"[INFO] Recording started: {filename}")
            
            # Get user email from database to send alert later
            from database.mongo_db import MongoDB
            mongo_db = MongoDB()
            settings = mongo_db.get_settings()
            self.alert_email = settings.get('email_to') if settings else None
            
            return filename

    def stop_recording(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
            self.recording = False
            filename = f"static/videos/unknown_{int(self.last_unknown_detection_time)}.mp4"
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                from database.mongo_db import MongoDB
                mongo_db = MongoDB()
                settings = mongo_db.get_settings()
        
                if hasattr(self, 'frame_count'):
                    self.frame_count += 1
                else:
                    self.frame_count = 0
                    
                if self.frame_count % 3 != 0:  # Only process every 3rd frame
                    return self.authorized_count, self.unauthorized_count

                # Resize BEFORE face detection to improve performance
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                if settings:
                    email_from = settings.get('email_from')
                    email_password = settings.get('email_password')
                    email_to = settings.get('email_to')
                    
                    from utils.email_sender import send_email_alert
                    success = send_email_alert(filename, email_from, email_password, email_to)
                    
                    if success:
                        print(f"[EMAIL SENT] {filename}")
                        mongo_db.update_alert_email_sent(filename)

    def release(self):
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()
        cv2.destroyAllWindows()
    
    # NEW: Add a method to get a frame without processing
    def get_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None
