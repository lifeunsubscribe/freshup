"""
Receipt processing endpoints for FreshUp.

Provides endpoints for users to submit receipts for async LLM parsing and
confirm parsed receipt data to add items to their inventory. All endpoints
are scoped to the authenticated user.

Logging Policy:
    Receipt text content is NOT logged as it may contain sensitive information
    (e.g., prescription names, dietary restrictions). Logs include operational
    metadata (user_id, task_id, timestamps) for debugging while protecting
    user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID, uuid4
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.config import get_settings
from src.db.database import get_db
from src.db.models.user import User
from src.schemas.receipt import (
    ReceiptSubmitRequest,
    ReceiptSubmitResponse,
    ReceiptConfirmRequest,
    ReceiptConfirmResponse,
)
from src.schemas.inventory import InventoryItemResponse
from src.services.receipt_service import submit_receipt, confirm_receipt_items
from src.services.ocr_service import OCRService, OCRError
from src.services.storage_service import get_storage_client
from src.middleware.auth import get_current_user
from src.exceptions import DomainException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _detect_image_type(image_bytes: bytes) -> Optional[str]:
    """
    Detect image type from magic bytes.

    Returns 'jpeg' for JPEG images, 'png' for PNG images, or None for other types.
    This defends against Content-Type header spoofing by validating actual file content.
    """
    if not image_bytes:
        return None

    # JPEG magic bytes: FF D8 FF
    if image_bytes[:3] == b'\xff\xd8\xff':
        return 'jpeg'

    # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
    if image_bytes[:8] == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a':
        return 'png'

    return None


def _cleanup_minio_object(s3_client, bucket: str, object_path: str) -> None:
    """
    Delete a MinIO object, logging any errors without re-raising.

    Used for compensation logic when operations after MinIO upload fail
    (e.g., OCR extraction, task creation) to prevent orphan objects.

    Args:
        s3_client: boto3 S3 client
        bucket: MinIO bucket name
        object_path: Object key/path to delete

    Note:
        Does not raise exceptions - cleanup failures are logged but don't
        block error propagation from the original failure.
    """
    try:
        s3_client.delete_object(Bucket=bucket, Key=object_path)
        logger.info(f"Cleaned up MinIO object after failure: {object_path}")
    except Exception as e:
        # Log cleanup failure but don't raise - original error takes precedence
        logger.error(
            f"Failed to cleanup MinIO object {object_path} after operation failure: {e}"
        )
        logger.debug(f"MinIO cleanup error details: {e}")


@router.post(
    "",
    response_model=ReceiptSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def submit_receipt_for_processing(
    request: ReceiptSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit receipt text for async LLM parsing.

    Accepts receipt text (e.g., from Costco digital receipt copy-paste) and
    optional store name, creates a ProcessingTask for background LLM parsing,
    and returns 202 Accepted with task ID for status polling.

    This is text-only input for digital receipts. File upload is handled
    separately in Phase 4B.

    Multi-tenant isolation: Task is created with current_user.id for ownership.

    Args:
        request: ReceiptSubmitRequest with receipt_text and optional store_name
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ReceiptSubmitResponse with task_id, status='pending', and message

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If receipt_text is empty, too short, or too long
        HTTPException(500): If database error occurs during task creation
    """
    try:
        # Submit receipt via service layer
        task = submit_receipt(
            receipt_text=request.receipt_text,
            user_id=current_user.id,
            db=db,
            store_name=request.store_name,
        )

        return ReceiptSubmitResponse(
            task_id=task.id,
            status=task.status,
            message="Receipt submitted for processing"
        )

    except DomainException as e:
        # Convert domain exceptions to HTTPException
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        # Convert runtime errors to 500
        logger.error(f"Runtime error in submit_receipt_for_processing: user_id={current_user.id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/upload",
    response_model=ReceiptSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def upload_receipt_image(
    file: UploadFile = File(...),
    store_hint: Optional[str] = Query(None, max_length=255),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload receipt image for OCR extraction and async LLM parsing.

    Accepts a multipart form upload with an image file (JPEG or PNG), stores
    the image in MinIO, extracts text via Tesseract OCR, creates a ProcessingTask
    for background LLM parsing, and returns 202 Accepted with task ID for polling.

    This endpoint handles paper receipt photos. For digital receipt text, use
    POST /receipts instead.

    Multi-tenant isolation: Image stored under user's directory, task owned by user.

    Args:
        file: Uploaded image file (JPEG or PNG, max 10MB via FastAPI defaults)
        store_hint: Optional store name hint for parsing (e.g., 'Costco')
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ReceiptSubmitResponse with task_id, status='pending', and message

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If file is not a valid image type (JPEG/PNG)
        HTTPException(413): If file size exceeds 10MB limit
        HTTPException(500): If OCR, MinIO storage, or database error occurs
    """
    # Validate file type (accept only JPEG and PNG images)
    allowed_types = {"image/jpeg", "image/png"}
    if file.content_type not in allowed_types:
        logger.warning(
            f"Invalid file type upload attempt by user {current_user.id}: {file.content_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only JPEG and PNG images are supported."
        )

    try:
        # Read image bytes from upload
        image_bytes = file.file.read()
        # Ensure file handle is closed to prevent descriptor exhaustion
        file.file.close()

        # Validate actual file type using magic bytes (defense against Content-Type spoofing)
        detected_type = _detect_image_type(image_bytes)
        if detected_type not in {"jpeg", "png"}:
            logger.warning(
                f"Magic byte validation failed for user {current_user.id}: "
                f"Content-Type={file.content_type}, detected={detected_type}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Only JPEG and PNG images are supported."
            )

        # Validate file size (max 10MB to prevent memory exhaustion attacks)
        max_size_bytes = 10 * 1024 * 1024  # 10MB
        if len(image_bytes) > max_size_bytes:
            logger.warning(
                f"Oversized file upload attempt by user {current_user.id}: {len(image_bytes)} bytes"
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of 10MB."
            )

        # Generate unique filename with original extension
        # UUID prevents conflicts and path traversal attacks
        file_ext = "jpg" if file.content_type == "image/jpeg" else "png"
        file_uuid = uuid4()
        filename = f"{file_uuid}.{file_ext}"
        # Store under user-specific directory for multi-tenant isolation
        minio_path = f"receipts/{current_user.id}/{filename}"

        # Store image in MinIO before OCR to preserve original for debugging
        settings = get_settings()
        s3_client = get_storage_client()

        s3_client.put_object(
            Bucket=settings.minio_bucket,
            Key=minio_path,
            Body=image_bytes,
            ContentType=file.content_type,
        )

        logger.info(
            f"Uploaded receipt image to MinIO: user_id={current_user.id}, "
            f"path={minio_path}"
        )

        # Wrap post-upload operations in try-except to cleanup MinIO object on failure
        try:
            # Extract text from image using OCR service
            ocr_text = OCRService.extract_text(image_bytes)

            # Validate OCR extracted at least some text
            if not ocr_text or len(ocr_text.strip()) < 10:
                logger.warning(
                    f"OCR extracted insufficient text from image: user_id={current_user.id}, "
                    f"path={minio_path}, text_length={len(ocr_text.strip())}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to extract readable text from image. Please ensure the image is clear and readable."
                )

            logger.debug(
                f"OCR extracted text from image: user_id={current_user.id}, "
                f"text_length={len(ocr_text)}"
            )

            # Submit receipt via service layer (creates ProcessingTask)
            # OCR text goes into input_reference (same format as text submission)
            task = submit_receipt(
                receipt_text=ocr_text,
                user_id=current_user.id,
                db=db,
                store_name=store_hint,
            )

            # Update task metadata to track image source and MinIO path
            # This allows:
            # 1. Future filtering/analytics (e.g., "image vs text receipt success rate")
            # 2. Linking task back to original image for debugging OCR issues
            # 3. Potential re-processing with different OCR settings in Phase 4B
            task.task_metadata = {
                "source": "image",
                "minio_path": minio_path,
                "store_hint": store_hint,
            }
            db.commit()
            db.refresh(task)

            return ReceiptSubmitResponse(
                task_id=task.id,
                status=task.status,
                message="Receipt image uploaded and submitted for processing"
            )

        except OCRError as e:
            # OCR processing failed (corrupt image, tesseract error, etc.)
            _cleanup_minio_object(s3_client, settings.minio_bucket, minio_path)
            logger.error(
                f"OCR error during receipt upload: user_id={current_user.id}, "
                f"filename={file.filename}"
            )
            logger.debug(f"OCR error details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process image. The image may be corrupt or unreadable."
            )
        except DomainException as e:
            # Convert domain exceptions to HTTPException after cleanup
            _cleanup_minio_object(s3_client, settings.minio_bucket, minio_path)
            raise HTTPException(status_code=e.http_status_code, detail=e.message)
        except SQLAlchemyError as e:
            # Database error during task creation or metadata update
            _cleanup_minio_object(s3_client, settings.minio_bucket, minio_path)
            logger.error(
                f"Database error during receipt upload: user_id={current_user.id}, "
                f"filename={file.filename}"
            )
            logger.debug(f"Database error details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the processing task"
            )
        except HTTPException:
            # Re-raise HTTPExceptions (e.g., validation errors) after cleanup
            _cleanup_minio_object(s3_client, settings.minio_bucket, minio_path)
            raise
        except Exception as e:
            # Catch other unexpected errors during post-upload operations
            # Don't re-catch HTTPException here - let it propagate
            if isinstance(e, HTTPException):
                raise
            _cleanup_minio_object(s3_client, settings.minio_bucket, minio_path)
            logger.error(
                f"Error during receipt processing: user_id={current_user.id}, "
                f"filename={file.filename}"
            )
            logger.debug(f"Processing error details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing the receipt image"
            )

    except HTTPException:
        # Re-raise HTTPExceptions from inner block
        raise
    except Exception as e:
        # Catch S3/MinIO upload errors (no cleanup needed - upload failed)
        logger.error(
            f"Error during receipt image upload to MinIO: user_id={current_user.id}, "
            f"filename={file.filename}"
        )
        logger.debug(f"MinIO upload error details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while uploading the receipt image"
        )


@router.post(
    "/{task_id}/confirm",
    response_model=ReceiptConfirmResponse,
    status_code=status.HTTP_201_CREATED
)
def confirm_receipt(
    task_id: UUID,
    request: ReceiptConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm receipt inventory candidates and create inventory items.

    Users review parsed receipt items, optionally edit quantities/categories,
    and confirm to add items to their inventory. This endpoint creates
    InventoryItem records from the confirmed candidates.

    Multi-tenant isolation: Only the user who created the parsing task can
    confirm its items. Task ownership is validated at the service layer.

    Args:
        task_id: UUID of the receipt parsing task to confirm
        request: ReceiptConfirmRequest with list of inventory candidates
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ReceiptConfirmResponse with created item count and full item details

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If task doesn't exist or doesn't belong to user
        HTTPException(400): If task status is not "completed"
        HTTPException(422): If validation fails (empty items, invalid enums, etc.)
        HTTPException(500): If database error occurs during creation
    """
    try:
        # Confirm items via service layer (validates task ownership and status)
        created_items = confirm_receipt_items(
            task_id=task_id,
            candidates=request.items,
            user_id=current_user.id,
            db=db
        )

        # Convert to response schemas
        items_response = [
            InventoryItemResponse.model_validate(item)
            for item in created_items
        ]

        logger.info(
            f"User {current_user.id} confirmed {len(created_items)} items "
            f"from task {task_id}"
        )

        return ReceiptConfirmResponse(
            created_count=len(created_items),
            items=items_response
        )

    except DomainException as e:
        # Convert domain exceptions to HTTPException
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        # Convert runtime errors to 500
        logger.error(f"Runtime error in confirm_receipt: user_id={current_user.id}, task_id={task_id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during receipt confirmation for user {current_user.id}, "
            f"task {task_id}"
        )
        logger.debug(f"Database error occurred during receipt confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while confirming the receipt"
        )
