from camera import CameraCaptureProcess
import time
import os

IMAGES_DIR = "images"

if __name__ == "__main__":
    # Create image directory if it doesn't exist
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Start the camera capture process
    process = CameraCaptureProcess(
        output_dir=IMAGES_DIR,
        interval=10.0,
        max_images=10,
        camera_index=0
    )
    thread = process.run_in_thread()
    print("Camera capture process started. Press Ctrl+C to stop.")
    try:
        while True:
            # Placeholder for future image processing logic
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping camera capture process...")
        process.stop()
        thread.join()
        print("Process stopped.")
