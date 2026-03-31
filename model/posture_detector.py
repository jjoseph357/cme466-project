import numpy as np
import onnxruntime as ort
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

classes = ['sitting_good_posture', 'sitting_bad_posture']


class PostureDetectorYOLOv5:
    def __init__(self, model_path: str, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.session = ort.InferenceSession(
            model_path, providers=['CPUExecutionProvider']
        )

    def detect(self, img):
        img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
        img = np.ascontiguousarray(img).astype(np.float32) / 255.0
        img = img[None]

        outputs = self.session.run(None, {self.session.get_inputs()[0].name: img})
        preds = outputs[0]

        out = preds[0]
        obj_conf = out[:, 4]
        class_conf = np.max(out[:, 5:], axis=1)
        combined_conf = obj_conf * class_conf

        i = np.where(combined_conf > self.conf_threshold)[0]

        if len(i) == 0:
            return "No posture detected", 0.0, None

        best_idx = i[np.argmax(combined_conf[i])]
        label_idx = np.argmax(out[best_idx, 5:])
        final_conf = combined_conf[best_idx]

        x, y, w, h = out[best_idx, :4]

        x1 = x - w / 2
        y1 = y - h / 2
        x2 = x + w / 2
        y2 = y + h / 2

        bbox = [x1, y1, x2, y2]

        return classes[label_idx], float(final_conf), bbox


class PostureCoach:
    def __init__(self, model_path: str, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.session = ort.InferenceSession(
            model_path, providers=['CPUExecutionProvider']
        )

    def detect(self, img):
        # 1. Preprocessing
        img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
        img = np.ascontiguousarray(img).astype(np.float32) / 255.0
        img = img[None] # Add batch dimension

        # 2. Run Inference
        outputs = self.session.run(None, {self.session.get_inputs()[0].name: img})
        detections = outputs[0][0]

        # Remove zero rows
        detections = detections[detections[:, 4] > 0]

        if len(detections) == 0:
            return None, 0.0, None

        # Extract fields
        boxes = detections[:, :4]
        conf = detections[:, 4]
        class_ids = detections[:, 5].astype(int)

        # Pick best detection
        best_idx = np.argmax(conf)

        x1, y1, x2, y2 = boxes[best_idx]
        final_conf = conf[best_idx]
        label_idx = class_ids[best_idx]

        if final_conf < self.conf_threshold:
            return None, 0.0, None
        
        # This model uses 0 for bad posture and 1 for good posture
        label_idx = int(1 - label_idx)

        return classes[label_idx], float(final_conf), [x1, y1, x2, y2]


def init_model():
    return PostureCoach(BASE_DIR / 'PostureCoach-nms.onnx')
    # return PostureDetectorYOLOv5(BASE_DIR / 'small640.onnx')
