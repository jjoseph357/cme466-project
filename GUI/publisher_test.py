import paho.mqtt.client as mqtt
import time

# --- Configuration ---
BROKER_ADDRESS = "test.mosquitto.org" 
TOPIC = "sensor/posture"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT Broker at {BROKER_ADDRESS}")
    else:
        print(f"Failed to connect, return code {rc}\n")

# Setup the MQTT client
client = mqtt.Client()
client.on_connect = on_connect

try:
    client.connect(BROKER_ADDRESS, 1883, 60)
    client.loop_start()  # Start the background thread
    
    print("\n--- Posture Sensor Simulator ---")
    print("Commands:")
    print("  [s] - Simulate STAGNANT posture")
    print("  [m] - Simulate MOVING posture")
    print("  [q] - Quit simulator")
    print("--------------------------------\n")

    while True:
        command = input("Enter command (s/m/q): ").strip().lower()
        
        if command == 's':
            print(f"Publishing: STAGNANT to {TOPIC}")
            client.publish(TOPIC, "STAGNANT")
        elif command == 'm':
            print(f"Publishing: MOVING to {TOPIC}")
            client.publish(TOPIC, "MOVING")
        elif command == 'q':
            print("Disconnecting...")
            break
        else:
            print("Invalid command. Use 's', 'm', or 'q'.")
            
        time.sleep(0.1) # Small delay to prevent terminal input glitching

except ConnectionRefusedError:
    print(f"Error: Could not connect to broker at {BROKER_ADDRESS}.")
    print("Make sure your MQTT broker (like Mosquitto) is running locally.")
except KeyboardInterrupt:
    print("\nSimulator stopped by user.")
finally:
    client.loop_stop()
    client.disconnect()