from backend import app, db, User
from datetime import datetime, timedelta

def add_sample_patients():
    """
    Add sample patients to the database for testing
    """
    print("Adding sample patients to the database...")
    
    with app.app_context():
        # Check if patients already exist
        existing_count = User.query.count()
        if existing_count > 0:
            print(f"Database already has {existing_count} patients. Skipping sample data creation.")
            return
        
        # Sample patients data
        sample_patients = [
            {
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'phone': '9876543201',
                'password': 'John@98',
                'gender': 'Male',
                'age': 35,
                'address': '123 Main St, Anytown, USA',
                'dob': datetime.now() - timedelta(days=35*365)
            },
            {
                'name': 'Jane Smith',
                'email': 'jane.smith@example.com',
                'phone': '9876543202',
                'password': 'Jane@95',
                'gender': 'Female',
                'age': 28,
                'address': '456 Oak Ave, Somewhere, USA',
                'dob': datetime.now() - timedelta(days=28*365)
            },
            {
                'name': 'Robert Johnson',
                'email': 'robert.johnson@example.com',
                'phone': '9876543203',
                'password': 'Robert@85',
                'gender': 'Male',
                'age': 42,
                'address': '789 Pine Rd, Nowhere, USA',
                'dob': datetime.now() - timedelta(days=42*365)
            },
            {
                'name': 'Emily Davis',
                'email': 'emily.davis@example.com',
                'phone': '9876543204',
                'password': 'Emily@90',
                'gender': 'Female',
                'age': 31,
                'address': '321 Elm St, Anyplace, USA',
                'dob': datetime.now() - timedelta(days=31*365)
            },
            {
                'name': 'Michael Wilson',
                'email': 'michael.wilson@example.com',
                'phone': '9876543205',
                'password': 'Michael@88',
                'gender': 'Male',
                'age': 45,
                'address': '654 Maple Dr, Somewhere, USA',
                'dob': datetime.now() - timedelta(days=45*365)
            }
        ]
        
        # Add patients to the database
        for patient_data in sample_patients:
            patient = User(**patient_data)
            db.session.add(patient)
        
        # Commit the changes
        db.session.commit()
        print(f"Added {len(sample_patients)} sample patients to the database.")

if __name__ == "__main__":
    add_sample_patients()
    print("Sample data creation completed.")
