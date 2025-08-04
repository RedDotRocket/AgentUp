#!/usr/bin/env python3
import asyncio
import httpx

async def test_format():
    """Quick test of JSON-RPC format"""
    url = "http://localhost:8000/"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "test-api-key"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello test"}],
                "message_id": "format-test",
                "kind": "message"
            }
        },
        "id": "req-format-test"
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_format())
    print(f"Success: {result}")