import cv2
import time
import os
import threading
import argparse

class CameraCaptureProcess:
    def __init__(self, 
                 output_dir: str = "images", 
                 interval: float = 10.0, 
                 max_images: int = 10, 
                 camera_index: int = 0,
                 resolution: tuple = (1920, 1080)):
        """
        Args:
            output_dir (str): Directory to save images.
            interval (float): Time in seconds between captures.
            max_images (int): Maximum number of images to keep.
            camera_index (int): Index of the camera.
            resolution (tuple): (width, height) for the capture.
        """
        self.output_dir = output_dir
        self.interval = interval
        self.max_images = max_images
        self.camera_index = camera_index
        self.resolution = resolution
        self._stop_event = threading.Event()
        
        # Initialize camera once using V4L2 backend
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Error: Could not open camera index {camera_index}.")

        # Set hardware resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        
        # Verify resolution (some cameras only support specific steps)
        actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"Camera initialized at {actual_w}x{actual_h}")

        os.makedirs(self.output_dir, exist_ok=True)

    def next_capture_path(self) -> str:
        return os.path.join(self.output_dir, f"image_{time.time_ns()}.jpg")

    def _get_image_path(self) -> str:
        return self.next_capture_path()

    def capture_to_path(self, path: str) -> bool:
        """Grab a fresh frame and write to path. Camera stays open."""
        for _ in range(5):
            self.cap.grab()
        ret, frame = self.cap.retrieve()
        if not ret:
            return False
        return bool(cv2.imwrite(path, frame))

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def cleanup_old_captures(self):
        """Removes the oldest files if the count exceeds max_images."""
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
        print(f"Starting capture: {self.interval}s interval, max {self.max_images} files.")
        
        # Initial warm-up for auto-exposure to settle
        time.sleep(2)

        try:
            while not self._stop_event.is_set():
                # To prevent getting an old frame from the hardware buffer, 
                # we grab a few frames and discard them before retrieving the final one.
                for _ in range(5):
                    self.cap.grab()
                
                ret, frame = self.cap.retrieve()
                
                if ret:
                    image_path = self._get_image_path()
                    cv2.imwrite(image_path, frame)
                    print(f"Saved: {image_path}")
                    self.cleanup_old_captures()
                else:
                    print("Error: Capture failed. Retrying...")

                # Wait for next interval or until stop signal
                self._stop_event.wait(self.interval)
        
        finally:
            self.release()
            print("Camera hardware released.")

    def stop(self):
        self._stop_event.set()

    def run_in_thread(self) -> threading.Thread:
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Continuous camera capture")
    parser.add_argument("-i", "--index", type=int, default=0, help="Camera index (default 0).")
    parser.add_argument("--dir", type=str, default="images", help="Directory to save images.")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between captures.")
    parser.add_argument("--max-images", type=int, default=100, help="Max images to keep.")
    parser.add_argument("--width", type=int, default=1920, help="Target width.")
    parser.add_argument("--height", type=int, default=1080, help="Target height.")
    
    args = parser.parse_args()

    process = CameraCaptureProcess(
        output_dir=args.dir,
        interval=args.interval,
        max_images=args.max_images,
        camera_index=args.index,
        resolution=(args.width, args.height)
    )

    try:
        process.run()
    except KeyboardInterrupt:
        print("\nStopping capture process...")
        process.stop()