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

from crewai.agentup_tool import AgentUpTool, create_agentup_tools  # type: ignore  # noqa: I001
from crewai.discovery import AgentUpDiscovery  # type: ignore  # noqa: I001


class MultiAgentWorkflow:
    """Multi-agent workflow orchestrator using CrewAI and AgentUp."""

    def __init__(
        self,
        agentup_configs: list[dict[str, str]],
        global_api_key: str | None = None,
    ):
        """Initialize the multi-agent workflow.

        Args:
            agentup_configs: List of AgentUp agent configurations
            global_api_key: Global API key for all agents (if not specified per agent)
        """
        self.agentup_configs = agentup_configs
        self.global_api_key = global_api_key
        self.agentup_tools: list[AgentUpTool] = []
        self.crew: Crew | None = None

    async def setup_agentup_tools(self):
        """Setup AgentUp tools from configurations."""
        if not CREWAI_AVAILABLE:
            print("CrewAI not available, skipping tool setup")
            return

        # Prepare agent configs for tool creation
        agent_configs = []
        for config in self.agentup_configs:
            agent_config = {
                "name": config["name"],
                "base_url": config["base_url"],
                "api_key": config.get("api_key", self.global_api_key),
                "description": config.get("description"),
            }
            agent_configs.append(agent_config)

        # Create tools
        self.agentup_tools = create_agentup_tools(agent_configs)
        print(f"✅ Created {len(self.agentup_tools)} AgentUp tools")

        # Test connections
        for tool in self.agentup_tools:
            is_healthy = tool.health_check()
            status = "✅" if is_healthy else "❌"
            print(f"   {status} {tool.agent_name}: {tool.config.base_url}")

    def create_crew(self) -> Crew | None:
        """Create a multi-agent CrewAI crew."""
        if not CREWAI_AVAILABLE or not self.agentup_tools:
            return None

        # Create different types of agents with different tool combinations

        # Coordinator agent with access to all tools
        coordinator = Agent(
            role="Project Coordinator",
            goal="Coordinate complex projects by leveraging specialized agents",
            backstory=(
                "You are an experienced project coordinator who knows how to "
                "delegate tasks to the right specialists. You have access to "
                "multiple specialized agents and can orchestrate their work."
            ),
            tools=self.agentup_tools,  # All tools available
            verbose=True,
            allow_delegation=True,
            max_execution_time=300,  # 5 minutes max
        )

        # Research specialist with research-focused tools
        research_tools = [
            tool for tool in self.agentup_tools if "research" in tool.name.lower() or "data" in tool.name.lower()
        ]
        if not research_tools:
            research_tools = self.agentup_tools[:2]  # First 2 tools as fallback

        researcher = Agent(
            role="Senior Research Specialist",
            goal="Conduct thorough research and gather comprehensive information",
            backstory=(
                "You are a research specialist who excels at finding and "
                "synthesizing information from multiple sources. You work with "
                "specialized research tools to gather accurate data."
            ),
            tools=research_tools,
            verbose=True,
            allow_delegation=False,
        )

        # Analysis specialist with analysis-focused tools
        analysis_tools = [
            tool for tool in self.agentup_tools if "analysis" in tool.name.lower() or "expert" in tool.name.lower()
        ]
        if not analysis_tools:
            analysis_tools = self.agentup_tools[-2:]  # Last 2 tools as fallback

        analyst = Agent(
            role="Strategic Analyst",
            goal="Analyze complex data and provide strategic insights",
            backstory=(
                "You are a strategic analyst with deep expertise in interpreting "
                "data and identifying patterns. You use specialized analytical "
                "tools to derive actionable insights."
            ),
            tools=analysis_tools,
            verbose=True,
            allow_delegation=False,
        )

        # Implementation specialist
        implementer = Agent(
            role="Implementation Specialist",
            goal="Create detailed implementation plans and recommendations",
            backstory=(
                "You are an implementation specialist who translates analysis "
                "and research into concrete action plans. You focus on "
                "practical, executable solutions."
            ),
            tools=self.agentup_tools,  # Access to all tools for comprehensive planning
            verbose=True,
            allow_delegation=False,
        )

        self.crew = Crew(
            agents=[coordinator, researcher, analyst, implementer],
            tasks=[],  # Tasks added dynamically
            process=Process.sequential,
            verbose=2,
            max_execution_time=600,  # 10 minutes total
        )

        return self.crew

    def create_complex_workflow_tasks(self, project_description: str) -> list[Task]:
        """Create a complex workflow of tasks.

        Args:
            project_description: Description of the project to work on

        Returns:
            List of configured tasks
        """
        if not CREWAI_AVAILABLE:
            return []

        tasks = []

        # Task 1: Project coordination and planning
        coordination_task = Task(
            description=f"""
            Coordinate the analysis of this project: {project_description}

            Your responsibilities:
            1. Break down the project into key components
            2. Identify what type of research is needed
            3. Determine what analysis should be performed
            4. Create a coordination plan for the team
            5. Use specialized agents to gather preliminary information

            Work with the available AgentUp specialists to understand the scope
            and complexity of the project. Provide clear direction for the team.
            """,
            expected_output="Project coordination plan with component breakdown and team direction",
            agent=None,
        )
        tasks.append(coordination_task)

        # Task 2: Comprehensive research
        research_task = Task(
            description=f"""
            Conduct comprehensive research on: {project_description}

            Your research should include:
            1. Background information and context
            2. Current state of the domain
            3. Key stakeholders and players
            4. Recent trends and developments
            5. Potential challenges and opportunities
            6. Relevant data and statistics

            Use the specialized research tools available to you to gather
            accurate and comprehensive information. Focus on credible sources
            and current information.
            """,
            expected_output="Comprehensive research report with background, trends, and key findings",
            agent=None,
        )
        tasks.append(research_task)

        # Task 3: Strategic analysis
        analysis_task = Task(
            description=f"""
            Perform strategic analysis based on the research findings for: {project_description}

            Your analysis should cover:
            1. SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)
            2. Market/domain analysis and positioning
            3. Risk assessment and mitigation strategies
            4. Competitive landscape analysis
            5. Financial implications and considerations
            6. Strategic recommendations

            Use specialized analytical tools to dive deep into the data and
            provide insights that go beyond surface-level observations.
            """,
            expected_output="Strategic analysis report with SWOT, risks, opportunities, and recommendations",
            agent=None,
        )
        tasks.append(analysis_task)

        # Task 4: Implementation planning
        implementation_task = Task(
            description=f"""
            Create a detailed implementation plan for: {project_description}

            Your implementation plan should include:
            1. Detailed action items and milestones
            2. Resource requirements and allocation
            3. Timeline with critical path analysis
            4. Success metrics and KPIs
            5. Risk mitigation strategies
            6. Stakeholder communication plan
            7. Budget considerations and cost estimates

            Use insights from research and analysis to create a practical,
            executable plan. Consider both short-term and long-term objectives.
            """,
            expected_output="Comprehensive implementation plan with timeline, resources, metrics, and action items",
            agent=None,
        )
        tasks.append(implementation_task)

        return tasks

    async def execute_workflow(self, project_description: str) -> str:
        """Execute the complete multi-agent workflow.

        Args:
            project_description: Description of the project to analyze

        Returns:
            Final result or error message
        """
        if not CREWAI_AVAILABLE:
            return "CrewAI not available"

        print("🚀 Starting Multi-Agent Workflow")
        print(f"📋 Project: {project_description}")
        print(f"🤖 AgentUp Agents: {len(self.agentup_tools)}")
        print()

        try:
            # Setup tools if not already done
            if not self.agentup_tools:
                await self.setup_agentup_tools()

            # Create crew if not already done
            if not self.crew:
                self.crew = self.create_crew()
                if not self.crew:
                    return "Failed to create crew"

            # Create tasks
            tasks = self.create_complex_workflow_tasks(project_description)
            if not tasks:
                return "Failed to create tasks"

            # Assign agents to tasks
            tasks[0].agent = self.crew.agents[0]  # coordinator
            tasks[1].agent = self.crew.agents[1]  # researcher
            tasks[2].agent = self.crew.agents[2]  # analyst
            tasks[3].agent = self.crew.agents[3]  # implementer

            # Add tasks to crew
            self.crew.tasks = tasks

            print("Multi-agent crew assembled:")
            print(f"   Coordinator with {len(self.crew.agents[0].tools)} tools")
            print(f"   Researcher with {len(self.crew.agents[1].tools)} tools")
            print(f"   Analyst with {len(self.crew.agents[2].tools)} tools")
            print(f"   Implementer with {len(self.crew.agents[3].tools)} tools")
            print()
            print("Starting workflow execution...")
            print("This may take several minutes...")
            print()

            # Execute the workflow
            result = self.crew.kickoff()

            print("\n✅ Multi-agent workflow completed successfully!")
            print("Final Implementation Plan:")
            print("=" * 60)
            return str(result)

        except Exception as e:
            error_msg = f"❌ Error during workflow execution: {str(e)}"
            print(error_msg)
            return error_msg


async def discover_and_create_workflow(
    agent_urls: list[str],
    project_description: str,
    api_key: str | None = None,
) -> str:
    """Discover AgentUp agents and create a workflow automatically.

    Args:
        agent_urls: List of AgentUp agent URLs
        project_description: Project description
        api_key: Optional API key for authentication

    Returns:
        Workflow execution result
    """
    print("🔍 Discovering AgentUp agents...")

    # Discover agents
    discovery = AgentUpDiscovery(base_urls=agent_urls, api_key=api_key)
    agents = await discovery.discover_agents()

    if not agents:
        return "No AgentUp agents discovered"

    print(f"✅ Discovered {len(agents)} agents:")
    for agent in agents:
        print(f"   🤖 {agent['name']}: {agent['base_url']}")

    # Convert to configs
    agentup_configs = [
        {
            "name": agent["name"],
            "base_url": agent["base_url"],
            "description": agent["description"],
        }
        for agent in agents
    ]

    # Create and execute workflow
    workflow = MultiAgentWorkflow(agentup_configs, api_key)
    await workflow.setup_agentup_tools()
    return await workflow.execute_workflow(project_description)


def main():
    """Main function to run the multi-agent example."""
    print("CrewAI + AgentUp Multi-Agent Integration Example")
    print("=" * 60)

    # Configuration from environment
    agent_urls_str = os.getenv("AGENTUP_URLS", "http://localhost:8000,http://localhost:8001")
    agent_urls = [url.strip() for url in agent_urls_str.split(",")]
    api_key = os.getenv("AGENTUP_API_KEY")
    project = os.getenv("PROJECT_DESCRIPTION", "Building a sustainable smart city initiative")

    print(f"Agent URLs: {agent_urls}")
    print(f"API Key: {'***' if api_key else 'None'}")
    print(f"Project: {project}")
    print()

    # Run discovery-based workflow
    result = asyncio.run(discover_and_create_workflow(agent_urls, project, api_key))
    print(result)


if __name__ == "__main__":
    main()
