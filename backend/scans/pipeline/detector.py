import os
import uuid
import logging
import cv2
from django.conf import settings
from ultralytics import YOLO

logger = logging.getLogger(__name__)

_model = None

def get_model():
    global _model
    if _model is None:
        _model = YOLO('yolov8n.pt')
    return _model


def detect_spines(image_path, conf_threshold=0.25):
    """
    Returns list of dicts: [{"box": [x1,y1,x2,y2], "detection_confidence": float, "crop_path": str}]
    Never raises — caller decides how to handle an empty list.
    """
    model = get_model()
    results = model(image_path, conf=conf_threshold, classes=[73])  # COCO 'book'

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    crop_dir = os.path.join(settings.MEDIA_ROOT, 'crops', str(uuid.uuid4()))
    os.makedirs(crop_dir, exist_ok=True)

    spines = []
    for i, box in enumerate(results[0].boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf[0])
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        crop_path = os.path.join(crop_dir, f"spine_{i}.jpg")
        cv2.imwrite(crop_path, crop)

        spines.append({
            "box": [x1, y1, x2, y2],
            "detection_confidence": round(conf, 2),
            "crop_path": crop_path,
        })

    return spines