import os
import time
import cv2
from datetime import datetime
from utils.email_sender import send_email_alert

class AlertSystem:
    def __init__(self, mongo_db):
        self.mongo_db = mongo_db
        self.video_writers = {}
        self.recording_start_times = {}
        self.stats = {
            'authorized_count': 0,
            'unauthorized_count': 0,
            'alert_count': 0
        }
        
        # Create videos directory if not exists
        videos_dir = os.path.join('static', 'videos')
        if not os.path.exists(videos_dir):
            os.makedirs(videos_dir)
        
    def handle_unknown_face(self, frame, face_location):
        """Handle detection of an unknown face"""
        current_time = int(time.time())
        filename = f"static/videos/unknown_{current_time}.mp4"
        
        # Start recording if not already
        if filename not in self.video_writers:
            directory = os.path.dirname(filename)
            if not os.path.exists(directory):
                os.makedirs(directory)
                
            width = int(frame.shape[1])
            height = int(frame.shape[0])
            
            self.video_writers[filename] = cv2.VideoWriter(
                filename,
                cv2.VideoWriter_fourcc(*'mp4v'),
                10.0,
                (width, height)
            )
            
            self.recording_start_times[filename] = current_time
            
            # Insert alert into MongoDB
            self.mongo_db.insert_alert(filename)
            
        # Update stats
        self.stats['unauthorized_count'] += 1
        
        return filename
        
    def update_recordings(self, frame, current_time):
        """Update ongoing recordings and stop if needed"""
        completed_recordings = []
        for filename, writer in self.video_writers.items():
            # Write frame to video
            writer.write(frame)
            
            # Check if recording should be stopped (after 10 seconds)
            start_time = self.recording_start_times.get(filename)
            if start_time and current_time - start_time > 60:
                writer.release()
                completed_recordings.append(filename)
                
                # Send email alert
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    # Get email settings
                    settings = self.mongo_db.get_settings()
                    
                    if settings:
                        email_from = settings.get('email_from')
                        email_password = settings.get('email_password')
                        email_to = settings.get('email_to')
                        
                        success = send_email_alert(filename, email_from, email_password, email_to)
                        
                        if success:
                            self.stats['alert_count'] += 1
                            self.mongo_db.update_alert_email_sent(filename)
        
        # Remove completed recordings
        for filename in completed_recordings:
            del self.video_writers[filename]
            del self.recording_start_times[filename]
    
    def get_stats(self):
        """Get current statistics"""
        return self.stats.copy()