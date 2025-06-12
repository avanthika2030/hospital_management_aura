import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_test_email():
    # Email configuration
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'arunthomas7072@gmail.com'  # Your email
    EMAIL_HOST_PASSWORD = input("Enter your Gmail app password: ")  # Get password securely
    
    # Email details
    to_email = 'arunthomas7072@gmail.com'
    subject = 'AURA Hospital: Test Email'
    message = '''
    This is a test email from the AURA Hospital Management System.
    
    If you received this email, it means the email functionality is working correctly.
    
    Please use this app password for the EMAIL_HOST_PASSWORD in the backend.py file.
    
    Thank you!
    '''
    
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        # Add message body
        msg.attach(MIMEText(message, 'plain'))

        # Print the email content to console for debugging
        print(f"\n--- EMAIL NOTIFICATION ---")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        print(f"--- END EMAIL NOTIFICATION ---\n")

        # Try to send the email using SMTP
        try:
            # Create SMTP session
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
            server.starttls()  # Enable security
            
            # Login to the server
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            
            # Send the email
            server.send_message(msg)
            
            # Close the connection
            server.quit()
            
            print(f"Email successfully sent to {to_email}")
            return True
        except Exception as smtp_error:
            print(f"SMTP Error: {str(smtp_error)}")
            print("Email not sent due to SMTP error.")
            return False
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")
        return False

if __name__ == "__main__":
    print("This script will send a test email to arunthomas7072@gmail.com")
    print("You will need to enter your Gmail app password.")
    print("If you don't have an app password, you can create one at: https://myaccount.google.com/apppasswords")
    print("Note: You need to have 2-factor authentication enabled on your Google account to use app passwords.")
    print("\n")
    
    send_test_email()
