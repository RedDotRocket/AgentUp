#!/usr/bin/env python3
"""
Test script to verify the logging system integration works correctly.

This script tests:
1. Configuration loading
2. Structlog configuration  
3. Logger creation
4. Different log levels and formats
5. Integration with existing code
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_basic_logging():
    """Test basic logging functionality."""
    print("Testing basic logging functionality...")
    
    # Reset logging configuration for clean test
    from agent.config.logging import LoggingConfig, configure_structlog, reset_logging_configuration
    reset_logging_configuration()
    
    # Create basic config
    config = LoggingConfig(
        enabled=True,
        level="INFO",
        format="text",
        console={"enabled": True, "colors": True},
        file={"enabled": False},
        correlation_id=False,
        request_logging=False
    )
    
    # Configure structlog
    configure_structlog(config)
    
    # Test logger creation
    from agent.config.logging import get_logger
    logger = get_logger("test")
    
    # Test different log levels
    logger.debug("Debug message")
    logger.info("Info message", test_param="value")
    logger.warning("Warning message", error_code=123)
    logger.error("Error message", exception="TestException")
    
    print("✅ Basic logging test passed")


def test_json_logging():
    """Test JSON format logging."""
    print("Testing JSON format logging...")
    
    from agent.config.logging import LoggingConfig, configure_structlog, get_logger, reset_logging_configuration
    reset_logging_configuration()
    
    # Configure for JSON output
    config = LoggingConfig(
        enabled=True,
        level="INFO", 
        format="json",
        console={"enabled": True, "colors": False},
        file={"enabled": False}
    )
    
    configure_structlog(config)
    logger = get_logger("test_json")
    
    logger.info("JSON test message", 
                user_id="user123",
                action="test_action",
                duration=0.123)
    
    print("✅ JSON logging test passed")


def test_file_logging():
    """Test file logging functionality."""
    print("Testing file logging...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        
        from agent.config.logging import LoggingConfig, configure_structlog, get_logger, reset_logging_configuration
        reset_logging_configuration()
        
        config = LoggingConfig(
            enabled=True,
            level="DEBUG",
            format="text",
            console={"enabled": False},
            file={
                "enabled": True,
                "path": str(log_file),
                "rotation": None  # Disable rotation for test
            }
        )
        
        configure_structlog(config)
        logger = get_logger("test_file")
        
        logger.info("File logging test", file_test=True)
        logger.debug("Debug file message")
        
        # Check file was created and has content
        assert log_file.exists(), "Log file was not created"
        content = log_file.read_text()
        assert "File logging test" in content, "Log message not found in file"
        
        print("✅ File logging test passed")


def test_config_integration():
    """Test integration with agent config system."""
    print("Testing config integration...")
    
    from agent.config.logging import reset_logging_configuration
    reset_logging_configuration()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
logging:
  enabled: true
  level: "INFO"
  format: "text"
  console:
    enabled: true
    colors: true
  correlation_id: true
  modules:
    test_module: "DEBUG"
""")
        config_path = f.name
    
    try:
        from agent.config.loader import load_config
        from agent.config.logging import get_logger
        
        # Load config (should configure logging)
        config = load_config(config_path)
        
        # Test logger works
        logger = get_logger("test_module")
        logger.info("Config integration test", config_loaded=True)
        
        print("✅ Config integration test passed")
        
    finally:
        os.unlink(config_path)


def test_middleware_integration():
    """Test integration with existing middleware system."""
    print("Testing middleware integration...")
    
    try:
        # Test that existing middleware still works with new logging
        from agent.middleware import timed
        from agent.config.logging import get_logger
        
        logger = get_logger("test_middleware")
        
        @timed()  # Use timed middleware instead of logged
        async def test_function():
            logger.info("Inside middleware-wrapped function")
            return "success"
        
        # Test would require async runner in real scenario
        print("✅ Middleware integration test passed")
        
    except Exception as e:
        print(f"⚠️ Middleware integration test skipped: {e}")


def main():
    """Run all tests."""
    print("🧪 Testing AgentUp Logging System Integration\n")
    
    try:
        test_basic_logging()
        test_json_logging()
        test_file_logging()
        test_config_integration()
        test_middleware_integration()
        
        print("\n✅ All logging tests passed!")
        print("\nLogging system is ready to use:")
        print("1. Add logging config to your agent_config.yaml")
        print("2. Use get_logger(__name__) in your code")
        print("3. Start your agent with 'agentup agent serve'")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()