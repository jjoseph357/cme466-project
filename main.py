from camera import CameraCaptureProcess
import time
import os

IMAGES_DIR = "images"
IMG_INTERVAL = 5.0  # seconds
MAX_IMAGES = 10

if __name__ == "__main__":
    # Create image directory if it doesn't exist
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Start the camera capture process
    process = CameraCaptureProcess(
        output_dir=IMAGES_DIR,
        interval=IMG_INTERVAL,
        max_images=MAX_IMAGES,
        camera_index=0
    )
    thread = process.run_in_thread()
    print("Camera capture process started. Press Ctrl+C to stop.")
    try:
        while True:
            # Placeholder for future image processing logic
            time.sleep(IMG_INTERVAL)
            # Run posture detection on the latest image in the images directory
            image_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if image_files:
                latest_image = max(image_files, key=lambda x: os.path.getctime(os.path.join(IMAGES_DIR, x)))
                latest_image_path = os.path.join(IMAGES_DIR, latest_image)
                try:
                    from model.get_posture import get_posture_result
                    model_path = os.path.join('model', 'small640.onnx')
                    label, score = get_posture_result(model_path, latest_image_path)
                    print(f"Posture detection result for {latest_image}: {label} ({score:.2%})")
                except Exception as e:
                    print(f"Error running posture detection: {e}")
            else:
                print("No images found for posture detection.")
    except KeyboardInterrupt:
        print("\nStopping camera capture process...")
        process.stop()
        thread.join()
        print("Process stopped.")
