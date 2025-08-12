#!/usr/bin/env python3
"""
Streaming CrewAI + AgentUp Integration Example

This example demonstrates real-time streaming capabilities between CrewAI and AgentUp,
showing how to handle streaming responses and provide real-time feedback.
"""

import asyncio
import os
import time

# Check if CrewAI is available
try:
    from crewai import Agent, Task  # noqa: F401

    CREWAI_AVAILABLE = True
except ImportError:
    print("CrewAI not installed. Install with: pip install crewai")
    CREWAI_AVAILABLE = False

# Import AgentUp integration
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from crewai.agentup_tool import AgentUpTool  # type: ignore


class StreamingAgentUpTool(AgentUpTool):
    """Extended AgentUp tool with enhanced streaming capabilities."""

    def __init__(self, *args, **kwargs):
        """Initialize the streaming tool."""
        super().__init__(*args, **kwargs)
        self.streaming_enabled = True

    async def stream_with_callback(self, query: str, callback=None, context_id: str | None = None) -> str:
        """Stream response with real-time callback.

        Args:
            query: Query to send to AgentUp agent
            callback: Callback function to handle streaming chunks
            context_id: Optional context ID

        Returns:
            Complete response text
        """
        full_response = ""
        chunk_count = 0

        try:
            async for chunk in self.stream_response(query, context_id):
                chunk_count += 1

                # Extract text from chunk if it's a dict
                if isinstance(chunk, dict):
                    if "error" in chunk:
                        if callback:
                            callback(f"❌ Error: {chunk['error']}", chunk_count, True)
                        break

                    # Handle different chunk formats
                    chunk_text = ""
                    if "message" in chunk:
                        message = chunk["message"]
                        if isinstance(message, dict) and "parts" in message:
                            for part in message["parts"]:
                                if part.get("kind") == "text":
                                    chunk_text = part.get("text", "")
                    elif "text" in chunk:
                        chunk_text = chunk["text"]
                    elif "content" in chunk:
                        chunk_text = chunk["content"]
                    else:
                        chunk_text = str(chunk)

                    if chunk_text:
                        full_response += chunk_text
                        if callback:
                            callback(chunk_text, chunk_count, False)

                # Small delay to make streaming visible
                await asyncio.sleep(0.1)

        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            if callback:
                callback(error_msg, chunk_count, True)
            full_response += error_msg

        if callback:
            callback("", chunk_count, True)  # Signal completion

        return full_response or f"No response received from {self.agent_name}"


class StreamingWorkflowManager:
    """Manage streaming workflows with real-time feedback."""

    def __init__(
        self,
        agentup_url: str = "http://localhost:8000",
        api_key: str | None = None,
    ):
        """Initialize the streaming manager.

        Args:
            agentup_url: URL of the AgentUp agent
            api_key: Optional API key for authentication
        """
        self.agentup_url = agentup_url
        self.api_key = api_key
        self.streaming_tool = None

    async def setup(self):
        """Setup the streaming tool and test connection."""
        if not CREWAI_AVAILABLE:
            print("CrewAI not available")
            return False

        self.streaming_tool = StreamingAgentUpTool(
            base_url=self.agentup_url,
            api_key=self.api_key,
            agent_name="Streaming Agent",
            name="Streaming AgentUp Tool",
            description="AgentUp agent with streaming capabilities",
        )

        # Test connection
        try:
            capabilities = await self.streaming_tool.get_capabilities()
            print("✅ Connected to streaming agent")
            print(f"🎯 Capabilities: {len(capabilities)} items")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {str(e)}")
            return False

    def create_streaming_callback(self, task_name: str):
        """Create a callback for streaming updates.

        Args:
            task_name: Name of the task for display

        Returns:
            Callback function
        """

        def callback(chunk: str, chunk_number: int, is_complete: bool):
            if is_complete:
                if chunk.startswith("❌"):
                    print(f"\n{chunk}")
                else:
                    print(f"\n✅ {task_name} completed ({chunk_number} chunks)")
            else:
                # Print streaming content with a prefix
                if chunk.strip():
                    print(f"📡 [{task_name}]: {chunk}", end="", flush=True)

        return callback

    async def run_streaming_research_task(self, topic: str, show_progress: bool = True) -> str:
        """Run a research task with streaming output.

        Args:
            topic: Research topic
            show_progress: Whether to show streaming progress

        Returns:
            Complete research result
        """
        if not self.streaming_tool:
            return "Tool not initialized"

        query = f"""
        Research the topic: {topic}

        Please provide a comprehensive analysis that includes:
        1. Background and context
        2. Current state and trends
        3. Key challenges and opportunities
        4. Future outlook and predictions
        5. Actionable insights and recommendations

        Take your time to provide detailed information, and think through
        each section carefully. This is for a comprehensive report.
        """

        print(f"🔬 Starting streaming research on: {topic}")
        print("📡 Streaming output (live):")
        print("=" * 50)

        if show_progress:
            callback = self.create_streaming_callback("Research")
        else:
            callback = None

        start_time = time.time()
        result = await self.streaming_tool.stream_with_callback(query, callback=callback)
        end_time = time.time()

        print(f"\n⏱️  Total time: {end_time - start_time:.2f} seconds")
        return result

    async def run_interactive_conversation(self):
        """Run an interactive streaming conversation."""
        if not self.streaming_tool:
            print("Tool not initialized")
            return

        print("💬 Interactive Streaming Conversation Mode")
        print("Type 'exit' to quit, 'clear' to clear context")
        print("=" * 50)

        context_id = f"interactive-{int(time.time())}"

        while True:
            try:
                user_input = input("\n🤔 Your question: ").strip()

                if user_input.lower() in ["exit", "quit"]:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == "clear":
                    context_id = f"interactive-{int(time.time())}"
                    print("🧹 Context cleared")
                    continue

                if not user_input:
                    continue

                print("\n🤖 Agent response:")
                print("-" * 30)

                # Simple callback for interactive mode
                def interactive_callback(chunk: str, chunk_num: int, complete: bool):
                    if complete:
                        print()  # New line after completion
                    else:
                        if chunk.strip():
                            print(chunk, end="", flush=True)

                await self.streaming_tool.stream_with_callback(
                    user_input, callback=interactive_callback, context_id=context_id
                )

            except KeyboardInterrupt:
                print("\n👋 Conversation interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")

    async def run_parallel_streaming_tasks(self, topics: list[str]) -> dict[str, str]:
        """Run multiple streaming tasks in parallel.

        Args:
            topics: List of topics to research in parallel

        Returns:
            Dictionary mapping topics to results
        """
        if not self.streaming_tool:
            return {}

        print(f"🔄 Running {len(topics)} parallel streaming tasks")
        print("Topics:", ", ".join(topics))
        print("=" * 50)

        # Create tasks
        tasks = []
        for _i, topic in enumerate(topics):
            task = self.run_streaming_research_task(
                topic,
                show_progress=False,  # Disable individual progress for parallel
            )
            tasks.append((topic, task))

        # Run tasks concurrently with progress tracking
        results = {}
        completed = 0

        async def track_task(topic: str, task_coro):
            nonlocal completed
            print(f"🚀 Started: {topic}")
            result = await task_coro
            completed += 1
            print(f"✅ Completed ({completed}/{len(topics)}): {topic}")
            return topic, result

        # Execute all tasks
        tracked_tasks = [track_task(topic, task_coro) for topic, task_coro in tasks]

        task_results = await asyncio.gather(*tracked_tasks, return_exceptions=True)

        # Process results
        for result in task_results:
            if isinstance(result, Exception):
                print(f"❌ Task failed: {str(result)}")
            else:
                topic, task_result = result
                results[topic] = task_result

        print(f"\n🎉 All parallel tasks completed: {len(results)}/{len(topics)} successful")
        return results


async def demonstrate_streaming_capabilities():
    """Demonstrate various streaming capabilities."""
    # Configuration
    agentup_url = os.getenv("AGENTUP_URL", "http://localhost:8000")
    api_key = os.getenv("AGENTUP_API_KEY")

    print("🌊 AgentUp Streaming Integration Demo")
    print("=" * 40)

    # Initialize manager
    manager = StreamingWorkflowManager(agentup_url, api_key)

    if not await manager.setup():
        print("❌ Cannot proceed without AgentUp connection")
        return

    # Demo 1: Single streaming task
    print("\n🎯 Demo 1: Single Streaming Research Task")
    result1 = await manager.run_streaming_research_task("Future of Renewable Energy Technology")
    print(f"\n📄 Final result length: {len(result1)} characters")

    # Demo 2: Parallel streaming tasks
    print("\n🎯 Demo 2: Parallel Streaming Tasks")
    topics = ["Artificial Intelligence Ethics", "Quantum Computing Applications", "Sustainable Urban Development"]
    results = await manager.run_parallel_streaming_tasks(topics)

    for topic, result in results.items():
        print(f"\n📊 {topic}: {len(result)} characters")

    # Demo 3: Interactive conversation (optional)
    response = input("\n🤔 Would you like to try interactive mode? (y/n): ")
    if response.lower().startswith("y"):
        await manager.run_interactive_conversation()


def main():
    """Main function to run the streaming example."""
    print("🌊 CrewAI + AgentUp Streaming Integration Example")
    print("=" * 50)

    try:
        asyncio.run(demonstrate_streaming_capabilities())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")


if __name__ == "__main__":
    main()
