#!/usr/bin/env python3
"""
MCP Usage Example - Practical File Management

This demonstrates practical usage of MCP for file management and system operations
using the AgentUp MCP server.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"✗ MCP SDK not available: {e}")
    print("Install with: pip install mcp")
    MCP_AVAILABLE = False
    exit(1)


class MCPFileManager:
    """A practical file manager using MCP tools."""
    
    def __init__(self, server_url: str = "http://localhost:8000/mcp"):
        self.server_url = server_url
        self.session = None
        self.available_tools = []
    
    async def connect(self):
        """Connect to the MCP server."""
        try:
            print(f"🔗 Connecting to MCP server at {self.server_url}")
            
            # Use context manager for proper cleanup
            self.client_context = streamablehttp_client(self.server_url)
            read_stream, write_stream, _ = await self.client_context.__aenter__()
            
            self.session = ClientSession(read_stream, write_stream)
            await self.session.initialize()
            
            # Get available tools
            tools = await self.session.list_tools()
            self.available_tools = [tool.name for tool in tools]
            
            print(f"✓ Connected! Available tools: {', '.join(self.available_tools)}")
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            if self.session:
                await self.session.close()
            if hasattr(self, 'client_context'):
                await self.client_context.__aexit__(None, None, None)
            print("🔌 Disconnected from MCP server")
        except Exception as e:
            print(f"⚠️  Disconnect warning: {e}")
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool with error handling."""
        if tool_name not in self.available_tools:
            print(f"✗ Tool '{tool_name}' not available")
            return None
            
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            print(f"✗ Tool call failed for '{tool_name}': {e}")
            return None
    
    async def create_test_environment(self):
        """Create a test environment for file operations."""
        print("\n🏗️  Creating test environment...")
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
        print(f"📁 Created temp directory: {temp_dir}")
        
        # Create test files using MCP
        test_files = [
            {"name": "hello.txt", "content": "Hello, MCP World!"},
            {"name": "data.json", "content": json.dumps({"test": True, "timestamp": "2025-01-01"})},
            {"name": "notes.md", "content": "# MCP Test Notes\n\nThis is a test file created via MCP."},
        ]
        
        for file_info in test_files:
            file_path = os.path.join(temp_dir, file_info["name"])
            result = await self.call_tool("write_file", {
                "path": file_path,
                "content": file_info["content"]
            })
            
            if result:
                print(f"✓ Created: {file_info['name']}")
            else:
                print(f"✗ Failed to create: {file_info['name']}")
        
        return temp_dir
    
    async def explore_directory(self, directory_path: str):
        """Explore a directory using MCP tools."""
        print(f"\nExploring directory: {directory_path}")
        
        # List directory contents
        result = await self.call_tool("list_directory", {"path": directory_path})
        if result:
            print("Directory contents:")
            for item in result:
                print(f"  • {item}")
        
        # Get directory info
        result = await self.call_tool("get_file_info", {"path": directory_path})
        if result:
            print(f"Directory info: {result}")
    
    async def read_and_analyze_files(self, directory_path: str):
        """Read and analyze files in a directory."""
        print(f"\n📖 Reading files in: {directory_path}")
        
        # List files first
        files_result = await self.call_tool("list_directory", {"path": directory_path})
        if not files_result:
            print("✗ Could not list directory")
            return
        
        for file_name in files_result:
            file_path = os.path.join(directory_path, file_name)
            
            # Check if it's a file
            exists_result = await self.call_tool("file_exists", {"path": file_path})
            if not exists_result:
                continue
            
            # Get file info
            info_result = await self.call_tool("get_file_info", {"path": file_path})
            if info_result:
                print(f"\nFile: {file_name}")
                print(f"   Size: {info_result.get('size', 'unknown')} bytes")
                print(f"   Modified: {info_result.get('modified', 'unknown')}")
            
            # Read file content
            content_result = await self.call_tool("read_file", {"path": file_path})
            if content_result:
                print(f"   Content preview: {content_result[:100]}...")
            
            # Get file hash
            hash_result = await self.call_tool("get_file_hash", {"path": file_path})
            if hash_result:
                print(f"   SHA256: {hash_result}")
    
    async def cleanup_test_environment(self, directory_path: str):
        """Clean up the test environment."""
        print(f"\n🧹 Cleaning up: {directory_path}")
        
        # List files to delete
        files_result = await self.call_tool("list_directory", {"path": directory_path})
        if files_result:
            for file_name in files_result:
                file_path = os.path.join(directory_path, file_name)
                result = await self.call_tool("delete_file", {"path": file_path})
                if result:
                    print(f"🗑️  Deleted: {file_name}")
        
        # Remove the directory itself (using Python since MCP might not have rmdir)
        try:
            os.rmdir(directory_path)
            print(f"🗑️  Removed directory: {directory_path}")
        except Exception as e:
            print(f"⚠️  Could not remove directory: {e}")
    
    async def run_file_management_demo(self):
        """Run a complete file management demonstration."""
        print(" Starting MCP File Management Demo")
        print("=" * 50)
        
        if not await self.connect():
            return
        
        try:
            # Create test environment
            temp_dir = await self.create_test_environment()
            
            # Explore the directory
            await self.explore_directory(temp_dir)
            
            # Read and analyze files
            await self.read_and_analyze_files(temp_dir)
            
            # Test system info
            print("\n💻 Getting system information...")
            system_info = await self.call_tool("get_system_info", {})
            if system_info:
                print(f"System: {system_info}")
            
            # Test working directory
            print("\n📂 Getting working directory...")
            working_dir = await self.call_tool("get_working_directory", {})
            if working_dir:
                print(f"Working directory: {working_dir}")
            
            # Cleanup
            await self.cleanup_test_environment(temp_dir)
            
            print("\n✓ File management demo completed successfully!")
            
        except Exception as e:
            print(f"✗ Demo failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    if not MCP_AVAILABLE:
        return
    
    # Create and run the file manager demo
    file_manager = MCPFileManager()
    await file_manager.run_file_management_demo()


if __name__ == "__main__":
    asyncio.run(main())