from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import uuid
import secrets
from datetime import datetime, timedelta
from functools import wraps

from backend import db, User, Doctor, Appointment, Notification, ChatMessage, DoctorReview, send_email_notification  # Use the shared db instance

# Create the Flask app
app = Flask(__name__)
app.secret_key = 'client_secret.json'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)  # Correctly bind the shared db instance to this app

# Model for admin login verification
class AdminLoginVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)
    expires_at = db.Column(db.DateTime)
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    is_used = db.Column(db.Boolean, default=False)

    def is_valid(self):
        """Check if the token is valid (not expired, not used, and approved)"""
        now = datetime.now()
        return (not self.is_used and
                self.is_approved and
                not self.is_rejected and
                self.expires_at > now)

# Admin credentials (hardcoded for security)
ADMIN_USERNAME = "arun"
ADMIN_PASSWORD = "arun@159"
ADMIN_NOTIFICATION_EMAIL = "arunthomas7072@gmail.com"


# Login required decorator
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if admin is logged in
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Route for waiting page - No longer needed but kept for backward compatibility
@app.route('/admin/verification/waiting')
def admin_verification_waiting():
    # Redirect to login page
    return redirect(url_for('admin_login'))

# Routes
@app.route('/')
def admin_index():
    return redirect(url_for('admin_login'))

# Debug route to get the latest verification token
@app.route('/admin/debug/latest-token')
def admin_debug_latest_token():
    # Get the latest verification token
    latest_verification = AdminLoginVerification.query.order_by(AdminLoginVerification.created_at.desc()).first()

    if latest_verification:
        # Create approval and rejection URLs
        base_url = request.host_url.rstrip('/')
        approve_url = f"{base_url}/admin/verify/{latest_verification.token}/approve"
        reject_url = f"{base_url}/admin/verify/{latest_verification.token}/reject"

        # Return the URLs
        return f"""
        <h1>Latest Verification Token</h1>
        <p>Token: {latest_verification.token}</p>
        <p>Created at: {latest_verification.created_at}</p>
        <p>Expires at: {latest_verification.expires_at}</p>
        <p>IP Address: {latest_verification.ip_address}</p>
        <p>User Agent: {latest_verification.user_agent}</p>
        <p>Is Approved: {latest_verification.is_approved}</p>
        <p>Is Rejected: {latest_verification.is_rejected}</p>
        <p>Is Used: {latest_verification.is_used}</p>
        <h2>Approval URL</h2>
        <p><a href="{approve_url}">{approve_url}</a></p>
        <h2>Rejection URL</h2>
        <p><a href="{reject_url}">{reject_url}</a></p>
        """
    else:
        return "<h1>No verification tokens found</h1>"





@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Set admin as logged in directly
            session['admin_logged_in'] = True

            # Get login details for notification
            login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Send notification email
            try:
                email_subject = "AURA Hospital: Admin Login Alert"
                email_message = f"""
Admin Login Alert

Someone has logged into the admin account at {login_time}.

Details:
- Username: {username}
- IP Address: {request.remote_addr}
- Browser: {request.user_agent.browser}
- Platform: {request.user_agent.platform}

If this was not you, please secure your account immediately.

AURA Hospital Security Team
                """
                send_email_notification(ADMIN_NOTIFICATION_EMAIL, email_subject, email_message)

                # We've removed SMS notifications as requested

                print(f"\n--- ADMIN LOGIN SUCCESSFUL ---")
                print(f"Username: {username}")
                print(f"IP Address: {request.remote_addr}")
                print(f"Browser: {request.user_agent.browser}")
                print(f"Platform: {request.user_agent.platform}")
                print(f"Time: {login_time}")
                print(f"Notification email sent to: {ADMIN_NOTIFICATION_EMAIL}")
                print(f"--- END ADMIN LOGIN ---\n")

                # Redirect to admin dashboard
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                print(f"Failed to send admin login notification: {str(e)}")
                # Continue with login even if notification fails
                return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid credentials. Please try again.'

    return render_template('admin_login.html', error=error)

# This route is no longer needed but kept for backward compatibility
@app.route('/admin/verify/<token>/<action>')
def verify_admin_login(token, action):
    # Just redirect to login page
    return redirect(url_for('admin_login'))

# This route is no longer needed but kept for backward compatibility
@app.route('/admin/verify/check')
def check_verification():
    # Just return a redirect to the dashboard
    return jsonify({'status': 'approved', 'redirect': url_for('admin_dashboard')})

@app.route('/admin/logout')
def admin_logout():
    # Clear admin session
    session.pop('admin_logged_in', None)

    # Log the logout
    print(f"\n--- ADMIN LOGOUT ---")
    print(f"IP Address: {request.remote_addr}")
    print(f"Browser: {request.user_agent.browser}")
    print(f"Platform: {request.user_agent.platform}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"--- END ADMIN LOGOUT ---\n")

    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    try:
        # Get current date for display
        now = datetime.now()

        # Get counts for dashboard
        patient_count = User.query.count()
        doctor_count = Doctor.query.count()
        appointment_count = Appointment.query.count()

        # Get recent patients
        recent_patients = User.query.order_by(User.id.desc()).limit(5).all()

        # Get recent doctors
        recent_doctors = Doctor.query.order_by(Doctor.id.desc()).limit(5).all()

        return render_template('admin_dashboard.html',
                              now=now,
                              patient_count=patient_count,
                              doctor_count=doctor_count,
                              appointment_count=appointment_count,
                              recent_patients=recent_patients,
                              recent_doctors=recent_doctors)
    except Exception as e:
        print(f"Error in admin_dashboard: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('admin_dashboard.html', now=datetime.now())

@app.route('/admin/patients')
@admin_login_required
def admin_patients():
    try:
        patients = User.query.all()
        return render_template('admin_patients.html', patients=patients)
    except Exception as e:
        print(f"Error in admin_patients: {str(e)}")
        flash(f'Error loading patients: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/doctors')
@admin_login_required
def admin_doctors():
    try:
        doctors = Doctor.query.all()
        return render_template('admin_doctors.html', doctors=doctors)
    except Exception as e:
        print(f"Error in admin_doctors: {str(e)}")
        flash(f'Error loading doctors: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/doctor/<int:doctor_id>')
@admin_login_required
def doctor_details(doctor_id):
    try:
        doctor = Doctor.query.get_or_404(doctor_id)
        appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()

        # Get patient names for each appointment
        for appointment in appointments:
            patient = User.query.get(appointment.user_id)
            appointment.patient_name = patient.name if patient else "Unknown"

        # Get doctor reviews
        reviews = DoctorReview.query.filter_by(doctor_id=doctor_id).all()
        for review in reviews:
            patient = User.query.get(review.user_id)
            review.patient_name = patient.name if patient else "Unknown"

        return render_template('admin_doctor_details.html', doctor=doctor, appointments=appointments, reviews=reviews)
    except Exception as e:
        print(f"Error in doctor_details: {str(e)}")
        flash(f'Error loading doctor details: {str(e)}', 'error')
        return redirect(url_for('admin_doctors'))

@app.route('/api/admin/search_patients')
@admin_login_required
def search_patients():
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify({'patients': []})

        # Search for patients with names containing the query
        patients = User.query.filter(User.name.ilike(f'%{query}%')).all()

        # Format the results
        results = []
        for patient in patients:
            results.append({
                'id': patient.id,
                'name': patient.name,
                'phone': patient.phone,
                'email': patient.email
            })

        return jsonify({'patients': results})
    except Exception as e:
        print(f"Error in search_patients: {str(e)}")
        return jsonify({'patients': [], 'error': str(e)})

@app.route('/api/admin/search_doctors')
@admin_login_required
def search_doctors():
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify({'doctors': []})

        # Search for doctors with names containing the query
        doctors = Doctor.query.filter(Doctor.name.ilike(f'%{query}%')).all()

        # Format the results
        results = []
        for doctor in doctors:
            # Handle cases where some fields might be None
            phone = doctor.phone if hasattr(doctor, 'phone') and doctor.phone else "Not provided"
            email = doctor.email if hasattr(doctor, 'email') and doctor.email else "Not provided"
            specialty = doctor.specialty if doctor.specialty else "General"

            results.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialty': specialty,
                'phone': phone,
                'email': email
            })

        return jsonify({'doctors': results})
    except Exception as e:
        print(f"Error in search_doctors: {str(e)}")
        return jsonify({'doctors': [], 'error': str(e)})

@app.route('/admin/patient/<int:patient_id>')
@admin_login_required
def patient_details(patient_id):
    try:
        patient = User.query.get_or_404(patient_id)
        appointments = Appointment.query.filter_by(user_id=patient_id).all()

        # Get doctor names for each appointment
        for appointment in appointments:
            doctor = Doctor.query.get(appointment.doctor_id)
            appointment.doctor_name = doctor.name if doctor else "Unknown"

        return render_template('admin_patient_details.html', patient=patient, appointments=appointments)
    except Exception as e:
        print(f"Error in patient_details: {str(e)}")
        flash(f'Error loading patient details: {str(e)}', 'error')
        return redirect(url_for('admin_patients'))

@app.route('/admin/edit/patient/<int:patient_id>', methods=['GET', 'POST'])
@admin_login_required
def edit_patient(patient_id):
    try:
        patient = User.query.get_or_404(patient_id)

        if request.method == 'POST':
            if 'confirm' in request.form:
                # Get form data
                patient.name = request.form.get('name')
                patient.email = request.form.get('email')
                patient.phone = request.form.get('phone')
                patient.gender = request.form.get('gender')
                patient.age = request.form.get('age')
                patient.address = request.form.get('address')
                patient.password = request.form.get('password')

                # Save changes to database
                db.session.commit()

                flash('Patient information updated successfully', 'success')
                return redirect(url_for('patient_details', patient_id=patient.id))
            elif 'preview' in request.form:
                # Create a temporary patient object with the new data
                preview_patient = {
                    'id': patient.id,
                    'name': request.form.get('name'),
                    'email': request.form.get('email'),
                    'phone': request.form.get('phone'),
                    'gender': request.form.get('gender'),
                    'age': request.form.get('age'),
                    'address': request.form.get('address'),
                    'password': request.form.get('password')
                }

                # Show confirmation page
                return render_template('admin_confirm_edit.html',
                                      original=patient,
                                      preview=preview_patient,
                                      edit_type='patient')

        return render_template('admin_edit_patient.html', patient=patient)
    except Exception as e:
        print(f"Error in edit_patient: {str(e)}")
        flash(f'Error editing patient: {str(e)}', 'error')
        return redirect(url_for('patient_details', patient_id=patient_id))

@app.route('/admin/edit/doctor/<int:doctor_id>', methods=['GET', 'POST'])
@admin_login_required
def edit_doctor(doctor_id):
    try:
        doctor = Doctor.query.get_or_404(doctor_id)

        if request.method == 'POST':
            if 'confirm' in request.form:
                # Get form data
                doctor.name = request.form.get('name')
                doctor.email = request.form.get('email')
                doctor.phone = request.form.get('phone')
                doctor.specialty = request.form.get('specialty')
                doctor.qualification = request.form.get('qualification')
                doctor.experience = request.form.get('experience')
                doctor.available_days = request.form.get('available_days')
                doctor.fee = request.form.get('fee')

                # Save changes to database
                db.session.commit()

                flash('Doctor information updated successfully', 'success')
                return redirect(url_for('doctor_details', doctor_id=doctor.id))
            elif 'preview' in request.form:
                # Create a temporary doctor object with the new data
                preview_doctor = {
                    'id': doctor.id,
                    'name': request.form.get('name'),
                    'email': request.form.get('email'),
                    'phone': request.form.get('phone'),
                    'specialty': request.form.get('specialty'),
                    'qualification': request.form.get('qualification'),
                    'experience': request.form.get('experience'),
                    'available_days': request.form.get('available_days'),
                    'fee': request.form.get('fee')
                }

                # Show confirmation page
                return render_template('admin_confirm_edit.html',
                                      original=doctor,
                                      preview=preview_doctor,
                                      edit_type='doctor')

        return render_template('admin_edit_doctor.html', doctor=doctor)
    except Exception as e:
        print(f"Error in edit_doctor: {str(e)}")
        flash(f'Error editing doctor: {str(e)}', 'error')
        return redirect(url_for('doctor_details', doctor_id=doctor_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables exist
    app.run(debug=True, port=5002)  # Use a different port than the main app and reception
