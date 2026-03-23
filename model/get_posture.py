#!/usr/bin/env python

import sys
import cv2
import numpy as np
import onnxruntime as ort

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114)):
    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2] # current shape [height, width]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1] # wh padding
    dw /= 2 # divide padding into 2 sides
    dh /= 2
    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color) # add border
    return im

def get_posture_result(model_path, image_path, conf_threshold=0.25):
    classes = ['sitting_good', 'sitting_bad']
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

    # 1. Letterbox Preprocessing (Crucial for YOLO accuracy)
    img0 = cv2.imread(image_path)
    img = letterbox(img0, (640, 640))
    img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
    img = np.ascontiguousarray(img).astype(np.float32) / 255.0
    img = img[None] # Add batch dimension

    # 2. Run Inference
    outputs = session.run(None, {session.get_inputs()[0].name: img})
    preds = outputs[0] # Shape [1, 25200, 7]

    # 3. Process Predictions
    # Column 4 is Objectness, Columns 5 & 6 are Class Scores
    # We filter where Object Confidence * Class Confidence > threshold
    out = preds[0]
    obj_conf = out[:, 4]
    class_conf = np.max(out[:, 5:], axis=1)
    combined_conf = obj_conf * class_conf

    i = np.where(combined_conf > conf_threshold)[0]

    if len(i) == 0:
        return "No posture detected", 0.0

    # Get the best detection index
    best_idx = i[np.argmax(combined_conf[i])]
    label_idx = np.argmax(out[best_idx, 5:])
    final_conf = combined_conf[best_idx]

    return classes[label_idx], final_conf

# --- Execution ---
if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Expected 1 cmd-line arg: image path')
    img_path = sys.argv[1]
    label, score = get_posture_result("small640.onnx", img_path)
    print(f"Result: {label} ({score:.2%})")
