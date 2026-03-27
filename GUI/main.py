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

# --- Suppress the internal PyQt5/SIP deprecation warnings ---
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- 1. Thread-Safe Signals ---
class MqttSignals(QObject):
    # Unified signal to handle incoming commands (e.g., 'N', 'A', 'P')
    sensor_data = pyqtSignal(str) 
    video_frame = pyqtSignal(QImage)

# --- 2. The Notification Widget ---
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

# --- 3. The Main Window Application ---
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

        # Setup thread-safe signals
        self.mqtt_signals = MqttSignals()
        self.mqtt_signals.sensor_data.connect(self.handle_sensor_data)
        self.mqtt_signals.video_frame.connect(self.update_image)

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
            self.client.publish("sensor/interval", str(minutes), qos=1, retain=True)

    def update_work_time(self):
        """Ticks every second to track total work duration."""
        if not self.is_absent:
            self.work_seconds += 1
            
            hours, remainder = divmod(self.work_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"Time Worked: {hours:02d}:{minutes:02d}:{seconds:02d}"
            
            if hasattr(self, 'work_time_label'):
                self.work_time_label.setText(time_str)

    def setup_mqtt(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        broker_address = "test.mosquitto.org" 
        try:
            self.client.connect(broker_address, 1883, 60)
            self.client.loop_start() 
        except Exception as e:
            self.status_label.setText(f"MQTT Error: Could not connect to {broker_address}")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.status_label.setText("MQTT: Connected | Monitoring Posture...")
            client.subscribe([("sensor/posture", 0), ("sensor/video", 0)])
        else:
            self.status_label.setText(f"MQTT Connection Failed: {reason_code}")

    def on_message(self, client, userdata, msg):
        """Processes incoming data and emits signals safely to the GUI thread."""
        if msg.topic == "sensor/posture":
            payload = msg.payload.decode().strip().upper()
            self.mqtt_signals.sensor_data.emit(payload)
                
        elif msg.topic == "sensor/video":
            nparr = np.frombuffer(msg.payload, np.uint8)
            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if cv_img is not None:
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                
                qt_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                p = qt_img.scaled(640, 480, Qt.KeepAspectRatio)
                self.mqtt_signals.video_frame.emit(p)

    def handle_sensor_data(self, payload):
        """Acts strictly on commands from the RPi5."""
        if payload == "N":
            # RPi5 says it's time to notify
            self.notifier.show_notification()
        elif payload == "A":
            # RPi5 says user left frame (pauses work timer)
            self.is_absent = True
        elif payload == "P":
            # RPi5 says user is present in frame (resumes work timer)
            self.is_absent = False

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