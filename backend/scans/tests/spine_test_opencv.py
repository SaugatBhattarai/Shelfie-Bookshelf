import cv2
import numpy as np
from pathlib import Path

IMG = Path(__file__).resolve().parent / "media" / "scans" / "10304eb0-373b-4726-8c9c-05479b7025c1.jpg"


def cluster_boundaries(boundaries, min_gap=20):
    """Collapse nearby boundary columns into a single representative column."""
    if not boundaries:
        return []

    clusters = [[boundaries[0]]]
    for boundary in boundaries[1:]:
        if boundary - clusters[-1][-1] < min_gap:
            clusters[-1].append(boundary) # same cluster
        else:
            clusters.append([boundary]) # start new cluster

    return [int(round(np.mean(cluster))) for cluster in clusters]


def segment_spines_classical(image_path, min_width=20):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # sum edge intensity per column -> vertical gaps between spines show as edge peaks
    col_sums = np.sum(edges, axis=0)
    threshold = np.mean(col_sums) * 1.5
    boundaries = [i for i, v in enumerate(col_sums) if v > threshold]
    
    # cluster nearby boundaries into spine dividers
    spine_edges = cluster_boundaries(boundaries, min_gap=min_width)
    crops = [img[:, spine_edges[i]:spine_edges[i+1]] for i in range(len(spine_edges)-1)]
    return crops, spine_edges


def main():
    crops, spine_edges = segment_spines_classical(str(IMG))
    print(f"Detected {len(crops)} spine(s) in {IMG}")

    image = cv2.imread(str(IMG))
    segmented = image.copy()

    # Show each detected divider and spine bounding box in the preview.
    for edge in spine_edges:
        cv2.line(
            segmented,
            (edge, 0),
            (edge, segmented.shape[0] - 1),
            (0, 255, 255),
            2,
        )

    for left, right in zip(spine_edges, spine_edges[1:]):
        cv2.rectangle(
            segmented,
            (left, 0),
            (right - 1, segmented.shape[0] - 1),
            (0, 255, 0),
            2,
        )

    # Resize the displayed result to exactly 900 by 600 pixels.
    segmented = cv2.resize(segmented, (900, 600), interpolation=cv2.INTER_AREA)
    cv2.imshow("Segmented spines", segmented)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()


