from admin import app, db, AdminLoginVerification

if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        print("Database tables created/verified")

    print("Starting AURA Hospital Admin Portal on http://0.0.0.0:5002")
    print("Use username: arun and password: arun@159 to login")
    print("A notification email will be sent to arunthomas7072@gmail.com when someone logs in")
    app.run(debug=True, host='0.0.0.0', port=5002)  # Use a different port than the main app and reception
