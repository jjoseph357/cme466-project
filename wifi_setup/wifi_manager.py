import subprocess
import time

def is_connected():
    try:
        # Try to ping Google DNS
        subprocess.check_output(["ping", "-c", "1", "8.8.8.8"])
        return True
    except:
        return False

def start_hotspot():
    print("Starting Hotspot...")
    # Create the hotspot using NetworkManager
    subprocess.run(["nmcli", "device", "wifi", "hotspot", "ssid", "setup-pi", "password", "raspberrypi"])

if __name__ == "__main__":
    time.sleep(10) # Give the system time to try auto-connecting first
    if not is_connected():
        start_hotspot()
        # Start the Flask app
        subprocess.run(["python3", "app.py"])
    else:
        print("Connected to WiFi. No setup needed.")
