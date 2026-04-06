"""
Unit tests for OCR service.

Tests cover:
- Successful text extraction from valid image
- Corrupt/invalid image file handling
- Empty text result from blank image
- Tesseract processing errors

All tests mock pytesseract and Pillow - no real OCR processing is performed.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from io import BytesIO
from PIL import Image
import pytesseract

from src.services.ocr_service import OCRService, OCRError


@pytest.fixture
def mock_image():
    """Create a mock PIL Image object."""
    mock = MagicMock(spec=Image.Image)
    return mock


@pytest.fixture
def valid_image_bytes():
    """Create valid image bytes for testing."""
    # Create a simple 1x1 pixel image in memory
    img = Image.new('RGB', (1, 1), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def test_extract_text_success(mock_image):
    """Test successful text extraction from valid image."""
    # Mock image bytes
    image_bytes = b"fake-image-data"

    # Mock Pillow Image.open to return our mock image
    with patch('src.services.ocr_service.Image.open') as mock_open:
        mock_open.return_value = mock_image

        # Mock pytesseract to return sample receipt text
        with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
            expected_text = "COSTCO WHOLESALE\nTOTAL: $142.37\nTHANK YOU"
            mock_tesseract.return_value = expected_text

            # Execute
            result = OCRService.extract_text(image_bytes)

            # Verify
            assert result == expected_text
            mock_open.assert_called_once()
            mock_tesseract.assert_called_once_with(mock_image)

            # Verify Image.open was called with BytesIO containing our bytes
            call_args = mock_open.call_args[0][0]
            assert isinstance(call_args, BytesIO)


def test_extract_text_empty_result(mock_image):
    """Test extraction from blank image returns empty string."""
    image_bytes = b"fake-blank-image-data"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        mock_open.return_value = mock_image

        with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
            # Tesseract returns empty string for blank images
            mock_tesseract.return_value = ""

            result = OCRService.extract_text(image_bytes)

            assert result == ""
            mock_tesseract.assert_called_once_with(mock_image)


def test_extract_text_corrupt_image_oserror():
    """Test handling of corrupt image that raises OSError."""
    corrupt_bytes = b"not-a-valid-image-file"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        # Pillow raises OSError for corrupt image files
        mock_open.side_effect = OSError("cannot identify image file")

        with pytest.raises(OCRError) as exc_info:
            OCRService.extract_text(corrupt_bytes)

        # Verify error message
        assert "Failed to read image" in str(exc_info.value)
        assert "cannot identify image file" in str(exc_info.value)

        # Verify the original exception is chained
        assert isinstance(exc_info.value.__cause__, OSError)


def test_extract_text_corrupt_image_ioerror():
    """Test handling of corrupt image that raises IOError."""
    corrupt_bytes = b"not-a-valid-image-file"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        # Pillow may also raise IOError for I/O issues
        mock_open.side_effect = IOError("I/O error reading image")

        with pytest.raises(OCRError) as exc_info:
            OCRService.extract_text(corrupt_bytes)

        assert "Failed to read image" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, IOError)


def test_extract_text_tesseract_error(mock_image):
    """Test handling of Tesseract processing errors."""
    image_bytes = b"fake-image-data"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        mock_open.return_value = mock_image

        with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
            # Tesseract raises TesseractError for OCR processing failures
            mock_tesseract.side_effect = pytesseract.TesseractError(
                status=1,
                message="Tesseract processing failed"
            )

            with pytest.raises(OCRError) as exc_info:
                OCRService.extract_text(image_bytes)

            assert "Tesseract OCR failed" in str(exc_info.value)
            assert isinstance(exc_info.value.__cause__, pytesseract.TesseractError)


def test_extract_text_unexpected_error(mock_image):
    """Test handling of unexpected errors during OCR."""
    image_bytes = b"fake-image-data"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        mock_open.return_value = mock_image

        with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
            # Simulate unexpected error (e.g., out of memory)
            mock_tesseract.side_effect = RuntimeError("Out of memory")

            with pytest.raises(OCRError) as exc_info:
                OCRService.extract_text(image_bytes)

            assert "Unexpected error during OCR" in str(exc_info.value)
            assert "Out of memory" in str(exc_info.value)
            assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_extract_text_with_real_image_bytes(valid_image_bytes):
    """Test extraction with actual image bytes (still mocking pytesseract)."""
    # This test uses real image bytes to verify BytesIO handling
    # but still mocks pytesseract to avoid external dependencies

    with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
        expected_text = "Sample receipt text"
        mock_tesseract.return_value = expected_text

        result = OCRService.extract_text(valid_image_bytes)

        # Verify result
        assert result == expected_text

        # Verify pytesseract was called with a PIL Image
        mock_tesseract.assert_called_once()
        called_image = mock_tesseract.call_args[0][0]
        assert isinstance(called_image, Image.Image)


def test_extract_text_whitespace_handling(mock_image):
    """Test that whitespace in OCR results is preserved."""
    image_bytes = b"fake-image-data"

    with patch('src.services.ocr_service.Image.open') as mock_open:
        mock_open.return_value = mock_image

        with patch('src.services.ocr_service.pytesseract.image_to_string') as mock_tesseract:
            # Tesseract often returns text with extra whitespace/newlines
            text_with_whitespace = "\n  STORE NAME  \n\n  Item 1    $5.99\n  \n"
            mock_tesseract.return_value = text_with_whitespace

            result = OCRService.extract_text(image_bytes)

            # Verify whitespace is preserved (no automatic stripping)
            assert result == text_with_whitespace
