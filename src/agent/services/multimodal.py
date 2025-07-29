import base64
import hashlib
import io
import json
import mimetypes
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from a2a.types import DataPart, FilePart, FileWithBytes, Part
from PIL import Image

logger = structlog.get_logger(__name__)


class MultiModalProcessor:
    # Supported image formats
    IMAGE_FORMATS = {
        "image/png": [".png"],
        "image/jpeg": [".jpg", ".jpeg"],
        "image/webp": [".webp"],
        "image/gif": [".gif"],
        "image/bmp": [".bmp"],
    }

    # Supported document formats
    DOCUMENT_FORMATS = {
        "application/pdf": [".pdf"],
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        "text/plain": [".txt"],
        "text/csv": [".csv"],
        "application/json": [".json"],
    }

    # File size limits (in MB)
    MAX_FILE_SIZES = {"image": 10, "document": 50, "default": 100}

    @classmethod
    def extract_parts_by_type(cls, parts: list[Part], mime_type_prefix: str) -> list[Part]:
        matching_parts = []

        for part in parts:
            # Check FilePart (for images, documents, etc.)
            if hasattr(part, "root") and part.root.kind == "file":
                file_part = part.root
                if file_part.file.mimeType and file_part.file.mimeType.startswith(mime_type_prefix):
                    matching_parts.append(part)
            # Check DataPart (for structured data)
            elif hasattr(part, "root") and part.root.kind == "data":
                data_part = part.root
                if (
                    hasattr(data_part, "mimeType")
                    and data_part.mimeType
                    and data_part.mimeType.startswith(mime_type_prefix)
                ):
                    matching_parts.append(part)

        return matching_parts

    @classmethod
    def extract_image_parts(cls, parts: list[Part]) -> list[dict[str, str]]:
        image_parts = []

        for part in parts:
            # Images should be FilePart according to A2A spec
            if hasattr(part, "root") and part.root.kind == "file":
                file_part = part.root
                if file_part.file.mimeType and file_part.file.mimeType.startswith("image/"):
                    # Return dict with file info for easier processing
                    image_info = {
                        "name": file_part.file.name or "image",
                        "mimeType": file_part.file.mimeType,
                        "data": file_part.file.bytes if hasattr(file_part.file, "bytes") else None,
                        "uri": file_part.file.uri if hasattr(file_part.file, "uri") else None,
                    }
                    image_parts.append(image_info)

        return image_parts

    @classmethod
    def extract_document_parts(cls, parts: list[Part]) -> list[dict[str, str]]:
        doc_parts = []

        for part in parts:
            # Documents should be FilePart according to A2A spec
            if hasattr(part, "root") and part.root.kind == "file":
                file_part = part.root
                if file_part.file.mimeType and file_part.file.mimeType in cls.DOCUMENT_FORMATS:
                    # Return dict with file info for easier processing
                    doc_info = {
                        "name": file_part.file.name or "document",
                        "mimeType": file_part.file.mimeType,
                        "data": file_part.file.bytes if hasattr(file_part.file, "bytes") else None,
                        "uri": file_part.file.uri if hasattr(file_part.file, "uri") else None,
                    }
                    doc_parts.append(doc_info)

        return doc_parts

    @classmethod
    def process_image(cls, image_data: str, mime_type: str) -> dict[str, Any]:
        try:
            # Decode base64 data
            image_bytes = base64.b64decode(image_data)

            # Open image with PIL
            image = Image.open(io.BytesIO(image_bytes))

            # Extract metadata
            metadata = {
                "format": image.format,
                "mode": image.mode,
                "size": image.size,
                "width": image.width,
                "height": image.height,
                "mime_type": mime_type,
            }

            # Convert to numpy array for processing
            image_array = np.array(image)

            # Basic image analysis
            metadata["shape"] = image_array.shape
            metadata["dtype"] = str(image_array.dtype)

            # Calculate basic statistics
            if len(image_array.shape) == 2:  # Grayscale
                metadata["mean_brightness"] = float(np.mean(image_array))
                metadata["std_brightness"] = float(np.std(image_array))
            elif len(image_array.shape) == 3:  # Color
                metadata["mean_brightness"] = float(np.mean(image_array))
                metadata["channel_means"] = [float(np.mean(image_array[:, :, i])) for i in range(image_array.shape[2])]

            # Generate hash for deduplication
            metadata["hash"] = hashlib.sha256(image_bytes).hexdigest()

            return {
                "success": True,
                "metadata": metadata,
                "image": image,  # Return PIL Image object for further processing
            }

        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def save_image(cls, image: Image.Image, output_path: str | Path, format: str | None = None) -> bool:
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine format from extension if not provided
            if not format:
                format = output_path.suffix[1:].upper()
                if format == "JPG":
                    format = "JPEG"

            image.save(output_path, format=format)
            logger.info(f"Saved image to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            return False

    @classmethod
    def resize_image(cls, image: Image.Image, max_size: tuple) -> Image.Image:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image

    @classmethod
    def convert_image_format(cls, image: Image.Image, target_format: str) -> bytes:
        output = io.BytesIO()

        # Handle format conversions
        if target_format.upper() == "JPEG" and image.mode == "RGBA":
            # Convert RGBA to RGB for JPEG
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])
            image = rgb_image

        image.save(output, format=target_format.upper())
        return output.getvalue()

    @classmethod
    def encode_image_base64(cls, image: Image.Image, format: str = "PNG") -> str:
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @classmethod
    def process_document(cls, doc_data: str, mime_type: str) -> dict[str, Any]:
        try:
            # Decode base64 data
            doc_bytes = base64.b64decode(doc_data)

            # Extract basic metadata
            metadata = {
                "mime_type": mime_type,
                "size_bytes": len(doc_bytes),
                "size_mb": len(doc_bytes) / (1024 * 1024),
                "hash": hashlib.sha256(doc_bytes).hexdigest(),
            }

            # Process based on document type
            if mime_type == "text/plain":
                # Decode text content
                try:
                    content = doc_bytes.decode("utf-8")
                    metadata["content"] = content
                    metadata["line_count"] = len(content.split("\n"))
                    metadata["word_count"] = len(content.split())
                except UnicodeDecodeError:
                    metadata["error"] = "Failed to decode text content"

            elif mime_type == "application/json":
                # Parse JSON content
                try:
                    content = json.loads(doc_bytes.decode("utf-8"))
                    metadata["content"] = content
                    metadata["keys"] = list(content.keys()) if isinstance(content, dict) else None
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    metadata["error"] = f"Failed to parse JSON: {e}"

            return {"success": True, "metadata": metadata}

        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def validate_file_size(cls, data: str, file_type: str = "default") -> bool:
        # Calculate size in MB
        size_bytes = len(base64.b64decode(data))
        size_mb = size_bytes / (1024 * 1024)

        # Get limit for file type
        limit_mb = cls.MAX_FILE_SIZES.get(file_type, cls.MAX_FILE_SIZES["default"])

        return size_mb <= limit_mb

    @classmethod
    def create_data_part(cls, file_path: str | Path, name: str | None = None) -> DataPart | None:
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Determine mime type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

            # Read and encode file
            with open(file_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")

            # Create DataPart
            return DataPart(name=name or file_path.name, mimeType=mime_type, data=data)

        except Exception as e:
            logger.error(f"Failed to create DataPart from file: {e}")
            return None

    @classmethod
    def create_file_part(cls, file_path: str | Path, name: str | None = None) -> FilePart | None:
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Determine mime type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

            # Read file bytes
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # Create FileWithBytes object
            file_with_bytes = FileWithBytes(name=name or file_path.name, mimeType=mime_type, bytes=file_bytes)

            # Create FilePart
            return FilePart(file=file_with_bytes)

        except Exception as e:
            logger.error(f"Failed to create FilePart from file: {e}")
            return None

    @classmethod
    def extract_all_content(cls, parts: list[Part]) -> dict[str, list[Any]]:
        content = {"text": [], "images": [], "documents": [], "other": []}

        for part in parts:
            if hasattr(part, "root"):
                if part.root.kind == "text":
                    content["text"].append(part.root.text)

                elif part.root.kind == "file":
                    file_part = part.root
                    file_info = {
                        "name": file_part.file.name or "file",
                        "mime_type": file_part.file.mimeType,
                        "data": file_part.file.bytes if hasattr(file_part.file, "bytes") else None,
                        "uri": file_part.file.uri if hasattr(file_part.file, "uri") else None,
                    }

                    if file_part.file.mimeType and file_part.file.mimeType.startswith("image/"):
                        content["images"].append(file_info)
                    elif file_part.file.mimeType and file_part.file.mimeType in cls.DOCUMENT_FORMATS:
                        content["documents"].append(file_info)
                    else:
                        content["other"].append(file_info)

                elif part.root.kind == "data":
                    data_part = part.root
                    content["other"].append(
                        {"name": "structured_data", "mime_type": "application/json", "data": data_part.data}
                    )

        return content


class MultiModalService:
    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._initialized = False

        # Configuration options
        self.max_image_size_mb = config.get("max_image_size_mb", 10)
        self.max_document_size_mb = config.get("max_document_size_mb", 50)
        self.supported_image_formats = config.get(
            "supported_image_formats", list(MultiModalProcessor.IMAGE_FORMATS.keys())
        )
        self.supported_document_formats = config.get(
            "supported_document_formats", list(MultiModalProcessor.DOCUMENT_FORMATS.keys())
        )

    async def initialize(self) -> None:
        logger.info(f"Multi-modal service {self.name} initialized")
        self._initialized = True

    async def close(self) -> None:
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        try:
            return {
                "status": "healthy",
                "supported_image_formats": len(self.supported_image_formats),
                "supported_document_formats": len(self.supported_document_formats),
                "max_image_size_mb": self.max_image_size_mb,
                "max_document_size_mb": self.max_document_size_mb,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # Delegate to MultiModalProcessor for all processing methods
    def extract_image_parts(self, parts: list[Part]) -> list[dict[str, str]]:
        return MultiModalProcessor.extract_image_parts(parts)

    def extract_document_parts(self, parts: list[Part]) -> list[dict[str, str]]:
        return MultiModalProcessor.extract_document_parts(parts)

    def extract_all_content(self, parts: list[Part]) -> dict[str, list[Any]]:
        return MultiModalProcessor.extract_all_content(parts)

    def process_image(self, image_data: str, mime_type: str) -> dict[str, Any]:
        # Validate size if configured
        if not MultiModalProcessor.validate_file_size(image_data, "image"):
            return {"success": False, "error": f"Image exceeds maximum size of {self.max_image_size_mb}MB"}

        # Check format support
        if mime_type not in self.supported_image_formats:
            return {"success": False, "error": f"Unsupported image format: {mime_type}"}

        return MultiModalProcessor.process_image(image_data, mime_type)

    def process_document(self, doc_data: str, mime_type: str) -> dict[str, Any]:
        # Validate size if configured
        if not MultiModalProcessor.validate_file_size(doc_data, "document"):
            return {"success": False, "error": f"Document exceeds maximum size of {self.max_document_size_mb}MB"}

        # Check format support
        if mime_type not in self.supported_document_formats:
            return {"success": False, "error": f"Unsupported document format: {mime_type}"}

        return MultiModalProcessor.process_document(doc_data, mime_type)

    def resize_image(self, image: Image.Image, max_size: tuple) -> Image.Image:
        return MultiModalProcessor.resize_image(image, max_size)

    def convert_image_format(self, image: Image.Image, target_format: str) -> bytes:
        return MultiModalProcessor.convert_image_format(image, target_format)

    def encode_image_base64(self, image: Image.Image, format: str = "PNG") -> str:
        return MultiModalProcessor.encode_image_base64(image, format)

    def create_data_part(self, file_path: str | Path, name: str | None = None) -> DataPart | None:
        return MultiModalProcessor.create_data_part(file_path, name)

    def create_file_part(self, file_path: str | Path, name: str | None = None) -> FilePart | None:
        return MultiModalProcessor.create_file_part(file_path, name)

    def validate_file_size(self, data: str, file_type: str = "default") -> bool:
        return MultiModalProcessor.validate_file_size(data, file_type)

    def save_image(self, image: Image.Image, output_path: str | Path, format: str | None = None) -> bool:
        return MultiModalProcessor.save_image(image, output_path, format)


# Export utility classes
__all__ = ["MultiModalProcessor", "MultiModalService"]
