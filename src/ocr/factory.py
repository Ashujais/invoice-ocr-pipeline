import logging
from typing import Optional
from src.ocr.base import BaseOCREngine
from src.ocr.rapidocr_engine import RapidOCREngine
from src.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger(__name__)


def get_ocr_engine(engine_name: str = "auto", tesseract_cmd: Optional[str] = None) -> BaseOCREngine:
    """
    Factory function to instantiate the requested or best available local OCR engine.
    
    Args:
        engine_name: 'auto', 'rapidocr', or 'tesseract'.
        tesseract_cmd: Optional path to tesseract binary if using Tesseract.
        
    Returns:
        An instance of BaseOCREngine.
    """
    engine_name = engine_name.lower().strip()

    if engine_name == "rapidocr":
        return RapidOCREngine()

    if engine_name == "tesseract":
        return TesseractEngine(tesseract_cmd=tesseract_cmd)

    if engine_name == "auto":
        # First try RapidOCR (bundled ONNX runtime, cross-platform)
        try:
            return RapidOCREngine()
        except Exception as e:
            logger.debug(f"RapidOCR unavailable: {e}. Trying Tesseract...")

        # Fallback to Tesseract
        try:
            return TesseractEngine(tesseract_cmd=tesseract_cmd)
        except Exception as e:
            logger.debug(f"Tesseract unavailable: {e}.")

        raise RuntimeError(
            "No working OCR engine found. Please install rapidocr-onnxruntime "
            "(pip install rapidocr-onnxruntime) or install Tesseract OCR."
        )

    raise ValueError(f"Unknown OCR engine '{engine_name}'. Supported: 'auto', 'rapidocr', 'tesseract'")
