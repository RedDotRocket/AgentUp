#!/usr/bin/env python3
"""
Unified MCP Weather Server supporting all transport types (stdio, sse, streamable_http).

This server provides weather tools using the National Weather Service API and supports
authentication token validation for testing AgentUp configuration variable expansion.

Usage:
    python weather_server.py --transport stdio
    python weather_server.py --transport sse --port 8123
    python weather_server.py --transport streamable_http --port 8123 --auth-token test-token-123
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Any

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

# Initialize FastMCP server for Weather tools
mcp = FastMCP(name="weather")

# Configure logging to match AgentUp's format exactly


# Create a custom formatter that matches AgentUp's timestamp format
class AgentUpFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        _ = datefmt  # Ignore unused parameter
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# Set up logging to stderr (so AgentUp can colorize it)
handler = logging.StreamHandler(sys.stderr)
formatter = AgentUpFormatter("%(asctime)s [%(levelname)-8s] %(message)s [%(name)s]")
handler.setFormatter(formatter)

# Configure the logger
logger = logging.getLogger("mcp_client.weather")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False  # Don't propagate to root logger

# Remove any existing handlers from root logger for our weather server
root_logger = logging.getLogger()
root_logger.handlers = []

# Suppress or redirect FastMCP's verbose logging
fastmcp_logger = logging.getLogger("mcp.server.fastmcp")
fastmcp_logger.setLevel(logging.WARNING)  # Only show warnings and errors

# Also suppress the server.py logs
server_logger = logging.getLogger("server")
server_logger.setLevel(logging.WARNING)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# Global auth token (set via command line)
AUTH_TOKEN = None


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"NWS API request failed: {e}")
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)

    Returns:
        String containing weather alerts for the specified state
    """
    logger.info(f"🚨 Fetching alerts for state: {state.upper()}")

    if not state or len(state) != 2:
        return "Please provide a valid two-letter US state code (e.g., CA, NY, TX)"

    url = f"{NWS_API_BASE}/alerts/active/area/{state.upper()}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return f"Unable to fetch alerts for {state.upper()} or no alerts found."

    if not data["features"]:
        logger.info(f"✅ No active alerts for {state.upper()}")
        return f"No active weather alerts for {state.upper()}."

    alert_count = len(data["features"])
    logger.info(f"⚠️  Found {alert_count} active alert(s) for {state.upper()}")

    alerts = [format_alert(feature) for feature in data["features"]]
    return f"Weather alerts for {state.upper()}:\n" + "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location (-90 to 90)
        longitude: Longitude of the location (-180 to 180)

    Returns:
        String containing weather forecast for the specified coordinates
    """
    logger.info(f"🌡️  Fetching forecast for coordinates: {latitude:.4f}, {longitude:.4f}")

    # Validate coordinates
    if not (-90 <= latitude <= 90):
        return "Invalid latitude. Must be between -90 and 90."
    if not (-180 <= longitude <= 180):
        return "Invalid longitude. Must be between -180 and 180."

    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return f"Unable to fetch forecast data for coordinates ({latitude}, {longitude}). This may be outside the US coverage area."

    try:
        # Get the forecast URL from the points response
        forecast_url = points_data["properties"]["forecast"]
        forecast_data = await make_nws_request(forecast_url)

        if not forecast_data:
            return "Unable to fetch detailed forecast from NWS."

        # Format the periods into a readable forecast
        periods = forecast_data["properties"]["periods"]
        if not periods:
            return "No forecast periods available."

        forecasts = []
        for period in periods[:5]:  # Only show next 5 periods
            forecast = f"""
{period["name"]}:
Temperature: {period["temperature"]}°{period["temperatureUnit"]}
Wind: {period["windSpeed"]} {period["windDirection"]}
Forecast: {period["detailedForecast"]}
"""
            forecasts.append(forecast)

        location_info = points_data["properties"]
        city = location_info.get("relativeLocation", {}).get("properties", {}).get("city", "Unknown")
        state = location_info.get("relativeLocation", {}).get("properties", {}).get("state", "Unknown")

        logger.info(f"📍 Retrieved forecast for {city}, {state}")
        logger.info(f"🗓️  Showing {len(periods[:5])} forecast periods")

        return f"Weather forecast for {city}, {state} ({latitude}, {longitude}):\n" + "\n---\n".join(forecasts)

    except KeyError as e:
        return f"Error parsing forecast data: missing field {e}"
    except Exception as e:
        return f"Unexpected error getting forecast: {e}"


def create_authenticated_app(app_factory):
    """Wrap an MCP app with authentication middleware if token is provided."""
    if not AUTH_TOKEN:
        return app_factory()

    # Get the base app
    base_app = app_factory()

    # Create a custom middleware class for proper error handling
    from starlette.middleware.base import BaseHTTPMiddleware

    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method in ["POST", "GET"]:
                # Check for Authorization header
                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        {"error": "Missing or invalid Authorization header. Expected 'Bearer <token>'"}, status_code=401
                    )

                token = auth_header[7:]  # Remove "Bearer " prefix
                if token != AUTH_TOKEN:
                    return JSONResponse({"error": "Invalid authentication token"}, status_code=403)

            return await call_next(request)

    # Add middleware to the app
    base_app.add_middleware(AuthMiddleware)
    return base_app


def run_stdio():
    """Run MCP server with stdio transport."""
    # Pretty banner for demo
    logger.info("=" * 60)
    logger.info("🌤️  MCP DEMO - WEATHER SERVER (National Weather Service)")
    logger.info("=" * 60)
    logger.info("📡 Transport: stdio")
    logger.info("🔧 Available tools:")
    logger.info("   • get_alerts    - Get weather alerts for a US state")
    logger.info("   • get_forecast  - Get weather forecast for coordinates")
    logger.info("   • set `enabled: false` in agentup.yml to disable this demo server")
    if AUTH_TOKEN:
        logger.info("🔐 Authentication: ENABLED (token configured)")
    else:
        logger.info("🔓 Authentication: DISABLED")
    logger.info("=" * 60)

    # Use FastMCP's built-in stdio transport
    mcp.run(transport="stdio")


def run_http_server(transport: str, host: str, port: int):
    """Run MCP server with HTTP-based transport (sse or streamable_http)."""
    # Pretty banner for demo
    logger.info("=" * 60)
    logger.info("🌤️  MCP WEATHER SERVER (National Weather Service)")
    logger.info("=" * 60)
    logger.info(f"📡 Transport: {transport}")
    logger.info(f"🌐 Server: http://{host}:{port}")
    logger.info("🔧 Available tools:")
    logger.info("   • get_alerts    - Get weather alerts for a US state")
    logger.info("   • get_forecast  - Get weather forecast for coordinates")

    if AUTH_TOKEN:
        logger.info("🔐 Authentication: ENABLED")
        logger.info("   Use Authorization header: Bearer <token>")
    else:
        logger.info("🔓 Authentication: DISABLED")

    if transport == "sse":
        # SSE transport
        app = create_authenticated_app(mcp.sse_app)
        logger.info("📍 SSE endpoints:")
        logger.info("   • GET  /mcp      - SSE stream")
        logger.info("   • POST /messages - Send messages")
    elif transport == "streamable_http":
        # Streamable HTTP transport
        app = create_authenticated_app(mcp.streamable_http_app)
        logger.info("📍 Endpoint: /mcp (streamable HTTP)")
    else:
        raise ValueError(f"Unsupported HTTP transport: {transport}")

    logger.info("=" * 60)

    # Start the server
    uvicorn.run(app, host=host, port=port, log_level="info")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Unified MCP Weather Server supporting all transport types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # stdio transport (for testing with AgentUp stdio client)
  python weather_server.py --transport stdio

  # SSE transport on port 8123
  python weather_server.py --transport sse --port 8123

  # Streamable HTTP with authentication
  python weather_server.py --transport streamable_http --port 8123 --auth-token test-token-123

  # Use environment variable for auth token (tests AgentUp config expansion)
  export WEATHER_TOKEN=my-secret-token
  python weather_server.py --transport sse --auth-token $WEATHER_TOKEN

AgentUp Configuration Examples:

  # For stdio transport:
  - name: "weather"
    enabled: true
    transport: "stdio"
    command: "python"
    args: ["scripts/mcp/weather_server.py", "--transport", "stdio"]
    tool_scopes:
      get_alerts: ["weather:read"]
      get_forecast: ["weather:read"]

  # For SSE transport with auth:
  - name: "weather"
    enabled: true
    transport: "sse"
    url: "http://localhost:8123/sse"
    headers:
      Authorization: "Bearer ${WEATHER_TOKEN}"
    tool_scopes:
      get_alerts: ["weather:read"]
      get_forecast: ["weather:read"]

  # For streamable HTTP with auth:
  - name: "weather"
    enabled: true
    transport: "streamable_http"
    url: "http://localhost:8123/mcp"
    headers:
      Authorization: "Bearer ${WEATHER_TOKEN}"
    tool_scopes:
      get_alerts: ["weather:read"]
      get_forecast: ["weather:read"]
        """,
    )

    parser.add_argument(
        "--transport", choices=["stdio", "sse", "streamable_http"], required=True, help="MCP transport protocol to use"
    )

    parser.add_argument("--port", type=int, default=8123, help="Port to listen on (ignored for stdio transport)")

    parser.add_argument("--host", default="localhost", help="Host to bind to (ignored for stdio transport)")

    parser.add_argument(
        "--auth-token", help="Authentication token for HTTP transports (tests config variable expansion)"
    )

    args = parser.parse_args()

    # Set global auth token
    global AUTH_TOKEN
    AUTH_TOKEN = args.auth_token

    try:
        if args.transport == "stdio":
            # Run stdio server
            run_stdio()
        else:
            # Run HTTP-based server
            run_http_server(args.transport, args.host, args.port)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
