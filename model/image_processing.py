import cv2

classes = ['sitting_good_posture', 'sitting_bad_posture']


def square_resize(image, size=640):
    """Crops image to square and resizes to 640p."""
    h, w = image.shape[:2]
    min_dim = min(h, w)

    start_x = (w-min_dim) // 2
    start_y = (h-min_dim) // 2
    cropped = image[start_y:start_y+min_dim, start_x:start_x+min_dim]

    resized = cv2.resize(cropped, (size, size))

    return resized


def load_img(img_path):
    img = cv2.imread(img_path)
    img = square_resize(img)
    return img


def draw_and_save(img, bbox, label, conf, output_path="posture.jpg"):
    """
    Draw bounding box on the image and save it (overwrites output_path each update).
    """
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

