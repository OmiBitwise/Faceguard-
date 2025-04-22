import os
from urllib.parse import quote_plus
from dotenv import load_dotenv 


load_dotenv()

class Config:

    UPLOAD_FOLDER= 'uploads'
    # MongoDB settings
    MONGO_USER = os.environ.get('MONGO_USER')
    MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD')
    MONGO_CLUSTER = os.environ.get('MONGO_CLUSTER')
    
    if MONGO_PASSWORD:
        ENCODED_PASSWORD = quote_plus(MONGO_PASSWORD)
        MONGO_URI = f"mongodb+srv://{MONGO_USER}:{ENCODED_PASSWORD}@{MONGO_CLUSTER}/?retryWrites=true&w=majority&appName=registration"
    else:
        
        PASSWORD = "omi@2004"
        ENCODED_PASSWORD = quote_plus(PASSWORD)
        MONGO_URI = f"mongodb+srv://{MONGO_USER}:{ENCODED_PASSWORD}@{MONGO_CLUSTER}/?retryWrites=true&w=majority&appName=registration"

    EMAIL_CONFIG = {
    'email_from': 'facegaurdwebapp@gmail.com',  # Replace with your app's email
    'email_password': 'clsv tcln nhvp ghco',    # Replace with your app password
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587}

    SECRET_KEY = os.environ.get("SECRET_KEY")

        