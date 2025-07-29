from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    # Connect to a streamable HTTP server
    print("Connecting to MCP streamable HTTP server...")
    async with streamablehttp_client("/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()
            # Call a tool
            tool_result = await session.call_tool("echo", {"message": "hello"})
            print(f"Tool result: {tool_result}")

            # List available resources
            resources = await session.list_resources()
            print(f"Available resources: {resources}")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user, exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
