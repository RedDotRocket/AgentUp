#!/usr/bin/env python3
"""
Simple MCP Streamable HTTP Test

A focused test script demonstrating MCP streamable HTTP transport
with the official MCP Python SDK.
"""

import asyncio
import sys

try:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    print("✓ MCP SDK available")
except ImportError as e:
    print(f"✗ MCP SDK not available: {e}")
    print("Install with: pip install mcp")
    sys.exit(1)


async def check_server_health(base_url: str) -> bool:
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test basic server connectivity
            try:
                health_response = await client.get(f"{base_url}/health")
                if health_response.status_code == 200:
                    print(f"✓ Server health check passed (status: {health_response.status_code})")
                    return True
                else:
                    print(f"  Server responded but health check failed (status: {health_response.status_code})")
            except Exception:
                print("  Health endpoint not available, checking root...")

            # Test root endpoint
            try:
                root_response = await client.get(base_url)
                print(f"✓ Server is responding (status: {root_response.status_code})")
                return True
            except Exception:
                print(f"✗ Server not responding at {base_url}")
                return False

    except Exception as e:
        print(f"✗ Server connectivity check failed: {e}")
        return False


async def check_mcp_endpoint(server_url: str) -> bool:
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try a basic POST to the MCP endpoint to see if it exists
            test_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "test-123",
                "params": {
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }

            response = await client.post(
                server_url,
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                print(f"✓ MCP endpoint responding (status: {response.status_code})")

                # Debug: Show the actual response
                try:
                    response_json = response.json()
                    print(f"Response structure: {list(response_json.get('result', {}).keys())}")
                    if 'result' in response_json:
                        result = response_json['result']
                        if 'protocolVersion' in result:
                            print(f"✓ protocolVersion found: {result['protocolVersion']}")
                        else:
                            print(f"✗ protocolVersion missing! Response: {result}")
                except Exception as e:
                    print(f"  Could not parse response as JSON: {e}")

                return True
            else:
                print(f"  MCP endpoint exists but returned status: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return True  # Endpoint exists, might just be protocol issue

    except Exception as e:
        print(f"✗ MCP endpoint check failed: {e}")
        return False


async def test_mcp_streamable_http():
    

    base_url = "http://localhost:8001"
    server_url = f"{base_url}/mcp"
    print(f"🔗 Testing MCP Streamable HTTP at: {server_url}")

    # Pre-flight checks
    print("\nRunning pre-flight checks...")

    server_ok = await check_server_health(base_url)
    if not server_ok:
        print("✗ Server is not responding. Please check:")
        print("   1. Is the AgentUp server running?")
        print("   2. Is it running on port 8001?")
        print("   3. Try: agentup agent serve --port 8001")
        return

    mcp_ok = await check_mcp_endpoint(server_url)
    if not mcp_ok:
        print("✗ MCP endpoint is not available. Please check:")
        print("   1. Is MCP enabled in your agentup.yml?")
        print("   2. Is the MCP server configuration correct?")
        return

    print("\n Starting MCP streamable HTTP test...")

    try:
        # Connect using streamable HTTP client with timeout
        print(" Establishing streamable HTTP connection...")

        async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
            print("✓ Streamable HTTP connection established")

            # Create client session
            print("🔗 Creating MCP client session...")
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")

                # Initialize the connection
                print("🤝 Initializing MCP session...")
                await session.initialize()
                print("✓ Session initialized")

                # Test 1: List available tools
                print("\nListing available tools...")
                tools_result = await session.list_tools()
                tools = tools_result.tools if hasattr(tools_result, 'tools') else []
                print(f"Found {len(tools)} tools:")
                for tool in tools:
                    print(f"  • {tool.name}: {tool.description}")

                # Test 2: Call echo tool
                if any(tool.name == "echo" for tool in tools):
                    print("\n🔊 Testing echo tool...")
                    result = await session.call_tool("echo", {"message": "Hello from MCP client!"})
                    print(f"Echo result: {result}")

                # Test 3: List resources
                print("\n Listing available resources...")
                try:
                    resources_result = await session.list_resources()
                    resources = resources_result.resources if hasattr(resources_result, 'resources') else []
                    print(f"Found {len(resources)} resources:")
                    for resource in resources:
                        print(f"  • {resource.name}: {resource.uri}")

                    # Test reading a resource
                    if resources:
                        print(f"\n Reading resource: {resources[0].uri}")
                        content = await session.read_resource(resources[0].uri)
                        print(f"Resource content: {content}")

                except Exception as e:
                    print(f" Resources not supported or failed: {e}")

                # Test 4: Call a file operation tool
                if any(tool.name == "get_system_info" for tool in tools):
                    print("\n💻 Testing system info tool...")
                    result = await session.call_tool("get_system_info", {})
                    print(f"System info: {result}")

                print("\n✓ All tests completed successfully!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        print("\n Debugging information:")

        # Provide specific debugging based on error type
        error_str = str(e)
        if "ConnectError" in error_str:
            print("  • Connection error - server may not be running or reachable")
        elif "TaskGroup" in error_str:
            print("  • Task group error - possible protocol or implementation issue")
        elif "timeout" in error_str.lower():
            print("  • Timeout error - server may be slow or not responding properly")
        elif "json" in error_str.lower():
            print("  • JSON parsing error - server may not be returning valid responses")
        else:
            print(f"  • Unexpected error type: {type(e).__name__}")

        print("\n Troubleshooting steps:")
        print("  1. Verify server is running: curl http://localhost:8001/health")
        print("  2. Check MCP endpoint: curl -X POST http://localhost:8001/mcp")
        print("  3. Review server logs for errors")
        print("  4. Ensure MCP server configuration is correct")

        import traceback
        print("\n🐛 Full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    print(" MCP Streamable HTTP Test Starting...")
    asyncio.run(test_mcp_streamable_http())
    print("🏁 Test completed")
