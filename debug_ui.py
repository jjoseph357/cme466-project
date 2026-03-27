#!/usr/bin/env python3
"""
MQTT debug monitor for posture telemetry.
Loads posture image from the path in each message (same machine as publisher, or set POSTURE_DEBUG_IMAGE_BASE).

Env (defaults use the public Mosquitto test broker):
  POSTURE_MQTT_BROKER      default test.mosquitto.org (set to empty to not connect)
  POSTURE_MQTT_PORT        default 1883
  POSTURE_MQTT_TOPIC       default posture/status
  POSTURE_MQTT_USER / POSTURE_MQTT_PASSWORD  optional
  POSTURE_DEBUG_CLIENT_ID  default posture_debug_ui
  POSTURE_DEBUG_IMAGE_BASE directory to resolve posture_image paths (default cwd)
"""

from __future__ import annotations

import json
import os
import sys

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import paho.mqtt.client as mqtt


def _env_str(key: str, default: str) -> str:
    v = os.environ.get(key)
    return default if v is None or v.strip() == "" else v


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return int(v)


def _make_mqtt_client(client_id: str):

    try:
        return mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
    except (AttributeError, TypeError):
        return mqtt.Client(client_id=client_id)


class MqttStateBridge(QObject):
    """Marshals MQTT callbacks onto the Qt thread via queued signals."""

    state_received = pyqtSignal(dict)
    connection_changed = pyqtSignal(bool, str)


class DebugMainWindow(QMainWindow):
    def __init__(self, bridge: MqttStateBridge):
        super().__init__()
        self._bridge = bridge
        self._image_base = os.path.abspath(
            _env_str("POSTURE_DEBUG_IMAGE_BASE", os.getcwd())
        )

        self.setWindowTitle("Posture MQTT Debug")
        self.setMinimumSize(960, 640)
        self._apply_style()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        self._banner = QLabel("DISCONNECTED")
        self._banner.setAlignment(Qt.AlignCenter)
        self._banner.setMinimumHeight(44)
        self._banner.setObjectName("connBanner")
        root.addWidget(self._banner)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)

        # Image panel
        img_wrap = QFrame()
        img_wrap.setObjectName("imagePanel")
        img_lay = QVBoxLayout(img_wrap)
        img_lay.setContentsMargins(8, 8, 8, 8)
        self._image_label = QLabel("No image yet")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label.setMinimumSize(400, 300)
        self._image_label.setScaledContents(False)
        img_lay.addWidget(self._image_label)
        img_hint = QLabel(
            f"Image path resolved under:\n{self._image_base}\n"
            "(set POSTURE_DEBUG_IMAGE_BASE if the publisher saves elsewhere)"
        )
        img_hint.setObjectName("hint")
        img_hint.setWordWrap(True)
        img_lay.addWidget(img_hint)
        splitter.addWidget(img_wrap)

        # State panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        state_inner = QWidget()
        self._grid = QGridLayout(state_inner)
        self._grid.setColumnStretch(1, 1)
        self._grid.setSpacing(10)
        scroll.setWidget(state_inner)
        splitter.addWidget(scroll)
        splitter.setSizes([520, 400])

        self._rows: dict[str, QLabel] = {}
        for i, key in enumerate(
            [
                "ts",
                "label",
                "confidence",
                "bbox",
                "alarm",
                "posture_changing",
                "stable_duration_sec",
                "posture_image",
                "source_frame",
            ]
        ):
            k = QLabel(key)
            k.setObjectName("keyLabel")
            v = QLabel("—")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.setWordWrap(True)
            mono = QFont("monospace")
            mono.setStyleHint(QFont.TypeWriter)
            v.setFont(mono)
            self._grid.addWidget(k, i, 0)
            self._grid.addWidget(v, i, 1)
            self._rows[key] = v

        self._alarm_strip = QLabel("ALARM: idle")
        self._alarm_strip.setAlignment(Qt.AlignCenter)
        self._alarm_strip.setMinimumHeight(36)
        self._alarm_strip.setObjectName("alarmStrip")
        root.addWidget(self._alarm_strip)

        self._bridge.state_received.connect(self._on_state)
        self._bridge.connection_changed.connect(self._on_connection)

        self._raw_payload_preview = QLabel("")
        self._raw_payload_preview.setObjectName("hint")
        self._raw_payload_preview.setWordWrap(True)
        root.addWidget(self._raw_payload_preview)

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color: #1e1e1e; color: #e0e0e0; }
            QLabel#keyLabel { color: #888; font-weight: bold; }
            QLabel#hint { color: #666; font-size: 11px; }
            QFrame#imagePanel {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            QLabel#connBanner {
                background-color: #3d2f00;
                color: #ffcc66;
                font-weight: bold;
                border-radius: 4px;
            }
            QLabel#alarmStrip {
                background-color: #2a2a2a;
                color: #888;
                border-radius: 4px;
                border: 1px solid #444;
            }
            QSplitter::handle { background: #333; width: 4px; }
            """
        )

    def _on_connection(self, ok: bool, detail: str):
        if ok:
            self._banner.setText(f"CONNECTED — {detail}")
            self._banner.setStyleSheet(
                "background-color: #1b3d1b; color: #8fd98f; "
                "font-weight: bold; border-radius: 4px; padding: 8px;"
            )
        else:
            self._banner.setText(f"DISCONNECTED — {detail}")
            self._banner.setStyleSheet(
                "background-color: #3d1b1b; color: #ff9999; "
                "font-weight: bold; border-radius: 4px; padding: 8px;"
            )

    def _on_state(self, data: dict):
        def fmt(v) -> str:
            if v is None:
                return "null"
            if isinstance(v, (list, dict)):
                return json.dumps(v)
            return str(v)

        for key, lbl in self._rows.items():
            lbl.setText(fmt(data.get(key)))

        alarm = bool(data.get("alarm"))
        if alarm:
            self._alarm_strip.setText("ALARM: sustained bad posture")
            self._alarm_strip.setStyleSheet(
                "background-color: #5c1010; color: #ff6b6b; "
                "font-weight: bold; border-radius: 4px; border: 1px solid #a02020;"
            )
        else:
            self._alarm_strip.setText("ALARM: clear")
            self._alarm_strip.setStyleSheet(
                "background-color: #1e2d1e; color: #7a7; "
                "border-radius: 4px; border: 1px solid #355035;"
            )

        path = data.get("posture_image") or "posture.jpg"
        if not isinstance(path, str):
            path = str(path)
        full = path if os.path.isabs(path) else os.path.join(self._image_base, path)

        img = QImage()
        try:
            with open(full, "rb") as f:
                raw = f.read()
            if raw and img.loadFromData(raw):
                pm = QPixmap.fromImage(img)
                max_w, max_h = 780, 560
                if pm.width() > max_w or pm.height() > max_h:
                    pm = pm.scaled(
                        max_w,
                        max_h,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                self._image_label.setPixmap(pm)
                self._image_label.setText("")
            else:
                self._image_label.clear()
                self._image_label.setText(f"No readable image\n{full}")
        except OSError:
            self._image_label.clear()
            self._image_label.setText(f"Image not available\n{full}")

        try:
            self._raw_payload_preview.setText("Last JSON: " + json.dumps(data))
        except (TypeError, ValueError):
            self._raw_payload_preview.setText("Last message (non-JSON preview omitted)")


def main():
    broker = _env_str("POSTURE_MQTT_BROKER", "test.mosquitto.org")
    port = _env_int("POSTURE_MQTT_PORT", 1883)
    topic = _env_str("POSTURE_MQTT_TOPIC", "posture/status")
    client_id = _env_str("POSTURE_DEBUG_CLIENT_ID", "posture_debug_ui")
    user = os.environ.get("POSTURE_MQTT_USER") or None
    password = os.environ.get("POSTURE_MQTT_PASSWORD") or None

    app = QApplication(sys.argv)
    app.setApplicationName("Posture MQTT Debug")

    bridge = MqttStateBridge()
    win = DebugMainWindow(bridge)
    win.show()

    if not broker:
        bridge.connection_changed.emit(False, "POSTURE_MQTT_BROKER empty — not connecting")
        code = app.exec_()
        sys.exit(code)

    client = _make_mqtt_client(client_id)

    if user:
        client.username_pw_set(user, password or "")

    def on_connect_v2(client, userdata, flags, reason_code, properties=None):
        try:
            rc = int(reason_code)
            ok = rc == 0
        except (TypeError, ValueError):
            ok = str(reason_code) in ("Success", "0")
        if ok:
            client.subscribe(topic, qos=1)
            bridge.connection_changed.emit(True, f"{broker}:{port} / {topic}")
        else:
            bridge.connection_changed.emit(False, f"connect failed: {reason_code}")

    def on_connect_v1(c, u, f, rc):
        if rc == 0:
            c.subscribe(topic, qos=1)
            bridge.connection_changed.emit(True, f"{broker}:{port} / {topic}")
        else:
            bridge.connection_changed.emit(False, f"MQTT rc={rc}")

    if hasattr(mqtt, "CallbackAPIVersion"):
        client.on_connect = on_connect_v2
    else:
        client.on_connect = on_connect_v1

    def on_disconnect_v2(client, userdata, disconnect_flags, reason_code, properties=None):
        bridge.connection_changed.emit(False, f"disconnected: {reason_code}")

    def on_disconnect_v1(c, u, rc):
        bridge.connection_changed.emit(False, f"disconnected rc={rc}")

    if hasattr(mqtt, "CallbackAPIVersion"):
        client.on_disconnect = on_disconnect_v2
    else:
        client.on_disconnect = on_disconnect_v1

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                payload = {"raw": payload}
        except Exception:
            payload = {"parse_error": True, "raw": msg.payload.decode("utf-8", errors="replace")}
        bridge.state_received.emit(payload)

    client.on_message = on_message

    try:
        client.connect(broker, port, keepalive=60)
    except Exception as e:
        bridge.connection_changed.emit(False, str(e))

    client.loop_start()

    code = app.exec_()
    client.loop_stop()
    client.disconnect()
    sys.exit(code)


if __name__ == "__main__":
    main()
