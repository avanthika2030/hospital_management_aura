import os
import sys
import threading
import time
import webbrowser
from datetime import datetime

# Import the Flask apps
try:
    from backend import app as patient_app
    from reception import app as reception_app
    from admin import app as admin_app
    print("Successfully imported all Flask applications")
except ImportError as e:
    print(f"Error importing Flask applications: {e}")
    sys.exit(1)

# Configuration
PATIENT_PORT = 5000
RECEPTION_PORT = 5001
ADMIN_PORT = 5002

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log(message, color=Colors.ENDC):
    """Print a formatted log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {message}{Colors.ENDC}")

def run_patient_server():
    """Run the patient portal server"""
    log("Starting Patient Portal on http://127.0.0.1:5000", Colors.GREEN)
    patient_app.run(host='0.0.0.0', port=PATIENT_PORT, debug=True, use_reloader=False)

def run_reception_server():
    """Run the reception portal server"""
    log("Starting Reception Portal on http://127.0.0.1:5001", Colors.BLUE)
    reception_app.run(host='0.0.0.0', port=RECEPTION_PORT, debug=True, use_reloader=False)

def run_admin_server():
    """Run the admin portal server"""
    log("Starting Admin Portal on http://127.0.0.1:5002", Colors.YELLOW)
    admin_app.run(host='0.0.0.0', port=ADMIN_PORT, debug=True, use_reloader=False)

def open_browser_tabs():
    """Open browser tabs for all portals after a short delay"""
    time.sleep(3)  # Wait for servers to start
    log("Opening browser tabs for all portals...", Colors.CYAN)
    
    # Open patient portal
    webbrowser.open(f"http://127.0.0.1:{PATIENT_PORT}")
    time.sleep(1)  # Small delay between tabs
    
    # Open reception portal
    webbrowser.open(f"http://127.0.0.1:{RECEPTION_PORT}/reception/login")
    time.sleep(1)  # Small delay between tabs
    
    # Open admin portal
    webbrowser.open(f"http://127.0.0.1:{ADMIN_PORT}/admin/login")

def main():
    """Main function to start all servers"""
    # Clear the terminal
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Print welcome message
    print(f"{Colors.BOLD}{Colors.HEADER}=" * 70)
    print(f"AURA HOSPITAL MANAGEMENT SYSTEM - ALL SERVERS")
    print("=" * 70)
    print(f"{Colors.ENDC}")
    
    log("Initializing all servers...", Colors.BOLD)
    
    # Create threads for each server
    patient_thread = threading.Thread(target=run_patient_server)
    reception_thread = threading.Thread(target=run_reception_server)
    admin_thread = threading.Thread(target=run_admin_server)
    browser_thread = threading.Thread(target=open_browser_tabs)
    
    # Set threads as daemon so they exit when the main program exits
    patient_thread.daemon = True
    reception_thread.daemon = True
    admin_thread.daemon = True
    browser_thread.daemon = True
    
    # Start all threads
    patient_thread.start()
    log("Patient server thread started", Colors.GREEN)
    
    reception_thread.start()
    log("Reception server thread started", Colors.BLUE)
    
    admin_thread.start()
    log("Admin server thread started", Colors.YELLOW)
    
    browser_thread.start()
    log("Browser opener thread started", Colors.CYAN)
    
    # Print access information
    print(f"\n{Colors.BOLD}Access Information:{Colors.ENDC}")
    print(f"{Colors.GREEN}Patient Portal: http://127.0.0.1:{PATIENT_PORT}{Colors.ENDC}")
    print(f"{Colors.BLUE}Reception Portal: http://127.0.0.1:{RECEPTION_PORT}/reception/login{Colors.ENDC}")
    print(f"  - Username: aura")
    print(f"  - Password: aura@123")
    print(f"{Colors.YELLOW}Admin Portal: http://127.0.0.1:{ADMIN_PORT}/admin/login{Colors.ENDC}")
    print(f"  - Username: arun")
    print(f"  - Password: arun@159")
    
    print(f"\n{Colors.BOLD}Press Ctrl+C to stop all servers{Colors.ENDC}")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Shutting down all servers...", Colors.RED)
        print(f"{Colors.BOLD}{Colors.HEADER}=" * 70)
        print("AURA HOSPITAL MANAGEMENT SYSTEM - SHUTDOWN COMPLETE")
        print("=" * 70)
        print(f"{Colors.ENDC}")
        sys.exit(0)

if __name__ == "__main__":
    main()
