import paho.mqtt.client as mqtt
import time

# --- Configuration ---
BROKER_ADDRESS = "test.mosquitto.org" 
TOPIC = "sensor/posture"

# Updated to use the new API v2 signature (reason_code and properties)
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT Broker at {BROKER_ADDRESS}")
    else:
        print(f"Failed to connect, return code {reason_code}\n")

# Setup the MQTT client explicitly using API v2
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect

try:
    client.connect(BROKER_ADDRESS, 1883, 60)
    client.loop_start()  # Start the background thread
    
    print("\n--- Posture Sensor Simulator ---")
    print("Commands:")
    print("  [g] - Simulate GOOD posture")
    print("  [b] - Simulate BAD posture")
    print("  [s] - Simulate STAGNANT state")
    print("  [m] - Simulate MOVING state")
    print("  [a] - Simulate ABSENT state")
    print("  [q] - Quit simulator")
    print("--------------------------------\n")

    while True:
        command = input("Enter command (g/b/s/m/a/q): ").strip().lower()
        
        if command == 'g':
            print(f"Publishing: GOOD POSTURE (G) to {TOPIC}")
            client.publish(TOPIC, "G")
        elif command == 'b':
            print(f"Publishing: BAD POSTURE (B) to {TOPIC}")
            client.publish(TOPIC, "B")
        elif command == 's':
            print(f"Publishing: STAGNANT (S) to {TOPIC}")
            client.publish(TOPIC, "S")
        elif command == 'm':
            print(f"Publishing: MOVING (M) to {TOPIC}")
            client.publish(TOPIC, "M")
        elif command == 'a':
            print(f"Publishing: ABSENT (A) to {TOPIC}")
            client.publish(TOPIC, "A")
        elif command == 'q':
            print("Disconnecting...")
            break
        else:
            print("Invalid command. Use 'g', 'b', 's', 'm', 'a', or 'q'.")
            
        time.sleep(0.1) # Small delay to prevent terminal input glitching

except ConnectionRefusedError:
    print(f"Error: Could not connect to broker at {BROKER_ADDRESS}.")
    print("Make sure your MQTT broker is running or accessible.")
except KeyboardInterrupt:
    print("\nSimulator stopped by user.")
finally:
    client.loop_stop()
    client.disconnect()