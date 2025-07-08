import structlog
from a2a.types import Task

from ..config import load_config
from ..services.multimodal import MultiModalProcessor

_config = load_config()
_project_name = _config.get("agent", {}).get("name", "Agent")

# CONDITIONAL_PIL_IMPORT
try:
    from PIL import Image
except ImportError:
    Image = None


# Conditional middleware decorators
try:
    from ..middleware import cached, timed, with_middleware
except ImportError:

    def cached(ttl: int = None):
        def decorator(func):
            return func

        return decorator

    def timed():
        def decorator(func):
            return func

        return decorator

    def with_middleware():
        def decorator(func):
            return func

        return decorator


try:
    from ..core.dispatcher import ai_function
except ImportError:

    def ai_function(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


logger = structlog.get_logger(__name__)


# Import register_handler
try:
    from ..handlers.handlers import register_handler
except ImportError:

    def register_handler(skill_id: str):
        def decorator(func):
            return func

        return decorator


@register_handler("analyze_image")
@ai_function(
    description="Analyze an uploaded image and return insights",
    parameters={"analysis_type": {"type": "string", "description": "Type of analysis (basic, detailed, color)"}},
)
@timed()
async def handle_analyze_image(task: Task) -> str:
    """
    Analyze an uploaded image and return insights.

    Input modes: image/png, image/jpeg
    Output modes: application/json, text
    """
    logger.info(f"Handling analyze_image task: {task.id}")

    # Extract image parts
    if not task.history or not task.history[0].parts:
        return "Error: No image provided. Please upload an image to analyze."

    image_parts = MultiModalProcessor.extract_image_parts(task.history[0].parts)
    if not image_parts:
        return "Error: No image found in input. Please ensure you've uploaded a valid image."

    # Get analysis type from metadata
    metadata = getattr(task, "metadata", {}) or {}
    analysis_type = metadata.get("analysis_type", "basic")

    # Process first image
    image_part = image_parts[0]
    if not image_part["data"]:
        return "Error: No image data found. Images must be embedded as base64 data."
    result = MultiModalProcessor.process_image(image_part["data"], image_part["mimeType"])

    if not result["success"]:
        return f"Error processing image: {result.get('error', 'Unknown error')}"

    # Build analysis response
    image_metadata = result["metadata"]
    response_parts = [
        f"Image Analysis Results for {_project_name}:",
        f"- Format: {image_metadata['format']}",
        f"- Dimensions: {image_metadata['width']}x{image_metadata['height']} pixels",
        f"- Mode: {image_metadata['mode']}",
        f"- File Hash: {image_metadata['hash'][:8]}...",
    ]

    if analysis_type in ["detailed", "color"]:
        response_parts.extend(
            [
                f"- Mean Brightness: {image_metadata.get('mean_brightness', 'N/A'):.1f}",
                f"- Shape: {image_metadata.get('shape', 'N/A')}",
            ]
        )

        if analysis_type == "color" and "channel_means" in image_metadata:
            channels = image_metadata["channel_means"]
            response_parts.append(f"- RGB Channel Means: R={channels[0]:.1f}, G={channels[1]:.1f}, B={channels[2]:.1f}")

    return "\n".join(response_parts)


@register_handler("process_document")
@ai_function(
    description="Process uploaded documents and extract content",
    parameters={"extraction_type": {"type": "string", "description": "Type of extraction (summary, full, metadata)"}},
)
@cached(ttl=600)
@timed()
async def handle_process_document(task: Task) -> str:
    """
    Process uploaded documents and extract content.

    Input modes: text/plain, application/json, application/pdf
    Output modes: text, application/json
    """
    logger.info(f"Handling process_document task: {task.id}")

    # Extract document parts
    if not task.history or not task.history[0].parts:
        return "Error: No document provided. Please upload a document to process."

    doc_parts = MultiModalProcessor.extract_document_parts(task.history[0].parts)
    if not doc_parts:
        return "Error: No document found in input. Supported formats: text, JSON, PDF."

    # Get extraction type from metadata
    metadata = getattr(task, "metadata", {}) or {}
    extraction_type = metadata.get("extraction_type", "summary")

    # Process first document
    doc_part = doc_parts[0]
    if not doc_part["data"]:
        return "Error: No document data found. Documents must be embedded as base64 data."
    result = MultiModalProcessor.process_document(doc_part["data"], doc_part["mimeType"])

    if not result["success"]:
        return f"Error processing document: {result.get('error', 'Unknown error')}"

    doc_metadata = result["metadata"]
    response_parts = [
        f"Document Processing Results for {_project_name}:",
        f"- Type: {doc_metadata['mime_type']}",
        f"- Size: {doc_metadata['size_mb']:.2f} MB",
        f"- Hash: {doc_metadata['hash'][:8]}...",
    ]

    if extraction_type == "full" and "content" in doc_metadata:
        content = doc_metadata["content"]
        if isinstance(content, str):
            snippet = content[:500] + ("..." if len(content) > 500 else "")
            response_parts.append(f"\nContent:\n{snippet}")
        else:
            response_parts.append(f"\nContent Type: {type(content).__name__}")

    elif extraction_type == "summary":
        if "line_count" in doc_metadata:
            response_parts.append(f"- Lines: {doc_metadata['line_count']}")
        if "word_count" in doc_metadata:
            response_parts.append(f"- Words: {doc_metadata['word_count']}")
        if "keys" in doc_metadata:
            keys = doc_metadata["keys"]
            snippet_keys = ", ".join(keys[:5]) + ("..." if len(keys) > 5 else "")
            response_parts.append(f"- JSON Keys: {snippet_keys}")

    return "\n".join(response_parts)


@register_handler("transform_image")
@ai_function(
    description="Transform images with various operations",
    parameters={
        "operation": {"type": "string", "description": "Operation to perform (resize, format, thumbnail)"},
        "target_size": {"type": "string", "description": "Target size for resize (e.g., '800x600')"},
        "target_format": {"type": "string", "description": "Target format (PNG, JPEG, WEBP)"},
    },
)
@timed()
async def handle_transform_image(task: Task) -> str:
    """
    Transform images with various operations.

    Operations: resize, convert format, create thumbnail
    """
    logger.info(f"Handling transform_image task: {task.id}")

    if not Image:
        return "Error: PIL/Pillow not installed. Image transformation requires PIL."

    # Extract image parts
    if not task.history or not task.history[0].parts:
        return "Error: No image provided for transformation."

    image_parts = MultiModalProcessor.extract_image_parts(task.history[0].parts)
    if not image_parts:
        return "Error: No valid image found in input."

    # Get transformation parameters
    metadata = getattr(task, "metadata", {}) or {}
    operation = metadata.get("operation", "thumbnail")
    target_size = metadata.get("target_size", "200x200")
    target_format = metadata.get("target_format", "PNG")

    # Process image
    image_part = image_parts[0]
    if not image_part["data"]:
        return "Error: No image data found. Images must be embedded as base64 data."
    result = MultiModalProcessor.process_image(image_part["data"], image_part["mimeType"])

    if not result["success"]:
        return f"Error loading image: {result.get('error', 'Unknown error')}"

    image = result["image"]
    original_size = image.size

    try:
        if operation == "resize":
            width, height = map(int, target_size.split("x"))
            image = MultiModalProcessor.resize_image(image, (width, height))
            transform_msg = f"Resized from {original_size} to {image.size}"
        elif operation == "thumbnail":
            width, height = map(int, target_size.split("x"))
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            transform_msg = f"Created thumbnail from {original_size} to {image.size}"
        elif operation == "format":
            transform_msg = f"Converting to {target_format} format"
        else:
            return f"Error: Unknown operation '{operation}'. Supported: resize, thumbnail, format"

        encoded = MultiModalProcessor.encode_image_base64(image, target_format)
        return (
            f"Image Transformation Complete:\n"
            f"- {transform_msg}\n"
            f"- Output format: {target_format}\n"
            f"- Result encoded as base64 (length: {len(encoded)} chars)"
        )

    except Exception as e:
        logger.error(f"Image transformation error: {e}")
        return f"Error during transformation: {e}"


@register_handler("multimodal_chat")
@ai_function(
    description="Handle conversations with mixed text and media content",
    parameters={"response_mode": {"type": "string", "description": "Response mode (text, detailed, summary)"}},
)
async def handle_multimodal_chat(task: Task) -> str:
    """
    Handle conversations with mixed text and media content.

    Processes text, images, and documents in a single conversation.
    """
    logger.info(f"Handling multimodal_chat task: {task.id}")

    if not task.history or not task.history[0].parts:
        return (
            f"Hello! I'm {_project_name}, ready to help with text, images, and documents. What can I assist you with?"
        )

    # Extract all content types
    content = MultiModalProcessor.extract_all_content(task.history[0].parts)

    # Get response mode
    metadata = getattr(task, "metadata", {}) or {}
    response_mode = metadata.get("response_mode", "text")

    response_parts = [f"{_project_name} Multi-modal Response:"]

    # Process text content
    if content["text"]:
        text_content = " ".join(content["text"])
        snippet = text_content[:100] + ("..." if len(text_content) > 100 else "")
        response_parts.append(f"\nText received: '{snippet}'")

    # Process images
    if content["images"]:
        response_parts.append(f"\nImages detected: {len(content['images'])}")
        if response_mode in ["detailed", "summary"]:
            for i, img_data in enumerate(content["images"][:3]):
                result = MultiModalProcessor.process_image(img_data["data"], img_data["mime_type"])
                if result["success"]:
                    meta = result["metadata"]
                    response_parts.append(f"  - Image {i + 1}: {meta['width']}x{meta['height']} {meta['format']}")

    # Process documents
    if content["documents"]:
        response_parts.append(f"\nDocuments detected: {len(content['documents'])}")
        if response_mode in ["detailed", "summary"]:
            for i, doc_data in enumerate(content["documents"][:3]):
                result = MultiModalProcessor.process_document(doc_data["data"], doc_data["mime_type"])
                if result["success"]:
                    meta = result["metadata"]
                    response_parts.append(
                        f"  - Document {i + 1}: {doc_data.get('name', 'unknown')} ({meta['size_mb']:.2f} MB)"
                    )

    # Process other content
    if content.get("other"):
        response_parts.append(f"\nOther files detected: {len(content['other'])}")

    # Add summary
    total_items = sum(len(content.get(kind, [])) for kind in ["text", "images", "documents", "other"])
    response_parts.append(f"\nTotal items processed: {total_items}")

    return "\n".join(response_parts)


# Export handlers
__all__ = ["handle_analyze_image", "handle_process_document", "handle_transform_image", "handle_multimodal_chat"]
