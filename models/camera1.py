import cv2
import time
import face_recognition
import pickle
import numpy as np
import os
from models.alert_system import AlertSystem

class Camera:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()
        self.background = None
        
        # Initialize MongoDB connection and AlertSystem
        from database.mongo_db import MongoDB
        self.mongo_db = MongoDB()
        
        # Initialize the AlertSystem
        self.alert_system = AlertSystem(self.mongo_db)
        
        self.frame_counter = 0
        self.cap.set(cv2.CAP_PROP_FPS, 30)

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
            stats = self.alert_system.get_stats()
            return None, stats['authorized_count'], stats['unauthorized_count']

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

        current_time = int(time.time())

        if motion_detected:
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                # Scale back up face coordinates
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4
                
                face_location = (top, right, bottom, left)

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
                        self.alert_system.stats['authorized_count'] += 1
                    else:
                        # Handle unknown face using AlertSystem
                        self.alert_system.handle_unknown_face(frame, face_location)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
        
        # Update background every 30 frames for better motion detection
        if self.frame_counter % 30 == 0:
            self.background = gray_blurred

        # Update all ongoing recordings
        self.alert_system.update_recordings(frame, current_time)

        stats = self.alert_system.get_stats()
        return frame, stats['authorized_count'], stats['unauthorized_count']

    def release(self):
        if self.cap:
            self.cap.release()
            
        # Release all video writers in AlertSystem
        for writer in self.alert_system.video_writers.values():
            writer.release()
            
        cv2.destroyAllWindows()
    
    def get_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None