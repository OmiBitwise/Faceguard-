from pymongo import MongoClient
import certifi
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import datetime
import pickle
from config import Config


class MongoDB:
    def __init__(self):

        try:
            # Connect to MongoDB
            MONGO_URI = Config.MONGO_URI
            #self.client = MongoClient(MONGO_URI)
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
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
    
    def authenticate_user(self, email, password):
        """Authenticate a user based on email and password"""
        user = self.users_collection.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
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
        """
        Update a specific user's email address in the database 
        Args:
            user_id (str): The ID of the user
            email (str): The email address where alerts should be sent
        """
        """if user_id is None:
         user_id = session.get('user_id')"""

        self.db.users.update_one(
            {"_id": user_id},  # Query to find the right user
            {"$set": {"email_to": email}}  # Update operation - only changes the email field
        )
    
    # Face management
    def register_face(self, name, face_encoding, user_id, image_path):
        """Insert a new face into the database"""
        face_data = {
        "user_id": user_id,
        "name": name,
        "face_encoding": pickle.dumps(face_encoding),
        "image_path": image_path,
        'registered_at': datetime.datetime.now()
    }
        return self.faces_collection.insert_one(face_data).inserted_id
    
    def get_face_encodings_and_names(self):
        """Get all face encodings and names"""
        faces = list(self.faces_collection.find())
        
        encodings = []
        names = []
        
        for face in faces:
            encodings.append(pickle.loads(face["face_encoding"]))
            names.append(face["name"])
            
        return encodings, names
    
    def get_authorized_faces(self):
        """Get all authorized faces"""
        faces = list(self.faces_collection.find({}, {
            "_id": 1, 
            "name": 1, 
            "image_path": 1, 
            "registered_at": 1
        }))
        return faces
    
    # Alert management
    def record_alert(self, face_id=None, confidence=None, image_path=None , video_path=None):
        """Record a security alert"""
        alert = {
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
    
    def get_recent_alerts(self, limit=10):
        """Get recent alerts"""
        return list(self.alerts_collection.find().sort("timestamp", -1).limit(limit))
    
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
            return self.db.settings.find_one()
    
    # Stats
    def get_stats(self):
        """Get system stats"""
        authorized_count = self.db.stats.find_one({"type": "authorized"})
        #unauthorized_count = self.db.stats.find_one({"type": "unauthorized"})
        alert_count = self.db.stats.find_one({"type": "alert"})
        
        return {
            "total_authorized": self.faces_collection.count_documents({}),
            "total_alerts": self.alerts_collection.count_documents({}),
            "recent_alerts_count": self.alerts_collection.count_documents({
                "timestamp": {'$gt': datetime.datetime.now() - datetime.timedelta(days=7)}})
            
        }
    
    def update_stats(self, authorized=0, unauthorized=0, alert=0):
        """Update system stats"""
        if authorized > 0:
            self.db.stats.update_one(
                {"type": "authorized"},
                {"$inc": {"count": authorized}},
                upsert=True
            )
            
        if unauthorized > 0:
            self.db.stats.update_one(
                {"type": "unauthorized"},
                {"$inc": {"count": unauthorized}},
                upsert=True
            )
            
        if alert > 0:
            self.db.stats.update_one(
                {"type": "alert"},
                {"$inc": {"count": alert}},
                upsert=True
            )