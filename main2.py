import logging
import os
import time

from camera import CameraCaptureProcess
from mqtt_publisher import init_mqtt, publish_payload, shutdown_mqtt
from stability_tracker import PostureStabilityTracker
from model.posture_detector import PostureDetector
from model.image_processing import load_img, draw_and_save

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return float(v)


def _env_str(key: str, default: str) -> str:
    v = os.environ.get(key)
    return default if v is None or v.strip() == "" else v


IMAGES_DIR = _env_str("POSTURE_IMAGES_DIR", "images")
POSTURE_JPG = _env_str("POSTURE_OUTPUT_IMAGE", "posture.jpg")
MODEL_PATH = _env_str("POSTURE_MODEL_PATH", os.path.join("model", "small640.onnx"))
IMG_INTERVAL = _env_float("POSTURE_CAPTURE_INTERVAL", 1.0)
MAX_IMAGES = int(_env_float("POSTURE_MAX_IMAGES", 5))
CAMERA_INDEX = int(_env_float("POSTURE_CAMERA_INDEX", 0))

STABLE_BAD_SECONDS = _env_float("POSTURE_STABLE_BAD_SECONDS", 10.0)
MIN_BBOX_IOU_STABLE = _env_float("POSTURE_MIN_BBOX_IOU_STABLE", 0.85)
CONF_THRESHOLD = _env_float("POSTURE_CONF_THRESHOLD", 0.25)

def _mqtt_broker() -> str:
    """Unset → public test broker (no local Mosquitto). POSTURE_MQTT_BROKER= empty → MQTT off."""
    if "POSTURE_MQTT_BROKER" in os.environ:
        return os.environ["POSTURE_MQTT_BROKER"].strip()
    return "test.mosquitto.org"


MQTT_BROKER = _mqtt_broker()
MQTT_PORT = int(_env_float("POSTURE_MQTT_PORT", 1883))
MQTT_TOPIC = _env_str("POSTURE_MQTT_TOPIC", "posture/status")
MQTT_TIMER_TOPIC = _env_str("TIMER_MQTT_TOPIC", "posture/timer")
MQTT_CLIENT_ID = _env_str("POSTURE_MQTT_CLIENT_ID", "cme466_posture_rpi")
MQTT_USER = os.environ.get("POSTURE_MQTT_USER") or None
MQTT_PASSWORD = os.environ.get("POSTURE_MQTT_PASSWORD") or None


if __name__ == "__main__":
    os.makedirs(IMAGES_DIR, exist_ok=True)

    if not os.path.isfile(MODEL_PATH):
        log.error("Model not found: %s", MODEL_PATH)
        raise SystemExit(1)

    detector = PostureDetector(MODEL_PATH, conf_threshold=CONF_THRESHOLD)
    tracker = PostureStabilityTracker(
        stable_bad_seconds=STABLE_BAD_SECONDS,
        min_iou_for_stable=MIN_BBOX_IOU_STABLE,
        bad_label="sitting_bad_posture",
    )

    def handle_timer_update(new_seconds: float):
        log.info("Received new timer interval: %.1f", new_seconds)
        tracker.stable_bad_seconds = new_seconds

    if MQTT_BROKER:
        init_mqtt(
            broker=MQTT_BROKER,
            port=MQTT_PORT,
            topic=MQTT_TOPIC,
            client_id=MQTT_CLIENT_ID,
            username=MQTT_USER,
            password=MQTT_PASSWORD,
            timer_topic=MQTT_TIMER_TOPIC,
            on_timer_update=handle_timer_update
        )
    else:
        log.info("MQTT disabled (POSTURE_MQTT_BROKER is empty).")

    # Interval is only used by the standalone capture thread API; main uses IMG_INTERVAL for sleep.
    camera = CameraCaptureProcess(
        output_dir=IMAGES_DIR,
        interval=IMG_INTERVAL,
        max_images=MAX_IMAGES,
        camera_index=CAMERA_INDEX,
    )

    log.info("Warming up camera (auto-exposure)...")
    time.sleep(2)

    try:
        while True:
            frame_path = camera.next_capture_path()
            if not camera.capture_to_path(frame_path):
                log.warning("Capture failed; sleeping before retry.")
                time.sleep(IMG_INTERVAL)
                continue

            camera.cleanup_old_captures()

            try:
                img = load_img(frame_path)
                label, score, bbox = detector.detect(img)
                draw_and_save(img, bbox, label, score, POSTURE_JPG)
            except Exception as e:
                log.exception("Posture detection failed: %s", e)
                time.sleep(IMG_INTERVAL)
                continue

            now = time.time()
            st = tracker.update(label, bbox, now)

            payload = {
                "ts": int(now),
                "label": label,
                "confidence": str(round(score, 4)),
                "bbox": None if bbox is None else [str(round(x, 2)) for x in bbox],
                "alarm": st["alarm"],
                "posture_changing": st["posture_changing"],
                "stable_duration_sec": str(round(st["stable_duration_sec"], 2)),
                "posture_image": POSTURE_JPG,
                "source_frame": os.path.basename(frame_path),
            }

            publish_payload(payload)

            log.info(
                "%s (%.1f%%) alarm=%s changing=%s stable=%.1fs -> %s",
                label,
                100.0 * score,
                st["alarm"],
                st["posture_changing"],
                st["stable_duration_sec"],
                POSTURE_JPG,
            )

            time.sleep(IMG_INTERVAL)

    except KeyboardInterrupt:
        log.info("Stopping...")
    finally:
        camera.release()
        shutdown_mqtt()
        log.info("Stopped.")
