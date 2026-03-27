#!/usr/bin/env python

import sys
import cv2
import numpy as np
import onnxruntime as ort

classes = ['sitting_good_posture', 'sitting_bad_posture']

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114)):
    shape = im.shape[:2]  # (h, w)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    ratio = (r, r)

    # Compute new size
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))

    # Compute padding
    dw = new_shape[1] - new_unpad[0]
    dh = new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2

    # Resize
    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)

    # Pad
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

    im = cv2.copyMakeBorder(
        im, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=color
    )

    return im, ratio, (dw, dh)


def _run_inference(session, image_path, conf_threshold=0.25):
    img0 = cv2.imread(image_path)
    if img0 is None:
        return "No posture detected", 0.0, None

    h0, w0 = img0.shape[:2]
    img, ratio, pad = letterbox(img0, (640, 640))
    img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
    img = np.ascontiguousarray(img).astype(np.float32) / 255.0
    img = img[None]

    outputs = session.run(None, {session.get_inputs()[0].name: img})
    preds = outputs[0]

    out = preds[0]
    obj_conf = out[:, 4]
    class_conf = np.max(out[:, 5:], axis=1)
    combined_conf = obj_conf * class_conf

    i = np.where(combined_conf > conf_threshold)[0]

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

    x1 -= pad[0]
    x2 -= pad[0]
    y1 -= pad[1]
    y2 -= pad[1]

    x1 /= ratio[0]
    x2 /= ratio[0]
    y1 /= ratio[1]
    y2 /= ratio[1]

    x1 = max(0, min(w0, x1))
    x2 = max(0, min(w0, x2))
    y1 = max(0, min(h0, y1))
    y2 = max(0, min(h0, y2))

    bbox = [x1, y1, x2, y2]

    return classes[label_idx], float(final_conf), bbox


class PostureDetector:
    """Loads the ONNX model once; use on RPi to avoid repeated session creation."""

    def __init__(self, model_path: str, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.session = ort.InferenceSession(
            model_path, providers=['CPUExecutionProvider']
        )

    def detect(self, image_path: str):
        return _run_inference(self.session, image_path, self.conf_threshold)


def get_posture_result(model_path, image_path, conf_threshold=0.25):
    """
    Runs the YOLO model to detect good/bad sitting posture.
    One-shot helper (creates a new session each call — prefer PostureDetector in a loop).

    Returns:
        class: String for the detected class
        conf: Confidence score of prediction or 0 if no posture is detected above conf_threshold
        bbox: bounding box of the detected object (x1, y1, x2, y2) or None
    """
    det = PostureDetector(model_path, conf_threshold)
    return det.detect(image_path)


def draw_and_save(image_path, bbox, label, conf, output_path="posture.jpg"):
    """
    Draw bounding box on the image and save it (overwrites output_path each update).
    """
    img = cv2.imread(image_path)
    if img is None:
        return

    if bbox is not None:
        x1, y1, x2, y2 = map(int, bbox)

        color = (0, 255, 0) if label == classes[0] else (0, 0, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

        text = f"{label} {conf:.2f}"
        cv2.putText(
            img,
            text,
            (x1, max(0, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            img,
            f"{label}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (128, 128, 128),
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(output_path, img)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Expected 1 cmd-line arg: image path')
    img_path = sys.argv[1]
    label, score, bbox = get_posture_result("small640.onnx", img_path)
    print(f"Result: {label} ({score:.2%})")
    print(f"bbox: {bbox}")

    draw_and_save(img_path, bbox, label, score, "output.jpg")
