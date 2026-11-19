from pathlib import Path
from typing import Union
from src.ocr.base import BaseOCREngine


class RapidOCREngine(BaseOCREngine):
    """
    Local OCR engine backed by RapidOCR (ONNX runtime).
    Free, local, cross-platform, and requires no external system binary installation.
    """

    def __init__(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        except ImportError as e:
            raise ImportError(
                "rapidocr-onnxruntime is not installed. "
                "Install it with: pip install rapidocr-onnxruntime"
            ) from e

    @property
    def name(self) -> str:
        return "RapidOCR"

    def extract_text(self, image_path: Union[str, Path]) -> str:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: {path}")

        result, _ = self._engine(str(path))
        if not result:
            return ""

        # RapidOCR returns list of [box, text, score]
        # Box format: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        # Sort primarily by y (top to bottom), secondarily by x (left to right)
        def sort_key(item):
            box = item[0]
            # Average Y of top two vertices, with line grouping threshold of 10px
            top_y = (box[0][1] + box[1][1]) / 2.0
            left_x = box[0][0]
            # Quantize Y to line height bucket (approx 12px) to keep same-line text together
            line_bucket = round(top_y / 12.0)
            return (line_bucket, left_x)

        sorted_lines = sorted(result, key=sort_key)
        extracted_lines = [item[1].strip() for item in sorted_lines if item[1] and item[1].strip()]
        return "\n".join(extracted_lines)
