# AgentUp Routing System QA Testing Scenarios

## Overview
This document outlines comprehensive testing scenarios for the new routing system, covering configuration validation, routing behavior, backward compatibility, and edge cases.

## Test Environment Setup
Before running tests, ensure:
```bash
cd /Users/lhinds/repos/rdrocket-projects/AgentUp
uv sync  # Install dependencies
```

## 1. Configuration Validation Tests

### 1.1 Valid Configuration Tests


**Test Case**: Minimal Direct Routing

```bash
agentup-dev agent create -o ~/routing-minimal --template minimal
```

```yaml
# test-minimal.yaml
agent:
  name: MinimalAgent
  description: Basic direct routing test
  version: 0.1.0

routing:
  default_mode: direct
  fallback_skill: echo
  fallback_enabled: true

skills:
  - skill_id: echo
    name: Echo Skill
    description: Echo back messages
    routing_mode: direct
    keywords: [echo, repeat]
    patterns: ['echo.*']

security:
  enabled: false
```

**Expected**: ✅ Validation passes
```bash
agentup agent validate --config agent_config.yaml
```

```bash
curl -s -X POST http://localhost:8000/ \
      -H "Content-Type: application/json" \
      -H "X-API-Key: sk-strong-key-1-abcd1234xyz" \
      -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
          "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "echo hello"}],
            "messageId": "msg-005",
            "contextId": "context-001",
            "kind": "message"
          }
        },
        "id": "req-005"
      }' | jq
```

---

**Test Case**: Standard AI Routing
```yaml
# test-ai.yaml
agent:
  name: AIAgent
  description: AI routing test
  version: 0.1.0

routing:
  default_mode: ai
  fallback_skill: ai_assistant
  fallback_enabled: true

skills:
  - skill_id: ai_assistant
    name: AI Assistant
    description: General AI assistant
    routing_mode: ai

ai:
  enabled: true
  llm_service: openai
  model: gpt-4o-mini

services:
  openai:
    type: llm
    provider: openai
    api_key: ${OPENAI_API_KEY:test-key}

security:
  enabled: false
```

**Expected**: ✅ Validation passes
```bash
agentup agent validate --config agent_config.yaml
```

Test the endpoint:

```bash
curl -s -X POST http://localhost:8000/ \
      -H "Content-Type: application/json" \
      -H "X-API-Key: sk-strong-key-1-abcd1234xyz" \
      -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
          "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "are radiohead from the UK?"}],
            "messageId": "msg-005",
            "contextId": "context-001",
            "kind": "message"
          }
        },
        "id": "req-005"
      }' | jq
{
  "id": "req-005",
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
      {
        "artifactId": "ecbd543e-65bf-4e61-b057-7c33b316ec09",
        "description": null,
        "extensions": null,
        "metadata": null,
        "name": "AIAgent-result",
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Yes, the band Radiohead is from the United Kingdom. They were formed in Abingdon, Oxfordshire, England in 1985."
          }
        ]
      }
    ],
    "contextId": "context-001",
    "history": [
      {
        "contextId": "context-001",
        "extensions": null,
        "kind": "message",
        "messageId": "msg-005",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "are radiohead from the UK?"
          }
        ],
        "referenceTaskIds": null,
        "role": "user",
        "taskId": "9412c8e7-e27d-4726-810a-fc5cb1a45eda"
      },
      {
        "contextId": "context-001",
        "extensions": null,
        "kind": "message",
        "messageId": "6def2d76-1485-4281-a26c-ee8c4b18eb24",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Processing request with for task 9412c8e7-e27d-4726-810a-fc5cb1a45eda using AIAgent."
          }
        ],
        "referenceTaskIds": null,
        "role": "agent",
        "taskId": "9412c8e7-e27d-4726-810a-fc5cb1a45eda"
      }
    ],
    "id": "9412c8e7-e27d-4726-810a-fc5cb1a45eda",
    "kind": "task",
    "metadata": null,
    "status": {
      "message": null,
      "state": "completed",
      "timestamp": "2025-06-29T10:10:32.866146+00:00"
    }
  }
}
```

---

**Test Case**: Mixed Routing

```yaml
# test-mixed.yaml
agent:
  name: MixedAgent
  description: Mixed routing test
  version: 0.1.0

routing:
  default_mode: ai
  fallback_skill: ai_assistant
  fallback_enabled: true

skills:
  - skill_id: ai_assistant
    name: AI Assistant
    description: Conversational AI
    routing_mode: ai
  - skill_id: system_status
    name: System Status
    description: Quick system commands
    routing_mode: direct
    keywords: [status, health, ping]
    patterns: ['status.*']

ai:
  enabled: true
  llm_service: openai

services:
  openai:
    type: llm
    provider: openai
    config: {}
    api_key: ${OPENAI_API_KEY:test-key}

security:
  enabled: false
```

**Handler Code Required**: Create `src/agent/handlers/system_status_handler.py`:
```python
"""System status handler for direct routing."""


from typing import Any, dict, list
from a2a.types import Message, Artifact, Part, TextPart
import platform
import psutil
import datetime
import uuid

from .handlers import register_handler


@register_handler("system_status")
async def handle_system_status(task: Any) -> list[Artifact]:
    """Handle system status requests."""
    try:
        # Collect system information
        status_info = {
            "timestamp": datetime.datetime.now().isoformat(),
            "system": platform.system(),
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            }
        }
        
        # Format response
        status_text = f"""System Status Report:
- System: {status_info['system']} ({status_info['platform']})
- CPU: {status_info['cpu_count']} cores, {status_info['cpu_percent']}% usage
- Memory: {status_info['memory']['percent']}% used
- Disk: {status_info['disk']['percent']}% used
- Timestamp: {status_info['timestamp']}"""

        return [Artifact(
            artifactId=str(uuid.uuid4()),
            name="system-status",
            parts=[Part(root=TextPart(kind="text", text=status_text))]
        )]
        
    except Exception as e:
        return [Artifact(
            artifactId=str(uuid.uuid4()),
            name="system-status-error",
            parts=[Part(root=TextPart(kind="text", text=f"Error getting system status: {str(e)}"))]
        )]
```

**Expected**: ✅ Validation passes
```bash
agentup agent validate --config test-mixed.yaml
```

**Test the mixed routing behavior**:
```bash
# Start the mixed routing agent
agentup agent serve --config test-mixed.yaml --port 8000 &
export OPENAI_API_KEY=your_key_here

# Test direct routing to system_status skill
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "status"}],
        "messageId": "mixed-001",
        "contextId": "mixed-context",
        "kind": "message"
      }
    },
    "id": "mixed-req-001"
  }' | jq

# Test AI routing to ai_assistant skill
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "What is the capital of France?"}],
        "messageId": "mixed-002",
        "contextId": "mixed-context",
        "kind": "message"
      }
    },
    "id": "mixed-req-002"
  }' | jq

# Test keyword routing with health check
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "health check"}],
        "messageId": "mixed-003",
        "contextId": "mixed-context",
        "kind": "message"
      }
    },
    "id": "mixed-req-003"
  }' | jq

# Test fallback to AI assistant for unknown requests
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "unknown command xyz"}],
        "messageId": "mixed-004",
        "contextId": "mixed-context",
        "kind": "message"
      }
    },
    "id": "mixed-req-004"
  }' | jq
```

**Expected Results**:
- First request (status) → Direct routing to system_status skill
- Second request (capital question) → AI routing to ai_assistant skill  
- Third request (health) → Direct routing to system_status skill (keyword match)
- Fourth request (unknown) → AI routing to ai_assistant fallback skill

### 1.2 Invalid Configuration Tests

**Test Case**: AI Required But Not Configured
```yaml
# test-invalid-ai.yaml
agent:
  name: InvalidAI
  description: AI routing without AI config
  version: 0.1.0

routing:
  default_mode: ai
  fallback_skill: ai_assistant

skills:
  - skill_id: ai_assistant
    name: AI Assistant
    routing_mode: ai

ai:
  enabled: false  # AI disabled but required by skill

security:
  enabled: false
```

**Expected**: ❌ Validation fails with error about AI requirements
```bash
agentup agent validate --config test-invalid-ai.yaml
```

---

**Test Case**: Direct Routing Without Keywords/Patterns
```yaml
# test-invalid-direct.yaml
agent:
  name: InvalidDirect
  description: Direct routing without patterns
  version: 0.1.0

routing:
  default_mode: direct
  fallback_skill: empty_skill

skills:
  - skill_id: empty_skill
    name: Empty Skill
    routing_mode: direct
    # Missing keywords and patterns

security:
  enabled: false
```

**Expected**: ⚠️ Validation warns about missing keywords/patterns
```bash
agentup agent validate --config test-invalid-direct.yaml
```

---

**Test Case**: Invalid Regex Patterns
```yaml
# test-invalid-regex.yaml
agent:
  name: InvalidRegex
  description: Invalid regex patterns
  version: 0.1.0

routing:
  default_mode: direct
  fallback_skill: regex_skill

skills:
  - skill_id: regex_skill
    name: Regex Skill
    routing_mode: direct
    patterns: ['[invalid', 'missing)paren']  # Invalid regex

security:
  enabled: false
```

**Expected**: ❌ Validation fails with regex errors
```bash
agentup agent validate --config test-invalid-regex.yaml
```

## 2. Runtime Behavior Tests

### 3.1 Agent Creation Tests

**Test Case**: Create Agent with Each Template
```bash
# Test minimal template
agentup agent create test-minimal --template minimal --output-dir ./test-agents/

# Test standard template  
agentup agent create test-standard --template standard --output-dir ./test-agents/

# Test full template
agentup agent create test-full --template full --output-dir ./test-agents/

# Test demo template
agentup agent create test-demo --template demo --output-dir ./test-agents/
```

**Expected**: All agents created successfully with proper routing configurations

**Verify**: Check generated `agent_config.yaml` files contain:
- Correct `fallback_skill` (not `default_skill`)
- Appropriate routing modes for each template
- Valid skill configurations

### 3.2 Agent Startup Tests

**Test Case**: Start Each Generated Agent
```bash
cd test-agents/test-minimal
agentup agent serve --port 8001

cd ../test-standard  
agentup agent serve --port 8002

cd ../test-full
agentup agent serve --port 8003

cd ../test-demo
agentup agent serve --port 8004
```

**Expected**: All agents start without errors

**Verify**: Check logs for:
- ✅ "Routing mode set to: [direct/ai]"
- ✅ "AI functions registered successfully" (for AI agents)
- ✅ "Registry skills loaded successfully"
- ❌ No errors about missing skills or configuration issues

### 3.3 Routing Logic Tests

**Test Case**: Direct Routing Behavior
```bash
# Start minimal agent
cd test-agents/test-minimal
agentup agent serve --port 8001 &

# Test direct routing with keywords (A2A JSON-RPC format)
curl -s -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "echo hello world"}],
        "messageId": "msg-001",
        "contextId": "context-001",
        "kind": "message"
      }
    },
    "id": "req-001"
  }' | jq

# Test fallback routing
curl -s -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "unknown command"}],
        "messageId": "msg-002",
        "contextId": "context-001",
        "kind": "message"
      }
    },
    "id": "req-002"
  }' | jq
```

**Expected**: 
- First request routes to echo skill
- Second request routes to fallback skill (echo)

---

**Test Case**: AI Routing Behavior (if OPENAI_API_KEY available)
```bash
# Start standard agent
cd test-agents/test-standard
export OPENAI_API_KEY=your_key_here
agentup agent serve --port 8002 &

# Test AI routing
curl -s -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello, how can you help me?"}],
        "messageId": "msg-003",
        "contextId": "context-002",
        "kind": "message"
      }
    },
    "id": "req-003"
  }' | jq
```

**Expected**: AI assistant responds intelligently

---

**Test Case**: Mixed Routing Behavior
```bash
# Start demo agent (has mixed routing)
cd test-agents/test-demo
export OPENAI_API_KEY=your_key_here
agentup agent serve --port 8004 &

# Test direct routing skill (system status)
curl -s -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "status"}],
        "messageId": "msg-004",
        "contextId": "context-003",
        "kind": "message"
      }
    },
    "id": "req-004"
  }' | jq

# Test AI routing skill  
curl -s -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "help me plan a trip to Paris"}],
        "messageId": "msg-005",
        "contextId": "context-003",
        "kind": "message"
      }
    },
    "id": "req-005"
  }' | jq
```

**Expected**:
- First request uses direct routing to system_status skill
- Second request uses AI routing to ai_assistant skill

## 4. Edge Case Tests

### 4.1 Missing Handler Tests

**Test Case**: Skill Defined But Handler Missing
```yaml
# test-missing-handler.yaml
agent:
  name: MissingHandler
  description: Skill without handler
  version: 0.1.0

routing:
  default_mode: direct
  fallback_skill: nonexistent_skill

skills:
  - skill_id: nonexistent_skill
    name: Missing Skill
    routing_mode: direct
    keywords: [test]

security:
  enabled: false
```

**Test**: Start agent and send request
```bash
agentup agent validate --config test-missing-handler.yaml --check-handlers
agentup agent serve --config test-missing-handler.yaml
```

**Expected**: 
- Validation warns about missing handler
- Runtime handles gracefully with error message

### 4.2 Fallback Scenario Tests

**Test Case**: AI Fallback to Direct
```yaml
# test-ai-fallback.yaml  
agent:
  name: AIFallback
  description: AI with fallback enabled
  version: 0.1.0

routing:
  default_mode: ai
  fallback_skill: echo
  fallback_enabled: true

skills:
  - skill_id: ai_assistant
    name: AI Assistant
    routing_mode: ai
  - skill_id: echo
    name: Echo Skill
    routing_mode: direct
    keywords: [echo]
    patterns: ['.*']

ai:
  enabled: true
  llm_service: openai

# Intentionally misconfigured or missing service
services: {}

security:
  enabled: false
```

**Test**: Start agent without valid LLM service
```bash
agentup agent serve --config test-ai-fallback.yaml
# Send request - should fallback to direct routing
```

**Expected**: Graceful fallback to echo skill when AI unavailable

### 4.3 Security Integration Tests

**Test Case**: Authentication with Routing
```yaml
# test-auth-routing.yaml
agent:
  name: AuthAgent
  description: Authentication with routing
  version: 0.1.0

routing:
  default_mode: direct
  fallback_skill: echo

skills:
  - skill_id: echo
    name: Echo Skill
    routing_mode: direct
    keywords: [echo]

security:
  enabled: true
  type: api_key
  api_key:
    header_name: X-API-Key
    location: header
    keys:
      - valid-test-key
```

**Test**: 
```bash
# Valid auth
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: valid-test-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "echo test"}],
        "messageId": "msg-006",
        "contextId": "context-004",
        "kind": "message"
      }
    },
    "id": "req-006"
  }' | jq

# Invalid auth  
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: invalid-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "echo test"}],
        "messageId": "msg-007",
        "contextId": "context-004",
        "kind": "message"
      }
    },
    "id": "req-007"
  }' | jq

# Missing auth
curl -s -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "echo test"}],
        "messageId": "msg-008",
        "contextId": "context-004",
        "kind": "message"
      }
    },
    "id": "req-008"
  }' | jq
```

**Expected**: Proper authentication enforcement regardless of routing mode

## 5. Performance Tests

### 5.1 Routing Performance Comparison

**Test Case**: Measure Direct vs AI Routing Performance

```bash
# Setup
cd test-agents/test-minimal  # Direct routing
agentup agent serve --port 8001 &

cd ../test-standard  # AI routing  
export OPENAI_API_KEY=your_key_here
agentup agent serve --port 8002 &

# Benchmark direct routing (repeat 10 times, measure)
for i in {1..10}; do
  time curl -s -X POST http://localhost:8001/ \
    -H "Content-Type: application/json" \
    -H "X-API-Key: test-key" \
    -d '{
      "jsonrpc": "2.0",
      "method": "message/send",
      "params": {
        "message": {
          "role": "user",
          "parts": [{"kind": "text", "text": "echo performance test"}],
          "messageId": "perf-'$i'",
          "contextId": "perf-context",
          "kind": "message"
        }
      },
      "id": "perf-'$i'"
    }' > /dev/null
done

# Benchmark AI routing (repeat 10 times, measure)  
for i in {1..10}; do
  time curl -s -X POST http://localhost:8002/ \
    -H "Content-Type: application/json" \
    -H "X-API-Key: test-key" \
    -d '{
      "jsonrpc": "2.0",
      "method": "message/send", 
      "params": {
        "message": {
          "role": "user",
          "parts": [{"kind": "text", "text": "What is 2+2?"}],
          "messageId": "ai-perf-'$i'",
          "contextId": "ai-perf-context",
          "kind": "message"
        }
      },
      "id": "ai-perf-'$i'"
    }' > /dev/null
done
```

**Expected**:
- Direct routing: 1-50ms response time
- AI routing: 100-2000ms response time (depending on LLM)

### 5.2 Concurrent Request Tests

**Test Case**: Multiple Simultaneous Requests
```bash
# Send 10 concurrent requests to mixed routing agent
for i in {1..10}; do
  curl -s -X POST http://localhost:8004/ \
    -H "Content-Type: application/json" \
    -H "X-API-Key: test-key" \
    -d '{
      "jsonrpc": "2.0",
      "method": "message/send",
      "params": {
        "message": {
          "role": "user",
          "parts": [{"kind": "text", "text": "concurrent test '$i'"}],
          "messageId": "concurrent-'$i'",
          "contextId": "concurrent-context",
          "kind": "message"
        }
      },
      "id": "concurrent-'$i'"
    }' > /tmp/concurrent_result_$i.json &
done
wait

# Check all results
for i in {1..10}; do
  echo "Result $i:"
  cat /tmp/concurrent_result_$i.json | jq '.result.status.state'
done
```

**Expected**: All requests handled correctly without routing conflicts

## 6. Documentation Verification Tests

### 6.1 Example Validation

**Test**: Verify all configuration examples in documentation are valid
```bash
# Extract YAML blocks from documentation and validate each one
# This can be automated with a script that parses markdown
```

**Expected**: All documented examples pass validation

### 6.2 Migration Guide Tests

**Test**: Follow migration guide step-by-step with real configuration
```bash
# Start with legacy config from migration guide
# Apply each migration step
# Verify result works
```

**Expected**: Migration process works as documented

## 7. Error Handling Tests

### 7.1 Malformed Configuration

**Test Cases**:
- Invalid YAML syntax
- Missing required fields
- Circular skill references
- Invalid routing mode values
- Conflicting routing configurations

### 7.2 Runtime Error Recovery

**Test Cases**:
- Handler throws exception
- LLM service timeout
- Network connectivity issues
- Memory/resource constraints

## QA Checklist

- [ ] All validation tests pass/fail as expected
- [ ] All templates generate valid configurations
- [ ] Agent startup works for all templates
- [ ] Direct routing matches correct skills
- [ ] AI routing responds intelligently (if LLM available)
- [ ] Mixed routing uses appropriate mode per skill
- [ ] Fallback routing works when primary fails
- [ ] Legacy configurations work with warnings
- [ ] Authentication integrates properly with routing
- [ ] Performance meets expectations
- [ ] Error handling is graceful
- [ ] Documentation examples are accurate
- [ ] Migration guide is functional

## Environment Requirements

- Python with uv package manager
- Optional: OpenAI API key for AI routing tests
- Optional: Docker for containerized testing
- Sufficient disk space for test agent creation
- Network access for LLM API calls (if testing AI routing)

## Test Execution Notes

### Setup Test Environment
```bash
# Create test directory
mkdir -p test-routing-qa
cd test-routing-qa

# Create all test configuration files
# (Copy the YAML configurations from above into separate files)
```

### Automated Testing Script
```bash
#!/bin/bash
# qa-test-runner.sh

echo "🧪 Running AgentUp Routing QA Tests"

# Configuration validation tests
echo "📋 Testing configuration validation..."
agentup agent validate --config test-minimal.yaml
agentup agent validate --config test-ai.yaml
agentup agent validate --config test-mixed.yaml
agentup agent validate --config test-invalid-ai.yaml
agentup agent validate --config test-invalid-direct.yaml
agentup agent validate --config test-invalid-regex.yaml
agentup agent validate --config test-legacy.yaml

# Agent creation tests
echo "🏗️ Testing agent creation..."
agentup agent create test-minimal --template minimal --output-dir ./test-agents/
agentup agent create test-standard --template standard --output-dir ./test-agents/
agentup agent create test-full --template full --output-dir ./test-agents/
agentup agent create test-demo --template demo --output-dir ./test-agents/

echo "✅ QA Tests Complete"
```

This comprehensive test plan ensures the new routing system works correctly across all supported configurations and use cases.