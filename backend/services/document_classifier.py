from pathlib import Path
import cv2

def detect_document_type(image_path: Path, requested: str | None = None):
    allowed = {'passport','visa','national_id','driving_licence','permit'}
    if requested in allowed:
        return requested, 0.98, 'Officer selected document type'
    img = cv2.imread(str(image_path))
    if img is None:
        return 'unknown', 0.0, 'Image could not be decoded'
    h, w = img.shape[:2]
    ratio = w / max(h, 1)
    # Lightweight heuristic; a production model can replace this classifier.
    if 1.35 < ratio < 1.75:
        return 'passport', 0.72, 'Aspect-ratio heuristic suggests passport/travel document'
    return 'unknown', 0.35, 'No high-confidence document-type classifier result'
