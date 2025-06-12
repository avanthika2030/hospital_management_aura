from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
from datetime import datetime, timedelta
from functools import wraps
import os

from backend import db, User, Doctor, Appointment, Notification, ChatMessage, DoctorReview, Gallery, send_email_notification  # Use the shared db instance

# Create the Flask app
app = Flask(__name__)
app.secret_key = 'client_secret.json'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)  # Correctly bind the shared db instance to this app

# Reception credentials (hardcoded for simplicity)
RECEPTION_USERNAME = "aura"
RECEPTION_PASSWORD = "aura@123"

# Login required decorator
def reception_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'reception_logged_in' not in session:
            return redirect(url_for('reception_login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to check for appointment time conflicts
def check_appointment_conflict(doctor_id, date_obj, time_str, duration_minutes=30, exclude_appointment_id=None):
    """
    Check if there's a conflict with existing appointments for the given doctor, date and time.
    Also checks if the doctor works on the selected day.

    Args:
        doctor_id: The ID of the doctor
        date_obj: The date of the appointment (datetime.date object)
        time_str: The time of the appointment (string in format "HH:MM AM/PM")
        duration_minutes: The duration of the appointment in minutes (default: 30)
        exclude_appointment_id: Optional ID of an appointment to exclude from the check

    Returns:
        tuple: (has_conflict, conflicting_appointment, next_available_time)
    """
    # First, check if the doctor works on this day
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

            # Return conflict with a special message
            return True, None, f"Doctor doesn't work on {day_name}s. Next working day: {next_working_day.strftime('%A, %B %d')}"

    # Convert the time string to a datetime object for comparison
    time_format = "%I:%M %p"  # 12-hour format with AM/PM
    try:
        time_obj = datetime.strptime(time_str, time_format).time()
    except ValueError:
        # Try alternative format without space between time and AM/PM
        try:
            time_obj = datetime.strptime(time_str, "%I:%M%p").time()
        except ValueError:
            # Try 24-hour format
            try:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                return True, None, None  # Invalid time format

    # Calculate the end time of the requested appointment
    start_datetime = datetime.combine(date_obj, time_obj)
    end_datetime = start_datetime + timedelta(minutes=duration_minutes)

    # Get all confirmed appointments for this doctor on this date
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == date_obj,
        Appointment.status.in_(['confirmed', 'pending']),
        Appointment.id != exclude_appointment_id if exclude_appointment_id else True
    ).all()

    # Check for conflicts
    for appointment in appointments:
        # Skip if appointment has no time yet
        if not appointment.appointment_time:
            continue

        # Parse the appointment time
        try:
            appt_time_obj = datetime.strptime(appointment.appointment_time, time_format).time()
        except ValueError:
            # Try alternative format without space
            try:
                appt_time_obj = datetime.strptime(appointment.appointment_time, "%I:%M%p").time()
            except ValueError:
                # Try 24-hour format
                try:
                    appt_time_obj = datetime.strptime(appointment.appointment_time, "%H:%M").time()
                except ValueError:
                    continue  # Skip this appointment if time format is invalid

        # Calculate start and end times for existing appointment
        appt_start = datetime.combine(date_obj, appt_time_obj)
        appt_end = appt_start + timedelta(minutes=duration_minutes)

        # Check for overlap
        if (start_datetime < appt_end and end_datetime > appt_start):
            # Find the next available time slot
            next_time = appt_end

            # Format the next available time
            next_time_str = next_time.strftime(time_format)

            return True, appointment, next_time_str

    # No conflict found
    return False, None, None

# Helper function to suggest available time slots
def get_available_time_slots(doctor_id, date_obj, duration_minutes=30, start_hour=9, end_hour=17):
    """
    Get a list of available time slots for a doctor on a specific date.

    Args:
        doctor_id: The ID of the doctor
        date_obj: The date to check (datetime.date object)
        duration_minutes: The duration of each appointment in minutes
        start_hour: The hour to start checking from (24-hour format)
        end_hour: The hour to end checking at (24-hour format)

    Returns:
        list: List of available time slots in "HH:MM AM/PM" format
    """
    # Get all confirmed appointments for this doctor on this date
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == date_obj,
        Appointment.status.in_(['confirmed', 'pending'])
    ).all()

    # Extract the times of existing appointments
    booked_slots = []
    for appointment in appointments:
        if appointment.appointment_time:
            try:
                # Try to parse the time in 12-hour format
                time_obj = datetime.strptime(appointment.appointment_time, "%I:%M %p").time()
                start_time = datetime.combine(date_obj, time_obj)
                end_time = start_time + timedelta(minutes=duration_minutes)
                booked_slots.append((start_time, end_time))
            except ValueError:
                # Try alternative format without space
                try:
                    time_obj = datetime.strptime(appointment.appointment_time, "%I:%M%p").time()
                    start_time = datetime.combine(date_obj, time_obj)
                    end_time = start_time + timedelta(minutes=duration_minutes)
                    booked_slots.append((start_time, end_time))
                except ValueError:
                    # Try 24-hour format
                    try:
                        time_obj = datetime.strptime(appointment.appointment_time, "%H:%M").time()
                        start_time = datetime.combine(date_obj, time_obj)
                        end_time = start_time + timedelta(minutes=duration_minutes)
                        booked_slots.append((start_time, end_time))
                    except ValueError:
                        continue  # Skip this appointment if time format is invalid

    # Generate all possible time slots
    available_slots = []
    current_time = datetime.combine(date_obj, datetime.min.time().replace(hour=start_hour))
    end_time = datetime.combine(date_obj, datetime.min.time().replace(hour=end_hour))

    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=duration_minutes)

        # Check if this slot overlaps with any booked slot
        is_available = True
        for booked_start, booked_end in booked_slots:
            if current_time < booked_end and slot_end > booked_start:
                is_available = False
                break

        if is_available:
            available_slots.append(current_time.strftime("%I:%M %p"))

        # Move to the next slot
        current_time += timedelta(minutes=duration_minutes)

    return available_slots

# Routes
@app.route('/')
def reception_index():
    return redirect(url_for('reception_login'))

@app.route('/reception/login', methods=['GET', 'POST'])
def reception_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == RECEPTION_USERNAME and password == RECEPTION_PASSWORD:
            session['reception_logged_in'] = True
            return redirect(url_for('reception_dashboard'))
        else:
            error = 'Invalid credentials. Please try again.'

    return render_template('reception_login.html', error=error)

@app.route('/reception/logout')
def reception_logout():
    session.pop('reception_logged_in', None)
    return redirect(url_for('reception_login'))

@app.route('/reception/dashboard')
@reception_login_required
def reception_dashboard():
    try:
        # Get current date
        today = datetime.now().date()

        # Get counts for dashboard
        doctor_count = Doctor.query.count()
        patient_count = User.query.count()
        appointment_count = Appointment.query.count()
        pending_appointments = Appointment.query.filter_by(status='pending').count()
        today_appointments = Appointment.query.filter(
            Appointment.appointment_date == today
        ).count()

        # Get recent appointments
        recent_appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).limit(5).all()

        return render_template('reception_dashboard.html',
                              doctor_count=doctor_count,
                              patient_count=patient_count,
                              appointment_count=appointment_count,
                              pending_appointments=pending_appointments,
                              today_appointments=today_appointments,
                              recent_appointments=recent_appointments)
    except Exception as e:
        print(f"Error in reception_dashboard: {str(e)}")
        # If there's an error, still show the dashboard with default values
        return render_template('reception_dashboard.html',
                              doctor_count=0,
                              patient_count=0,
                              appointment_count=0,
                              pending_appointments=0,
                              today_appointments=0,
                              recent_appointments=[])

# Doctor management routes
@app.route('/reception/doctors')
@reception_login_required
def reception_doctors():
    doctors = Doctor.query.all()

    # Get review statistics for each doctor
    for doctor in doctors:
        reviews = DoctorReview.query.filter_by(doctor_id=doctor.id).all()
        doctor.review_count = len(reviews)
        doctor.avg_rating = round(sum(review.rating for review in reviews) / len(reviews), 1) if reviews else 5.0

    return render_template('reception_doctors.html', doctors=doctors)

@app.route('/reception/doctor_reviews/<int:doctor_id>')
@reception_login_required
def doctor_reviews(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    reviews = DoctorReview.query.filter_by(doctor_id=doctor_id).order_by(DoctorReview.created_at.desc()).all()

    # Calculate average rating
    avg_rating = round(sum(review.rating for review in reviews) / len(reviews), 1) if reviews else 5.0

    return render_template('reception_doctor_reviews.html', doctor=doctor, reviews=reviews, avg_rating=avg_rating)

@app.route('/reception/add_doctor', methods=['POST'])
@reception_login_required
def add_doctor():
    try:
        name = request.form.get('name')
        specialty = request.form.get('specialty')
        description = request.form.get('description', '')

        # Get selected days from checkboxes
        selected_days = request.form.getlist('days[]')

        # Join the selected days with commas
        available_days = ', '.join(selected_days) if selected_days else ''

        # Validate required fields
        if not name or not specialty:
            flash('Name and specialty are required fields', 'error')
            return redirect(url_for('reception_doctors'))

        # Validate that at least one day is selected
        if not selected_days:
            flash('Please select at least one available day', 'error')
            return redirect(url_for('reception_doctors'))

        new_doctor = Doctor(
            name=name,
            specialty=specialty,
            description=description,
            available_days=available_days
        )

        db.session.add(new_doctor)
        db.session.commit()
        flash('Doctor added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding doctor: {str(e)}', 'error')

    return redirect(url_for('reception_doctors'))

@app.route('/reception/delete_doctor', methods=['POST'])
@reception_login_required
def delete_doctor():
    try:
        doctor_id = request.form.get('doctor_id')
        action = request.form.get('action', 'cancel')  # Default to 'cancel' if not specified
        new_doctor_id = request.form.get('new_doctor_id')  # Only used if action is 'reassign'

        if not doctor_id:
            flash('No doctor ID provided', 'error')
            return redirect(url_for('reception_doctors'))

        doctor = Doctor.query.get_or_404(doctor_id)
        doctor_name = doctor.name

        # Find all appointments with this doctor
        appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()

        if action == 'cancel':
            # Cancel all appointments
            affected_user_ids = set()
            for appointment in appointments:
                affected_user_ids.add(appointment.user_id)

                # Update the appointment instead of deleting it
                appointment.status = 'cancelled'

            # Create notification for affected users
            for user_id in affected_user_ids:
                user = User.query.get(user_id)
                if user:
                    # Create notification
                    notification = Notification(
                        user_id=user_id,
                        message=f"Your appointment with Dr. {doctor_name} has been cancelled as the doctor is no longer available. Please book a new appointment with another doctor.",
                        created_at=datetime.now(),
                        read=False
                    )
                    db.session.add(notification)

            flash_message = f'Doctor {doctor_name} deleted successfully. All associated appointments have been marked as cancelled with a notification to patients.'

        elif action == 'reassign' and new_doctor_id:
            # Reassign all appointments to the new doctor
            new_doctor = Doctor.query.get_or_404(new_doctor_id)
            affected_user_ids = set()

            for appointment in appointments:
                affected_user_ids.add(appointment.user_id)

                # Update the appointment with the new doctor
                appointment.doctor_id = new_doctor_id

            # Create notification for affected users
            for user_id in affected_user_ids:
                user = User.query.get(user_id)
                if user:
                    # Create notification
                    notification = Notification(
                        user_id=user_id,
                        message=f"Your appointment with Dr. {doctor_name} has been reassigned to Dr. {new_doctor.name}.",
                        created_at=datetime.now(),
                        read=False
                    )
                    db.session.add(notification)

            flash_message = f'Doctor {doctor_name} deleted successfully. All appointments have been reassigned to Dr. {new_doctor.name} with a notification to patients.'

        else:
            db.session.rollback()
            flash('Invalid action specified. Doctor was not deleted.', 'error')
            return redirect(url_for('reception_doctors'))

        # Delete the doctor
        db.session.delete(doctor)
        db.session.commit()

        flash(flash_message, 'success')
        return redirect(url_for('reception_doctors'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting doctor: {str(e)}', 'error')
        return redirect(url_for('reception_doctors'))

@app.route('/reception/add_patient', methods=['POST'])
@reception_login_required
def add_patient():
    try:
        # Get all form fields
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        dob_str = request.form.get('dob')
        gender = request.form.get('gender')
        address = request.form.get('address', '')
        emergency_contact = request.form.get('emergency_contact', '')
        allergies = request.form.get('allergies', '')
        medical_history = request.form.get('medical_history', '')

        # Validate required fields
        if not name or not email or not phone:
            flash('Name, email, and phone are required fields', 'error')
            return redirect(url_for('reception_patients'))

        # Check if patient with this email or phone already exists
        existing_patient = User.query.filter((User.email == email) | (User.phone == phone)).first()
        if existing_patient:
            flash(f'A patient with this {"email" if existing_patient.email == email else "phone number"} already exists', 'error')
            return redirect(url_for('reception_patients'))

        # Convert date string to date object if provided
        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                # Validate that the date of birth is in the past
                today = datetime.now().date()
                if dob >= today:
                    flash('Date of Birth must be in the past', 'error')
                    return redirect(url_for('reception_patients'))
            except ValueError:
                flash('Invalid date format for Date of Birth', 'error')
                return redirect(url_for('reception_patients'))

        # Generate a password based on firstname@last-two-digits-of-year-of-birth
        first_name = name.split()[0].lower()

        # Get the last two digits of the birth year if available
        birth_year_digits = ""
        if dob:
            birth_year = dob.year
            birth_year_digits = str(birth_year)[-2:]
        else:
            # If no DOB provided, use current year's last two digits
            birth_year_digits = str(datetime.now().year)[-2:]

        # Create the password
        password = f"{first_name}@{birth_year_digits}"

        # Calculate age from DOB if provided
        age = None
        if dob:
            today = datetime.now().date()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        # Create new patient
        new_patient = User(
            name=name,
            email=email,
            phone=phone,
            gender=gender,
            password=password,
            age=age,
            dob=dob
        )

        # Store additional patient information if available
        if address:
            new_patient.address = address
        if emergency_contact:
            new_patient.emergency_contact = emergency_contact
        if allergies:
            new_patient.allergies = allergies
        if medical_history:
            new_patient.medical_history = medical_history

        # Add to database
        db.session.add(new_patient)
        db.session.commit()

        # Get the new patient ID for additional information
        patient_id = new_patient.id

        # Create a welcome notification for the patient
        # This is only sent when creating a patient without an appointment
        notification = Notification(
            user_id=patient_id,
            message=f"Welcome to AURA Hospital! Your account has been created by reception. You can log in using your phone number and password: {password}",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        flash(f'Patient {name} added successfully. Login credentials: Phone: {phone}, Password: {password}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding patient: {str(e)}', 'error')

    return redirect(url_for('reception_patients'))

# Patient management routes
@app.route('/reception/patients')
@reception_login_required
def reception_patients():
    try:
        patients = User.query.all()
        print(f"Found {len(patients)} patients")
        return render_template('reception_patients.html', patients=patients)
    except Exception as e:
        print(f"Error in reception_patients: {str(e)}")
        flash(f'Error loading patients: {str(e)}', 'error')
        return redirect(url_for('reception_dashboard'))

@app.route('/reception/patient/<int:patient_id>', methods=['GET', 'POST', 'DELETE'])
@reception_login_required
def patient_details(patient_id):
    patient = User.query.get_or_404(patient_id)

    if request.method == 'DELETE':
        try:
            print(f"Deleting patient with ID: {patient_id}")

            # 1. Delete all notifications for this patient
            notifications = Notification.query.filter_by(user_id=patient_id).all()
            print(f"Deleting {len(notifications)} notifications")
            for notification in notifications:
                db.session.delete(notification)

            # 2. Delete all chat messages sent by or to this patient
            sent_messages = ChatMessage.query.filter_by(sender_id=patient_id, sender_type='user').all()
            received_messages = ChatMessage.query.filter_by(recipient_id=patient_id, recipient_type='user').all()
            print(f"Deleting {len(sent_messages)} sent messages and {len(received_messages)} received messages")

            for message in sent_messages + received_messages:
                db.session.delete(message)

            # 3. Delete all doctor reviews by this patient
            reviews = DoctorReview.query.filter_by(user_id=patient_id).all()
            print(f"Deleting {len(reviews)} doctor reviews")
            for review in reviews:
                db.session.delete(review)

            # 4. Delete all appointments for this patient
            appointments = Appointment.query.filter_by(user_id=patient_id).all()
            print(f"Deleting {len(appointments)} appointments")
            for appointment in appointments:
                db.session.delete(appointment)

            # 5. Delete all gallery uploads by this patient
            gallery_items = Gallery.query.filter_by(uploaded_by_id=patient_id, uploaded_by_type='user').all()
            print(f"Deleting {len(gallery_items)} gallery items")
            for item in gallery_items:
                # Delete the actual file if it exists
                if item.image_path and item.image_path.startswith('/'):
                    file_path = item.image_path[1:]  # Remove leading slash
                    if os.path.exists(file_path):
                        os.remove(file_path)
                db.session.delete(item)

            # 6. Finally, delete the patient
            print(f"Deleting patient: {patient.name}")
            db.session.delete(patient)

            # Commit all changes
            db.session.commit()
            print("Patient deletion successful")

            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting patient: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            # Update patient details
            patient.name = request.form.get('name', patient.name)
            patient.email = request.form.get('email', patient.email)
            patient.phone = request.form.get('phone', patient.phone)
            patient.gender = request.form.get('gender', patient.gender)

            # Handle date of birth
            dob_str = request.form.get('dob')
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    # Validate that the date of birth is in the past
                    today = datetime.now().date()
                    if dob >= today:
                        flash('Date of Birth must be in the past', 'error')
                        return redirect(url_for('reception_patients'))

                    patient.dob = dob
                    # Update age based on DOB
                    patient.age = today.year - patient.dob.year - ((today.month, today.day) < (patient.dob.month, patient.dob.day))
                except ValueError:
                    pass  # Keep existing DOB if format is invalid

            # Update optional fields
            patient.address = request.form.get('address', patient.address)
            patient.emergency_contact = request.form.get('emergency_contact', patient.emergency_contact)
            patient.allergies = request.form.get('allergies', patient.allergies)
            patient.medical_history = request.form.get('medical_history', patient.medical_history)

            db.session.commit()
            flash('Patient details updated successfully', 'success')
            return redirect(url_for('reception_patients'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating patient: {str(e)}', 'error')
            return redirect(url_for('reception_patients'))

    # GET request - return patient details
    return jsonify({
        'id': patient.id,
        'name': patient.name,
        'email': patient.email,
        'phone': patient.phone,
        'gender': patient.gender if hasattr(patient, 'gender') else '',
        'age': patient.age if hasattr(patient, 'age') else None,
        'dob': patient.dob.isoformat() if patient.dob else None,
        'address': patient.address if hasattr(patient, 'address') else '',
        'emergency_contact': patient.emergency_contact if hasattr(patient, 'emergency_contact') else '',
        'allergies': patient.allergies if hasattr(patient, 'allergies') else '',
        'medical_history': patient.medical_history if hasattr(patient, 'medical_history') else ''
    })

# Appointment management routes
@app.route('/reception/appointments')
@reception_login_required
def reception_appointments():
    try:
        # Get all appointments
        appointments = Appointment.query.order_by(Appointment.appointment_date).all()

        # Get all doctors
        doctors = Doctor.query.all()

        # Get all users/patients
        users = User.query.all()

        # Debug print
        print(f"Found {len(appointments)} appointments, {len(doctors)} doctors, {len(users)} users")

        # For each appointment, attach user and doctor objects directly
        for appointment in appointments:
            appointment.user = next((u for u in users if u.id == appointment.user_id), None)
            appointment.doctor = next((d for d in doctors if d.id == appointment.doctor_id), None)
            print(f"Appointment {appointment.id}: User={appointment.user.name if appointment.user else 'None'}, Doctor={appointment.doctor.name if appointment.doctor else 'None'}")

        return render_template('reception_appointments.html',
                              appointments=appointments,
                              doctors=doctors,
                              users=users)
    except Exception as e:
        print(f"Error in reception_appointments: {str(e)}")
        db.session.rollback()
        flash(f'Error loading appointments: {str(e)}', 'error')
        return redirect(url_for('reception_dashboard'))

@app.route('/reception/add_appointment', methods=['POST'])
@reception_login_required
def add_appointment():
    try:
        user_id = request.form.get('user_id')
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        duration = request.form.get('duration', '30')  # Default to 30 minutes
        notes = request.form.get('notes', '')
        force_book = request.form.get('force_book', 'false') == 'true'  # Check if force booking is enabled

        # Convert date string to date object
        date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()

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
                    return jsonify({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s. Next available day is {day_names[next_working_day.weekday()]} ({next_working_day.strftime('%Y-%m-%d')}).",
                        'next_working_day': next_working_day.strftime('%Y-%m-%d')
                    }), 400
                else:
                    return jsonify({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s and no upcoming working days were found."
                    }), 400

        # Check if date is today and time is in the past
        today = datetime.now().date()
        if date_obj == today:
            # Parse the appointment time
            time_format = "%I:%M %p"  # 12-hour format with AM/PM
            try:
                time_obj = datetime.strptime(appointment_time, time_format).time()
            except ValueError:
                # Try alternative format without space
                try:
                    time_obj = datetime.strptime(appointment_time, "%I:%M%p").time()
                except ValueError:
                    # Try 24-hour format
                    try:
                        time_obj = datetime.strptime(appointment_time, "%H:%M").time()
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'message': 'Invalid time format'
                        }), 400

            # Compare with current time
            now = datetime.now().time()
            if time_obj < now:
                return jsonify({
                    'success': False,
                    'message': 'Cannot schedule an appointment for a past time on the current day'
                }), 400

        # Check for conflicts if not force booking
        if not force_book:
            has_conflict, conflicting_appointment, next_available_time = check_appointment_conflict(
                doctor_id, date_obj, appointment_time, int(duration)
            )

            if has_conflict:
                # Get available time slots for this doctor on this date
                available_slots = get_available_time_slots(
                    doctor_id, date_obj, int(duration), 9, 17
                )

                if available_slots:
                    # Return JSON with conflict information and available slots
                    response = {
                        'success': False,
                        'conflict': True,
                        'message': 'The selected time slot is already booked.',
                        'available_slots': available_slots
                    }

                    # Add next available time if it exists
                    if next_available_time:
                        response['next_available'] = next_available_time

                    return jsonify(response), 409  # 409 Conflict status code
                else:
                    # If no slots available on this day, suggest next day
                    next_day = date_obj + timedelta(days=1)
                    return jsonify({
                        'success': False,
                        'conflict': True,
                        'message': f'No available time slots on {date_obj.strftime("%B %d, %Y")}. Please try {next_day.strftime("%B %d, %Y")}.',
                        'next_day': next_day.strftime('%Y-%m-%d')
                    }), 409  # 409 Conflict status code

        # Create the appointment
        new_appointment = Appointment(
            user_id=user_id,
            doctor_id=doctor_id,
            appointment_date=date_obj,
            appointment_time=appointment_time,
            status='confirmed',  # Reception-created appointments are confirmed by default
            notes=notes  # Use notes directly without adding system notes
        )

        db.session.add(new_appointment)
        db.session.commit()

        # Create notification for the patient
        doctor = Doctor.query.get(doctor_id)
        patient = User.query.get(user_id)

        notification = Notification(
            user_id=user_id,
            message=f"An appointment has been scheduled for you with Dr. {doctor.name} on {date_obj.strftime('%B %d, %Y')} at {appointment_time}.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        flash('Appointment added successfully and notification sent to patient', 'success')
        return redirect(url_for('reception_appointments'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding appointment: {str(e)}', 'error')
        return redirect(url_for('reception_appointments'))

@app.route('/reception/update_appointment_status', methods=['POST'])
@reception_login_required
def update_appointment_status():
    try:
        appointment_id = request.form.get('appointment_id')
        new_status = request.form.get('status')

        appointment = Appointment.query.get_or_404(appointment_id)
        appointment.status = new_status

        db.session.commit()

        # If the appointment is marked as completed, send thank you notifications
        if new_status == 'completed':
            # Get doctor and patient information
            doctor = Doctor.query.get(appointment.doctor_id)
            patient = User.query.get(appointment.user_id)

            if doctor and patient:
                # Create in-app notification
                notification = Notification(
                    user_id=appointment.user_id,
                    message=f"Your appointment with Dr. {doctor.name} on {appointment.appointment_date.strftime('%B %d, %Y')} has been marked as completed.",
                    created_at=datetime.now(),
                    read=False
                )
                db.session.add(notification)
                db.session.commit()

                # Send thank you email notification if patient has an email
                if patient.email:
                    email_subject = f"AURA Hospital: Thank You for Your Visit"
                    email_message = f"""
Dear {patient.name},

Thank you for visiting AURA Hospital for your appointment with Dr. {doctor.name} on {appointment.appointment_date.strftime('%B %d, %Y')}.

We hope your experience with us was satisfactory. Your health is our priority, and we're committed to providing you with the best care possible.

If you have any questions about your treatment or need any further assistance, please don't hesitate to contact us.

We would appreciate your feedback on your experience with Dr. {doctor.name}. You can rate your experience by logging into your patient portal.

We look forward to seeing you again soon.

Best regards,
AURA Hospital Team
                    """
                    send_email_notification(patient.email, email_subject, email_message)

                # SMS notifications have been removed as requested

        flash('Appointment status updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating appointment status: {str(e)}', 'error')

    return redirect(url_for('reception_appointments'))

@app.route('/api/reception/confirm_appointment', methods=['POST'])
@reception_login_required
def reception_confirm_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    time = data.get('time')
    duration_str = data.get('duration', '30')
    force_book = data.get('force_book', False)

    # Convert duration to integer
    try:
        duration = int(duration_str)
    except ValueError:
        duration = 30  # Default to 30 minutes if invalid

    # Validate inputs
    if not appointment_id or not time:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Check for conflicts if not force booking
        if not force_book:
            has_conflict, _, next_available = check_appointment_conflict(
                appointment.doctor_id,
                appointment.appointment_date,
                time,
                duration,
                exclude_appointment_id=appointment_id  # Exclude this appointment from conflict check
            )

            if has_conflict:
                # Get available time slots for this doctor on this date
                available_slots = get_available_time_slots(
                    appointment.doctor_id,
                    appointment.appointment_date,
                    duration,
                    9, 17
                )

                if available_slots:
                    # Format available slots for display
                    available_slots_str = ", ".join(available_slots[:5])
                    if len(available_slots) > 5:
                        available_slots_str += f", and {len(available_slots) - 5} more"

                    return json.dumps({
                        'success': False,
                        'message': f'The selected time slot is already booked.',
                        'conflict': True,
                        'available_slots': available_slots,
                        'next_available': next_available
                    })
                else:
                    # If no slots available on this day, suggest next day
                    next_day = appointment.appointment_date + timedelta(days=1)
                    return json.dumps({
                        'success': False,
                        'message': f'No available time slots on {appointment.appointment_date.strftime("%B %d, %Y")}. Please try {next_day.strftime("%B %d, %Y")}.',
                        'conflict': True,
                        'next_day': next_day.strftime('%Y-%m-%d')
                    })

        # Update the appointment
        appointment.appointment_time = time
        appointment.status = 'confirmed'

        db.session.commit()

        # Create notification for the patient
        doctor = Doctor.query.get(appointment.doctor_id)
        patient = User.query.get(appointment.user_id)

        # Create the notification message
        notification_message = f"Your appointment with Dr. {doctor.name} has been confirmed for {appointment.appointment_date.strftime('%B %d, %Y')} at {time}."

        # Add in-app notification
        notification = Notification(
            user_id=appointment.user_id,
            message=notification_message,
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        # Send email notification if patient has an email
        if patient and patient.email:
            email_subject = f"AURA Hospital: Appointment Confirmation"
            email_message = f"""
Dear {patient.name},

Your appointment with Dr. {doctor.name} has been confirmed.

Appointment Details:
- Date: {appointment.appointment_date.strftime('%B %d, %Y')}
- Time: {time}
- Doctor: Dr. {doctor.name} ({doctor.specialty})

Please arrive 15 minutes before your scheduled appointment time.
If you need to reschedule or cancel, please contact us as soon as possible.

Thank you for choosing AURA Hospital.

Best regards,
AURA Hospital Team
            """
            send_email_notification(patient.email, email_subject, email_message)



        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in confirm_appointment: {str(e)}")
        return json.dumps({'success': False, 'message': str(e)})

@app.route('/api/reception/reject_appointment', methods=['POST'])
@reception_login_required
def reception_reject_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')

    # Validate inputs
    if not appointment_id:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Update the appointment
        appointment.status = 'cancelled'

        db.session.commit()

        # Create notification for the patient
        doctor = Doctor.query.get(appointment.doctor_id)
        notification = Notification(
            user_id=appointment.user_id,
            message=f"Your appointment request with Dr. {doctor.name} for {appointment.appointment_date.strftime('%B %d, %Y')} has been declined. Please book another appointment.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in reject_appointment: {str(e)}")
        return json.dumps({'success': False, 'message': str(e)})

@app.route('/api/reception/complete_appointment', methods=['POST'])
@reception_login_required
def reception_complete_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')

    # Validate inputs
    if not appointment_id:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Update the appointment
        appointment.status = 'completed'

        db.session.commit()

        # Create notification for the patient
        doctor = Doctor.query.get(appointment.doctor_id)
        patient = User.query.get(appointment.user_id)

        # Create the notification message
        notification_message = f"Your appointment with Dr. {doctor.name} on {appointment.appointment_date.strftime('%B %d, %Y')} has been marked as completed."

        # Add in-app notification
        notification = Notification(
            user_id=appointment.user_id,
            message=notification_message,
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        # Send thank you email notification if patient has an email
        if patient and patient.email:
            email_subject = f"AURA Hospital: Thank You for Your Visit"
            email_message = f"""
Dear {patient.name},

Thank you for visiting AURA Hospital for your appointment with Dr. {doctor.name} on {appointment.appointment_date.strftime('%B %d, %Y')}.

We hope your experience with us was satisfactory. Your health is our priority, and we're committed to providing you with the best care possible.

If you have any questions about your treatment or need any further assistance, please don't hesitate to contact us.

We would appreciate your feedback on your experience with Dr. {doctor.name}. You can rate your experience by logging into your patient portal.

We look forward to seeing you again soon.

Best regards,
AURA Hospital Team
            """
            send_email_notification(patient.email, email_subject, email_message)

        # SMS notifications have been removed as requested

        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in complete_appointment: {str(e)}")
        return json.dumps({'success': False, 'message': str(e)})

@app.route('/api/reception/cancel_appointment', methods=['POST'])
@reception_login_required
def reception_cancel_appointment():
    if not request.is_json:
        return json.dumps({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')

    # Validate inputs
    if not appointment_id:
        return json.dumps({'success': False, 'message': 'Missing required fields'})

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return json.dumps({'success': False, 'message': 'Appointment not found'})

    try:
        # Update the appointment
        appointment.status = 'cancelled'

        db.session.commit()

        # Create notification for the patient
        doctor = Doctor.query.get(appointment.doctor_id)
        notification = Notification(
            user_id=appointment.user_id,
            message=f"Your appointment with Dr. {doctor.name} on {appointment.appointment_date.strftime('%B %d, %Y')} has been cancelled.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()

        return json.dumps({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in cancel_appointment: {str(e)}")
        return json.dumps({'success': False, 'message': str(e)})

@app.route('/api/reception/suggest_date', methods=['POST'])
@reception_login_required
def suggest_date():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        suggested_date = data.get('suggested_date')
        suggested_time = data.get('suggested_time')
        reason = data.get('reason', '')

        # Validate inputs
        if not appointment_id or not suggested_date or not suggested_time:
            return jsonify({'success': False, 'message': 'Missing required fields'})

        # Get the appointment
        appointment = Appointment.query.get(appointment_id)
        if not appointment:
            return jsonify({'success': False, 'message': 'Appointment not found'})

        # Convert string date to Date object
        date_obj = datetime.strptime(suggested_date, '%Y-%m-%d').date()

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

        # Format the date in a more readable format
        formatted_date = date_obj.strftime('%B %d, %Y')

        # Update the appointment status
        appointment.status = 'date_suggested'
        appointment.notes = f"{appointment.notes}\n[SYSTEM] Reception suggested new date/time on {datetime.now().strftime('%Y-%m-%d %H:%M')}: {formatted_date} at {suggested_time}. Reason: {reason}"

        # Create notification for the patient
        doctor = Doctor.query.get(appointment.doctor_id)

        notification = Notification(
            user_id=appointment.user_id,
            message=f"Reception has suggested a new date/time for your appointment with Dr. {doctor.name}: {formatted_date} at {suggested_time}.",
            created_at=datetime.now(),
            read=False
        )
        db.session.add(notification)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in suggest_date: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/accept_patient_suggestion', methods=['POST'])
@reception_login_required
def accept_patient_suggestion():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    data = request.get_json()
    appointment_id = data.get('appointment_id')

    print(f"Accepting patient suggestion for appointment ID: {appointment_id}")

    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        print(f"Appointment not found with ID: {appointment_id}")
        return jsonify({'success': False, 'message': 'Appointment not found'})

    # Check if the appointment is in the correct status
    if appointment.status != 'patient_suggested':
        print(f"Appointment status is not 'patient_suggested', current status: {appointment.status}")
        return jsonify({'success': False, 'message': f'Cannot accept suggestion for appointment with status: {appointment.status}'})

    try:
        # Extract the suggested date and time from notes
        notes = appointment.notes
        print(f"Appointment notes: {notes}")

        if 'Patient suggested alternative date/time on' in notes:
            # Extract the date/time information
            suggested_info = notes.split('Patient suggested alternative date/time on ')[1]

            # Handle case where there might not be a reason
            if '. Reason:' in suggested_info:
                date_time_info = suggested_info.split('. Reason:')[0]
            else:
                date_time_info = suggested_info.strip()

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

                    # Update the appointment
                    appointment.appointment_date = date_obj
                    appointment.appointment_time = time_str
                    appointment.status = 'confirmed'
                    appointment.notes = f"{appointment.notes}\n[SYSTEM] Reception accepted patient's suggested date/time on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

                    # Create notification for the patient
                    doctor = Doctor.query.get(appointment.doctor_id)
                    patient = User.query.get(appointment.user_id)

                    # Create the notification message
                    notification_message = f"Your suggested appointment time with Dr. {doctor.name} on {date_str} at {time_str} has been confirmed."

                    # Add in-app notification
                    notification = Notification(
                        user_id=appointment.user_id,
                        message=notification_message,
                        created_at=datetime.now(),
                        read=False
                    )
                    db.session.add(notification)

                    # Send email notification if patient has an email
                    if patient and patient.email:
                        email_subject = f"AURA Hospital: Appointment Confirmation"
                        email_message = f"""
Dear {patient.name},

Your suggested appointment time with Dr. {doctor.name} has been confirmed.

Appointment Details:
- Date: {date_str}
- Time: {time_str}
- Doctor: Dr. {doctor.name} ({doctor.specialty})

Please arrive 15 minutes before your scheduled appointment time.
If you need to reschedule or cancel, please contact us as soon as possible.

Thank you for choosing AURA Hospital.

Best regards,
AURA Hospital Team
                        """
                        send_email_notification(patient.email, email_subject, email_message)



                    # Commit the changes
                    db.session.commit()
                    print("Successfully accepted patient suggestion")
                    return jsonify({'success': True})

                except ValueError as e:
                    print(f"Error parsing date: {str(e)}")
                    return jsonify({'success': False, 'message': f'Error parsing date: {str(e)}'})
            else:
                error_msg = "Could not extract date and time from appointment notes"
                if date_match:
                    error_msg += f". Found date: {date_match.group(1)} but no time."
                elif time_match:
                    error_msg += f". Found time: {time_match.group(1)} but no date."
                print(error_msg)
                return jsonify({'success': False, 'message': error_msg})
        else:
            print("Could not find patient suggestion in appointment notes")
            return jsonify({'success': False, 'message': 'Could not find patient suggestion in appointment notes'})

    except Exception as e:
        db.session.rollback()
        print(f"Error in accept_patient_suggestion: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/add_walkin_appointment', methods=['POST'])
@reception_login_required
def add_walkin_appointment():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'})

    try:
        data = request.get_json()

        # Extract patient data
        patient_data = data.get('patient', {})
        name = patient_data.get('name')
        age = patient_data.get('age')
        phone = patient_data.get('phone')
        email = patient_data.get('email', '')
        address = patient_data.get('address', '')
        password = patient_data.get('password')

        # Extract appointment data
        appointment_data = data.get('appointment', {})
        doctor_id = appointment_data.get('doctor_id')
        date_str = appointment_data.get('date')
        time = appointment_data.get('time')
        duration_str = appointment_data.get('duration', '30')
        notes = appointment_data.get('notes', '')
        force_book = appointment_data.get('force_book', False)

        # Convert duration to integer
        try:
            duration = int(duration_str)
        except ValueError:
            duration = 30  # Default to 30 minutes if invalid

        # Validate required fields
        if not name or not age or not phone:
            return jsonify({'success': False, 'message': 'Missing required patient information'})

        if not doctor_id or not date_str or not time:
            return jsonify({'success': False, 'message': 'Missing required appointment information'})

        # Convert date string to date object
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

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
                    return jsonify({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s. Next available day is {day_names[next_working_day.weekday()]} ({next_working_day.strftime('%Y-%m-%d')}).",
                        'next_working_day': next_working_day.strftime('%Y-%m-%d')
                    }), 400
                else:
                    return jsonify({
                        'success': False,
                        'message': f"Dr. {doctor.name} doesn't work on {day_name}s and no upcoming working days were found."
                    }), 400

        # Check if date is today and time is in the past
        today = datetime.now().date()
        if date_obj == today:
            # Parse the appointment time
            time_format = "%I:%M %p"  # 12-hour format with AM/PM
            try:
                time_obj = datetime.strptime(time, time_format).time()
            except ValueError:
                # Try alternative format without space
                try:
                    time_obj = datetime.strptime(time, "%I:%M%p").time()
                except ValueError:
                    # Try 24-hour format
                    try:
                        time_obj = datetime.strptime(time, "%H:%M").time()
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'message': 'Invalid time format'
                        }), 400

            # Compare with current time
            now = datetime.now().time()
            if time_obj < now:
                return jsonify({
                    'success': False,
                    'message': 'Cannot schedule an appointment for a past time on the current day'
                }), 400

        # Check for conflicts if not force booking
        if not force_book:
            has_conflict, conflicting_appt, next_available = check_appointment_conflict(
                doctor_id, date_obj, time, duration
            )

            if has_conflict:
                # Get available time slots for this doctor on this date
                available_slots = get_available_time_slots(
                    doctor_id, date_obj, duration, 9, 17
                )

                if available_slots:
                    # Format available slots for display
                    available_slots_str = ", ".join(available_slots[:5])
                    if len(available_slots) > 5:
                        available_slots_str += f", and {len(available_slots) - 5} more"

                    return jsonify({
                        'success': False,
                        'message': f'The selected time slot is already booked.',
                        'conflict': True,
                        'available_slots': available_slots,
                        'next_available': next_available
                    })
                else:
                    # If no slots available on this day, suggest next day
                    next_day = date_obj + timedelta(days=1)
                    return jsonify({
                        'success': False,
                        'message': f'No available time slots on {date_obj.strftime("%B %d, %Y")}. Please try {next_day.strftime("%B %d, %Y")}.',
                        'conflict': True,
                        'next_day': next_day.strftime('%Y-%m-%d')
                    })

        # Check if patient already exists
        existing_patient = User.query.filter_by(phone=phone).first()

        if existing_patient:
            # Update existing patient info if needed
            if existing_patient.name != name:
                existing_patient.name = name
            if existing_patient.age != int(age):
                existing_patient.age = int(age)
            if email and existing_patient.email != email:
                existing_patient.email = email
            if address:
                existing_patient.address = address

            user_id = existing_patient.id
            db.session.commit()
        else:
            # Create new patient
            gender = 'Not specified'  # Default gender

            new_patient = User(
                name=name,
                age=int(age),
                gender=gender,
                phone=phone,
                email=email,
                password=password,
                address=address
            )

            db.session.add(new_patient)
            db.session.commit()
            user_id = new_patient.id

            # Create a welcome notification for the new patient with login credentials
            welcome_notification = Notification(
                user_id=user_id,
                message=f"Welcome to AURA Hospital! Your account has been created by reception. You can log in using your phone number and password: {password}",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(welcome_notification)
            db.session.commit()

        # Create the appointment
        system_notes = f"Walk-in appointment created by reception on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}."
        if notes:
            full_notes = f"{system_notes}\n\nPatient Notes: {notes}"
        else:
            full_notes = system_notes

        new_appointment = Appointment(
            user_id=user_id,
            doctor_id=doctor_id,
            appointment_date=date_obj,
            appointment_time=time,
            status='confirmed',  # Walk-in appointments are confirmed by default
            notes=full_notes
        )

        db.session.add(new_appointment)

        # Create appointment notification for the patient
        doctor = Doctor.query.get(doctor_id)
        patient = User.query.get(user_id)

        # Create the notification message
        notification_message = f"An appointment has been scheduled for you with Dr. {doctor.name} on {date_obj.strftime('%B %d, %Y')} at {time}."

        # Add in-app notification
        appointment_notification = Notification(
            user_id=user_id,
            message=notification_message,
            created_at=datetime.now(),
            read=False
        )
        db.session.add(appointment_notification)
        db.session.commit()

        # Send email notification if patient has an email
        if patient and patient.email:
            email_subject = f"AURA Hospital: Appointment Confirmation"
            email_message = f"""
Dear {patient.name},

An appointment has been scheduled for you with Dr. {doctor.name}.

Appointment Details:
- Date: {date_obj.strftime('%B %d, %Y')}
- Time: {time}
- Doctor: Dr. {doctor.name} ({doctor.specialty})

Please arrive 15 minutes before your scheduled appointment time.
If you need to reschedule or cancel, please contact us as soon as possible.

Thank you for choosing AURA Hospital.

Best regards,
AURA Hospital Team
            """
            send_email_notification(patient.email, email_subject, email_message)

        # SMS notifications have been removed as requested

        return jsonify({
            'success': True,
            'message': 'Walk-in appointment created successfully',
            'patient_id': user_id,
            'appointment_id': new_appointment.id
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error in add_walkin_appointment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/remove_past_appointments', methods=['POST'])
@reception_login_required
def remove_past_appointments():
    try:
        # Get current date
        current_date = datetime.now().date()

        # Find all appointments with dates in the past OR with cancelled status
        past_appointments = Appointment.query.filter(
            (Appointment.appointment_date < current_date) |
            (Appointment.status == 'cancelled')
        ).all()

        if not past_appointments:
            return jsonify({'success': True, 'message': 'No past or cancelled appointments found to remove', 'count': 0})

        # Count of appointments to be removed
        count = len(past_appointments)

        # Delete all past and cancelled appointments
        for appointment in past_appointments:
            db.session.delete(appointment)

        db.session.commit()
        return jsonify({'success': True, 'message': f'Successfully removed {count} past and cancelled appointments', 'count': count})

    except Exception as e:
        db.session.rollback()
        print(f"Error removing appointments: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/reception/consultation_history')
@reception_login_required
def consultation_history():
    try:
        # Get all completed appointments
        completed_appointments = Appointment.query.filter_by(status='completed').order_by(Appointment.appointment_date.desc()).all()

        # Get all doctors and patients for reference
        doctors = Doctor.query.all()
        patients = User.query.all()

        # Prepare data for display
        history_data = []
        for appointment in completed_appointments:
            patient = next((p for p in patients if p.id == appointment.user_id), None)
            doctor = next((d for d in doctors if d.id == appointment.doctor_id), None)

            if patient and doctor:
                history_data.append({
                    'id': appointment.id,
                    'patient_name': patient.name,
                    'patient_id': patient.id,
                    'doctor_name': doctor.name,
                    'doctor_id': doctor.id,
                    'date': appointment.appointment_date,
                    'formatted_date': appointment.appointment_date.strftime('%B %d, %Y'),
                    'time': appointment.appointment_time,
                    'notes': appointment.notes
                })

        return render_template('reception_history.html',
                              history_data=history_data,
                              doctors=doctors,
                              patients=patients)
    except Exception as e:
        print(f"Error in consultation_history: {str(e)}")
        flash(f'Error loading consultation history: {str(e)}', 'error')
        return redirect(url_for('reception_dashboard'))

# Chat routes for reception
@app.route('/reception/chat')
@reception_login_required
def reception_chat():
    """Route for reception staff to access the chat interface"""
    return render_template('reception_chat.html')

# Gallery routes for reception
@app.route('/reception/gallery')
@reception_login_required
def reception_gallery():
    """Route for reception staff to access the gallery interface"""
    return render_template('reception_gallery.html')

@app.route('/api/reception/gallery')
@reception_login_required
def get_reception_gallery_photos():
    try:
        filter_type = request.args.get('filter', 'all')

        # Apply filter
        if filter_type == 'pending':
            photos = Gallery.query.filter_by(approved=False).order_by(Gallery.upload_date.desc()).all()
        elif filter_type == 'approved':
            photos = Gallery.query.filter_by(approved=True).order_by(Gallery.upload_date.desc()).all()
        else:  # 'all'
            photos = Gallery.query.order_by(Gallery.upload_date.desc()).all()

        result = []
        for photo in photos:
            # Get uploader name
            uploader_name = "Unknown"
            if photo.uploaded_by_type == 'user':
                user = User.query.get(photo.uploaded_by_id)
                if user:
                    uploader_name = user.name
            elif photo.uploaded_by_type == 'reception':
                uploader_name = "Reception Staff"

            result.append({
                'id': photo.id,
                'title': photo.title,
                'description': photo.description,
                'image_path': photo.image_path,
                'uploaded_by_id': photo.uploaded_by_id,
                'uploaded_by_type': photo.uploaded_by_type,
                'uploaded_by_name': uploader_name,
                'upload_date': photo.upload_date.isoformat(),
                'approved': photo.approved
            })

        return jsonify({'success': True, 'photos': result})
    except Exception as e:
        print(f"Error getting gallery photos: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/gallery/upload', methods=['POST'])
@reception_login_required
def upload_reception_gallery_photo():
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
        unique_filename = f"gallery_reception_{timestamp}_{filename}"

        # Save the file
        upload_folder = os.path.join('static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        file_path = os.path.join(upload_folder, unique_filename)
        photo.save(file_path)

        # Create gallery entry (reception uploads are automatically approved)
        gallery_item = Gallery(
            title=title,
            description=description,
            image_path=f"/{file_path}",
            uploaded_by_id=0,  # Use 0 for reception
            uploaded_by_type='reception',
            upload_date=datetime.now(),
            approved=True,  # Reception uploads are auto-approved
            approved_by=0,
            approval_date=datetime.now()
        )

        db.session.add(gallery_item)
        db.session.commit()

        return jsonify({'success': True, 'photo_id': gallery_item.id})
    except Exception as e:
        db.session.rollback()
        print(f"Error uploading gallery photo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/gallery/approve', methods=['POST'])
@reception_login_required
def approve_gallery_photo():
    try:
        data = request.json
        photo_id = data.get('photo_id')

        if not photo_id:
            return jsonify({'success': False, 'message': 'Photo ID is required'})

        # Get the photo
        photo = Gallery.query.get(photo_id)
        if not photo:
            return jsonify({'success': False, 'message': 'Photo not found'})

        # Update the photo
        photo.approved = True
        photo.approved_by = 0  # Use 0 for reception
        photo.approval_date = datetime.now()

        # Create notification for the user if it was uploaded by a patient
        if photo.uploaded_by_type == 'user':
            notification = Notification(
                user_id=photo.uploaded_by_id,
                message=f"Your photo '{photo.title}' has been approved and is now visible in the gallery.",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error approving gallery photo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/gallery/reject', methods=['POST'])
@reception_login_required
def reject_gallery_photo():
    try:
        data = request.json
        photo_id = data.get('photo_id')

        if not photo_id:
            return jsonify({'success': False, 'message': 'Photo ID is required'})

        # Get the photo
        photo = Gallery.query.get(photo_id)
        if not photo:
            return jsonify({'success': False, 'message': 'Photo not found'})

        # Store user ID for notification
        user_id = photo.uploaded_by_id if photo.uploaded_by_type == 'user' else None
        photo_title = photo.title or 'Untitled photo'

        # Delete the photo file
        if photo.image_path and photo.image_path.startswith('/'):
            import os
            file_path = photo.image_path[1:]  # Remove leading slash
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete the photo from the database
        db.session.delete(photo)

        # Create notification for the user if it was uploaded by a patient
        if user_id:
            notification = Notification(
                user_id=user_id,
                message=f"Your photo '{photo_title}' has been rejected and removed from the gallery.",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting gallery photo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/gallery/delete', methods=['POST'])
@reception_login_required
def delete_gallery_photo():
    try:
        data = request.json
        photo_id = data.get('photo_id')

        if not photo_id:
            return jsonify({'success': False, 'message': 'Photo ID is required'})

        # Get the photo
        photo = Gallery.query.get(photo_id)
        if not photo:
            return jsonify({'success': False, 'message': 'Photo not found'})

        # Store user ID for notification
        user_id = photo.uploaded_by_id if photo.uploaded_by_type == 'user' else None
        photo_title = photo.title or 'Untitled photo'

        # Delete the photo file
        if photo.image_path and photo.image_path.startswith('/'):
            import os
            file_path = photo.image_path[1:]  # Remove leading slash
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete the photo from the database
        db.session.delete(photo)

        # Create notification for the user if it was uploaded by a patient
        if user_id:
            notification = Notification(
                user_id=user_id,
                message=f"Your photo '{photo_title}' has been removed from the gallery by reception staff.",
                created_at=datetime.now(),
                read=False
            )
            db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting gallery photo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# API endpoint to search for patients by name
@app.route('/api/reception/search_patients')
@reception_login_required
def search_patients():
    try:
        query = request.args.get('query', '')
        if not query or len(query) < 2:  # Require at least 2 characters for search
            return jsonify({'success': True, 'patients': []})

        # Search for patients with names containing the query
        patients = User.query.filter(User.name.ilike(f'%{query}%')).limit(10).all()

        # Format the results
        results = []
        for patient in patients:
            results.append({
                'id': patient.id,
                'name': patient.name,
                'phone': patient.phone,
                'email': patient.email
            })

        return jsonify({'success': True, 'patients': results})
    except Exception as e:
        print(f"Error in search_patients: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# Reception chat API endpoints
@app.route('/api/reception/chat/patients')
@reception_login_required
def get_chat_patients():
    try:
        # Get all users who have sent messages to reception
        user_ids = db.session.query(ChatMessage.sender_id).filter(
            (ChatMessage.sender_type == 'user') &
            (ChatMessage.recipient_type == 'reception')
        ).distinct().all()

        user_ids = [id[0] for id in user_ids]

        # Get user details
        patients = []
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user:
                # Get the latest message for preview
                latest_message = ChatMessage.query.filter(
                    ((ChatMessage.sender_id == user_id) & (ChatMessage.sender_type == 'user') & (ChatMessage.recipient_type == 'reception')) |
                    ((ChatMessage.sender_type == 'reception') & (ChatMessage.recipient_id == user_id) & (ChatMessage.recipient_type == 'user'))
                ).order_by(ChatMessage.timestamp.desc()).first()

                # Check for unread messages
                unread_count = ChatMessage.query.filter(
                    (ChatMessage.sender_id == user_id) &
                    (ChatMessage.sender_type == 'user') &
                    (ChatMessage.recipient_type == 'reception') &
                    (ChatMessage.read == False)
                ).count()

                patient_info = {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'phone': user.phone,
                    'unread_count': unread_count,
                    'last_message': {
                        'content': latest_message.content if latest_message else '',
                        'timestamp': latest_message.timestamp.isoformat() if latest_message else '',
                        'sender_type': latest_message.sender_type if latest_message else ''
                    }
                }
                patients.append(patient_info)

        print(f"Found {len(patients)} patients")
        return jsonify({'success': True, 'patients': patients})

    except Exception as e:
        print(f"Error getting chat patients: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/chat/messages/<int:patient_id>')
@reception_login_required
def get_patient_messages(patient_id):
    try:
        # Try to get all non-deleted messages between reception and this patient
        try:
            messages = ChatMessage.query.filter(
                (((ChatMessage.sender_id == patient_id) & (ChatMessage.sender_type == 'user') & (ChatMessage.recipient_type == 'reception')) |
                ((ChatMessage.recipient_id == patient_id) & (ChatMessage.sender_type == 'reception') & (ChatMessage.recipient_type == 'user'))) &
                (ChatMessage.is_deleted == False)  # Only get non-deleted messages
            ).order_by(ChatMessage.timestamp).all()
        except Exception as e:
            # If is_deleted column doesn't exist yet, try without it
            if "no such column: chat_message.is_deleted" in str(e):
                messages = ChatMessage.query.filter(
                    ((ChatMessage.sender_id == patient_id) & (ChatMessage.sender_type == 'user') & (ChatMessage.recipient_type == 'reception')) |
                    ((ChatMessage.recipient_id == patient_id) & (ChatMessage.sender_type == 'reception') & (ChatMessage.recipient_type == 'user'))
                ).order_by(ChatMessage.timestamp).all()
            else:
                raise e

        # Mark unread messages as read
        unread_messages = ChatMessage.query.filter(
            (ChatMessage.sender_id == patient_id) &
            (ChatMessage.sender_type == 'user') &
            (ChatMessage.recipient_type == 'reception') &
            (ChatMessage.read == False)
        ).all()

        for msg in unread_messages:
            msg.read = True

        db.session.commit()

        # Get patient info
        patient = User.query.get(patient_id)
        patient_info = None
        if patient:
            patient_info = {
                'id': patient.id,
                'name': patient.name,
                'email': patient.email,
                'phone': patient.phone
            }

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

        return jsonify({
            'success': True,
            'messages': message_list,
            'patient': patient_info
        })

    except Exception as e:
        print(f"Error getting patient messages: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/chat/send', methods=['POST'])
@reception_login_required
def send_reception_message():
    try:
        data = request.json
        patient_id = data.get('patientId')
        content = data.get('content')

        if not patient_id or not content:
            return jsonify({'success': False, 'message': 'Patient ID and content are required'})

        # Create new message
        new_message = ChatMessage(
            content=content,
            sender_type='reception',
            recipient_id=patient_id,
            recipient_type='user',
            timestamp=datetime.now(),
            read=False
        )

        db.session.add(new_message)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': {
                'id': new_message.id,
                'content': new_message.content,
                'sender_type': 'reception',
                'timestamp': new_message.timestamp.isoformat()
            }
        })

    except Exception as e:
        print(f"Error sending reception message: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/chat/delete', methods=['POST'])
@reception_login_required
def delete_message():
    try:
        data = request.json
        message_id = data.get('messageId')

        if not message_id:
            return jsonify({'success': False, 'message': 'Message ID is required'})

        # Find the message
        message = ChatMessage.query.get(message_id)
        if not message:
            return jsonify({'success': False, 'message': 'Message not found'})

        # Check if the message is related to reception (either sent by or to reception)
        if not ((message.sender_type == 'reception') or (message.recipient_type == 'reception')):
            return jsonify({'success': False, 'message': 'Unauthorized to delete this message'})

        # Soft delete the message
        try:
            message.is_deleted = True
            message.deleted_by = 'reception'
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
        print(f"Error deleting message: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reception/chat/new/<int:patient_id>')
@reception_login_required
def check_new_patient_messages(patient_id):
    try:
        since = request.args.get('since', '0')

        # Convert since to datetime
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            # If invalid timestamp, use a time far in the past
            since_time = datetime.now() - timedelta(days=1)

        # Try to get new non-deleted messages from this patient to reception
        try:
            messages = ChatMessage.query.filter(
                (ChatMessage.sender_id == patient_id) &
                (ChatMessage.sender_type == 'user') &
                (ChatMessage.recipient_type == 'reception') &
                (ChatMessage.timestamp > since_time) &
                (ChatMessage.is_deleted == False)  # Only get non-deleted messages
            ).order_by(ChatMessage.timestamp).all()
        except Exception as e:
            # If is_deleted column doesn't exist yet, try without it
            if "no such column: chat_message.is_deleted" in str(e):
                messages = ChatMessage.query.filter(
                    (ChatMessage.sender_id == patient_id) &
                    (ChatMessage.sender_type == 'user') &
                    (ChatMessage.recipient_type == 'reception') &
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
        print(f"Error checking new patient messages: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables exist
        # ChatMessage table will be created by db.create_all()
    app.run(debug=True, port=5001)  # Use a different port than the main app




































































