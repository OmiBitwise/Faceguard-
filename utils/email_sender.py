
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from datetime import datetime

def send_email_alert(video_path, sender_email, sender_password, recipient_email):
    """Send email alert with attached video"""
    if not all([sender_email, sender_password, recipient_email]):
        print("[ERROR] Email credentials missing")
        return False
        
    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"🚨 SECURITY ALERT: Unauthorized Face Detected - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        body = f"""
        <html>
        <body>
            <h2>⚠️ Security Alert Notification</h2>
            <p>An <strong>unauthorized person</strong> was detected by your FaceGuard security system.</p>
            <p>A 1-minute video recording is attached to this email for your review.</p>
            <p>Time of detection: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</strong></p>
            <hr>
            <p><i>This is an automated message from your FaceGuard Facial Recognition Security System.</i></p>
            <p><small>To manage your alert settings, please log in to your FaceGuard dashboard.</small></p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Attach the video
        if os.path.exists(video_path):
            with open(video_path, "rb") as f:
                file_data = f.read()

            attach_part = MIMEApplication(file_data)   
            file_name = os.path.basename(video_path)
            attach_part.add_header('Content-Disposition', 'attachment', filename=file_name)
            msg.attach(attach_part)

            # Send the email
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.quit()
            
            print("[INFO] Alert email sent successfully!")
            return True
            
        else:
            print(f"[ERROR] Video file not found: {video_path}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False