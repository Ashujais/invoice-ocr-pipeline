import os
from pathlib import Path
from typing import Union, Optional
from src.ocr.base import BaseOCREngine


class TesseractEngine(BaseOCREngine):
    """
    Local OCR engine backed by Google Tesseract via pytesseract.
    Requires Tesseract OCR binary to be installed on the system.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        try:
            import pytesseract
            self._pytesseract = pytesseract
        except ImportError as e:
            raise ImportError(
                "pytesseract is not installed. Install it with: pip install pytesseract"
            ) from e

        # Resolve tesseract executable path
        cmd = (
            tesseract_cmd
            or os.environ.get("TESSERACT_CMD")
            or self._detect_tesseract_binary()
        )
        if cmd:
            self._pytesseract.pytesseract.tesseract_cmd = cmd

    @property
    def name(self) -> str:
        return "Tesseract"

    def _detect_tesseract_binary(self) -> Optional[str]:
        """Look for tesseract binary in common standard directories."""
        import shutil

        # Check PATH
        path_binary = shutil.which("tesseract")
        if path_binary:
            return path_binary

        # Common Windows paths
        win_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for wp in win_paths:
            if wp and os.path.isfile(wp):
                return wp

        # Common Linux / macOS paths
        nix_paths = ["/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]
        for np in nix_paths:
            if os.path.isfile(np):
                return np

        return None

    def extract_text(self, image_path: Union[str, Path]) -> str:
        from PIL import Image

        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: {path}")

        try:
            image = Image.open(path)
            text = self._pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            raise RuntimeError(
                f"Tesseract OCR failed: {e}. Ensure Tesseract is installed and on PATH."
            ) from e
