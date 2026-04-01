"""Optional MQTT publish for posture telemetry (JSON payload)."""

from __future__ import annotations

import json
import logging
from typing import Any
import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

_client = None
_config: dict[str, Any] | None = None


def _make_client(client_id: str):

    try:
        return mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
    except (AttributeError, TypeError):
        return mqtt.Client(client_id=client_id)


def init_mqtt(
    broker: str,
    port: int = 1883,
    topic: str = "posture/status",
    client_id: str = "cme466_posture_rpi",
    username: str | None = None,
    password: str | None = None,
    timer_topic: str | None = None,
    on_timer_update: callable | None = None
) -> bool:
    global _client, _config
    if not broker:
        _client = None
        _config = None
        return False

    client = _make_client(client_id)

    if username:
        client.username_pw_set(username, password or "")


    # Handle messages
    def on_message(client, userdata, msg):
        if timer_topic and msg.topic == timer_topic:
            if on_timer_update:
                try:
                    val = float(msg.payload.decode().strip())
                    on_timer_update(val)
                except ValueError:
                    log.warning("Invalid timer value received")
    client.on_message = on_message
    
    def on_connect_v2(client, userdata, flags, reason_code, properties=None):
        try:
            rc = int(reason_code)
            if rc == 0:
                log.info("MQTT connected to %s", broker)
            else:
                log.warning("MQTT connect issue: %s", reason_code)
        except (TypeError, ValueError):
            if str(reason_code) in ("Success", "0"):
                log.info("MQTT connected to %s", broker)
                if timer_topic:
                    client.subscribe(timer_topic)
                    log.info("Subscribed to %s", timer_topic)
            else:
                log.warning("MQTT connect issue: %s", reason_code)

    def on_connect_v1(c, u, f, rc):
        if rc == 0:
            log.info("MQTT connected to %s", broker)
            if timer_topic:
                    client.subscribe(timer_topic)
                    log.info("Subscribed to %s", timer_topic)
        else:
            log.warning("MQTT connect rc=%s", rc)

    if hasattr(mqtt, "CallbackAPIVersion"):
        client.on_connect = on_connect_v2
    else:
        client.on_connect = on_connect_v1

    try:
        client.connect(broker, port, keepalive=60)
        client.loop_start()
    except Exception as e:
        log.warning("MQTT connect failed: %s", e)
        _client = None
        _config = None
        return False

    _client = client
    _config = {"topic": topic}
    return True


def publish_payload(payload: dict[str, Any]) -> None:
    if _client is None or _config is None:
        return
    topic = _config["topic"]
    try:
        body = json.dumps(payload, separators=(",", ":"))
        _client.publish(topic, body, qos=1)
    except Exception as e:
        log.warning("MQTT publish failed: %s", e)


def shutdown_mqtt() -> None:
    global _client, _config
    if _client is not None:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
    _client = None
    _config = None
