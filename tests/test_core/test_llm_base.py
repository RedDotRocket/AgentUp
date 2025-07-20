import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestLLMResponse:
    """Test the LLMResponse data class."""

