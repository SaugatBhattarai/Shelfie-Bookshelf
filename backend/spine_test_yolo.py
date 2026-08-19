from pathlib import Path

from ultralytics import YOLO

# Anchored to this file, not the shell's cwd: the photos live in media/scans/,
# the subdirectory ImageField's upload_to="scans/" puts them in.
IMG = Path(__file__).resolve().parent / "media" / "scans" / "0fd3e1b5-18e0-44fc-8bfd-b53909e7f9a6.jpg"

model = YOLO("yolov8n.pt")          # downloads automatically first run    
results = model(str(IMG))           # predict on an image
results[0].show()                   # visualize what it detects
