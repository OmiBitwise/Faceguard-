from pymongo import MongoClient
import certifi
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import datetime
import pickle
import numpy as np
from config import Config


class MongoDB:
    def __init__(self):
        try:
            # Connect to MongoDB
            MONGO_URI = Config.MONGO_URI
            self.client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

            # Testing the connection
            self.client.admin.command('ping')
            print("MongoDB connection successful")

            self.db = self.client['faceguard_db']
            self.users_collection = self.db['users']
            self.faces_collection = self.db['authorized_faces']
            self.alerts_collection = self.db['alerts']
            

            # Create indexes for performance
            self.users_collection.create_index('email', unique=True)
            #self.faces_collection.create_index('user_id') 
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            raise

    
    # User management
    def create_user(self,username,email,password):
        """Insert a new user into the database"""
        try:
            user = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'created_at': datetime.datetime.now(),
                'settings': {
                    'email_alerts': True,
                    'notification_email': email
                }
            }
            result = self.users_collection.insert_one(user)
            
            self.current_user_id = str(result.inserted_id) 

            # Initialize user stats when creating a user
            self.reset_user_stats(str(result.inserted_id))
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
    
    def authenticate_user(self, email, password):
        """Authenticate a user based on email and password"""
        user = self.users_collection.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            self.current_user_id = str(user['_id'])
            return user
        return None
    
    def find_user_by_email(self, email):
        """Find a user by email"""
        try:
            return self.users_collection.find_one({'email':email})
        except:
            return None
    
    def find_user_by_id(self, user_id):
        """Find a user by ID"""
        try:
            return self.users_collection.find_one({'_id': ObjectId(user_id)})
        except:
            return None
    
    def update_user_settings(self, user_id, settings):
        """Update user settings"""
        return self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'settings': settings}}
        )
    
    def save_user_email(self, user_id, email):
        self.db.users.update_one(
            {"_id": user_id},  # Query to find the right user
            {"$set": {"email_to": email}}  # Update operation - only changes the email field
        )
    
    # Face management
    def register_face(self, name, face_encoding, user_id, image_path):
        try:
            # Handle numpy array if that's what we're getting
            if isinstance(face_encoding, np.ndarray):
                face_encoding_to_store = pickle.dumps(face_encoding)
            else:
                # If already a list, pickle it directly
                face_encoding_to_store = pickle.dumps(face_encoding)
                
            face_data = {
                "user_id": user_id,
                "name": name,
                "face_encoding": face_encoding_to_store,
                "image_path": image_path,
                'registered_at': datetime.datetime.now()
            }
            
            # Debug print to verify data
            print(f"Registering face: {name} for user {user_id}, image path: {image_path}")
            
            return self.faces_collection.insert_one(face_data).inserted_id
        except Exception as e:
            print(f"Error registering face: {e}")
            return None
    
    def get_face_encodings_and_names(self,user_id=None):
        """Get all face encodings and names"""
        try:
            # Create query filter if user_id is provided
            query = {}
            if user_id:
                query["user_id"] = user_id
                
            faces = list(self.faces_collection.find(query))
            
            encodings = []
            names = []
            
            for face in faces:
                try:
                    # Unpickle the face encoding
                    encoding = pickle.loads(face["face_encoding"])
                    encodings.append(encoding)
                    names.append(face["name"])
                except Exception as e:
                    print(f"Error unpickling face encoding: {e}")
                    continue
                    
            return encodings, names
        except Exception as e:
            print(f"Error getting face encodings and names: {e}")
            return [], []
    
    
    def get_authorized_faces(self,user_id=None):
        """Get all authorized faces"""
        query = {}
        if user_id:
            query["user_id"] = user_id
            
        faces = list(self.faces_collection.find(query, {
            "_id": 1, 
            "name": 1, 
            "image_path": 1, 
            "registered_at": 1,
            "user_id": 1
        }))
        return faces
    
    # Alert management
    def record_alert(self, user_id=None,face_id=None, confidence=None, image_path=None , video_path=None):
        """Record a security alert"""
        alert = {
            'user_id': user_id,
            'timestamp': datetime.datetime.now(),
            'face_id': face_id,
            'confidence': confidence,
            'image_path': image_path,
            'video_path' : video_path ,
            'email_sent' : False,
            'processed': False
        }
        return self.alerts_collection.insert_one(alert)

    
    def update_alert_email_sent(self, video_path):
        """Update alert email sent status"""
        return self.alerts_collection.update_one(
            {"video_path": video_path},
            {"$set": {"email_sent": True}}
        )
    
    def get_recent_alerts(self,user_id=None, limit=10):
        """Get recent alerts"""
        query = {}
        if user_id:
            query["user_id"] = user_id
            
        return list(self.alerts_collection.find(query).sort("timestamp", -1).limit(limit))
    
    # Settings management
    def update_user_credentials(self, user_id, email=None, password=None):
        update_data = {}
        if email:
            update_data['email'] = email
            # Also update the notification email in settings
            update_data['settings.notification_email'] = email
            
        if password:
            update_data['password'] = generate_password_hash(password)
            
        if not update_data:
            return False  # Nothing to update
            
        result = self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update_data}
        )
        
        return result.modified_count > 0
    
    def get_settings(self,user_id=None):
        """Get settings"""
        if user_id:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            return user.get('settings', {}) if user else {}
        else:
        # Fallback to global settings if needed
            return self.db.settings.find_one() or {}
    
    # Stats
    def get_user_stats(self, user_id):
        try:
            stats_collection = self.db.get_collection('user_stats')
            stats = stats_collection.find_one({"user_id": user_id})
            
            if not stats:
                # Return default stats if none exist yet
                return {
                    "user_id": user_id,
                    "authorized_count": 0,
                    "unauthorized_count": 0,
                    "last_updated": None,
                    "last_reset": None
                }
                
            return stats
        except Exception as e:
            print(f"Error getting stats for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "authorized_count": 0,
                "unauthorized_count": 0,
                "error": str(e)
            }
    
    def update_user_stats(self, user_id, authorized_increment=0, unauthorized_increment=0):
        try:
            stats_collection = self.db.get_collection('user_stats')
            
            # Build the update based on provided increments
            update = {"$inc": {}}
            
            if authorized_increment != 0:
                update["$inc"]["authorized_count"] = authorized_increment
                
            if unauthorized_increment != 0:
                update["$inc"]["unauthorized_count"] = unauthorized_increment
                
            if not update["$inc"]:
                return False  # Nothing to update
                
            # Add last updated timestamp
            update["$set"] = {"last_updated": datetime.datetime.now()}
            
            # Update the stats document
            result = stats_collection.update_one(
                {"user_id": user_id},
                update,
                upsert=True
            )
            
            return result.acknowledged
        except Exception as e:
            print(f"Error updating stats for user {user_id}: {e}")
            return False

    def reset_user_stats(self, user_id):
        try:
            # Create a stats document for this user if it doesn't exist
            stats_collection = self.db.get_collection('user_stats')
            
            # Update or create the stats document with reset counters
            stats_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "authorized_count": 0,
                    "unauthorized_count": 0,
                    "last_reset": datetime.datetime.now()
                }},
                upsert=True
            )
            
            print(f"Stats reset for user {user_id}")
            return True
        except Exception as e:
            print(f"Error resetting stats for user {user_id}: {e}")
            return False