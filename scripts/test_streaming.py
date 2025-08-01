#!/usr/bin/env python3
"""
A2A Streaming Test Client for AgentUp

This script tests the message/stream endpoint
"""

import argparse
import asyncio
import json
import sys
import time

import httpx
import structlog

# Set up logging
logger = structlog.get_logger(__name__)

class StreamingTestClient:


    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.session_timeout = 30.0

    def _get_headers(self) -> dict[str, str]:

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        return headers

    def _create_stream_request(self, message_text: str, message_id: str | None = None) -> dict:

        if not message_id:
            message_id = f"msg-{int(time.time()*1000)}"

        return {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message_text}],
                    "message_id": message_id,
                    "kind": "message"
                }
            },
            "id": f"req-{int(time.time()*1000)}"
        }

    async def test_stream_endpoint(self, message: str, show_raw: bool = False) -> bool:

        print(f"Testing streaming endpoint: {self.base_url}/")
        print(f"Message: {message}")
        print("Starting stream...\n")

        request_data = self._create_stream_request(message)

        if show_raw:
            print("Request JSON:")
            print(json.dumps(request_data, indent=2))
            print()

        try:
            async with httpx.AsyncClient(timeout=self.session_timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/",
                    headers=self._get_headers(),
                    json=request_data
                ) as response:

                    print(f"Response Status: {response.status_code}")
                    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
                    print()

                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"Error Response: {error_text.decode()}")
                        return False

                    # Process SSE stream
                    event_count = 0
                    async for line in response.aiter_lines():
                        if show_raw:
                            print(f"Raw line: {repr(line)}")

                        # SSE format: "data: {json}\n"
                        if line.startswith("data: "):
                            event_count += 1
                            json_data = line[6:]  # Remove "data: " prefix

                            try:
                                event_data = json.loads(json_data)
                                await self._process_stream_event(event_data, event_count, show_raw)
                            except json.JSONDecodeError as e:
                                print(f"Invalid JSON in event {event_count}: {e}")
                                print(f"   Raw data: {json_data}")

                        elif line.strip() == "":
                            # Empty line marks end of SSE event
                            continue
                        else:
                            print(f"Non-data line: {line}")

                    print(f"\nStream completed. Total events: {event_count}")
                    return True

        except httpx.TimeoutException:
            print("Request timed out")
            return False
        except httpx.ConnectError:
            print("Failed to connect to server")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    async def _process_stream_event(self, event_data: dict, event_num: int, show_raw: bool = False) -> None:

        print(f"Event {event_num}:")

        if show_raw:
            print(f"   Raw JSON: {json.dumps(event_data, indent=4)}")

        # Check if it's an error response
        if "error" in event_data:
            error = event_data["error"]
            print(f"   Error: {error.get('message', 'Unknown error')}")
            if "code" in error:
                print(f"   Error Code: {error['code']}")
            return

        # Check if it's a successful response
        if "result" in event_data:
            result = event_data["result"]

            # Extract task information
            task_id = result.get("id", "unknown")
            status = result.get("status", {})
            state = status.get("state", "unknown")

            print(f"   Task ID: {task_id}")
            print(f"   Status: {state}")

            # Extract artifacts if present
            artifacts = result.get("artifacts", [])
            if artifacts:
                print(f"   Artifacts ({len(artifacts)}):")
                for i, artifact in enumerate(artifacts):
                    artifact_id = artifact.get("artifactId", f"artifact-{i}")
                    name = artifact.get("name", "Unnamed")
                    parts = artifact.get("parts", [])

                    print(f"      📎 {name} ({artifact_id})")

                    # Show text parts
                    for part in parts:
                        if part.get("kind") == "text":
                            text = part.get("text", "")
                            # Truncate long text
                            if len(text) > 200:
                                text = text[:200] + "..."
                            print(f"         {text}")

            # Extract history if present
            history = result.get("history", [])
            if history:
                print(f"   History ({len(history)} messages):")
                for msg in history[-3:]:  # Show last 3 messages
                    role = msg.get("role", "unknown")
                    parts = msg.get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
                    if text_parts:
                        text = " ".join(text_parts)
                        if len(text) > 100:
                            text = text[:100] + "..."
                        print(f"      👤 {role}: {text}")

        print()

    async def test_authentication(self) -> bool:

        print("🔐 Testing authentication...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test unauthenticated request
                response = await client.post(
                    f"{self.base_url}/",
                    headers={"Content-Type": "application/json"},
                    json={"jsonrpc": "2.0", "method": "status", "id": 1}
                )

                if response.status_code == 401:
                    print("Server requires authentication (as expected)")

                    if not self.auth_token:
                        print("No auth token provided, but authentication is required")
                        return False

                    # Test authenticated request
                    auth_response = await client.post(
                        f"{self.base_url}/",
                        headers=self._get_headers(),
                        json={"jsonrpc": "2.0", "method": "status", "id": 1}
                    )

                    if auth_response.status_code == 200:
                        print("Authentication successful")
                        return True
                    else:
                        print(f"Authentication failed: {auth_response.status_code}")
                        return False

                elif response.status_code == 200:
                    print("Server allows unauthenticated requests")
                    return True
                else:
                    print(f"Unexpected response: {response.status_code}")
                    return False

        except Exception as e:
            print(f"Authentication test failed: {e}")
            return False

    async def run_comprehensive_test(self, messages: list[str], show_raw: bool = False) -> None:

        print("🧪 Starting Comprehensive A2A Streaming Tests")
        print("=" * 50)
        print()

        # Test authentication first
        auth_ok = await self.test_authentication()
        if not auth_ok:
            print("Authentication test failed. Aborting.")
            return

        print()

        # Test each message
        success_count = 0
        for i, message in enumerate(messages, 1):
            print(f"🔹 Test {i}/{len(messages)}")
            print("-" * 30)

            success = await self.test_stream_endpoint(message, show_raw)
            if success:
                success_count += 1

            print()

            # Small delay between tests
            if i < len(messages):
                await asyncio.sleep(1)

        # Summary
        print("Test Summary")
        print("=" * 20)
        print(f"Successful: {success_count}/{len(messages)}")
        print(f"Failed: {len(messages) - success_count}/{len(messages)}")

        if success_count == len(messages):
            print("All tests passed!")
        else:
            print("Some tests failed. Check the output above for details.")


async def main():

    parser = argparse.ArgumentParser(
        description="Test A2A streaming endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test
  python test_streaming.py --url http://localhost:8000

  # With authentication
  python test_streaming.py --url http://localhost:8000 --token YOUR_TOKEN

  # Custom message
  python test_streaming.py --url http://localhost:8000 --message "Tell me a joke"

  # Show raw SSE data
  python test_streaming.py --url http://localhost:8000 --raw

  # Multiple test messages
  python test_streaming.py --url http://localhost:8000 --message "Hello" --message "How are you?" --message "Tell me about AI"
        """
    )

    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the server (default: http://localhost:8000)"
    )

    parser.add_argument(
        "--token",
        help="Authentication token (Bearer token)"
    )

    parser.add_argument(
        "--message",
        action="append",
        default=[],
        help="Message to send (can be specified multiple times)"
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw SSE data and JSON"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Default messages if none provided
    if not args.message:
        args.message = [
            "Hello, this is a streaming test",
            "Can you count from 1 to 5?",
            "Tell me a short joke"
        ]

    print(f"Target URL: {args.url}")
    print(f"Auth Token: {'Provided' if args.token else 'None'}")
    print(f"Messages: {len(args.message)}")
    print(f"Timeout: {args.timeout}s")
    print()

    # Create client and run tests
    client = StreamingTestClient(args.url, args.token)
    client.session_timeout = args.timeout

    try:
        await client.run_comprehensive_test(args.message, args.raw)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
