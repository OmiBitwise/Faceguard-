import face_recognition
import cv2
import numpy as np

class FaceRecognition:
    def __init__(self, known_face_encodings=None, known_face_names=None):
        self.known_face_encodings = known_face_encodings or []
        self.known_face_names = known_face_names or []
        
    def detect_faces(self, frame):
        """
        Detect and recognize faces in a frame
        
        Returns:
            list: List of tuples (location, name, is_known)
        """
        # Resize for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Find faces
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        detected_faces = []
        for i, face_encoding in enumerate(face_encodings):
            location = face_locations[i]
            name = "Unknown"
            is_known = False
            
            if self.known_face_encodings:
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, face_encoding, tolerance=0.55
                )
                
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings, face_encoding
                )
                
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    confidence = 1 - face_distances[best_match_index]
                    
                    if matches[best_match_index] and confidence > 0.45:
                        name = self.known_face_names[best_match_index]
                        is_known = True
            
            # Scale back to original size
            top, right, bottom, left = location
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            
            detected_faces.append({
                'location': (top, right, bottom, left),
                'name': name,
                'is_known': is_known
            })
            
        return detected_faces
    
    def update_known_faces(self, known_face_encodings, known_face_names):
        """Update the known faces"""
        self.known_face_encodings = known_face_encodings
        self.known_face_names = known_face_names