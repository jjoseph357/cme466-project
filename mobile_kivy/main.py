"""
Kivy mobile frontend for posture monitoring.
Keeps the same MQTT topics as the original reference:
- subscribe: posture/status
- publish: posture/timer

Supports:
1. JSON posture/status messages
2. JSON messages that include a base64 image
3. Raw image bytes (fallback)
"""

import base64
import json
import logging
import os
import threading
from queue import Queue, Empty
from typing import Optional

import paho.mqtt.client as mqtt
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Desktop testing only
Window.size = (720, 1280)


class MQTTClient(threading.Thread):
    def __init__(self, broker: str, port: int, message_queue: Queue):
        super().__init__(daemon=True)
        self.broker = broker
        self.port = port
        self.message_queue = message_queue
        self.client: Optional[mqtt.Client] = None

    def run(self):
        try:
            try:
                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id="posture_kivy_app",
                )
            except (AttributeError, TypeError):
                self.client = mqtt.Client(client_id="posture_kivy_app")

            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            log.info("MQTT: Connecting to %s:%s", self.broker, self.port)
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_forever()

        except Exception as e:
            log.error("MQTT thread error: %s", e)
            self.message_queue.put({"type": "error", "message": str(e)})

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            log.info("MQTT: Connected successfully")
            client.subscribe([("posture/status", 0)])
            self.message_queue.put({"type": "connection", "connected": True})
        else:
            log.error("MQTT: Connection failed with code %s", reason_code)
            self.message_queue.put(
                {"type": "connection", "connected": False, "reason": reason_code}
            )

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        log.warning("MQTT: Disconnected with code %s", reason_code)
        self.message_queue.put(
            {"type": "connection", "connected": False, "reason": reason_code}
        )

    def _on_message(self, client, userdata, msg):
        # Keep the same topic as the old reference: posture/status
        # Try JSON first; if it is not JSON, treat it as raw image bytes.
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            log.info("Received JSON: %s", str(payload)[:100])  # Log first 100 chars
            self.message_queue.put({"type": "posture_data", "data": payload})
            return
        except Exception as e:
            log.debug("Not JSON, treating as raw data: %s", e)

        # Not JSON -> assume image data (could be base64 string or raw bytes)
        log.info("Received raw data, size: %d bytes", len(msg.payload))
        self.message_queue.put({"type": "image_bytes", "data": msg.payload})

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = True):
        if self.client and self.client.is_connected():
            try:
                self.client.publish(topic, payload, qos=qos, retain=retain)
                log.info("MQTT: Published to %s: %s", topic, payload)
            except Exception as e:
                log.error("MQTT publish error: %s", e)

    def stop(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


class PostureApp(App):
    connection_status = StringProperty("Connecting...")
    posture_label = StringProperty("--")
    time_worked = StringProperty("00:00:00")
    interval_minutes = NumericProperty(30)
    is_connected = BooleanProperty(False)
    image_source = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mqtt_thread: Optional[MQTTClient] = None
        self.message_queue: Queue = Queue()
        self.work_seconds = 0
        self.is_absent = False

    def build(self):
        current_dir = os.path.dirname(__file__)
        kv_path = os.path.join(current_dir, "posture.kv")

        if not os.path.exists(kv_path):
            raise FileNotFoundError(f"posture.kv not found at {kv_path}")

        return Builder.load_file(kv_path)

    def on_start(self):
        Clock.schedule_interval(self._tick_work_timer, 1.0)
        Clock.schedule_interval(self._process_mqtt_messages, 0.1)

        self.mqtt_thread = MQTTClient(
            broker="test.mosquitto.org",
            port=1883,
            message_queue=self.message_queue,
        )
        self.mqtt_thread.start()

    def on_stop(self):
        if self.mqtt_thread:
            self.mqtt_thread.stop()

    def _process_mqtt_messages(self, dt):
        while True:
            try:
                msg = self.message_queue.get_nowait()
            except Empty:
                break

            if msg["type"] == "connection":
                self._handle_connection(msg)
            elif msg["type"] == "posture_data":
                self._handle_posture_data(msg["data"])
            elif msg["type"] == "image_bytes":
                self._handle_image_bytes(msg["data"])
            elif msg["type"] == "error":
                self.connection_status = f"Error: {msg['message']}"
                self.is_connected = False

    def _handle_connection(self, msg: dict):
        connected = msg.get("connected", False)
        if connected:
            self.is_connected = True
            self.connection_status = "MQTT Connected | Monitoring Posture..."
        else:
            self.is_connected = False
            reason = msg.get("reason", "unknown")
            self.connection_status = f"Disconnected (reason: {reason})"

    def _handle_posture_data(self, data: dict):
        log.info("Received MQTT JSON data: %s", data)

        if data.get("alarm") is True:
            self.show_notification(
                "Posture Reminder",
                "Time to shift your posture and give your eyes a break!",
            )

        # Support a few possible label keys
        label = (
            data.get("label")
            or data.get("posture")
            or data.get("status")
            or ""
        )

        if label == "No posture detected":
            self.is_absent = True
        elif label in ("sitting_bad_posture", "sitting_good_posture"):
            self.is_absent = False

        self.posture_label = label if label else "--"

        # Old compatibility: image path from JSON
        image_path = data.get("posture_image")
        if image_path and os.path.exists(image_path):
            self.image_source = image_path
            log.info("Loaded image from local path: %s", image_path)
            return

        # New: base64 image inside JSON
        # Try common possible keys
        image_b64 = (
            data.get("image")
            or data.get("image_base64")
            or data.get("frame")
            or data.get("frame_base64")
            or data.get("source_frame_base64")
            or data.get("posture_frame")
        )

        # Based on your screenshot, source_frame looks like the filename,
        # so we do NOT use source_frame as the image bytes.
        if image_b64:
            self._handle_base64_image(image_b64)

    def _handle_base64_image(self, image_b64: str):
        """
        Decode a base64 image string, save it locally, then update image_source.
        """
        try:
            # Remove possible data URL prefix like:
            # data:image/jpeg;base64,/9j/4AAQ...
            if "," in image_b64 and image_b64.strip().startswith("data:image"):
                image_b64 = image_b64.split(",", 1)[1]

            image_bytes = base64.b64decode(image_b64)
            self._save_and_set_image(image_bytes)
            log.info("Decoded and displayed base64 image successfully")

        except Exception as e:
            log.error("Failed to decode/display base64 image: %s", e)

    def _handle_image_bytes(self, image_data):
        """
        Saves raw image bytes to the app's local writable area, then displays it.
        Handles both raw bytes and base64-encoded string data.
        This keeps the MQTT topic unchanged.
        """
        try:
            # Check if it's a string (base64) or bytes
            if isinstance(image_data, str):
                # It's base64 encoded string
                log.info("Image is base64 string, decoding...")
                image_bytes = base64.b64decode(image_data)
            elif isinstance(image_data, bytes):
                # Check if it looks like base64 (starts with valid base64 chars)
                try:
                    decoded = image_data.decode("utf-8")
                    # Try to decode as base64
                    image_bytes = base64.b64decode(decoded)
                    log.info("Image was bytes-encoded base64, decoded successfully")
                except Exception:
                    # Just use as raw bytes
                    image_bytes = image_data
                    log.info("Image is raw bytes")
            else:
                log.error("Image data is unexpected type: %s", type(image_data))
                return
            
            self._save_and_set_image(image_bytes)
            log.info("Image saved and displayed successfully")
        except Exception as e:
            log.error("Failed to process image bytes: %s", e)

    def _save_and_set_image(self, image_bytes: bytes):
        """
        Save image bytes to a local file and refresh the Kivy Image widget source.
        """
        try:
            save_dir = self.user_data_dir
            os.makedirs(save_dir, exist_ok=True)
            img_path = os.path.join(save_dir, "latest_posture.jpg")

            # Write image
            with open(img_path, "wb") as f:
                bytes_written = f.write(image_bytes)
            
            log.info("Saved %d bytes to %s", bytes_written, img_path)

            # Force refresh in Kivy in case the same filename is reused
            self.image_source = ""
            self.image_source = img_path
            log.info("Image source updated to: %s", img_path)
        except Exception as e:
            log.error("Failed to save image: %s", e)
            raise

    def show_notification(self, title, message):
        box = BoxLayout(orientation="vertical", padding=10, spacing=10)
        box.add_widget(Label(text=message))
        popup = Popup(title=title, content=box, size_hint=(0.8, 0.3))
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 5)

    def _tick_work_timer(self, dt):
        if not self.is_absent:
            self.work_seconds += 1
            hours, remainder = divmod(self.work_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.time_worked = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def on_interval_value_change(self, value):
        self.interval_minutes = value
        if self.mqtt_thread:
            self.mqtt_thread.publish(
                topic="posture/timer",
                payload=str(int(value)),
                qos=1,
                retain=True,
            )

    def send_interval_now(self):
        if self.mqtt_thread:
            self.mqtt_thread.publish(
                topic="posture/timer",
                payload=str(int(self.interval_minutes)),
                qos=1,
                retain=True,
            )


if __name__ == "__main__":
    PostureApp().run()