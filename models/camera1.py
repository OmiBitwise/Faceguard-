import cv2
import time
import numpy as np
import os
from models.face_detector import FaceRecognition
from models.alert_system import AlertSystem

class Camera:
    def __init__(self, camera_id=0):
        # Initialize camera capture
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Initialize MongoDB connection and AlertSystem
        from database.mongo_db import MongoDB
        self.mongo_db = MongoDB()
        
        # Load known faces from database
        self.known_face_encodings, self.known_face_names = self.mongo_db.get_face_encodings_and_names()
        
        # Initialize the face recognition system
        self.face_detector = FaceRecognition(self.known_face_encodings, self.known_face_names)
        
        # Initialize the alert system
        self.alert_system = AlertSystem(self.mongo_db)
        
        # Initialize background for motion detection
        self.background = None
        self.frame_counter = 0

    def load_known_faces(self):
        """Update face encodings from database"""
        self.known_face_encodings, self.known_face_names = self.mongo_db.get_face_encodings_and_names()
        self.face_detector.update_known_faces(self.known_face_encodings, self.known_face_names)

    def process_frame(self):
        """Process a single frame with face detection"""
        # Get a frame from the camera
        ret, frame = self.cap.read()
        if not ret:
            stats = self.alert_system.get_stats()
            return None, stats['authorized_count'], stats['unauthorized_count']

        # Increment frame counter
        self.frame_counter += 1

        # Initialize background for motion detection if not already done
        if self.background is None:
            self.background = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self.background = cv2.GaussianBlur(self.background, (21, 21), 0)

        # Motion detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        diff = cv2.absdiff(self.background, gray_blurred)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_detected = any(cv2.contourArea(c) > 1000 for c in contours)

        current_time = int(time.time())

        # Only do face detection if motion is detected to conserve CPU
        if motion_detected:
            # Use the face detector module to detect faces
            detected_faces = self.face_detector.detect_faces(frame)
            
            # Process each detected face
            for face in detected_faces:
                location = face['location']
                name = face['name']
                is_known = face['is_known']
                confidence = face.get('confidence', 0.0)
                
                # Extract coordinates
                top, right, bottom, left = location
                
                # Set color based on recognition status
                color = (0, 255, 0) if is_known else (0, 0, 255)  # Green for known, Red for unknown
                
                # Draw rectangle and name
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                
                # Handle face based on recognition status
                if is_known:
                    self.alert_system.stats['authorized_count'] += 1
                else:
                    # This is crucial - handle unknown face with alerts
                    self.alert_system.handle_unknown_face(frame, location)
                    self.alert_system.stats['unauthorized_count'] += 1
        
        # Update background every 30 frames for better motion detection
        if self.frame_counter % 30 == 0:
            self.background = gray_blurred

        # Update all ongoing recordings
        self.alert_system.update_recordings(frame, current_time)

        # Get updated statistics
        stats = self.alert_system.get_stats()
        return frame, stats['authorized_count'], stats['unauthorized_count']

    def get_frame(self):
        """Get raw frame from camera"""
        ret, frame = self.cap.read()
        return frame if ret else None

    def get_processed_frame(self):
        """Get processed frame with face detection"""
        frame, auth_count, unauth_count = self.process_frame()
        return frame

    def release(self):
        """Release camera and other resources"""
        if self.cap:
            self.cap.release()
            
        # Release all video writers in AlertSystem
        for writer in self.alert_system.video_writers.values():
            writer.release()
            
        cv2.destroyAllWindows()