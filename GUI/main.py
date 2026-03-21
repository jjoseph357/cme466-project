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

# These act as a bridge between the MQTT background thread and the main GUI thread.
class MqttSignals(QObject):
    posture_stagnant = pyqtSignal()
    posture_moving = pyqtSignal()  
    video_frame = pyqtSignal(QImage)

class NotificationWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        # Make the window translucent 
        self.setWindowOpacity(0.80) 

        # Applied mid-gray background, white text, and no border
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
        QSound.play("alert.wav") 
        self.hide_timer.start(6000)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load the UI file created in Qt Designer
        try:
            uic.loadUi("posture_gui.ui", self)
        except FileNotFoundError:
            print("Error: Could not find 'posture_gui.ui'. Make sure it's in the same folder.")
            sys.exit(1)

        self.status_label.setText("UI Loaded Successfully! Starting systems...")
        self.notifier = NotificationWidget()
        
        # Initialize core logic
        self.setup_logic()

    def setup_logic(self):
        """Wires up timers, signals, and MQTT networking."""
        self.posture_timer = QTimer()
        self.posture_timer.timeout.connect(self.trigger_notification)
        self.timer_interval = 5000 

        self.mqtt_signals = MqttSignals()
        self.mqtt_signals.posture_stagnant.connect(self.handle_stagnant_posture)
        self.mqtt_signals.posture_moving.connect(self.handle_moving_posture) 
        self.mqtt_signals.video_frame.connect(self.update_image)

        self.setup_mqtt()

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        broker_address = "test.mosquitto.org" 
        try:
            self.client.connect(broker_address, 1883, 60)
            self.client.loop_start() # Spawns the network background thread
        except Exception as e:
            self.status_label.setText(f"MQTT Error: Could not connect to {broker_address}")

    def on_connect(self, client, userdata, flags, rc):
        # Safely update the status label from the callback
        self.status_label.setText("MQTT: Connected | Monitoring Posture...")
        client.subscribe([("sensor/posture", 0), ("sensor/video", 0)])

    def on_message(self, client, userdata, msg):
        """Processes incoming data and emits signals to the GUI thread."""
        if msg.topic == "sensor/posture":
            payload = msg.payload.decode()
            if payload == "STAGNANT":
                self.mqtt_signals.posture_stagnant.emit()
            elif payload == "MOVING":
                self.mqtt_signals.posture_moving.emit()
                
        elif msg.topic == "sensor/video":
            # Convert raw bytes to a NumPy array, then decode via OpenCV
            nparr = np.frombuffer(msg.payload, np.uint8)
            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if cv_img is not None:
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                
                qt_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                p = qt_img.scaled(640, 480, Qt.KeepAspectRatio)
                
                self.mqtt_signals.video_frame.emit(p)

    def update_image(self, qt_img):
        """Receives the image signal and updates the UI."""
        self.video_label.setPixmap(QPixmap.fromImage(qt_img))

    def handle_stagnant_posture(self):
        """Starts the notification timer if it isn't already running."""
        if not self.posture_timer.isActive():
            self.posture_timer.start(self.timer_interval)
    
    def handle_moving_posture(self):
        """Safely stops the timer from the main GUI thread."""
        self.posture_timer.stop()

    def trigger_notification(self):
        """Fires the popup and resets the timer."""
        self.notifier.show_notification()
        self.posture_timer.stop() 

    def closeEvent(self, event):
        """Ensures the MQTT thread shuts down cleanly when the window is closed."""
        self.client.loop_stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # handle the interrupt signal natively
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    window = MainWindow()
    window.show()
    
    # register the Ctrl+C command from your terminal.
    catch_timer = QTimer()
    catch_timer.start(500)
    catch_timer.timeout.connect(lambda: None)
    
    sys.exit(app.exec_())