import os
import sys

# Add the current directory to the path so Python can find the backend module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend import app, db
except ImportError as e:
    print(f"Error importing backend app: {str(e)}")
    print("Make sure backend.py is in the same directory.")
    sys.exit(1)

if __name__ == "__main__":
    try:
        print("Starting AURA Hospital Management System on http://0.0.0.0:5000")

        # Create all tables before running the app
        with app.app_context():
            db.create_all()
            print("Database tables created successfully.")

        # Run the app with host=0.0.0.0 to make it accessible from other devices
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error starting the application: {str(e)}")
        import traceback
        traceback.print_exc()
