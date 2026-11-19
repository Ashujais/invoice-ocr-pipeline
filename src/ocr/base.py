from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union


class BaseOCREngine(ABC):
    """Abstract interface for local OCR engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the OCR engine."""
        pass

    @abstractmethod
    def extract_text(self, image_path: Union[str, Path]) -> str:
        """
        Run OCR on the given image path and return raw extracted text.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Extracted text as a string.
            
        Raises:
            FileNotFoundError: If image does not exist.
            RuntimeError: If OCR processing fails.
        """
        pass
