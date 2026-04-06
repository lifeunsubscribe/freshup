"""
OCR service for extracting text from receipt images using Tesseract.

This service provides the first step in the paper receipt pipeline:
image → OCR text → LLM parsing.
"""

from io import BytesIO
from PIL import Image
import pytesseract


class OCRError(Exception):
    """Raised when OCR processing fails due to corrupt or unreadable images."""
    pass


class OCRService:
    """Service for extracting text from images using Tesseract OCR."""

    @staticmethod
    def extract_text(image_bytes: bytes) -> str:
        """
        Extract text from an image using Tesseract OCR.

        Args:
            image_bytes: Raw bytes of the image file (JPEG, PNG, etc.)

        Returns:
            Extracted text string. May be empty for blank images.

        Raises:
            OCRError: If the image is corrupt or unreadable.

        Example:
            >>> with open("receipt.jpg", "rb") as f:
            ...     image_bytes = f.read()
            >>> text = OCRService.extract_text(image_bytes)
            >>> print(text)
            'COSTCO WHOLESALE\\nTOTAL: $142.37\\n...'
        """
        try:
            # Open image from bytes using Pillow
            image = Image.open(BytesIO(image_bytes))

            # Extract text using Tesseract with default config
            # No PSM mode tuning or preprocessing per scope boundary
            text = pytesseract.image_to_string(image)

            return text

        except (OSError, IOError) as e:
            # Pillow raises OSError/IOError for corrupt/invalid image files
            raise OCRError(f"Failed to read image: {str(e)}") from e
        except pytesseract.TesseractError as e:
            # Tesseract-specific errors during OCR processing
            raise OCRError(f"Tesseract OCR failed: {str(e)}") from e
        except Exception as e:
            # Catch-all for unexpected errors (e.g., out of memory, etc.)
            raise OCRError(f"Unexpected error during OCR: {str(e)}") from e
