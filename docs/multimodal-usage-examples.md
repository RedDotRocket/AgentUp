# Multi-modal Processing Examples

This document provides examples of how to use AgentUp's universal multi-modal processing capabilities.

## Important: Agent Architecture

**Agents in AgentUp are pure configuration projects** - they contain only:
- `agent_config.yaml` - Configuration file
- `pyproject.toml` - Dependencies
- `.env` - Environment variables (optional)

**Agents do NOT contain source code or handlers**. All functionality comes from:
1. **The AgentUp framework package** - Provides built-in handlers
2. **Plugins** - For custom functionality

## Overview

AgentUp provides universal multi-modal processing through:
- **Built-in handlers** - Pre-made handlers like `analyze_image`, `process_document`
- **Plugin development** - Custom plugins can use multi-modal helpers
- **Configuration** - Enable features through `agent_config.yaml`

## Quick Start

### Using Built-in Multi-modal Handlers

AgentUp provides several pre-built multi-modal handlers that are automatically available when you enable multi-modal processing in your agent configuration:

- **`analyze_image`** - Analyze uploaded images and return insights
- **`process_document`** - Process documents and extract content  
- **`transform_image`** - Transform images (resize, convert format)
- **`multimodal_chat`** - Handle mixed content conversations

To use them, simply add them to your `agent_config.yaml`:

```yaml
skills:
  - skill_id: analyze_image
    name: Image Analysis
    description: Analyze uploaded images
    input_mode: multimodal
    output_mode: text
    
  - skill_id: process_document
    name: Document Processing
    description: Process uploaded documents
    input_mode: multimodal
    output_mode: text
```

### For Custom Functionality (Plugins)

```python
from agentup.multimodal import MultiModalHelper
from a2a.types import Task

class MyPlugin:
    async def execute_skill(self, context):
        task = context.task
        
        if MultiModalHelper.has_multimodal_content(task):
            summary = MultiModalHelper.create_multimodal_summary(task)
            return f"Multi-modal content detected:\n{summary}"
        
        return "Text-only content"
```

## Available Helper Functions for Plugin Development

The following examples show how to use multi-modal helpers when developing custom plugins. These are **not** for editing handlers (agents don't contain handler code).

### Content Detection in Plugins

```python
# In your plugin's execute_skill method
from agentup.multimodal import MultiModalHelper

class MyPlugin:
    def execute_skill(self, context):
        task = context.task
        results = []
        
        if MultiModalHelper.has_images(task):
            results.append("📷 Images detected")
        
        if MultiModalHelper.has_documents(task):
            results.append("📄 Documents detected")
        
        if not MultiModalHelper.has_multimodal_content(task):
            results.append("💬 Text-only content")
        
        return SkillResult(
            content="\n".join(results),
            success=True
        )
```

### Content Extraction in Plugins

```python
# Example plugin that extracts and analyzes content
from agentup.multimodal import MultiModalHelper
from agentup.plugins.models import SkillResult

class ContentAnalyzerPlugin:
    def execute_skill(self, context):
        task = context.task
        content = MultiModalHelper.extract_all_content(task)
        
        response_parts = []
        
        # Process text
        if content["text"]:
            text_snippet = " ".join(content["text"])[:100]
            response_parts.append(f"Text: {text_snippet}...")
        
        # Process images
        if content["images"]:
            response_parts.append(f"Images: {len(content['images'])} files")
            for i, img in enumerate(content["images"][:3]):
                response_parts.append(f"  - {img.get('name', f'image_{i+1}')}")
        
        # Process documents
        if content["documents"]:
            response_parts.append(f"Documents: {len(content['documents'])} files")
            for i, doc in enumerate(content["documents"][:3]):
                response_parts.append(f"  - {doc.get('name', f'document_{i+1}')}")
        
        return SkillResult(
            content="\n".join(response_parts),
            success=True
        )
```

### Image Processing in Plugins

```python
# Plugin for detailed image processing
from agentup.multimodal import MultiModalHelper

class ImageProcessorPlugin:
    def execute_skill(self, context):
        """Process images with detailed analysis."""
        task = context.task
        images = MultiModalHelper.extract_images(task)
    
        if not images:
            return SkillResult(content="No images found", success=False)
    
        results = []
        
        # Process first image in detail
        first_result = MultiModalHelper.process_first_image(task)
        if first_result and first_result["success"]:
            metadata = first_result["metadata"]
            results.append("Primary Image Analysis:")
            results.append(f"  Format: {metadata['format']}")
            results.append(f"  Size: {metadata['width']}x{metadata['height']}")
            results.append(f"  Color Mode: {metadata['mode']}")
            
            if 'mean_brightness' in metadata:
                results.append(f"  Brightness: {metadata['mean_brightness']:.1f}")
        
        # List other images
        if len(images) > 1:
            results.append(f"\nAdditional Images: {len(images) - 1}")
            for i, img in enumerate(images[1:], 2):
                results.append(f"  - Image {i}: {img.name}")
        
        return SkillResult(
            content="\n".join(results),
            success=True
        )
```

### Document Processing in Plugins

```python
# Plugin for document processing
from agentup.multimodal import MultiModalHelper

class DocumentProcessorPlugin:
    def execute_skill(self, context):
        """Process documents with content extraction."""
        task = context.task
        documents = MultiModalHelper.extract_documents(task)
    
        if not documents:
            return SkillResult(content="No documents found", success=False)
    
        results = []
        
        # Process first document
        first_result = MultiModalHelper.process_first_document(task)
        if first_result and first_result["success"]:
            metadata = first_result["metadata"]
            results.append("Primary Document Analysis:")
            results.append(f"  Type: {metadata['mime_type']}")
            results.append(f"  Size: {metadata['size_mb']:.2f} MB")
            
            # Content-specific information
            if metadata['mime_type'] == 'text/plain':
                if 'line_count' in metadata:
                    results.append(f"  Lines: {metadata['line_count']}")
                if 'word_count' in metadata:
                    results.append(f"  Words: {metadata['word_count']}")
            
            elif metadata['mime_type'] == 'application/json':
                if 'keys' in metadata:
                    keys_preview = ", ".join(metadata['keys'][:5])
                    if len(metadata['keys']) > 5:
                        keys_preview += "..."
                    results.append(f"  Keys: {keys_preview}")
        
        # List other documents
        if len(documents) > 1:
            results.append(f"\nAdditional Documents: {len(documents) - 1}")
            for i, doc in enumerate(documents[1:], 2):
                results.append(f"  - Document {i}: {doc.name}")
        
        return SkillResult(
            content="\n".join(results),
            success=True
        )
```

### Multi-modal Chat Plugin

```python
# Plugin that intelligently handles mixed content
from agentup.multimodal import MultiModalHelper

class SmartChatPlugin:
    def execute_skill(self, context):
        """Intelligent handler that adapts to content type."""
        task = context.task
    
        # Get a summary of all content
        summary = MultiModalHelper.create_multimodal_summary(task)
    
        if "No multi-modal content" in summary:
            # Handle as text-only conversation
            return SkillResult(
                content="I'm ready to chat! How can I help you today?",
                success=True
            )
        
        # Multi-modal response
        response_parts = [
            "I can see you've shared some interesting content!",
            "",
            summary,
            "",
            "How would you like me to help with this content?"
        ]
        
        return SkillResult(
            content="\n".join(response_parts),
            success=True
        )
```

## When to Use Built-in Handlers vs Plugins

### Use Built-in Handlers When:
- The default functionality meets your needs
- You want standard image/document processing
- You're building a simple agent quickly
- You don't need custom business logic

### Develop a Plugin When:
- You need custom processing logic
- You want to integrate with external APIs
- You need specialized analysis (e.g., OCR, AI analysis)
- You want to combine multi-modal with other services

## Configuration Examples

### Basic Multi-modal Setup

```yaml
# agent_config.yaml
services:
  multimodal:
    type: multimodal
    enabled: true
    config:
      max_image_size_mb: 10
      max_document_size_mb: 50

skills:
  - skill_id: analyze_image
    name: Image Analysis
    description: Analyze uploaded images
    input_mode: multimodal
    output_mode: text
    
  - skill_id: process_document
    name: Document Processing  
    description: Process uploaded documents
    input_mode: multimodal
    output_mode: text
```

### Advanced Multi-modal Configuration

```yaml
# agent_config.yaml
services:
  multimodal:
    type: multimodal
    enabled: true
    config:
      max_image_size_mb: 25
      max_document_size_mb: 100
      supported_image_formats:
        - "image/png"
        - "image/jpeg"
        - "image/webp"
        - "image/gif"
        - "image/bmp"
      supported_document_formats:
        - "text/plain"
        - "application/json"
        - "application/pdf"
        - "text/csv"

middleware:
  - name: cached
    params:
      ttl: 600  # Cache multi-modal processing results
  - name: logged
    params:
      log_level: 20

skills:
  - skill_id: multimodal_chat
    name: Multi-modal Chat
    description: Smart handler for mixed content
    input_mode: multimodal
    output_mode: text
    priority: 100
```

## Plugin Integration

### Plugin with Multi-modal Support

```python
# my_plugin.py
from agentup.multimodal import MultiModalHelper
from agentup.plugins.models import SkillInfo, SkillResult, SkillCapability

class ImageAnalysisPlugin:
    def register_skill(self) -> SkillInfo:
        return SkillInfo(
            id="advanced_image_analysis",
            name="Advanced Image Analysis",
            description="Detailed image analysis with AI insights",
            capabilities=[SkillCapability.MULTIMODAL, SkillCapability.AI_FUNCTION],
            tags=["image", "analysis", "ai"]
        )
    
    def can_handle_task(self, context) -> float:
        """Check if we can handle this task."""
        if MultiModalHelper.has_images(context.task):
            return 0.9  # High confidence for image tasks
        return 0.0
    
    def execute_skill(self, context) -> SkillResult:
        """Execute the image analysis skill."""
        task = context.task
        
        if not MultiModalHelper.has_images(task):
            return SkillResult(
                content="Please upload an image for analysis",
                success=False
            )
        
        # Process all images
        image_results = MultiModalHelper.process_all_images(task)
        
        response_parts = ["Advanced Image Analysis Results:"]
        
        for i, result in enumerate(image_results, 1):
            if result["success"]:
                metadata = result["metadata"]
                response_parts.append(f"\nImage {i} ({result['name']}):")
                response_parts.append(f"  - Resolution: {metadata['width']}x{metadata['height']}")
                response_parts.append(f"  - Format: {metadata['format']}")
                response_parts.append(f"  - Color Mode: {metadata['mode']}")
                
                if 'mean_brightness' in metadata:
                    brightness = metadata['mean_brightness']
                    if brightness < 85:
                        tone = "dark"
                    elif brightness > 170:
                        tone = "bright" 
                    else:
                        tone = "balanced"
                    response_parts.append(f"  - Tone: {tone} (brightness: {brightness:.1f})")
                
                if 'channel_means' in metadata:
                    channels = metadata['channel_means']
                    dominant_color = "red" if channels[0] > max(channels[1:]) else \
                                   "green" if channels[1] > max([channels[0], channels[2]]) else "blue"
                    response_parts.append(f"  - Dominant channel: {dominant_color}")
        
        return SkillResult(
            content="\n".join(response_parts),
            success=True,
            metadata={"processed_images": len(image_results)}
        )
```

## Error Handling

### Robust Multi-modal Plugin

```python
# Plugin with comprehensive error handling
from agentup.multimodal import MultiModalHelper
import logging

logger = logging.getLogger(__name__)

class RobustMultimodalPlugin:
    def execute_skill(self, context):
        """Handler with comprehensive error handling."""
        task = context.task
        try:
            if not MultiModalHelper.has_multimodal_content(task):
                return SkillResult(
                    content="This handler processes images and documents. Please upload some files!",
                    success=True
                )
            
            content = MultiModalHelper.extract_all_content(task)
            results = []
            
            # Handle images with error checking
            if content["images"]:
                image_result = MultiModalHelper.process_first_image(task)
                if image_result:
                    if image_result["success"]:
                        metadata = image_result["metadata"]
                        results.append(f"✅ Image processed: {metadata['format']} {metadata['width']}x{metadata['height']}")
                    else:
                        error_msg = image_result.get("error", "Unknown error")
                        results.append(f"❌ Image processing failed: {error_msg}")
                else:
                    results.append("❌ Could not access image processing service")
            
            # Handle documents with error checking  
            if content["documents"]:
                doc_result = MultiModalHelper.process_first_document(task)
                if doc_result:
                    if doc_result["success"]:
                        metadata = doc_result["metadata"]
                        results.append(f"✅ Document processed: {metadata['mime_type']} ({metadata['size_mb']:.2f} MB)")
                    else:
                        error_msg = doc_result.get("error", "Unknown error")
                        results.append(f"❌ Document processing failed: {error_msg}")
                else:
                    results.append("❌ Could not access document processing service")
            
            return SkillResult(
                content="\n".join(results) if results else "No supported content types found",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error in multimodal handler: {e}")
            return SkillResult(
                content=f"Sorry, I encountered an error processing your content: {str(e)}",
                success=False,
                error=str(e)
            )
```

## Best Practices

### 1. Always Check Content Type First
```python
# Good
if has_images(task):
    result = process_first_image(task)

# Avoid
result = process_first_image(task)  # May return None if no images
```

### 2. Handle Service Unavailability
```python
from agentup.services.registry import get_services

def check_multimodal_availability():
    services = get_services()
    multimodal_service = services.get_multimodal()
    return multimodal_service is not None and multimodal_service.is_initialized
```

### 3. Use Configuration for Limits
```yaml
# Configure appropriate limits for your use case
services:
  multimodal:
    config:
      max_image_size_mb: 10      # Adjust based on your needs
      max_document_size_mb: 50   # Balance performance vs capability
```

### 4. Provide Helpful Error Messages
```python
if not has_multimodal_content(task):
    return "I can analyze images and documents. Please upload a file to get started!"
```

## Testing Multi-modal Functionality

### Unit Test Example
```python
import pytest
from unittest.mock import Mock
from agentup.utils.multimodal import has_images

def test_has_images():
    # Mock task with image
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = [Mock()]
    task.history[0].parts[0].dataPart = Mock()
    task.history[0].parts[0].dataPart.mimeType = "image/png"
    
    assert has_images(task) == True

def test_no_images():
    # Mock task without images
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = []
    
    assert has_images(task) == False
```

## Performance Considerations

1. **Caching**: Multi-modal processing can be expensive. Use caching middleware:
   ```yaml
   middleware:
     - name: cached
       params:
         ttl: 600
   ```

2. **Size Limits**: Configure appropriate size limits to prevent memory issues.

3. **Async Processing**: All multi-modal functions are designed to work with async handlers.

4. **Error Handling**: Always handle processing failures gracefully.

## Summary

AgentUp's multi-modal processing provides:

- ✅ Universal access through helper utilities
- ✅ Automatic service registration and initialization  
- ✅ Configuration-driven feature enablement
- ✅ Plugin system integration
- ✅ Comprehensive error handling
- ✅ Performance optimizations through caching
- ✅ A2A protocol compliance

Use these examples as starting points for building powerful multi-modal agents and plugins!