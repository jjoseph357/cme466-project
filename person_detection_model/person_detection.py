{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 2,
   "id": "9b8692e4-042c-4aa1-a432-3ef4f81ea2ef",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "False\n"
     ]
    }
   ],
   "source": [
    "from ultralytics import YOLO\n",
    "\n",
    "class PersonDetector:\n",
    "    def __init__(self, model_path=\"yolov8n.pt\", conf_threshold=0.5, min_box_area=0):\n",
    "        self.model = YOLO(model_path)\n",
    "        self.conf_threshold = conf_threshold\n",
    "        self.min_box_area = min_box_area\n",
    "\n",
    "    def predict(self, image_path):\n",
    "        results = self.model.predict(source=image_path, conf=self.conf_threshold, verbose=False)\n",
    "        for r in results:\n",
    "            for box in r.boxes:\n",
    "                cls_id = int(box.cls[0].item())\n",
    "                conf = float(box.conf[0].item())\n",
    "                class_name = self.model.names[cls_id]\n",
    "                x1, y1, x2, y2 = box.xyxy[0].tolist()\n",
    "                area = max(0, x2 - x1) * max(0, y2 - y1)\n",
    "                if class_name == \"person\" and conf >= self.conf_threshold and area >= self.min_box_area:\n",
    "                    return True\n",
    "        return False\n",
    "\n",
    "detector = PersonDetector(model_path=\"yolov8n.pt\", conf_threshold=0.5)\n",
    "\n",
    "# image_path = \"PNGImages/PennPed00096.png\"\n",
    "image_path = \"NegativeImages/img7.webp\"\n",
    "#\n",
    "result = detector.predict(image_path)\n",
    "print(result)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "b58527cb-ed4c-4218-b7a7-18bac13f411e",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.12.2"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
