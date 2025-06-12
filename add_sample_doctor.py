from backend import app, db, Doctor

def add_sample_doctors():
    """
    Add sample doctors to the database for testing
    """
    print("Adding sample doctors to the database...")
    
    with app.app_context():
        # Check if doctors already exist
        existing_count = Doctor.query.count()
        if existing_count > 0:
            print(f"Database already has {existing_count} doctors. Skipping sample data creation.")
            return
        
        # Sample doctors data
        sample_doctors = [
            {
                'name': 'John Smith',
                'specialty': 'Cardiology',
                'description': 'Experienced cardiologist with over 15 years of practice.',
                'qualification': 'MD, FACC',
                'experience': 15,
                'phone': '9876543210',
                'email': 'john.smith@aurahospital.com',
                'fee': 1500,
                'available_days': 'Monday, Wednesday, Friday'
            },
            {
                'name': 'Sarah Johnson',
                'specialty': 'Pediatrics',
                'description': 'Caring pediatrician specializing in newborn care.',
                'qualification': 'MD, FAAP',
                'experience': 10,
                'phone': '9876543211',
                'email': 'sarah.johnson@aurahospital.com',
                'fee': 1200,
                'available_days': 'Tuesday, Thursday, Saturday'
            },
            {
                'name': 'Michael Chen',
                'specialty': 'Orthopedics',
                'description': 'Orthopedic surgeon specializing in sports injuries.',
                'qualification': 'MD, FAAOS',
                'experience': 12,
                'phone': '9876543212',
                'email': 'michael.chen@aurahospital.com',
                'fee': 1800,
                'available_days': 'Monday, Tuesday, Thursday'
            },
            {
                'name': 'Emily Davis',
                'specialty': 'Dermatology',
                'description': 'Board-certified dermatologist with expertise in skin cancer treatment.',
                'qualification': 'MD, FAAD',
                'experience': 8,
                'phone': '9876543213',
                'email': 'emily.davis@aurahospital.com',
                'fee': 1600,
                'available_days': 'Wednesday, Friday, Saturday'
            },
            {
                'name': 'Robert Wilson',
                'specialty': 'Neurology',
                'description': 'Neurologist specializing in headache disorders and stroke management.',
                'qualification': 'MD, PhD',
                'experience': 20,
                'phone': '9876543214',
                'email': 'robert.wilson@aurahospital.com',
                'fee': 2000,
                'available_days': 'Monday, Wednesday, Friday'
            }
        ]
        
        # Add doctors to the database
        for doctor_data in sample_doctors:
            doctor = Doctor(**doctor_data)
            db.session.add(doctor)
        
        # Commit the changes
        db.session.commit()
        print(f"Added {len(sample_doctors)} sample doctors to the database.")

if __name__ == "__main__":
    add_sample_doctors()
    print("Sample data creation completed.")
