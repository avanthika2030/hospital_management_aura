<<<<<<< HEAD
# AURA Hospital Management System

A comprehensive hospital management system with patient, reception, and admin portals.

## System Requirements

- Python 3.6 or higher
- Flask and other dependencies (see requirements below)
- Modern web browser (Chrome, Firefox, Edge recommended)

## Quick Start

### Windows Users
1. Double-click the `start_hospital_system.bat` file
2. The system will start all three portals and open them in your browser

### Manual Start
Run the following command to start all three portals at once:
```
python run_all.py
```




## Individual Servers

If you prefer to run the servers individually:

- Patient Portal: `python run.py`
- Reception Portal: `python run_reception.py`
- Admin Portal: `python run_admin.py`



## Core Files

- `backend.py` - Main backend for patient functionality
- `reception.py` - Reception portal functionality
- `admin.py` - Admin panel functionality
- `run.py`, `run_reception.py`, `run_admin.py` - Individual runner scripts
- `run_all.py` - Combined runner script for all portals
- `database.db` - SQLite database file
- `client_secret.json` - The credentials file obtained from GCP for your registered gmail account.
- `gmail_token.json` - The file automatically generated after you grant your application permission to access Google services.

## Features

- Patient registration and login
- Appointment scheduling and management
- Doctor profiles and ratings
- Patient-doctor chat system
- Photo gallery with approval system
- Email notifications
- Admin dashboard for system management

## Troubleshooting

If you encounter any issues:

1. Make sure all required Python packages are installed
2. Check that ports 5000, 5001, and 5002 are not in use by other applications
3. Verify that the database file exists and is not corrupted
4. For email issues, confirm your app password is correctly configured

## Required
Please make sure to obtain the client_secret.json file and the adjoining gmail_token.json file for your company's gmail account with GCP to ensure proper working of the Gmail functionalities.

## License

This project is proprietary and confidential.
Copyright © 2025 AURA Dental Hospital. All rights reserved.
=======
