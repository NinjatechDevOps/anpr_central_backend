"""
File Storage Service - Handles local and S3 file storage for ANPR images.
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from loguru import logger

from app.core.config import settings


class StorageService:
    """Service for handling file uploads to local filesystem or S3."""

    def __init__(self):
        """Initialize storage service based on configuration."""
        self.storage_type = settings.STORAGE_TYPE.lower()

        if self.storage_type == "s3":
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            self.folder_prefix = settings.S3_FOLDER_PREFIX
            logger.info(f"Storage service initialized with S3: bucket={self.bucket_name}")
        else:
            self.upload_dir = Path(settings.UPLOAD_DIR)
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage service initialized with local storage: {self.upload_dir}")

    def _generate_file_path(self, organization_id: int, original_filename: str) -> str:
        """
        Generate a unique file path for storing the image.

        Args:
            organization_id: ID of the organization uploading the file
            original_filename: Original name of the uploaded file

        Returns:
            relative_path: Relative path from uploads directory (e.g., "detections/1/2025/01/uuid.jpg")
                          This will be accessible via /uploads/{relative_path}
        """
        # Extract file extension
        file_ext = Path(original_filename).suffix.lower()
        if not file_ext:
            file_ext = ".jpg"  # Default to jpg if no extension

        # Generate unique filename: detections/{org_id}/{year}/{month}/{uuid}.{ext}
        now = datetime.utcnow()
        year_month = f"{now.year}/{now.month:02d}"
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}{file_ext}"

        # Build relative path - this will be stored in DB and accessible via /uploads/
        relative_path = f"detections/{organization_id}/{year_month}/{unique_filename}"

        return relative_path

    async def save_file(
        self,
        file: UploadFile,
        organization_id: int
    ) -> str:
        """
        Save uploaded file to storage (local or S3).

        Args:
            file: FastAPI UploadFile object
            organization_id: ID of the organization

        Returns:
            relative_path: Relative path that can be used to access file via /uploads/{relative_path}

        Raises:
            Exception: If file upload fails
        """
        relative_path = self._generate_file_path(
            organization_id,
            file.filename or "image.jpg"
        )

        try:
            # Read file content
            file_content = await file.read()

            if self.storage_type == "s3":
                # Upload to S3
                s3_key = f"{self.folder_prefix}/{relative_path}"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=file.content_type or "image/jpeg",
                    Metadata={
                        'organization_id': str(organization_id),
                        'original_filename': file.filename or "unknown"
                    }
                )
                logger.info(f"File uploaded to S3: s3://{self.bucket_name}/{s3_key}")
            else:
                # Save to local filesystem
                full_path = self.upload_dir / relative_path
                full_path.parent.mkdir(parents=True, exist_ok=True)

                with open(full_path, 'wb') as f:
                    f.write(file_content)

                logger.info(f"File saved locally: {full_path}")

            return relative_path

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise Exception(f"Failed to upload file to S3: {str(e)}")
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise Exception(f"Failed to save file: {str(e)}")

    def get_file(self, file_path: str) -> bytes:
        """
        Retrieve file from storage.

        Args:
            file_path: Relative path to the file in storage (e.g., "detections/1/2025/01/uuid.jpg")

        Returns:
            File content as bytes

        Raises:
            Exception: If file retrieval fails
        """
        try:
            if self.storage_type == "s3":
                # Download from S3
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                return response['Body'].read()
            else:
                # Read from local filesystem - prepend upload_dir to relative path
                full_path = self.upload_dir / file_path
                with open(full_path, 'rb') as f:
                    return f.read()

        except ClientError as e:
            logger.error(f"S3 download failed: {e}")
            raise Exception(f"Failed to download file from S3: {str(e)}")
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise Exception(f"File not found: {file_path}")
        except Exception as e:
            logger.error(f"File retrieval failed: {e}")
            raise Exception(f"Failed to retrieve file: {str(e)}")

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage.

        Args:
            file_path: Path to the file in storage

        Returns:
            True if deletion was successful

        Raises:
            Exception: If file deletion fails
        """
        try:
            if self.storage_type == "s3":
                # Delete from S3
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                logger.info(f"File deleted from S3: {file_path}")
            else:
                # Delete from local filesystem
                local_path = Path(file_path)
                if local_path.exists():
                    local_path.unlink()
                    logger.info(f"File deleted locally: {file_path}")
                else:
                    logger.warning(f"File not found for deletion: {file_path}")

            return True

        except ClientError as e:
            logger.error(f"S3 deletion failed: {e}")
            raise Exception(f"Failed to delete file from S3: {str(e)}")
        except Exception as e:
            logger.error(f"File deletion failed: {e}")
            raise Exception(f"Failed to delete file: {str(e)}")

    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            file_path: Path to the file in storage

        Returns:
            True if file exists, False otherwise
        """
        try:
            if self.storage_type == "s3":
                # Check S3
                self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                return True
            else:
                # Check local filesystem
                return Path(file_path).exists()

        except ClientError:
            return False
        except Exception:
            return False


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the singleton storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
