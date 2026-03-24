

import cv2
import time
import os
import threading
from typing import Optional

def capture_photo(output_path: str = "photo.jpg", camera_index: int = 0):
	"""
	Captures a single photo from the specified USB webcam and saves it to the given path.
	Args:
		output_path (str): Path to save the captured photo.
		camera_index (int): Index of the camera (default 0 for first camera).
	"""
	cap = cv2.VideoCapture(camera_index)
	if not cap.isOpened():
		print(f"Error: Could not open camera index {camera_index}.")
		return False

	time.sleep(2)  # Camera warm-up
	ret, frame = cap.read()
	if not ret:
		print("Error: Failed to capture image.")
		cap.release()
		return False

	cv2.imwrite(output_path, frame)
	print(f"Photo saved to {output_path}")
	cap.release()
	return True

class CameraCaptureProcess:
	def __init__(self, 
				 output_dir: str = "images", 
				 interval: float = 10.0, 
				 max_images: int = 10, 
				 camera_index: int = 0):
		"""
		Args:
			output_dir (str): Directory to save images.
			interval (float): Time in seconds between captures.
			max_images (int): Maximum number of images to keep in the directory.
			camera_index (int): Index of the camera.
		"""
		self.output_dir = output_dir
		self.interval = interval
		self.max_images = max_images
		self.camera_index = camera_index
		self._stop_event = threading.Event()
		os.makedirs(self.output_dir, exist_ok=True)

	def _get_image_path(self) -> str:
		timestamp = int(time.time())
		return os.path.join(self.output_dir, f"image_{timestamp}.jpg")

	def _cleanup_images(self):
		files = [f for f in os.listdir(self.output_dir) if f.lower().endswith('.jpg')]
		files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(self.output_dir, x)))
		while len(files) > self.max_images:
			oldest = files.pop(0)
			try:
				os.remove(os.path.join(self.output_dir, oldest))
				print(f"Deleted old image: {oldest}")
			except Exception as e:
				print(f"Error deleting {oldest}: {e}")

	def run(self):
		print(f"Starting camera capture process. Saving to {self.output_dir}, interval: {self.interval}s, max images: {self.max_images}")
		while not self._stop_event.is_set():
			image_path = self._get_image_path()
			success = capture_photo(image_path, self.camera_index)
			if success:
				self._cleanup_images()
			else:
				print("Capture failed. Retrying after interval.")
			self._stop_event.wait(self.interval)
		print("Camera capture process stopped.")

	def stop(self):
		self._stop_event.set()

	def run_in_thread(self) -> threading.Thread:
		t = threading.Thread(target=self.run, daemon=True)
		t.start()
		return t

if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="Capture a photo or run continuous capture from a USB webcam.")
	parser.add_argument("-o", "--output", type=str, default="photo.jpg", help="Output file path for single photo.")
	parser.add_argument("-i", "--index", type=int, default=0, help="Camera index (default 0).")
	parser.add_argument("--continuous", action="store_true", help="Run in continuous capture mode.")
	parser.add_argument("--dir", type=str, default="images", help="Directory to save images in continuous mode.")
	parser.add_argument("--interval", type=float, default=10.0, help="Interval in seconds between captures (continuous mode).")
	parser.add_argument("--max-images", type=int, default=100, help="Maximum number of images to keep (continuous mode).")
	args = parser.parse_args()

	if args.continuous:
		process = CameraCaptureProcess(
			output_dir=args.dir,
			interval=args.interval,
			max_images=args.max_images,
			camera_index=args.index
		)
		try:
			process.run()
		except KeyboardInterrupt:
			print("\nStopping continuous capture...")
			process.stop()
	else:
		capture_photo(args.output, args.index)
