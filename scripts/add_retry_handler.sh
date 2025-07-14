#!/bin/bash

# Script to add retry test handler to your agent

echo "=== Adding Retry Test Handler ==="
echo

# Check if we're in an agent directory
if [ ! -f "src/agent/handlers.py" ]; then
    echo "✗ Error: Not in an agent directory (no src/agent/handlers.py found)"
    echo "Please run this from your agent project root directory"
    exit 1
fi

echo "✓ Found agent project structure"
echo

# Add the retry test handler to handlers.py
echo "📝 Adding retry_test handler to src/agent/handlers.py..."

cat >> src/agent/handlers.py << 'EOF'


@register_handler("retry_test")
@retryable(max_retries=3, delay=1, backoff=2)
@timed()
async def handle_retry_test(task: Task) -> str:
    """Test handler that randomly fails to demonstrate retry logic."""
    import random
    import time

    messages = MessageProcessor.extract_messages(task)
    latest_message = MessageProcessor.get_latest_user_message(messages)
    content = latest_message.get('content', '') if latest_message else ''

    # 70% chance of failure to demonstrate retries
    if random.random() < 0.7:
        raise Exception("Simulated failure for retry testing")

    # If we get here, the request succeeded
    timestamp = time.time()
    return f"RETRY TEST SUCCESS! Request succeeded at {timestamp}. Content: {content}"
EOF

echo "✓ Added retry_test handler"

# Add routing configuration
echo "📝 Adding routing for retry_test to agent_config.yaml..."

# Create a temporary file with the new routing rule
cat > /tmp/retry_routing.yaml << 'EOF'
    - skill_id: retry_test
      keywords: ["retry test", "test retry", "rtest"]
      patterns: ["retry.*test.*", "test.*retry.*"]
EOF

# Insert the routing rule into agent_config.yaml
if grep -q "rules:" agent_config.yaml; then
    # Add after existing rules
    sed -i '' '/rules:/r /tmp/retry_routing.yaml' agent_config.yaml
    echo "✓ Added routing rule to existing rules section"
else
    echo "✗ Could not find 'rules:' section in agent_config.yaml"
    echo "Please manually add this to your routing rules:"
    cat /tmp/retry_routing.yaml
fi

# Clean up
rm /tmp/retry_routing.yaml

echo
echo "🎉 Setup complete!"
echo
echo "Next steps:"
echo "1. Restart your server: uv run uvicorn src.agent.main:app --reload --port 8000"
echo "2. Test the retry functionality:"
echo
echo "curl -X POST http://localhost:8000/ \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo "    \"jsonrpc\": \"2.0\","
echo "    \"method\": \"send_message\","
echo "    \"params\": {"
echo "      \"messages\": [{\"role\": \"user\", \"content\": \"retry test\"}]"
echo "    },"
echo "    \"id\": \"1\""
echo "  }'"
echo
echo "3. Watch the server logs for retry attempts!"
echo "   You should see messages like:"
echo "   WARNING: Attempt 1 failed... Retrying in 1s..."
echo "   WARNING: Attempt 2 failed... Retrying in 2s..."