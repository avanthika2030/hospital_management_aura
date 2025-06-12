from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_sqlalchemy import SQLAlchemy
import re
from functools import wraps
from datetime import datetime, timedelta
import json
import os
from simplegmail import Gmail
app = Flask(__name__)
#app.secret_key = 'client_secret.json'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
gmail=Gmail()


# Utility function to send email notifications
def send_email_notification(to_email, subject, message):
    """
    Send an email notification to a user

    Args:
        to_email: The recipient's email address
        subject: The email subject
        message: The email message body

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        

        # Print the email content to console for debugging
        print(f"\n--- EMAIL NOTIFICATION ---")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        print(f"--- END EMAIL NOTIFICATION ---\n")

        # For OTP emails, print the OTP code clearly
        if "Your OTP Code" in subject:
            try:
                otp_code = message.split("Your OTP code is: ")[1].strip()
                print(f"\n=================================================================")
                print(f"OTP CODE: {otp_code}")
                print(f"=================================================================\n")
            except:
                pass

        # Try to send the email using SMTP
        try:
            params = {
            "sender": "me",
            "to": to_email,
            "subject": subject,
            "msg_plain": message,
        }
            gmail.send_message(**params)
            print(f"Email sent to {to_email}")
            return True
        except Exception as smtp_error:
            print(f"SMTP Error: {str(smtp_error)}")

            # For testing purposes, we'll still return True so the app can function
            # This allows testing without a valid app password
            print(f"For testing: Email would be sent to {to_email}")
            return True
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")
        return False

# Helper function to check if user is logged in
def is_logged_in():
    return 'user_id' in session

# Decorator function to require login for certain routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Add a specific decorator for doctor routes
def doctor_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            return redirect('/doctor/login')
        return f(*args, **kwargs)
    return decorated_function

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    email = db.Column(db.String(80), unique=True)
    username = db.Column(db.String(80), nullable=True)  # Kept for backward compatibility
    password = db.Column(db.String(80))
    dob = db.Column(db.Date, nullable=True)
    address = db.Column(db.Text, nullable=True)
    emergency_contact = db.Column(db.String(15), nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    medical_history = db.Column(db.Text, nullable=True)
    # Relationship with appointments is defined in the Appointment model

# Add new models for doctors and appointments
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    specialty = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    qualification = db.Column(db.String(200), nullable=True)
    experience = db.Column(db.Integer, default=0)  # Years of experience
    phone = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(80), nullable=True)
    fee = db.Column(db.Integer, default=0)  # Consultation fee
    available_days = db.Column(db.String(100))  # Comma-separated days
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date)
    appointment_time = db.Column(db.String(10), nullable=True)  # Can be null initially
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    notes = db.Column(db.Text)

    # Add relationship to User model
    user = db.relationship('User', backref=db.backref('appointments', lazy=True))

# Add this model to your database models if not already present
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

# Add this model for reception notifications
class ReceptionNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

# Chat message model for communication between users, reception, and doctors
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)
    sender_type = db.Column(db.String(20))  # 'user', 'reception', 'doctor'
    recipient_id = db.Column(db.Integer, nullable=True)
    recipient_type = db.Column(db.String(20))  # 'user', 'reception', 'doctor'
    timestamp = db.Column(db.DateTime, default=datetime.now)
    attachment_url = db.Column(db.String(255), nullable=True)
    read = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)  # Flag for soft deletion
    deleted_by = db.Column(db.String(20), nullable=True)  # Who deleted the message
    deleted_at = db.Column(db.DateTime, nullable=True)  # When the message was deleted

    def __repr__(self):
        return f'<ChatMessage {self.id}: {self.sender_type} to {self.recipient_type}>'

# Doctor review model for patient feedback
class DoctorReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review_text = db.Column(db.Text, nullable=True)  # Optional review text
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Add relationships
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('reviews', lazy=True))
    appointment = db.relationship('Appointment', backref=db.backref('review', uselist=False, lazy=True))

# Gallery model for photo sharing
class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)  # Title is now optional
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(255), nullable=False)
    thumbnail_path = db.Column(db.String(255), nullable=True)  # For optimized thumbnails
    uploaded_by_id = db.Column(db.Integer, nullable=False)
    uploaded_by_type = db.Column(db.String(20), nullable=False)  # 'user', 'reception'
    upload_date = db.Column(db.DateTime, default=datetime.now)
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, nullable=True)
    approval_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Gallery {self.id}: {self.title}>'

@app.route('/')
def index():
    # Check if user is logged in by looking for user-specific session data
    if 'user_id' in session:
        # User is logged in, redirect to user home
        return redirect('/userhome')
    # User is not logged in, show the index page
    return render_template('index.html')

@app.route('/home')
def home():
    return redirect('/')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Initialize error message
    error_message = None

    if request.method == 'POST':
        print("Form submitted!")
        print("Form data received:", request.form)

        action = request.form.get('action')
        print(f"Action: {action}")

        # Save form fields to session
        if action == 'verify':
            email = request.form.get('email', '')

            # Check if user with this email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                try:
                    # Delete the existing user with this email
                    db.session.delete(existing_user)
                    db.session.commit()
                    print(f"Deleted existing user with email: {email}")
                except Exception as delete_error:
                    db.session.rollback()
                    print(f"Error deleting existing user: {str(delete_error)}")

                # Save other form fields but clear email
                session['name'] = request.form.get('name')
                session['age'] = request.form.get('age', '')
                session['gender'] = request.form.get('gender', '')
                session['phone'] = request.form.get('phone', '')
                session['email'] = ''  # Clear the email
                if 'verified_email' in session:
                    del session['verified_email']  # Clear any verification
                return render_template('signup.html', error_message="A user with this email already exists. Please use a different email.")

            # If email doesn't exist, proceed with verification
            session['name'] = request.form.get('name')
            session['age'] = request.form.get('age', '')
            session['gender'] = request.form.get('gender', '')
            session['phone'] = request.form.get('phone', '')
            session['email'] = email
            # Clear any previous verification if email changed
            if 'verified_email' in session and session['verified_email'] != session['email']:
                del session['verified_email']
            print(f"Name: {session['name']}, Age: {session['age']}, Gender: {session['gender']}, Phone: {session['phone']}, Email: {session['email']}")
            print("Session after saving form data:", dict(session))
            return redirect(f"/otp?contact={session['email']}&method=email")

        elif action == 'complete':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm-password')

            if password != confirm_password:
                return render_template('signup.html', error_message="Passwords do not match.")

            # Simplified password validation
            has_letter = any(c.isalpha() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(not c.isalnum() for c in password)

            if len(password) < 6 or not has_letter or not has_digit or not has_special:
                return render_template('signup.html', error_message="Password must be at least 6 characters and include a letter, number, and special character.")

            if session.get('verified_email') != session.get('email'):
                return render_template('signup.html', error_message="Please verify your email first.")

            # Check if user with this email already exists
            existing_user = User.query.filter_by(email=session['email']).first()
            if existing_user:
                try:
                    # Delete the existing user with this email
                    db.session.delete(existing_user)
                    db.session.commit()
                    print(f"Deleted existing user with email: {session['email']}")
                except Exception as delete_error:
                    db.session.rollback()
                    print(f"Error deleting existing user: {str(delete_error)}")

                # Clear email from session
                session['email'] = ''
                if 'verified_email' in session:
                    del session['verified_email']
                return render_template('signup.html', error_message="A user with this email already exists. Please use a different email.")

            try:
                # Create a new user in the database
                new_user = User(
                    name=session['name'],
                    age=session['age'],
                    gender=session['gender'],
                    phone=session['phone'],
                    email=session['email'],
                    username=session['phone'],  # Set username to phone number by default
                    password=password
                )
                db.session.add(new_user)
                db.session.commit()

                session.clear()
                print("Session cleared after registration")
                return redirect('/login')
            except Exception as e:
                db.session.rollback()
                print(f"Database error: {str(e)}")

                # Check if it's an integrity error (likely duplicate email)
                if "UNIQUE constraint failed" in str(e) or "IntegrityError" in str(e):
                    # Try to delete any existing user with this email
                    try:
                        existing_user = User.query.filter_by(email=session['email']).first()
                        if existing_user:
                            db.session.delete(existing_user)
                            db.session.commit()
                            print(f"Deleted existing user with email: {session['email']}")
                    except Exception as delete_error:
                        db.session.rollback()
                        print(f"Error deleting existing user: {str(delete_error)}")

                    # Clear email from session
                    session['email'] = ''
                    if 'verified_email' in session:
                        del session['verified_email']

                    return render_template('signup.html', error_message="This email is already registered. Please use a different email.")

                return render_template('signup.html', error_message=f"Registration failed: {str(e)}")

    # Set button visibility based on verification status
    if 'email' in session and 'verified_email' in session and session['email'] == session['verified_email']:
        show_verify_button = False
        show_verified_button = True
    else:
        show_verify_button = True
        show_verified_button = False

    return render_template('signup.html',
                          error_message=error_message,
                          show_verify_button=show_verify_button,
                          show_verified_button=show_verified_button)


@app.route('/otp')
def otp():
    contact = request.args.get('contact')
    method = request.args.get('method')

    if not contact:
        return "Invalid OTP request: Missing contact information", 400

    # Only generate and send a new OTP if the method parameter is present
    # This prevents duplicate OTP sending when redirected from signup
    if method == 'email':
        # Generate a new OTP code
        otp_code = str(random.randint(100000, 999999))
        session['email_otp'] = otp_code
        session['email_contact'] = contact

        try:
            # Send OTP via email
            subject = "Your OTP Code"
            message = f"Your OTP code is: {otp_code}"
            send_email_notification(contact, subject, message)
            print(f"OTP sent to {contact}: {otp_code}")  # Print OTP for debugging
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return f"Failed to send email: {str(e)}"

    return render_template('otp.html', contact=contact)

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form.get('otp')
    contact = request.form.get('contact')

    # Debug prints to see what's being received and compared
    print(f"Entered OTP: {entered_otp}")
    print(f"Stored OTP: {session.get('email_otp')}")
    print(f"Contact: {contact}")
    print(f"Stored Contact: {session.get('email_contact')}")
    print("Full session before verification:", dict(session))

    # Check if OTP matches - use string comparison to ensure types match
    if str(entered_otp) == str(session.get('email_otp')) and contact == session.get('email_contact'):
        # Mark this email as verified
        session['verified_email'] = contact
        print(f"OTP verified successfully for {contact}")
        print("Session after verification:", dict(session))

        # Make sure the email in the form matches the verified email
        if 'email' in session and session['email'] != contact:
            session['email'] = contact

        return redirect(url_for('signup'))

    # If OTP doesn't match, show error
    print(f"Invalid OTP: {entered_otp} != {session.get('email_otp')}")
    return render_template('otp.html', contact=contact, error="Invalid OTP. Please try again.")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone_number = request.form['phone']
        password = request.form['password']

        print(f"Login attempt - Phone: {phone_number}, Password: {password}")

        # Try to find user by phone number (keeping username for backward compatibility)
        user = User.query.filter(
            ((User.phone == phone_number) | (User.username == phone_number)) &
            (User.password == password)
        ).first()

        if user:
            # Store user ID in session to mark them as logged in
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email
            print(f"Login successful for user: {user.name} (ID: {user.id})")
            return redirect('/userhome')

        # If login failed, try to find if the user exists but password is wrong
        user_exists = User.query.filter(
            (User.phone == phone_number)
        ).first()

        if user_exists:
            print(f"User exists but password is wrong. User: {user_exists.name}")
            return render_template('login.html', error_message="Invalid password. Please try again.")
        else:
            print(f"No user found with phone number: {phone_number}")
            return render_template('login.html', error_message="No account found with that phone number")

    return render_template('login.html')

@app.route('/userhome')
@login_required
def userhome():
    # Get user name from session to personalize the page
    user_name = session.get('user_name', 'Patient')

    # Check for unread notifications
    user_id = session['user_id']
    unread_count = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('userhome.html', user_name=user_name, unread_notifications=unread_count)

# Add a route to clear the database (for development only)
@app.route('/clear_db')
def clear_db():
    try:
        # Drop all tables
        db.drop_all()
        # Recreate all tables
        db.create_all()
        # Clear session
        session.clear()
        return "Database cleared successfully. <a href='/signup'>Go to signup</a>"
    except Exception as e:
        return f"Error clearing database: {str(e)}"

# Add a route to clear the session
@app.route('/clear_session')
def clear_session():
    session.clear()
    return "Session cleared successfully. <a href='/signup'>Go to signup</a>"

@app.route('/clear_user/<email>')
def clear_user(email):
    try:
        # Find and delete the user with this email
        user = User.query.filter_by(email=email).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            return f"User with email {email} deleted successfully. <a href='/signup'>Go to signup</a>"
        else:
            return f"No user found with email {email}. <a href='/signup'>Go to signup</a>"
    except Exception as e:
        db.session.rollback()
        return f"Error deleting user: {str(e)}. <a href='/signup'>Go to signup</a>"

@app.route('/debug/users')
def debug_users():
    """Debug route to view all users in the database"""
    try:
        users = User.query.all()
        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'name': user.name,
                'username': user.username,
                'phone': user.phone,
                'email': user.email,
                'password': user.password
            })

        return render_template('debug_users.html', users=user_list)
    except Exception as e:
        return f"Error retrieving users: {str(e)}"

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    # Redirect to login page
    return redirect('/login')

# Username functionality has been removed

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['POST'])
def reset_password():
    identifier = request.form.get('identifier')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validate inputs
    if not identifier or not new_password or not confirm_password:
        return render_template('forgot_password.html', error_message="All fields are required")

    # Check if passwords match
    if new_password != confirm_password:
        return render_template('forgot_password.html', error_message="Passwords do not match")

    # Validate password complexity
    has_letter = any(c.isalpha() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    has_special = any(not c.isalnum() for c in new_password)

    if len(new_password) < 6 or not has_letter or not has_digit or not has_special:
        return render_template('forgot_password.html', error_message="Password must be at least 6 characters and include a letter, number, and special character.")

    # Find user by phone number or username
    user = User.query.filter(
        (User.phone == identifier) | (User.username == identifier)
    ).first()

    if not user:
        return render_template('forgot_password.html', error_message="No account found with that phone number or username")

    try:
        # Update the user's password
        user.password = new_password
        db.session.commit()
        return render_template('reset_success.html')
    except Exception as e:
        db.session.rollback()
        return render_template('forgot_password.html', error_message=f"Error resetting password: {str(e)}")

@app.route('/appointment')
@login_required
def appointment():
    # Get all doctors from the database
    doctors = Doctor.query.all()

    # Calculate ratings for each doctor
    for doctor in doctors:
        reviews = DoctorReview.query.filter_by(doctor_id=doctor.id).all()
        doctor.review_count = len(reviews)
        doctor.avg_rating = round(sum(review.rating for review in reviews) / len(reviews), 1) if reviews else 5.0

    # Get unread notification count
    user_id = session['user_id']
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('userappointment.html', doctors=doctors, unread_notifications=unread_notifications)

@app.route('/status')
@login_required
def appointment_status():
    user_id = session['user_id']
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.appointment_date.desc()).all()

    # Format appointments for the template
    formatted_appointments = []
    for appointment in appointments:
        doctor = Doctor.query.get(appointment.doctor_id)
        if doctor:
            doctor_name = doctor.name
            doctor_specialty = doctor.specialty
        else:
            # Handle case where doctor has been deleted
            doctor_name = "Former Doctor"
            doctor_specialty = "No longer available"

        # Check if this appointment has a review
        has_review = DoctorReview.query.filter_by(appointment_id=appointment.id).first() is not None

        formatted_appointments.append({
            'id': appointment.id,
            'doctor_name': doctor_name,
            'doctor_specialty': doctor_specialty,
            'date': appointment.appointment_date.strftime('%B %d, %Y'),
            'time': appointment.appointment_time,
            'status': appointment.status,
            'notes': appointment.notes,
            'has_review': has_review
        })

    # Get unread notification count
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('userstatus.html', appointments=formatted_appointments, unread_notifications=unread_notifications)

@app.route('/history')
@login_required
def history():
    user_id = session['user_id']

    # Get all completed appointments for this user
    completed_appointments = Appointment.query.filter_by(
        user_id=user_id,
        status='completed'
    ).order_by(Appointment.appointment_date.desc()).all()

    # Prepare data for the template
    history_data = []
    for appointment in completed_appointments:
        doctor = Doctor.query.get(appointment.doctor_id)
        if doctor:
            history_data.append({
                'id': appointment.id,
                'doctor_name': doctor.name,
                'doctor_specialty': doctor.specialty,
                'consultation_date': appointment.appointment_date.strftime('%Y-%m-%d'),
                'details': appointment.notes or "No details available"
            })

    # Get unread notification count
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('userhistory.html', history_data=history_data, unread_notifications=unread_notifications)

@app.route('/chat')
@login_required
def chat():
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    # Get unread notification count
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('userchat.html', user_id=user_id, user_name=user.name, unread_notifications=unread_notifications)

# Chat API endpoints for patient-reception communication
@app.route('/api/chat/history')
@login_required
def get_chat_history():
    try:
        user_id = session.get('user_id')
        chat_type = request.args.get('type', 'reception')

        # Try to get non-deleted messages between user and reception
        try:
            messages = ChatMessage.query.filter(
                (((ChatMessage.sender_id == user_id) & (ChatMessage.sender_type == 'user') & (ChatMessage.recipient_type == chat_type)) |
                ((ChatMessage.recipient_id == user_id) & (ChatMessage.recipient_type == 'user') & (ChatMessage.sender_type == chat_type))) &
                (ChatMessage.is_deleted == False)  # Only get non-deleted messages
            ).order_by(ChatMessage.timestamp).all()
        except Exception as e:
            # If is_deleted column doesn't exist yet, try without it
            if "no such column: chat_message.is_deleted" in str(e):
                messages = ChatMessage.query.filter(
                    ((ChatMessage.sender_id == user_id) & (ChatMessage.sender_type == 'user') & (ChatMessage.recipient_type == chat_type)) |
                    ((ChatMessage.recipient_id == user_id) & (ChatMessage.recipient_type == 'user') & (ChatMessage.sender_type == chat_type))
                ).order_by(ChatMessage.timestamp).all()
            else:
                raise e

        # Format messages for frontend
        message_list = []
        for msg in messages:
            try:
                message_data = {
                    'id': msg.id,
                    'content': msg.content,
                    'sender_type': msg.sender_type,
                    'timestamp': msg.timestamp.isoformat(),
                    'attachment': msg.attachment_url if msg.attachment_url else None,
                    'is_deleted': msg.is_deleted  # Include deletion status (should always be False here)
                }
            except AttributeError:
                # If is_deleted attribute doesn't exist yet
                message_data = {
                    'id': msg.id,
                    'content': msg.content,
                    'sender_type': msg.sender_type,
                    'timestamp': msg.timestamp.isoformat(),
                    'attachment': msg.attachment_url if msg.attachment_url else None,
                    'is_deleted': False  # Default to False if attribute doesn't exist
                }
            message_list.append(message_data)

        return jsonify({'success': True, 'messages': message_list})

    except Exception as e:
        print(f"Error getting chat history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_chat_message():
    try:
        user_id = session.get('user_id')
        content = request.form.get('message', '')
        recipient_type = request.form.get('recipient_type', 'reception')

        # Handle file upload if present
        attachment_url = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                from werkzeug.utils import secure_filename
                import os
                import time

                # Create uploads directory if it doesn't exist
                UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
                if not os.path.exists(UPLOAD_FOLDER):
                    os.makedirs(UPLOAD_FOLDER)

                # Create unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"user_{user_id}_{int(time.time())}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(file_path)
                attachment_url = f"/static/uploads/{unique_filename}"

        # Create new message
        new_message = ChatMessage(
            content=content,
            sender_id=user_id,
            sender_type='user',
            recipient_type=recipient_type,
            timestamp=datetime.now(),
            attachment_url=attachment_url,
            read=False
        )

        db.session.add(new_message)
        db.session.commit()

        return jsonify({'success': True, 'message_id': new_message.id})

    except Exception as e:
        print(f"Error sending message: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/chat/delete', methods=['POST'])
@login_required
def delete_chat_message():
    try:
        user_id = session.get('user_id')

        if not request.is_json:
            return jsonify({'success': False, 'message': 'Invalid request format'})

        data = request.get_json()
        message_id = data.get('messageId')

        if not message_id:
            return jsonify({'success': False, 'message': 'Message ID is required'})

        # Find the message
        message = ChatMessage.query.get(message_id)
        if not message:
            return jsonify({'success': False, 'message': 'Message not found'})

        # Check if the user is authorized to delete this message
        # Users can only delete their own messages
        if not (message.sender_id == user_id and message.sender_type == 'user'):
            return jsonify({'success': False, 'message': 'You can only delete your own messages'})

        # Soft delete the message
        try:
            message.is_deleted = True
            message.deleted_by = 'user'
            message.deleted_at = datetime.now()
        except Exception as e:
            # If is_deleted column doesn't exist yet, inform the user
            if "no such column: is_deleted" in str(e):
                return jsonify({
                    'success': False,
                    'message': 'Delete functionality is not available yet. Please restart the server to enable this feature.'
                })
            else:
                raise e

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting message: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/chat/new')
@login_required
def check_new_messages():
    try:
        user_id = session.get('user_id')
        since = request.args.get('since', '0')
        chat_type = request.args.get('type', 'reception')

        # Convert since to datetime
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            # If invalid timestamp, use a time far in the past
            since_time = datetime.now() - timedelta(days=1)

        # Try to get new non-deleted messages from reception to this user
        try:
            messages = ChatMessage.query.filter(
                (ChatMessage.sender_type == chat_type) &
                (ChatMessage.recipient_id == user_id) &
                (ChatMessage.recipient_type == 'user') &
                (ChatMessage.timestamp > since_time) &
                (ChatMessage.is_deleted == False)  # Only get non-deleted messages
            ).order_by(ChatMessage.timestamp).all()
        except Exception as e:
            # If is_deleted column doesn't exist yet, try without it
            if "no such column: chat_message.is_deleted" in str(e):
                messages = ChatMessage.query.filter(
                    (ChatMessage.sender_type == chat_type) &
                    (ChatMessage.recipient_id == user_id) &
                    (ChatMessage.recipient_type == 'user') &
                    (ChatMessage.timestamp > since_time)
                ).order_by(ChatMessage.timestamp).all()
            else:
                raise e

        # Mark messages as read
        for msg in messages:
            msg.read = True

        db.session.commit()

        # Format messages for frontend
        message_list = []
        for msg in messages:
            try:
                message_data = {
                    'id': msg.id,
                    'content': msg.content,
                    'sender_type': msg.sender_type,
                    'timestamp': msg.timestamp.isoformat(),
                    'attachment': msg.attachment_url if msg.attachment_url else None,
                    'is_deleted': msg.is_deleted  # Include deletion status (should always be False here)
                }
            except AttributeError:
                # If is_deleted attribute doesn't exist yet
                message_data = {
                    'id': msg.id,
                    'content': msg.content,
                    'sender_type': msg.sender_type,
                    'timestamp': msg.timestamp.isoformat(),
                    'attachment': msg.attachment_url if msg.attachment_url else None,
                    'is_deleted': False  # Default to False if attribute doesn't exist
                }
            message_list.append(message_data)

        return jsonify({'success': True, 'messages': message_list})

    except Exception as e:
        print(f"Error checking new messages: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# Route to get all doctors
@app.route('/api/doctors')
@login_required
def get_doctors():
    doctors = Doctor.query.all()
    result = []
    for doctor in doctors:
        result.append({
            'id': doctor.id,
            'name': doctor.name,
            'specialty': doctor.specialty,
            'description': doctor.description,
            'available_days': doctor.available_days
        })
    return json.dumps(result)

# Route to book an appointment
@app.route('/api/book_appointment', methods=['POST'])
@login_required
def book_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    doctor_id = data.get('doctor_id')
    preferred_date = data.get('date')
    notes = data.get('notes', '')

    # Debug logging
    print(f"Received appointment request: doctor_id={doctor_id}, date={preferred_date}, notes={notes}")

    # Validate inputs
    if not doctor_id or not preferred_date:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    try:
        # Convert string date from DD-MM-YYYY to Date object
        date_obj = datetime.strptime(preferred_date, '%d-%m-%Y').date()
        print(f"Parsed date: {date_obj}")

        # Check if date is in the past
        today = datetime.now().date()
        if date_obj < today:
            return json.dumps({'success': False, 'message': 'Appointment date must not be in the past'})

        # Check if the selected date is a working day for the doctor
        doctor = Doctor.query.get(doctor_id)
        if doctor and doctor.available_days:
            # Get the day of the week (0 = Monday in Python's weekday)
            day_of_week = date_obj.weekday()
            # Convert to 0 = Sunday format
            day_of_week = (day_of_week + 1) % 7
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            day_name = day_names[day_of_week]

            # Check if the day is in the doctor's working days
            working_days = [day.strip() for day in doctor.available_days.split(',')]
            if day_name not in working_days:
                # Find the next working day
                next_working_day = None
                for i in range(1, 8):  # Check the next 7 days
                    next_date = date_obj + timedelta(days=i)
                    next_day_of_week = (next_date.weekday() + 1) % 7
                    next_day_name = day_names[next_day_of_week]
                    if next_day_name in working_days:
                        next_working_day = next_date
                        break

                if next_working_day:
                    return json.dumps({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s. Next available day is {day_names[next_working_day.weekday()]} ({next_working_day.strftime('%d-%m-%Y')})."
                    })
                else:
                    return json.dumps({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s and no upcoming working days were found."
                    })

        # Create new appointment
        new_appointment = Appointment(
            user_id=session['user_id'],
            doctor_id=doctor_id,
            appointment_date=date_obj,
            appointment_time=None,  # Time will be assigned by doctor
            status='pending',
            notes=notes
        )

        db.session.add(new_appointment)
        db.session.commit()
        print(f"Appointment created with ID: {new_appointment.id}")

        return json.dumps({'success': True, 'appointment_id': new_appointment.id})

    except ValueError as ve:
        print(f"Date parsing error: {str(ve)}")
        return json.dumps({'success': False, 'message': f'Invalid date format. Please use DD-MM-YYYY format. Error: {str(ve)}'})
    except Exception as e:
        db.session.rollback()
        print(f"Error creating appointment: {str(e)}")
        return json.dumps({'success': False, 'message': str(e)})

# Route to get user's appointments
@app.route('/api/appointments')
@login_required
def get_appointments():
    user_id = session['user_id']
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.appointment_date.desc()).all()

    result = []
    for appointment in appointments:
        doctor = Doctor.query.get(appointment.doctor_id)
        result.append({
            'id': appointment.id,
            'doctor_name': doctor.name,
            'doctor_specialty': doctor.specialty,
            'date': appointment.appointment_date.strftime('%d-%m-%Y') if appointment.appointment_date else None,
            'time': appointment.appointment_time,
            'status': appointment.status,
            'notes': appointment.notes,
            'created_at': appointment.created_at.strftime('%d-%m-%Y %H:%M:%S')
        })

    return json.dumps(result)

# Route to cancel an appointment
@app.route('/api/cancel_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    user_id = session['user_id']
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=user_id).first()

    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Get user and doctor information for notification
        user = User.query.get(user_id)
        doctor = Doctor.query.get(appointment.doctor_id)

        # Update appointment status
        appointment.status = 'cancelled'

        db.session.commit()
        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        return json.dumps({'success': False, 'message': str(e)})

# Route to reschedule an appointment
@app.route('/api/reschedule_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def reschedule_appointment(appointment_id):
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    new_date = data.get('date')
    new_time = data.get('time')

    if not new_date or not new_time:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    user_id = session['user_id']
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=user_id).first()

    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Convert string date to Date object
        date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()

        # Check if date is in the future
        if date_obj < datetime.now().date():
            return json.dumps({'success': False, 'message': 'Appointment date must be in the future'})

        appointment.appointment_date = date_obj
        appointment.appointment_time = new_time
        appointment.status = 'pending'  # Reset to pending for re-approval

        db.session.commit()
        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        return json.dumps({'success': False, 'message': str(e)})

# Add this route to handle notifications
@app.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()

    # Get unread count before marking as read
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    # Mark all as read
    for notification in notifications:
        notification.read = True
    db.session.commit()

    return render_template('notifications.html', notifications=notifications, unread_notifications=0)

@app.route('/gallery')
@login_required
def user_gallery():
    user_id = session['user_id']

    # Get unread notification count
    unread_notifications = Notification.query.filter_by(user_id=user_id, read=False).count()

    return render_template('user_gallery.html', user_id=user_id, unread_notifications=unread_notifications)

@app.route('/api/gallery')
@login_required
def get_gallery_photos():
    user_id = session['user_id']

    try:
        # Get all approved photos and user's own pending photos
        photos = Gallery.query.filter(
            (Gallery.approved == True) |
            ((Gallery.uploaded_by_id == user_id) & (Gallery.uploaded_by_type == 'user'))
        ).order_by(Gallery.upload_date.desc()).all()

        result = []
        for photo in photos:
            result.append({
                'id': photo.id,
                'title': photo.title,
                'description': photo.description,
                'image_path': photo.image_path,
                'uploaded_by_id': photo.uploaded_by_id,
                'uploaded_by_type': photo.uploaded_by_type,
                'upload_date': photo.upload_date.isoformat(),
                'approved': photo.approved
            })

        return jsonify({'success': True, 'photos': result})
    except Exception as e:
        print(f"Error getting gallery photos: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/gallery/upload', methods=['POST'])
@login_required
def upload_gallery_photo():
    user_id = session['user_id']

    try:
        title = request.form.get('title', '')
        description = request.form.get('description', '')
        photo = request.files.get('photo')

        if not photo:
            return jsonify({'success': False, 'message': 'Photo is required'})

        # Check if the file is an image
        if not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            return jsonify({'success': False, 'message': 'Only image files are allowed'})

        # Create a unique filename
        import os
        from werkzeug.utils import secure_filename

        filename = secure_filename(photo.filename)
        timestamp = int(datetime.now().timestamp())
        unique_filename = f"gallery_{user_id}_{timestamp}_{filename}"

        # Save the file
        upload_folder = os.path.join('static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        file_path = os.path.join(upload_folder, unique_filename)
        photo.save(file_path)

        # Create gallery entry
        gallery_item = Gallery(
            title=title,
            description=description,
            image_path=f"/{file_path}",
            uploaded_by_id=user_id,
            uploaded_by_type='user',
            upload_date=datetime.now(),
            approved=False  # Patient uploads need approval
        )

        db.session.add(gallery_item)

        # Create notification for reception
        notification = ReceptionNotification(
            message=f"New photo uploaded by a patient: '{title}'. Waiting for approval.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True, 'photo_id': gallery_item.id})
    except Exception as e:
        db.session.rollback()
        print(f"Error uploading gallery photo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/notifications/count')
@login_required
def get_notification_count():
    user_id = session['user_id']
    unread_count = Notification.query.filter_by(user_id=user_id, read=False).count()
    return jsonify({'count': unread_count})

@app.route('/api/submit_review', methods=['POST'])
@login_required
def submit_review():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    rating = data.get('rating')
    review_text = data.get('review_text', '')

    # Validate inputs
    if not appointment_id or not rating or not rating.isdigit():
        return jsonify({'success': False, 'message': 'Missing or invalid required fields'})

    rating = int(rating)
    if rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'})

    # Verify the appointment belongs to the current user
    user_id = session['user_id']
    if appointment.user_id != user_id:
        return jsonify({'success': False, 'message': 'You can only review your own appointments'})

    # Verify the appointment is completed
    if appointment.status != 'completed':
        return jsonify({'success': False, 'message': 'You can only review completed appointments'})

    # Check if a review already exists
    existing_review = DoctorReview.query.filter_by(appointment_id=appointment_id).first()
    if existing_review:
        return jsonify({'success': False, 'message': 'You have already reviewed this appointment'})

    try:
        # Create the review
        review = DoctorReview(
            user_id=user_id,
            doctor_id=appointment.doctor_id,
            appointment_id=appointment_id,
            rating=rating,
            review_text=review_text,
            created_at=datetime.now()
        )
        db.session.add(review)
        db.session.commit()

        # Create notification for the doctor (if we had doctor login)
        # For now, create a notification for reception
        notification = ReceptionNotification(
            message=f"Patient {appointment.user.name} has submitted a {rating}-star review for Dr. {appointment.doctor.name}.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in submit_review: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_doctor_reviews/<int:doctor_id>')
def get_doctor_reviews(doctor_id):
    # Get all reviews for the doctor
    reviews = DoctorReview.query.filter_by(doctor_id=doctor_id).order_by(DoctorReview.created_at.desc()).all()

    # Calculate average rating
    total_rating = sum(review.rating for review in reviews) if reviews else 0
    avg_rating = round(total_rating / len(reviews), 1) if reviews else 5.0

    # Format reviews for JSON response
    reviews_data = []
    for review in reviews:
        reviews_data.append({
            'id': review.id,
            'user_name': review.user.name,
            'rating': review.rating,
            'review_text': review.review_text,
            'created_at': review.created_at.strftime('%Y-%m-%d %H:%M')
        })

    return jsonify({
        'success': True,
        'doctor_id': doctor_id,
        'doctor_name': Doctor.query.get(doctor_id).name if Doctor.query.get(doctor_id) else 'Unknown',
        'avg_rating': avg_rating,
        'review_count': len(reviews),
        'reviews': reviews_data
    })

# Doctor routes for appointment management
@app.route('/doctor/pending')
@login_required
def doctor_pending():
    # Get the doctor ID from the session
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        flash('You must be logged in as a doctor to view this page', 'error')
        return redirect('/login')

    # Get all pending appointments for this doctor
    pending_appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        status='pending'
    ).order_by(Appointment.appointment_date).all()

    return render_template('doctor_pending.html', pending_appointments=pending_appointments)

@app.route('/api/doctor/confirm_appointment', methods=['POST'])
@login_required
def confirm_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    time = data.get('time')
    duration = data.get('duration', '30')  # Default to 30 minutes if not specified

    # Validate inputs
    if not appointment_id or not time:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the doctor ID from the session
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        return json.dumps({'success': False, 'message': 'You must be logged in as a doctor'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment or appointment.doctor_id != doctor_id:
        return json.dumps({'success': False, 'message': 'Appointment not found or does not belong to you'})

    try:
        # Update the appointment
        appointment.appointment_time = time
        appointment.status = 'confirmed'

        db.session.commit()

        # Create notification for the patient
        notification = Notification(
            user_id=appointment.user_id,
            message=f"Your appointment with Dr. {Doctor.query.get(doctor_id).name} has been confirmed for {appointment.appointment_date.strftime('%B %d, %Y')} at {time}.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        return json.dumps({'success': False, 'message': str(e)})

@app.route('/api/doctor/reject_appointment', methods=['POST'])
@login_required
def reject_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')

    # Validate inputs
    if not appointment_id:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the doctor ID from the session
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        return json.dumps({'success': False, 'message': 'You must be logged in as a doctor'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment or appointment.doctor_id != doctor_id:
        return json.dumps({'success': False, 'message': 'Appointment not found or does not belong to you'})

    try:
        # Update the appointment
        appointment.status = 'cancelled'

        db.session.commit()

        # Create notification for the patient
        notification = Notification(
            user_id=appointment.user_id,
            message=f"Your appointment request with Dr. {Doctor.query.get(doctor_id).name} for {appointment.appointment_date.strftime('%B %d, %Y')} has been declined. Please book another appointment.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        return json.dumps({'success': False, 'message': str(e)})

def init_sample_doctors():
    # Check if doctors already exist
    if Doctor.query.count() > 0:
        return

    # Create sample doctors
    doctors = [
        Doctor(
            name="Dr. Ramesh Kumar",
            specialty="Cardiologist",
            description="Specializes in heart conditions with over 15 years of experience. Available on weekdays.",
            available_days="Monday,Tuesday,Wednesday,Thursday,Friday"
        ),
        Doctor(
            name="Dr. Anita Sharma",
            specialty="Neurologist",
            description="Expert in neurological disorders with advanced training in the latest treatments. Available Mon-Wed.",
            available_days="Monday,Tuesday,Wednesday"
        ),
        Doctor(
            name="Dr. Ritu Verma",
            specialty="Pediatrician",
            description="Child healthcare specialist with a gentle approach. Available all week including weekends.",
            available_days="Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday"
        )
    ]

    for doctor in doctors:
        db.session.add(doctor)

    try:
        db.session.commit()
        print("Sample doctors added successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Error adding sample doctors: {str(e)}")

@app.route('/api/respond_to_suggestion', methods=['POST'])
@login_required
def respond_to_suggestion():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    response = data.get('response')  # 'accept' or 'reject'

    # Validate inputs
    if not appointment_id or not response:
        return jsonify({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'})

    # Verify that this appointment belongs to the current user
    if appointment.user_id != session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized access'})

    try:
        if response == 'accept':
            # Extract the suggested date and time from notes
            notes = appointment.notes
            if 'Reception suggested new date/time on' in notes:
                suggested_info = notes.split('Reception suggested new date/time on ')[1]
                date_time_info = suggested_info.split('. Reason:')[0]

                # Parse the date from the note using regex
                print(f"Extracted date/time info: {date_time_info}")

                # Try to extract date and time using regex
                import re

                # Look for a date in format "Month Day, Year" (e.g., "May 19, 2025")
                date_match = re.search(r'(\w+ \d+, \d{4})', date_time_info)

                # Look for a time in format "HH:MM AM/PM" (e.g., "10:30 AM")
                time_match = re.search(r'(\d{1,2}:\d{2} [AP]M)', date_time_info)

                if date_match and time_match:
                    date_str = date_match.group(1)
                    time_str = time_match.group(1)

                    print(f"Extracted date: {date_str}, time: {time_str}")

                    try:
                        # Convert "Month Day, Year" to a date object
                        date_obj = datetime.strptime(date_str, '%B %d, %Y').date()
                        print(f"Converted date object: {date_obj}")

                        # Update the appointment with the extracted date and time
                        appointment.appointment_date = date_obj
                        appointment.appointment_time = time_str
                    except ValueError as e:
                        print(f"Error parsing date: {str(e)}")
                        # Don't update the date/time if parsing fails, but continue with acceptance

                # Update appointment status regardless of date parsing success
                appointment.status = 'confirmed'
                appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient accepted the suggested date/time on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

                # Create notification for reception
                notification = ReceptionNotification(
                    message=f"Patient {User.query.get(appointment.user_id).name} accepted the suggested appointment time with Dr. {Doctor.query.get(appointment.doctor_id).name}.",
                    created_at=datetime.now(),
                    read=False
                )
                db.session.add(notification)
            else:
                appointment.status = 'confirmed'
                appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient accepted the appointment on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

        elif response == 'reject':
            appointment.status = 'pending'  # Reset to pending
            appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient rejected the suggested date/time on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

            # Create notification for reception
            notification = ReceptionNotification(
                message=f"Patient {User.query.get(appointment.user_id).name} rejected the suggested appointment time with Dr. {Doctor.query.get(appointment.doctor_id).name}. Please contact the patient to arrange a new time.",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(notification)

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Error in respond_to_suggestion: {str(e)}")
        # Don't show the actual error to the user, provide a more user-friendly message
        return jsonify({'success': False, 'message': 'There was an issue processing your request. The appointment has been accepted but may need to be rescheduled.'})

@app.route('/api/suggest_alternative', methods=['POST'])
@login_required
def suggest_alternative():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    alternative_date = data.get('alternative_date')
    alternative_time = data.get('alternative_time')
    reason = data.get('reason', '')

    # Validate inputs
    if not appointment_id or not alternative_date or not alternative_time:
        return jsonify({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'})

    # Verify that this appointment belongs to the current user
    if appointment.user_id != session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized access'})

    try:
        # Convert string date to Date object
        date_obj = datetime.strptime(alternative_date, '%Y-%m-%d').date()

        # Check if the selected date is a working day for the doctor
        doctor = Doctor.query.get(appointment.doctor_id)
        if doctor and doctor.available_days:
            # Get the day of the week (0 = Monday in Python's weekday)
            day_of_week = date_obj.weekday()
            # Convert to 0 = Sunday format
            day_of_week = (day_of_week + 1) % 7
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            day_name = day_names[day_of_week]

            # Check if the day is in the doctor's working days
            working_days = [day.strip() for day in doctor.available_days.split(',')]
            if day_name not in working_days:
                return jsonify({
                    'success': False,
                    'message': f"Dr. {doctor.name} doesn't work on {day_name}s. Please select one of their working days: {', '.join(working_days)}."
                })

        # Update the appointment status
        appointment.status = 'patient_suggested'  # New status for patient suggestions
        appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient suggested alternative date/time on {datetime.now().strftime('%Y-%m-%d %H:%M')}: {date_obj.strftime('%B %d, %Y')} at {alternative_time}. Reason: {reason}"

        # Create notification for reception
        notification = ReceptionNotification(
            message=f"Patient {User.query.get(appointment.user_id).name} suggested an alternative date/time for appointment with Dr. {Doctor.query.get(appointment.doctor_id).name}: {date_obj.strftime('%B %d, %Y')} at {alternative_time}.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in suggest_alternative: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/respond_to_doctor_reschedule', methods=['POST'])
@login_required
def respond_to_doctor_reschedule():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    response = data.get('response')  # 'accept' or 'reject'

    # Validate inputs
    if not appointment_id or not response:
        return jsonify({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'})

    # Verify that this appointment belongs to the current user
    if appointment.user_id != session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized access'})

    try:
        if response == 'accept':
            # Extract the rescheduled date and time from notes
            notes = appointment.notes
            if 'Doctor rescheduled your appointment to' in notes:
                reschedule_info = notes.split('Doctor rescheduled your appointment to ')[1]
                date_time_info = reschedule_info.split('. Reason:')[0]

                print(f"Extracted date/time info: {date_time_info}")

                # Try to extract date and time using regex
                import re

                # Look for a date in format "Month Day, Year" (e.g., "May 19, 2025")
                date_match = re.search(r'(\w+ \d+, \d{4})', date_time_info)

                # Look for a time in format "HH:MM AM/PM" (e.g., "10:30 AM")
                time_match = re.search(r'(\d{1,2}:\d{2} [AP]M)', date_time_info)

                if date_match and time_match:
                    date_str = date_match.group(1)
                    time_str = time_match.group(1)

                    print(f"Extracted date: {date_str}, time: {time_str}")

                    try:
                        # Convert "Month Day, Year" to a date object
                        date_obj = datetime.strptime(date_str, '%B %d, %Y').date()
                        print(f"Converted date object: {date_obj}")

                        # Update the appointment with the extracted date and time
                        appointment.appointment_date = date_obj
                        appointment.appointment_time = time_str
                    except ValueError as e:
                        print(f"Error parsing date: {str(e)}")
                        # Don't update the date/time if parsing fails, but continue with acceptance

                # Update appointment status regardless of date parsing success
                appointment.status = 'confirmed'
                appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient accepted the doctor's rescheduled appointment on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

                # Create notification for reception
                notification = ReceptionNotification(
                    message=f"Patient {User.query.get(appointment.user_id).name} accepted the rescheduled appointment with Dr. {Doctor.query.get(appointment.doctor_id).name}.",
                    created_at=datetime.now(),
                    read=False
                )
                db.session.add(notification)
            else:
                return jsonify({'success': False, 'message': 'Could not find doctor reschedule information in appointment notes'})

        elif response == 'reject':
            # Update appointment status
            appointment.status = 'pending'  # Reset to pending
            appointment.notes = f"{appointment.notes}\n[SYSTEM] Patient rejected the doctor's rescheduled appointment on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

            # Create notification for reception
            notification = ReceptionNotification(
                message=f"Patient {User.query.get(appointment.user_id).name} rejected the rescheduled appointment with Dr. {Doctor.query.get(appointment.doctor_id).name}. Please contact the patient to arrange a new time.",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(notification)

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Error in respond_to_doctor_reschedule: {str(e)}")
        # Don't show the actual error to the user, provide a more user-friendly message
        return jsonify({'success': False, 'message': 'There was an issue processing your request. The appointment has been accepted but may need to be rescheduled.'})

@app.route('/api/update_appointment', methods=['POST'])
@login_required
def update_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    new_date = data.get('new_date')
    new_time = data.get('new_time')

    # Validate inputs
    if not appointment_id or not new_date:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    user_id = session['user_id']
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=user_id).first()

    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Convert string date to Date object
        date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()

        # Check if date is in the future
        if date_obj < datetime.now().date():
            return json.dumps({'success': False, 'message': 'Appointment date must be in the future'})

        appointment.appointment_date = date_obj
        appointment.appointment_time = new_time
        appointment.status = 'pending'  # Reset to pending for re-approval

        db.session.commit()
        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        return json.dumps({'success': False, 'message': str(e)})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        init_sample_doctors()
        # ChatMessage table will be created by db.create_all()
    app.run(debug=True)
