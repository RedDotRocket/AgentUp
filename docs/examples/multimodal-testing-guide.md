# Multi-Modal Testing Guide

This guide shows you how to set up and test AgentUp's multi-modal capabilities using vision-capable language models.

## Overview

AgentUp supports comprehensive multi-modal processing, allowing your agents to handle:
- **Text content**: Natural language input and responses
- **Images**: JPEG, PNG, WebP, GIF analysis and description
- **Documents**: Text files, JSON, XML, YAML, and Markdown processing
- **Mixed media**: Combining text, images, and documents in single conversations

This is powered by vision-capable language models like GPT-4o, which can analyze images and process various document types simultaneously.

## Prerequisites

- OpenAI API key with access to GPT-4o or GPT-4-vision-preview
- AgentUp framework installed
- Test files for multi-modal processing:
  - **Images**: JPEG, PNG, WebP, GIF files
  - **Documents**: Text files, JSON, XML, YAML, Markdown files
  - **Mixed content**: Combinations of text, images, and documents

## Quick Setup

### Step 1: Create Multi-Modal Agent

Create a new agent with multi-modal capabilities:

```bash
cd ~/dev/agentup-workspace/agents
agentup agent create multimodal-test --template standard
cd multimodal-test
```

### Step 2: Configure for GPT-4 Vision

Edit your `agent_config.yaml` to enable multi-modal processing with GPT-4:

```yaml
agent:
  name: "Multi-Modal Test Agent"
  description: "AI agent with image processing capabilities"
  version: "1.0.0"

# Configure GPT-4 with vision capabilities
ai_provider:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o  # GPT-4o has excellent vision capabilities
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0

# Enable multi-modal skill
skills:
  - skill_id: ai_assistant
    name: "AI Assistant"
    description: "Multi-modal AI assistant that can process text and images"
    input_mode: multimodal  # This enables multi-modal processing
    output_mode: text
    priority: 100

# Security configuration
security:
  enabled: true
  type: api_key
  config:
    keys:
      - ${API_KEY:test-key-12345}

# Enable middleware
middleware:
  - type: rate_limiting
    config:
      requests_per_minute: 60
  - type: caching
    config:
      ttl: 300

# Enable MCP for additional capabilities
mcp:
  client:
    servers:
      - name: filesystem
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
        env: {}
```

### Step 3: Set Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
export API_KEY="test-key-12345"  # For agent authentication
```

### Step 4: Install Dependencies and Start Agent

```bash
uv sync
agentup agent serve --port 8000
```

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Testing Multi-Modal Capabilities

### Method 1: Using cURL

For small images, you can use direct command substitution:

```bash
# Encode image to base64
base64 -i test-image.jpg > image.b64

# For small images only - may fail with "argument list too long" for larger files
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key-12345" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "test-multimodal-1",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "What do you see in this image? Please describe it in detail."
          },
          {
            "kind": "file",
            "file": {
              "name": "image.jpeg",
              "mimeType": "image/jpeg",
              "bytes": "$(cat image.b64)"
            }
          }
        ]
      }
    },
    "id": "test-multimodal-1"
  }'
```

For larger images, use a JSON file:

```bash
# Create JSON template
cat > request.json << 'EOF'
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "test-multimodal-1",
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "What do you see in this image?"
        },
        {
          "kind": "file",
          "file": {
            "name": "image.jpeg",
            "mimeType": "image/jpeg",
            "bytes": "PLACEHOLDER"
          }
        }
      ]
    }
  },
  "id": "test-multimodal-1"
}
EOF

# Replace placeholder with base64 data
jq --rawfile img image.b64 '.params.message.parts[1].file.bytes = $img' request.json > request-final.json

# Send request
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key-12345" \
  -d @request-final.json
```

### Method 2: Using Python Script

Create a test script `test_multimodal.py`:

```python
import requests
import base64
import json
import sys
import os
import mimetypes

def test_multimodal_agent(file_path, prompt="Analyze this content"):
    """Test multi-modal capabilities with various file types."""
    
    # Read and encode file
    try:
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        return
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Fallback based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        fallback_types = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif',
            '.txt': 'text/plain', '.md': 'text/markdown',
            '.json': 'application/json', '.xml': 'application/xml',
            '.yaml': 'application/yaml', '.yml': 'application/yaml'
        }
        mime_type = fallback_types.get(ext, 'application/octet-stream')
    
    # Send request to AgentUp
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "multimodal-test",
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": prompt
                    },
                    {
                        "kind": "file",
                        "file": {
                            "name": os.path.basename(file_path),
                            "mimeType": mime_type,
                            "bytes": file_data
                        }
                    }
                ]
            }
        },
        "id": "multimodal-test"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key-12345"
    }
    
    try:
        response = requests.post("http://localhost:8000", 
                               json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if "result" in result and "artifacts" in result["result"]:
            for artifact in result["result"]["artifacts"]:
                if artifact["type"] == "text":
                    print("AI Response:")
                    print("-" * 50)
                    print(artifact["data"])
                    print("-" * 50)
        else:
            print("Unexpected response format:")
            print(json.dumps(result, indent=2))
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing response: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_multimodal.py <file_path> [prompt]")
        print("Examples:")
        print("  python test_multimodal.py cat.jpg 'What animal is this?'")
        print("  python test_multimodal.py document.txt 'Summarize this document'")
        print("  python test_multimodal.py data.json 'Analyze this data structure'")
        sys.exit(1)
    
    file_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Analyze this content"
    
    test_multimodal_agent(file_path, prompt)
```

Run the test:
```bash
# Test with images
python test_multimodal.py your-image.jpg "What do you see in this image?"

# Test with documents
python test_multimodal.py document.txt "Summarize this document"

# Test with JSON data
python test_multimodal.py config.json "Explain this configuration"

# Test with mixed content (create a request with both text and files)
python test_multimodal.py data.yaml "Analyze this YAML structure"
```

### Method 3: Using JavaScript/Node.js

Create `test_multimodal.js`:

```javascript
const fs = require('fs');
const path = require('path');

async function testMultiModal(imagePath, prompt = "Describe this image") {
    try {
        // Read and encode image
        const imageBuffer = fs.readFileSync(imagePath);
        const imageData = imageBuffer.toString('base64');
        
        // Determine MIME type
        const ext = path.extname(imagePath).toLowerCase();
        const mimeType = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif'
        }[ext] || 'image/jpeg';
        
        // Send request
        const response = await fetch('http://localhost:8000', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-key-12345'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "message/send",
                params: {
                    message: {
                        messageId: "multimodal-test-js",
                        role: "user",
                        parts: [
                            {
                                kind: "text",
                                text: prompt
                            },
                            {
                                kind: "file",
                                file: {
                                    name: path.basename(imagePath),
                                    mimeType: mimeType,
                                    bytes: imageData
                                }
                            }
                        ]
                    }
                },
                id: "multimodal-test-js"
            })
        });
        
        const result = await response.json();
        
        if (result.result && result.result.artifacts) {
            result.result.artifacts.forEach(artifact => {
                if (artifact.type === 'text') {
                    console.log('AI Response:');
                    console.log('-'.repeat(50));
                    console.log(artifact.data);
                    console.log('-'.repeat(50));
                }
            });
        } else {
            console.log('Unexpected response:', JSON.stringify(result, null, 2));
        }
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

// Usage
const imagePath = process.argv[2];
const prompt = process.argv[3] || "Describe this image in detail";

if (!imagePath) {
    console.log('Usage: node test_multimodal.js <image_path> [prompt]');
    process.exit(1);
}

testMultiModal(imagePath, prompt);
```

Run with:
```bash
node test_multimodal.js your-image.jpg "What's happening in this picture?"
```

## Expected Response Format

A successful multi-modal request will return:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
      {
        "type": "text",
        "data": "I can see an image that shows [detailed description from GPT-4]...",
        "mimeType": "text/plain"
      }
    ],
    "context": "context-id-here",
    "metadata": {
      "skill_used": "ai_assistant",
      "processing_time": 1234
    }
  },
  "id": "test-multimodal-1"
}
```

## Example Test Scenarios

### Image Processing

#### 1. Image Description
```bash
python test_multimodal.py landscape.jpg "Describe the scenery in this image"
```

#### 2. Object Recognition
```bash
python test_multimodal.py object.jpg "What objects can you identify in this image?"
```

#### 3. Text Extraction (OCR)
```bash
python test_multimodal.py document.jpg "Extract any text you can see in this image"
```

#### 4. Scene Analysis
```bash
python test_multimodal.py street.jpg "Analyze the scene and describe what's happening"
```

#### 5. Technical Analysis
```bash
python test_multimodal.py chart.jpg "Analyze this chart and explain the data trends"
```

### Document Processing

#### 1. Text Document Analysis
```bash
python test_multimodal.py report.txt "Summarize the key points in this report"
```

#### 2. JSON Configuration Analysis
```bash
python test_multimodal.py config.json "Explain this configuration file structure"
```

#### 3. YAML Data Processing
```bash
python test_multimodal.py data.yaml "Analyze this YAML file and explain its purpose"
```

#### 4. Markdown Document Processing
```bash
python test_multimodal.py README.md "Summarize this documentation"
```

#### 5. XML Data Analysis
```bash
python test_multimodal.py data.xml "Parse this XML and explain its structure"
```

### Mixed Content Scenarios

#### 1. Multiple Files
You can process multiple files in a single request by creating a custom payload:

```python
# Custom script for multiple files
payload = {
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
        "message": {
            "messageId": "multi-file-test",
            "role": "user",
            "parts": [
                {"kind": "text", "text": "Analyze these files together"},
                {"kind": "file", "file": {"name": "image.jpg", "mimeType": "image/jpeg", "bytes": image_data}},
                {"kind": "file", "file": {"name": "report.txt", "mimeType": "text/plain", "bytes": text_data}},
                {"kind": "file", "file": {"name": "config.json", "mimeType": "application/json", "bytes": json_data}}
            ]
        }
    },
    "id": "multi-file-test"
}
```

#### 2. Image + Document Analysis
```bash
# Process chart image with accompanying data file
python test_multimodal.py chart.jpg "Analyze this chart"
python test_multimodal.py data.json "Compare with this data"
```

## Troubleshooting

### Common Issues

**1. "Model not found" error**
- Ensure you're using `gpt-4o` or `gpt-4-vision-preview`
- Check your OpenAI API key has access to GPT-4

**2. "Authentication failed"**
- Verify the `API_KEY` environment variable matches your agent config
- Include the `Authorization: Bearer` header in requests

**3. "Image too large" error**
- GPT-4 has image size limits (typically 20MB)
- Resize large images before sending

**4. "Invalid base64" error**
- Ensure proper base64 encoding without newlines
- Use `base64 -w 0` on Linux to avoid line wrapping

### Debugging

Enable debug logging by setting:
```bash
export LOG_LEVEL=DEBUG
agentup agent serve --port 8000
```

Check the agent logs for detailed processing information including:
- Image processing steps
- LLM API calls
- Response generation

## Advanced Usage

### Multiple Images

You can send multiple images in a single request:

```python
payload = {
    "jsonrpc": "2.0",
    "method": "message/send", 
    "params": {
        "message": {
            "messageId": "multi-image-test",
            "role": "user",
            "parts": [
                {"kind": "text", "text": "Compare these two images"},
                {"kind": "file", "file": {"name": "image1.jpg", "mimeType": "image/jpeg", "bytes": image1_data}},
                {"kind": "file", "file": {"name": "image2.png", "mimeType": "image/png", "bytes": image2_data}}
            ]
        }
    },
    "id": "multi-image-test"
}
```

### Streaming Responses

For streaming responses, use the `message/stream` method:

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key-12345" \
  -H "Accept: text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/stream",
    "params": {
      "message": {
        "messageId": "stream-test",
        "role": "user",
        "parts": [
          {"kind": "text", "text": "Analyze this image in detail"},
          {"kind": "file", "file": {"name": "image.jpg", "mimeType": "image/jpeg", "bytes": "..."}}
        ]
      }
    },
    "id": "stream-test"
  }'
```

## Performance Notes

- **Response Time**: Multi-modal requests typically take 2-10 seconds depending on image size and complexity
- **Rate Limits**: OpenAI has rate limits for GPT-4 vision requests
- **Image Size**: Larger images take longer to process; consider resizing for faster responses
- **Cost**: GPT-4 vision requests are more expensive than text-only requests

## Security Considerations

- Never include sensitive information in images
- Validate image uploads in production environments
- Consider implementing image content filtering
- Monitor API usage and costs

## Next Steps

Once you have multi-modal working:

1. **Integrate with MCP**: Use filesystem MCP to process images from disk
2. **Add File Upload**: Create a web interface for image uploads
3. **Batch Processing**: Process multiple images programmatically
4. **Custom Skills**: Create specialized image analysis skills
5. **Error Handling**: Add robust error handling for production use

For more advanced features, see the [Plugin Development Guide](plugin-development.md) and [MCP Integration Guide](mcp-integration.md).