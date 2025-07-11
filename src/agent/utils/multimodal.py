from typing import Any

import structlog
from a2a.types import DataPart, Task

logger = structlog.get_logger(__name__)


class MultiModalHelper:
    """Helper class providing easy access to multi-modal processing for handlers."""

    @staticmethod
    def get_multimodal_service():
        """Get the multi-modal service from the service registry."""
        try:
            from agent.services.registry import get_services

            services = get_services()
            return services.get_multimodal()
        except Exception as e:
            logger.warning(f"Could not access multi-modal service: {e}")
            return None

    @staticmethod
    def has_images(task: Task) -> bool:
        """Check if task contains image data."""
        if not task.history or not task.history[0].parts:
            return False

        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            image_parts = multimodal.extract_image_parts(task.history[0].parts)
            return len(image_parts) > 0

        # Fallback direct check
        from agent.services.multimodal import MultiModalProcessor

        image_parts = MultiModalProcessor.extract_image_parts(task.history[0].parts)
        return len(image_parts) > 0

    @staticmethod
    def has_documents(task: Task) -> bool:
        """Check if task contains document data."""
        if not task.history or not task.history[0].parts:
            return False

        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            doc_parts = multimodal.extract_document_parts(task.history[0].parts)
            return len(doc_parts) > 0

        # Fallback direct check
        from agent.services.multimodal import MultiModalProcessor

        doc_parts = MultiModalProcessor.extract_document_parts(task.history[0].parts)
        return len(doc_parts) > 0

    @staticmethod
    def has_multimodal_content(task: Task) -> bool:
        """Check if task contains any multi-modal content."""
        return MultiModalHelper.has_images(task) or MultiModalHelper.has_documents(task)

    @staticmethod
    def extract_images(task: Task) -> list[DataPart]:
        """Extract all image parts from a task."""
        if not task.history or not task.history[0].parts:
            return []

        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            return multimodal.extract_image_parts(task.history[0].parts)

        # Fallback direct access
        from agent.services.multimodal import MultiModalProcessor

        return MultiModalProcessor.extract_image_parts(task.history[0].parts)

    @staticmethod
    def extract_documents(task: Task) -> list[DataPart]:
        """Extract all document parts from a task."""
        if not task.history or not task.history[0].parts:
            return []

        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            return multimodal.extract_document_parts(task.history[0].parts)

        # Fallback direct access
        from agent.services.multimodal import MultiModalProcessor

        return MultiModalProcessor.extract_document_parts(task.history[0].parts)

    @staticmethod
    def extract_all_content(task: Task) -> dict[str, list[Any]]:
        """Extract all content from task organized by type."""
        if not task.history or not task.history[0].parts:
            return {"text": [], "images": [], "documents": [], "other": []}

        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            return multimodal.extract_all_content(task.history[0].parts)

        # Fallback direct access
        from agent.services.multimodal import MultiModalProcessor

        return MultiModalProcessor.extract_all_content(task.history[0].parts)

    @staticmethod
    def process_first_image(task: Task) -> dict[str, Any] | None:
        """Process the first image in a task and return metadata."""
        images = MultiModalHelper.extract_images(task)
        if not images:
            return None

        first_image = images[0]
        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            return multimodal.process_image(first_image.data, first_image.mimeType)

        # Fallback direct access
        from agent.services.multimodal import MultiModalProcessor

        return MultiModalProcessor.process_image(first_image.data, first_image.mimeType)

    @staticmethod
    def process_first_document(task: Task) -> dict[str, Any] | None:
        """Process the first document in a task and return metadata."""
        documents = MultiModalHelper.extract_documents(task)
        if not documents:
            return None

        first_doc = documents[0]
        multimodal = MultiModalHelper.get_multimodal_service()
        if multimodal:
            return multimodal.process_document(first_doc.data, first_doc.mimeType)

        # Fallback direct access
        from agent.services.multimodal import MultiModalProcessor

        return MultiModalProcessor.process_document(first_doc.data, first_doc.mimeType)

    @staticmethod
    def process_all_images(task: Task) -> list[dict[str, Any]]:
        """Process all images in a task and return metadata for each."""
        images = MultiModalHelper.extract_images(task)
        results = []

        multimodal = MultiModalHelper.get_multimodal_service()

        for image in images:
            if multimodal:
                result = multimodal.process_image(image.data, image.mimeType)
            else:
                # Fallback direct access
                from agent.services.multimodal import MultiModalProcessor

                result = MultiModalProcessor.process_image(image.data, image.mimeType)

            result["name"] = image.name
            results.append(result)

        return results

    @staticmethod
    def process_all_documents(task: Task) -> list[dict[str, Any]]:
        """Process all documents in a task and return metadata for each."""
        documents = MultiModalHelper.extract_documents(task)
        results = []

        multimodal = MultiModalHelper.get_multimodal_service()

        for doc in documents:
            if multimodal:
                result = multimodal.process_document(doc.data, doc.mimeType)
            else:
                # Fallback direct access
                from agent.services.multimodal import MultiModalProcessor

                result = MultiModalProcessor.process_document(doc.data, doc.mimeType)

            result["name"] = doc.name
            results.append(result)

        return results

    @staticmethod
    def create_multimodal_summary(task: Task) -> str:
        """Create a summary of all multi-modal content in a task."""
        content = MultiModalHelper.extract_all_content(task)

        lines = []

        # Text content
        if content["text"]:
            text_content = " ".join(content["text"])
            snippet = text_content[:100] + ("..." if len(text_content) > 100 else "")
            lines.append(f"Text: '{snippet}'")

        # Images
        if content["images"]:
            lines.append(f"Images: {len(content['images'])} file(s)")
            for i, img in enumerate(content["images"][:3]):
                lines.append(f"  - Image {i + 1}: {img.get('name', 'unnamed')}")

        # Documents
        if content["documents"]:
            lines.append(f"Documents: {len(content['documents'])} file(s)")
            for i, doc in enumerate(content["documents"][:3]):
                lines.append(f"  - Document {i + 1}: {doc.get('name', 'unnamed')}")

        # Other files
        if content.get("other"):
            lines.append(f"Other files: {len(content['other'])} file(s)")

        if not lines:
            return "No multi-modal content detected"

        return "\n".join(lines)


# Convenience functions for easy import
def has_images(task: Task) -> bool:
    """Check if task contains image data."""
    return MultiModalHelper.has_images(task)


def has_documents(task: Task) -> bool:
    """Check if task contains document data."""
    return MultiModalHelper.has_documents(task)


def has_multimodal_content(task: Task) -> bool:
    """Check if task contains any multi-modal content."""
    return MultiModalHelper.has_multimodal_content(task)


def extract_images(task: Task) -> list[DataPart]:
    """Extract all image parts from a task."""
    return MultiModalHelper.extract_images(task)


def extract_documents(task: Task) -> list[DataPart]:
    """Extract all document parts from a task."""
    return MultiModalHelper.extract_documents(task)


def extract_all_content(task: Task) -> dict[str, list[Any]]:
    """Extract all content from task organized by type."""
    return MultiModalHelper.extract_all_content(task)


def process_first_image(task: Task) -> dict[str, Any] | None:
    """Process the first image in a task and return metadata."""
    return MultiModalHelper.process_first_image(task)


def process_first_document(task: Task) -> dict[str, Any] | None:
    """Process the first document in a task and return metadata."""
    return MultiModalHelper.process_first_document(task)


def create_multimodal_summary(task: Task) -> str:
    """Create a summary of all multi-modal content in a task."""
    return MultiModalHelper.create_multimodal_summary(task)


# Export all helper functions
__all__ = [
    "MultiModalHelper",
    "has_images",
    "has_documents",
    "has_multimodal_content",
    "extract_images",
    "extract_documents",
    "extract_all_content",
    "process_first_image",
    "process_first_document",
    "create_multimodal_summary",
]
