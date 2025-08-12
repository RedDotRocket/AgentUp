import asyncio
import os

# Check if CrewAI is available
try:
    from crewai import Agent, Crew, Process, Task

    CREWAI_AVAILABLE = True
except ImportError:
    print("CrewAI not installed. Install with: pip install crewai")
    CREWAI_AVAILABLE = False

# Import AgentUp integration
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from crewai.agentup_tool import AgentUpTool  # type: ignore  # noqa: I001


def create_basic_crew(
    agentup_url: str = "http://localhost:8000",
    api_key: str | None = None,
) -> Crew | None:
    """Create a basic CrewAI crew with AgentUp integration.

    Args:
        agentup_url: URL of the AgentUp agent
        api_key: Optional API key for authentication

    Returns:
        Configured CrewAI crew or None if CrewAI not available
    """
    if not CREWAI_AVAILABLE:
        print("CrewAI is not available")
        return None

    # Create AgentUp tool
    agentup_tool = AgentUpTool(
        base_url=agentup_url,
        api_key=api_key,
        agent_name="Domain Expert",
        name="Domain Expert Tool",
        description="Access domain-specific expertise from AgentUp agent",
    )

    # Create CrewAI agents
    researcher = Agent(
        role="Senior Researcher",
        goal="Gather comprehensive information and insights on given topics",
        backstory=(
            "You are an experienced researcher with access to specialized tools. "
            "You excel at gathering accurate information and providing detailed analysis."
        ),
        tools=[agentup_tool],
        verbose=True,
        allow_delegation=False,
    )

    analyst = Agent(
        role="Data Analyst",
        goal="Analyze data and provide actionable insights",
        backstory=(
            "You are a skilled data analyst who can interpret complex information "
            "and extract meaningful patterns and recommendations."
        ),
        tools=[agentup_tool],
        verbose=True,
        allow_delegation=False,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Create clear, comprehensive reports from research and analysis",
        backstory=(
            "You are a technical writer who specializes in creating well-structured "
            "reports that communicate complex findings clearly."
        ),
        verbose=True,
        allow_delegation=False,
    )

    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[],  # Tasks will be added dynamically
        process=Process.sequential,
        verbose=2,
    )


def create_research_task(topic: str) -> Task | None:
    """Create a research task for the given topic.

    Args:
        topic: Research topic

    Returns:
        Configured Task or None if CrewAI not available
    """
    if not CREWAI_AVAILABLE:
        return None

    return Task(
        description=f"""
        Research the topic: {topic}

        Your task is to:
        1. Gather comprehensive information about {topic}
        2. Identify key trends, challenges, and opportunities
        3. Collect relevant data and statistics
        4. Note any recent developments or changes

        Use the AgentUp tool to access specialized knowledge and expertise.
        Provide detailed findings with proper context and explanations.
        """,
        expected_output=f"Comprehensive research report on {topic} with key findings and insights",
        agent=None,  # Will be assigned when added to crew
    )


def create_analysis_task() -> Task | None:
    """Create an analysis task.

    Returns:
        Configured Task or None if CrewAI not available
    """
    if not CREWAI_AVAILABLE:
        return None

    return Task(
        description="""
        Analyze the research findings from the previous task.

        Your task is to:
        1. Review all gathered information
        2. Identify patterns and correlations
        3. Assess the significance of findings
        4. Provide actionable insights and recommendations
        5. Highlight potential risks and opportunities

        Use the AgentUp tool if you need additional specialized analysis.
        Focus on practical implications and strategic recommendations.
        """,
        expected_output="Detailed analysis with insights, patterns, and actionable recommendations",
        agent=None,  # Will be assigned when added to crew
    )


def create_report_task() -> Task | None:
    """Create a report writing task.

    Returns:
        Configured Task or None if CrewAI not available
    """
    if not CREWAI_AVAILABLE:
        return None

    return Task(
        description="""
        Create a comprehensive final report based on the research and analysis.

        Your task is to:
        1. Synthesize all research findings and analysis
        2. Structure the information in a clear, logical format
        3. Include executive summary, detailed findings, and recommendations
        4. Ensure the report is professional and actionable
        5. Add proper conclusions and next steps

        The report should be well-formatted and suitable for stakeholders.
        Include all key insights and recommendations from the analysis.
        """,
        expected_output="Professional comprehensive report with executive summary, findings, analysis, and recommendations",
        agent=None,  # Will be assigned when added to crew
    )


def run_basic_example(
    topic: str = "Artificial Intelligence in Healthcare",
    agentup_url: str = "http://localhost:8000",
    api_key: str | None = None,
) -> str:
    """Run the basic CrewAI + AgentUp example.

    Args:
        topic: Research topic
        agentup_url: URL of the AgentUp agent
        api_key: Optional API key for authentication

    Returns:
        Final report or error message
    """
    if not CREWAI_AVAILABLE:
        return "CrewAI is not installed. Please install with: pip install crewai"

    print("Starting CrewAI + AgentUp integration example")
    print(f"Topic: {topic}")
    print(f"AgentUp URL: {agentup_url}")
    print(f"API Key: {'***' if api_key else 'None'}")
    print()

    try:
        # Create crew
        crew = create_basic_crew(agentup_url, api_key)
        if not crew:
            return "Failed to create crew"

        # Create tasks
        research_task = create_research_task(topic)
        analysis_task = create_analysis_task()
        report_task = create_report_task()

        if not all([research_task, analysis_task, report_task]):
            return "Failed to create tasks"

        # Assign agents to tasks
        research_task.agent = crew.agents[0]  # researcher
        analysis_task.agent = crew.agents[1]  # analyst
        report_task.agent = crew.agents[2]  # writer

        # Add tasks to crew
        crew.tasks = [research_task, analysis_task, report_task]

        print("Crew assembled with 3 agents and 3 tasks")
        print("▶Starting workflow execution...\n")

        # Execute the crew
        result = crew.kickoff()

        print("\nWorkflow completed successfully!")
        print("Final Report:")
        print("=" * 50)
        return str(result)

    except Exception as e:
        error_msg = f"❌ Error during execution: {str(e)}"
        print(error_msg)
        return error_msg


async def test_agentup_connection(
    agentup_url: str = "http://localhost:8000",
    api_key: str | None = None,
) -> bool:
    """Test connection to AgentUp agent.

    Args:
        agentup_url: URL of the AgentUp agent
        api_key: Optional API key for authentication

    Returns:
        True if connection successful, False otherwise
    """
    try:
        from crewai.a2a_client import A2AClient  # type: ignore  # noqa: I001

        async with A2AClient(base_url=agentup_url, api_key=api_key) as client:
            agent_card = await client.get_agent_card()
            print(f"Connected to AgentUp agent: {agent_card.get('name', 'Unknown')}")
            print(f"Description: {agent_card.get('description', 'N/A')}")
            print(f"Skills: {len(agent_card.get('skills', []))}")
            return True

    except Exception as e:
        print(f"❌ Failed to connect to AgentUp agent: {str(e)}")
        return False


def main():
    """Main function to run the example."""
    # Configuration from environment variables
    agentup_url = os.getenv("AGENTUP_URL", "http://localhost:8000")
    api_key = os.getenv("AGENTUP_API_KEY")
    topic = os.getenv("RESEARCH_TOPIC", "Artificial Intelligence in Healthcare")

    print("CrewAI + AgentUp Basic Integration Example")
    print("=" * 50)

    # Test connection first
    print("Testing AgentUp connection...")
    if asyncio.run(test_agentup_connection(agentup_url, api_key)):
        print("✅ Connection successful, proceeding with example\n")

        # Run the example
        result = run_basic_example(topic, agentup_url, api_key)
        print(result)
    else:
        print("❌ Cannot proceed without AgentUp connection")
        print("\n Make sure:")
        print("   1. AgentUp agent is running")
        print("   2. URL is correct")
        print("   3. API key is valid (if required)")


if __name__ == "__main__":
    main()
