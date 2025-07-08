#!/usr/bin/env python3
"""
Example demonstrating the FastAPI + Structlog integration in AgentUp.

This example shows how to use the structured logging system with correlation IDs,
middleware integration, and both text and JSON output formats.
"""

import asyncio
import tempfile
from pathlib import Path

import yaml

from src.agent.config.logging import FastAPIStructLogger, configure_logging_from_config, setup_logging
from src.agent.config.models import LoggingConfig


async def main():
    """Demonstrate structured logging features."""
    print("=== AgentUp Structured Logging Example ===\n")

    # Example 1: Basic setup with LoggingConfig
    print("1. Setting up basic structured logging...")
    config = LoggingConfig(
        level="INFO",
        format="text",
        correlation_id=True,
        request_logging=True,
    )
    setup_logging(config)
    print("   ✓ Structured logging configured")

    # Example 2: Using FastAPIStructLogger
    print("\n2. Using FastAPIStructLogger...")
    logger = FastAPIStructLogger()
    
    # Basic logging
    logger.info("Application started", component="example", version="1.0.0")
    
    # Binding context variables
    logger.bind(user_id="user-123", request_id="req-456")
    logger.info("User action performed", action="login")
    
    # Different log levels
    logger.debug("Debug information", detail="verbose_mode")
    logger.warning("Something to watch", metric="high_latency")
    logger.error("Error occurred", error_code="E001")
    
    print("   ✓ Log messages sent with structured context")

    # Example 3: JSON format output
    print("\n3. Switching to JSON format...")
    json_config = LoggingConfig(
        level="INFO",
        format="json",
        correlation_id=True,
    )
    # Reset logging state to demonstrate JSON format
    import src.agent.config.logging as logging_module
    logging_module._logging_configured = False
    setup_logging(json_config)
    
    json_logger = FastAPIStructLogger("example.json")
    json_logger.bind(format="json", demo=True)
    json_logger.info("JSON formatted log message", 
                    timestamp="2024-07-08",
                    structured=True,
                    data={"key": "value", "number": 42})
    print("   ✓ JSON structured logging enabled")

    # Example 4: Configuration from YAML
    print("\n4. Loading configuration from YAML...")
    
    # Create a temporary YAML config
    config_dict = {
        "logging": {
            "enabled": True,
            "level": "DEBUG",
            "format": "text",
            "correlation_id": True,
            "request_logging": True,
            "console": {"enabled": True, "colors": True},
            "file": {"enabled": False},
            "modules": {
                "example": "DEBUG",
                "httpx": "WARNING"
            }
        },
        "agent": {
            "name": "LoggingExample",
            "version": "1.0.0"
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f, default_flow_style=False)
        config_file = f.name
    
    try:
        # Load and configure from YAML
        logging_module._logging_configured = False  # Reset for demo
        configure_logging_from_config(config_dict)
        
        yaml_logger = FastAPIStructLogger("example.yaml")
        yaml_logger.bind(source="yaml_config")
        yaml_logger.debug("Configuration loaded from YAML", config_file=config_file)
        yaml_logger.info("YAML configuration working", modules=["example", "httpx"])
        
        print("   ✓ YAML configuration loaded and applied")
        
    finally:
        # Clean up
        Path(config_file).unlink()

    # Example 5: Model binding (if you have objects with 'id' attribute)
    print("\n5. Demonstrating model binding...")
    
    class ExampleModel:
        def __init__(self, id: str, name: str):
            self.id = id
            self.name = name

    model_logger = FastAPIStructLogger("example.models")
    user_model = ExampleModel("user-789", "John Doe")
    order_model = ExampleModel("order-101", "Coffee Order")
    
    # Bind models - they'll be logged as user_model: user-789, order_model: order-101
    model_logger.bind(user_model, order_model, operation="checkout")
    model_logger.info("Order processed", status="completed")
    
    print("   ✓ Model binding demonstrated")

    print("\n=== Example Complete ===")
    print("\nKey Features Demonstrated:")
    print("• Structured logging with contextual information")
    print("• Correlation ID support for request tracing")
    print("• Both text and JSON output formats")
    print("• YAML configuration loading")
    print("• Model object binding")
    print("• Multiple logger instances")
    print("• Module-specific log levels")
    
    print("\nTo use in a FastAPI app:")
    print("1. Configure logging in your agent_config.yaml")
    print("2. Import and use StructLogMiddleware")
    print("3. Use FastAPIStructLogger in your handlers")
    print("4. Enjoy structured, searchable logs!")


if __name__ == "__main__":
    asyncio.run(main())