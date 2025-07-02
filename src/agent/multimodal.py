import base64
import hashlib
import io
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

import numpy as np
from a2a.types import DataPart, Part
from PIL import Image

logger = logging.getLogger(__name__)


class MultiModalProcessor:
    """Process multi-modal inputs and outputs."""

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
        """Extract parts matching a mime type prefix."""
        matching_parts = []

        for part in parts:
            if hasattr(part, "dataPart") and part.dataPart:
                if part.dataPart.mimeType.startswith(mime_type_prefix):
                    matching_parts.append(part)

        return matching_parts

    @classmethod
    def extract_image_parts(cls, parts: list[Part]) -> list[DataPart]:
        """Extract image data parts from message parts."""
        image_parts = []

        for part in parts:
            if hasattr(part, "dataPart") and part.dataPart:
                data_part = part.dataPart
                if data_part.mimeType.startswith("image/"):
                    image_parts.append(data_part)

        return image_parts

    @classmethod
    def extract_document_parts(cls, parts: list[Part]) -> list[DataPart]:
        """Extract document data parts from message parts."""
        doc_parts = []

        for part in parts:
            if hasattr(part, "dataPart") and part.dataPart:
                data_part = part.dataPart
                if data_part.mimeType in cls.DOCUMENT_FORMATS:
                    doc_parts.append(data_part)

        return doc_parts

    @classmethod
    def process_image(cls, image_data: str, mime_type: str) -> dict[str, Any]:
        """Process base64 encoded image data."""
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
        """Save PIL Image to file."""
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
        """Resize image maintaining aspect ratio."""
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image

    @classmethod
    def convert_image_format(cls, image: Image.Image, target_format: str) -> bytes:
        """Convert image to different format."""
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
        """Encode PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @classmethod
    def process_document(cls, doc_data: str, mime_type: str) -> dict[str, Any]:
        """Process base64 encoded document data."""
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
        """Validate file size against limits."""
        # Calculate size in MB
        size_bytes = len(base64.b64decode(data))
        size_mb = size_bytes / (1024 * 1024)

        # Get limit for file type
        limit_mb = cls.MAX_FILE_SIZES.get(file_type, cls.MAX_FILE_SIZES["default"])

        return size_mb <= limit_mb

    @classmethod
    def create_data_part(cls, file_path: str | Path, name: str | None = None) -> DataPart | None:
        """Create DataPart from file."""
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
    def extract_all_content(cls, parts: list[Part]) -> dict[str, list[Any]]:
        """Extract all content from message parts organized by type."""
        content = {"text": [], "images": [], "documents": [], "other": []}

        for part in parts:
            if hasattr(part, "textPart") and part.textPart:
                content["text"].append(part.textPart.text)

            elif hasattr(part, "dataPart") and part.dataPart:
                data_part = part.dataPart

                if data_part.mimeType.startswith("image/"):
                    content["images"].append(
                        {"name": data_part.name, "mime_type": data_part.mimeType, "data": data_part.data}
                    )

                elif data_part.mimeType in cls.DOCUMENT_FORMATS:
                    content["documents"].append(
                        {"name": data_part.name, "mime_type": data_part.mimeType, "data": data_part.data}
                    )

                else:
                    content["other"].append(
                        {"name": data_part.name, "mime_type": data_part.mimeType, "data": data_part.data}
                    )

        return content


# Export utility class
__all__ = ["MultiModalProcessor"]
