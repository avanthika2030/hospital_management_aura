from reception import app

if __name__ == "__main__":
    print("Starting AURA Reception Portal on http://0.0.0.0:5001")
    print("Use username: aura and password: aura@123 to login")
    app.run(debug=True, host='0.0.0.0', port=5001)



