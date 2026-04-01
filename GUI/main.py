import sys
import cv2
import numpy as np
import paho.mqtt.client as mqtt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QDesktopWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtMultimedia import QSound
from PyQt5 import uic
import signal
import os
import warnings
import json
import base64


# Suppress the internal PyQt5/SIP deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Thread-Safe Signals 
class MqttSignals(QObject):
    # Unified signal to handle incoming commands
    data_signal = pyqtSignal(dict) 

# The Notification Widget
class NotificationWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.80) 

        self.setStyleSheet("""
            background-color: #7a7a7a; 
            color: #ffffff; 
            border: none;
            border-radius: 8px;
        """)
        
        layout = QVBoxLayout()
        message = QLabel("Time to shift your posture \nand give your eyes a break!")
        message.setStyleSheet("font-size: 14pt; padding: 15px;")
        layout.addWidget(message)
        self.setLayout(layout)
        
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.hide)

    def show_notification(self):
        self.adjustSize()
        screen = QDesktopWidget().availableGeometry()
        
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 80 
        
        self.move(x, y)
        self.show()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        audio_path = os.path.join(script_dir, "alert.wav")
        QSound.play(audio_path) 
        
        self.hide_timer.start(6000)

# The Main Window Application 
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Get the absolute path of the directory where main.py lives
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(script_dir, "posture_gui.ui")

        try:
            uic.loadUi(ui_path, self)
        except FileNotFoundError:
            print(f"Error: Could not find '{ui_path}'.")
            sys.exit(1)

        self.status_label.setText("UI Loaded Successfully! Starting systems...")
        self.notifier = NotificationWidget()
        
        # Initialize MQTT first so the slider can publish its initial value
        self.setup_mqtt()
        self.setup_logic()

    def setup_logic(self):
        """Wires up timers, signals, and state variables."""
        # State Variables
        self.work_seconds = 0
        self.is_absent = False
        # Variables for Stats
        self.total_alarms = 0
        self.stop_alarm = False
        self.good_seconds = 0
        self.bad_seconds = 0
        self.session_score = 0.0
        
        self.current_label = "No posture detected"
        self.display_status = "Absent"
        self.current_confidence = 0.0
        self.current_hold_time = 0.0

        self.video_label.setMinimumSize(1, 1)
        self.video_label.setScaledContents(False)
        
        # Setup thread-safe signals
        self.mqtt_signals = MqttSignals()
        self.mqtt_signals.data_signal.connect(self.handle_sensor_data)

        # Connect Slider to update logic and publish to RPi5
        if not hasattr(self, 'interval_slider'):
            print("Warning: Slider not found. Please add 'interval_slider' in Qt Designer.")
        else:
            self.interval_slider.valueChanged.connect(self.publish_interval)
            self.publish_interval() # Publish the default value on startup

        # Setup Work Duration Timer (Ticks exactly once per second)
        self.work_timer = QTimer()
        self.work_timer.timeout.connect(self.update_work_time)
        self.work_timer.start(1000)

    def publish_interval(self):
        """Updates the label and publishes the slider value to the edge sensor."""
        minutes = self.interval_slider.value()
        self.interval_label.setText(f"Notification Interval: {minutes} minutes")
        
        # Publish to the RPi5 so it knows how long to wait
        # QoS 1 and Retain=True ensures the RPi5 gets it even if it connects a second later
        if hasattr(self, 'client'):
            self.client.publish("posture/timer", str(minutes), qos=1, retain=True)
            print(f"GUI: Published new timer interval ({minutes}) to 'posture/timer'")

    def update_stats_display(self):
        # Builds a single string of all stats and updates the one label
        if hasattr(self, 'current_status_label'):
            stats_text = (
                f"Status: {self.display_status}  |  "
                f"Confidence: {self.current_confidence:.1f}%  |  "
                f"Hold Time: {self.current_hold_time:.1f}s  |  "
                f"Alarms: {self.total_alarms}  |  "
                f"Session Health: {self.session_score:.1f}%"
            )
            self.current_status_label.setText(stats_text)

    def update_work_time(self):
        """Ticks every second to track total work duration and posture ratio."""
        if not self.is_absent:
            self.work_seconds += 1
            
            # Update overall work time
            hours, remainder = divmod(self.work_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"Time Worked: {hours:02d}:{minutes:02d}:{seconds:02d}"
            
            if hasattr(self, 'work_time_label'):
                self.work_time_label.setText(time_str)

            # Posture Health Score
            if self.current_label == "sitting_good_posture":
                self.good_seconds += 1
            elif self.current_label == "sitting_bad_posture":
                self.bad_seconds += 1
                
            total_posture_time = self.good_seconds + self.bad_seconds
            if total_posture_time > 0:
                self.session_score = (self.good_seconds / total_posture_time) * 100
            
            # Update the single label
            self.update_stats_display()

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        broker_address = "test.mosquitto.org" 
        try:
            self.client.connect(broker_address, 1883, 60)
            self.client.loop_start() 
        except Exception as e:
            self.status_label.setText(f"MQTT Error: Could not connect to {broker_address}")

    def on_connect(self, client, userdata, flags, reason_code):
        if reason_code == 0:
            self.status_label.setText("MQTT: Connected | Monitoring Posture...")
            client.subscribe([("posture/status", 0)])
        else:
            self.status_label.setText(f"MQTT Connection Failed: {reason_code}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"parse_error": True, "raw": msg.payload.decode("utf-8", errors="replace")}
        self.mqtt_signals.data_signal.emit(payload)

    # client.on_message = on_message
    
    def handle_sensor_data(self, data: dict):

        # Track alarms

        if data.get("alarm") and not self.stop_alarm:
            self.notifier.show_notification()
            self.total_alarms += 1
            self.stop_alarm = True
        if data.get("alarm") is False:
            self.stop_alarm = False
            

        # Track current status and presence
        label = data.get("label", "Unknown")
        self.current_label = label # Save for the 1-second timer
        
        if label == "No posture detected":
            self.is_absent = True
            display_status = "Absent"
        elif label == "sitting_bad_posture":
            self.is_absent = False
            display_status = "Bad Posture"
            # print("Getting bad posture")
        elif label == "sitting_good_posture":
            self.is_absent = False
            display_status = "Good Posture"
            # print("Getting good posture")
        else:
            display_status = label

        self.display_status = display_status

        # Update Confidence
        if data.get("confidence"):
            # Convert "0.95" to 95.0%
            self.current_confidence = float(data["confidence"]) * 100

        # Update Hold Time (Stagnation)
        if data.get("stable_duration_sec"):
            self.current_hold_time = float(data["stable_duration_sec"])

        self.update_stats_display()

        # Handle the image rendering
        if data.get("posture_image"):
            img_bytes = base64.b64decode(data["posture_image"])
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                
                # Dynamically grab the current dimensions of the UI label
                target_width = self.video_label.width()
                target_height = self.video_label.height()
                
                resized_image = cv2.resize(img_rgb, (target_width, target_height), interpolation=cv2.INTER_AREA)
                
                h, w, ch = resized_image.shape
                bytes_per_line = ch * w
                qt_img = QImage(resized_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.update_image(qt_img)

    def update_image(self, qt_img):
        self.video_label.setPixmap(QPixmap.fromImage(qt_img))

    def closeEvent(self, event):
        self.client.loop_stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    window = MainWindow()
    window.show()
    
    catch_timer = QTimer()
    catch_timer.start(500)
    catch_timer.timeout.connect(lambda: None)
    
    sys.exit(app.exec_())