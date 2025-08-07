#!/usr/bin/env python3
"""
Simple placeholder orchestrator for testing agent registration.

This server:
1. Receives agent registration at POST /agent/register
2. Responds with acknowledgment
3. Fetches the agent's AgentCard from the provided URL
4. Logs the entire process for testing/validation
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.agent.services.model import AgentRegistrationPayload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Placeholder Orchestrator",
    description="Simple orchestrator for testing agent registration",
    version="1.0.0"
)

# Store registrations for inspection
registrations: list[dict[str, Any]] = []


@app.post("/agent/register")
async def register_agent(payload: AgentRegistrationPayload) -> JSONResponse:
    """
    Receive agent registration and fetch its AgentCard.

    This simulates what a real orchestrator would do:
    1. Accept the registration
    2. Respond with success
    3. Fetch the AgentCard to see capabilities
    """
    timestamp = datetime.now().isoformat()

    logger.info("=" * 60)
    logger.info("🤖 AGENT REGISTRATION RECEIVED")
    logger.info("=" * 60)
    logger.info(f"Agent Name: {payload.name}")
    logger.info(f"Agent URL: {payload.agent_url}")
    logger.info(f"Agent Version: {payload.version}")
    logger.info(f"AgentCard URL: {payload.agent_card_url}")
    logger.info(f"Description: {payload.description}")
    logger.info(f"Timestamp: {timestamp}")

    # Store the registration
    registration_data = {
        "timestamp": timestamp,
        "payload": payload.model_dump(),
        "agent_card": None,
        "fetch_status": "pending"
    }

    # Respond immediately to the agent
    response_data = {
        "status": "accepted",
        "message": f"Registration received for agent '{payload.name}'",
        "timestamp": timestamp
    }

    # Fetch AgentCard in background
    asyncio.create_task(fetch_agent_card(payload.agent_card_url, len(registrations)))
    registrations.append(registration_data)

    logger.info("✅ Registration acknowledged, fetching AgentCard...")

    return JSONResponse(status_code=200, content=response_data)


async def fetch_agent_card(agent_card_url: str, registration_index: int):
    """Fetch the agent's card to see its capabilities."""

    try:
        logger.info(f"🔍 Fetching AgentCard from: {agent_card_url}")

        # Small delay to let agent fully initialize
        await asyncio.sleep(1)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(agent_card_url)

            if response.status_code == 200:
                agent_card = response.json()

                # Update stored registration
                registrations[registration_index]["agent_card"] = agent_card
                registrations[registration_index]["fetch_status"] = "success"

                logger.info("📋 AGENTCARD FETCHED SUCCESSFULLY")
                logger.info("-" * 40)
                logger.info(f"Card Name: {agent_card.get('name')}")
                logger.info(f"Card Version: {agent_card.get('version')}")
                logger.info(f"Card Description: {agent_card.get('description')}")

                # Log capabilities
                capabilities = agent_card.get('capabilities', {})
                logger.info(f"Streaming: {capabilities.get('streaming')}")
                logger.info(f"Push Notifications: {capabilities.get('push_notifications')}")
                logger.info(f"State Transition History: {capabilities.get('state_transition_history')}")

                # Log skills
                skills = agent_card.get('skills', [])
                logger.info(f"Skills Count: {len(skills)}")

                if skills:
                    logger.info("Available Skills:")
                    for skill in skills[:10]:  # Show first 10 skills
                        skill_name = skill.get('name') or skill.get('id', 'Unknown')
                        skill_desc = skill.get('description', 'No description')
                        tags = skill.get('tags', [])
                        logger.info(f"  - {skill_name}: {skill_desc}")
                        if tags:
                            logger.info(f"    Tags: {tags}")

                    if len(skills) > 10:
                        logger.info(f"  ... and {len(skills) - 10} more skills")
                else:
                    logger.info("No skills found in AgentCard")

                # Log security schemes
                security_schemes = agent_card.get('securitySchemes', {})
                if security_schemes:
                    logger.info(f"Security Schemes: {list(security_schemes.keys())}")

                logger.info("=" * 60)
                logger.info("🎉 REGISTRATION COMPLETE")
                logger.info("=" * 60)

            else:
                error_msg = f"Failed to fetch AgentCard: HTTP {response.status_code}"
                logger.error(f"❌ {error_msg}")
                registrations[registration_index]["fetch_status"] = f"error: {error_msg}"

    except httpx.ConnectError as e:
        error_msg = f"Failed to connect to agent: {str(e)}"
        logger.error(f"❌ {error_msg}")
        registrations[registration_index]["fetch_status"] = f"error: {error_msg}"

    except httpx.TimeoutException:
        error_msg = "Timeout while fetching AgentCard"
        logger.error(f"❌ {error_msg}")
        registrations[registration_index]["fetch_status"] = f"error: {error_msg}"

    except Exception as e:
        error_msg = f"Unexpected error fetching AgentCard: {str(e)}"
        logger.error(f"❌ {error_msg}")
        registrations[registration_index]["fetch_status"] = f"error: {error_msg}"


@app.get("/registrations")
async def list_registrations() -> JSONResponse:
    """List all received registrations."""
    return JSONResponse(status_code=200, content={
        "registrations": registrations,
        "count": len(registrations)
    })


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(status_code=200, content={
        "status": "healthy",
        "service": "placeholder-orchestrator",
        "registrations_received": len(registrations)
    })


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint with information."""
    return JSONResponse(status_code=200, content={
        "service": "Placeholder Orchestrator",
        "purpose": "Testing agent registration",
        "endpoints": {
            "POST /agent/register": "Receive agent registration",
            "GET /registrations": "List received registrations",
            "GET /health": "Health check"
        },
        "registrations_received": len(registrations)
    })


def main():
    """Run the placeholder orchestrator."""
    print("\n" + "="*60)
    print("🎭 PLACEHOLDER ORCHESTRATOR")
    print("="*60)
    print("This server simulates an orchestrator for testing agent registration.")
    print("\n📋 What it does:")
    print("1. Receives agent registrations at POST /agent/register")
    print("2. Acknowledges the registration")
    print("3. Fetches the agent's AgentCard")
    print("4. Logs everything for testing/validation")
    print("\n🔗 Endpoints:")
    print("  http://localhost:8050/agent/register  (POST)")
    print("  http://localhost:8050/registrations   (GET)")
    print("  http://localhost:8050/health          (GET)")
    print("\n▶️  Starting server...")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8050,
        log_level="info"
    )


if __name__ == "__main__":
    main()
