# AI Functions: Building LLM-Callable Skills

AI Functions are the most powerful feature of AgentUp plugins, allowing your skills to be automatically called by Large Language Models. This guide shows you how to build  AI-powered plugins that  integrate with LLM workflows.

## Understanding AI Functions

When a user talks to an AI-enabled AgentUp agent, the LLM can ly choose which of your plugin's functions to call based on the conversation context. This enables natural, conversational interfaces to your functionality.

### How It Works

```
User: "What's the weather like in Paris and what time is it there?"

LLM analyzes request → Calls your functions:
1. get_weather(location="Paris")
2. get_time(location="Paris", timezone="Europe/Paris")

LLM combines results → Natural response to user
```

## Creating Your First AI Function

Let's build a calculator plugin with AI functions:

### Step 1: Basic Plugin Setup

```bash
agentup plugin create calculator-plugin  # AI template is now the default
cd calculator-plugin
```

### Step 2: Understanding the Generated AI Plugin

The generated `src/calculator_plugin/plugin.py` uses the simplified decorator-based system:

```python
import math
from typing import Dict, Any

from agent.plugins.base import Plugin
from agent.plugins.decorators import capability
from agent.plugins.models import CapabilityContext


class CalculatorPlugin(Plugin):
    """AI-enabled plugin class for Calculator."""

    def __init__(self):
        """Initialize the plugin."""
        super().__init__()
        self.name = "calculator_plugin"
        self.version = "1.0.0"
        self.llm_service = None

    async def initialize(self, config: Dict[str, Any], services: Dict[str, Any]):
        """Initialize plugin with configuration and services."""
        self.config = config
        # Store LLM service for AI operations
        self.llm_service = services.get("llm")

    def _get_parameters(self, context: CapabilityContext) -> dict[str, Any]:
        """Extract parameters from context."""
        params = context.metadata.get("parameters", {})
        if not params and context.task and context.task.metadata:
            params = context.task.metadata
        return params

    @capability(
        id="calculate",
        name="Calculator",
        description="Perform mathematical calculations",
        scopes=["calculator:use", "ai:function"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                }
            },
            "required": ["expression"]
        },
        examples=[
            "Calculate 2 + 3 * 4",
            "What is the square root of 144?",
            "Evaluate (10 + 5) / 3"
        ]
    )
    async def calculate(self, context: CapabilityContext) -> Dict[str, Any]:
        """Execute calculator capability."""
        try:
            params = self._get_parameters(context)
            expression = params.get("expression", "")
            
            if not expression:
                expression = self._extract_task_content(context)
            
            # Safe evaluation of mathematical expression
            safe_dict = {
                '__builtins__': {},
                'math': math,
                'abs': abs, 'round': round, 'min': min, 'max': max
            }
            
            # Replace common math notation
            expression = expression.replace('^', '**')
            
            result = eval(expression, safe_dict)
            
            return {
                "success": True,
                "content": f"{expression} = {result}",
                "metadata": {
                    "capability": "calculate",
                    "expression": expression,
                    "result": result
                }
            }
            
        except Exception as e:
            self.logger.error("Calculation error", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "content": f"Error calculating '{expression}': {str(e)}"
            }
```

### Step 3: Adding More AI Capabilities

You can extend your plugin with additional capabilities:

```python
@capability(
    id="convert_units",
    name="Unit Converter",
    description="Convert between different units of measurement",
    scopes=["calculator:use", "ai:function"],
    ai_function=True,
    ai_parameters={
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "description": "The numeric value to convert"
            },
            "from_unit": {
                "type": "string",
                "description": "Source unit (e.g., 'meters', 'fahrenheit')"
            },
            "to_unit": {
                "type": "string",
                "description": "Target unit (e.g., 'feet', 'celsius')"
            }
        },
        "required": ["value", "from_unit", "to_unit"]
    },
    examples=[
        "Convert 100 meters to feet",
        "How many celsius is 72 fahrenheit?",
        "Convert 5 kilograms to pounds"
    ]
)
async def convert_units(self, context: CapabilityContext) -> Dict[str, Any]:
    """Convert between units."""
    try:
        params = self._get_parameters(context)
        value = params.get("value")
        from_unit = params.get("from_unit", "").lower()
        to_unit = params.get("to_unit", "").lower()
        
        # Simple conversion logic (extend as needed)
        conversions = {
            ('meters', 'feet'): 3.28084,
            ('feet', 'meters'): 0.3048,
            ('fahrenheit', 'celsius'): lambda f: (f - 32) * 5/9,
            ('celsius', 'fahrenheit'): lambda c: c * 9/5 + 32,
            ('kilograms', 'pounds'): 2.20462,
            ('pounds', 'kilograms'): 0.453592,
        }
        
        key = (from_unit, to_unit)
        if key in conversions:
            converter = conversions[key]
            if callable(converter):
                result = converter(value)
            else:
                result = value * converter
            
            return {
                "success": True,
                "content": f"{value} {from_unit} = {result:.2f} {to_unit}",
                "metadata": {
                    "value": value,
                    "from_unit": from_unit,
                    "to_unit": to_unit,
                    "result": result
                }
            }
        else:
            return {
                "success": False,
                "content": f"Conversion from {from_unit} to {to_unit} not supported"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": f"Error converting units: {str(e)}"
        }
        converted_value = self._perform_unit_conversion(value, from_unit, to_unit)

        response = f"{value} {from_unit} = {converted_value:.4g} {to_unit}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={
                "function": "convert_units",
                "original_value": value,
                "converted_value": converted_value,
                "from_unit": from_unit,
                "to_unit": to_unit,
            },
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Error converting {value} {from_unit} to {to_unit}: {str(e)}",
            success=False,
            error=str(e),
        )

def _perform_unit_conversion(self, value: float, from_unit: str, to_unit: str) -> float:
    """Perform the actual unit conversion."""
    # Temperature conversions
    if from_unit in ['fahrenheit', 'f'] and to_unit in ['celsius', 'c']:
        return (value - 32) * 5/9
    elif from_unit in ['celsius', 'c'] and to_unit in ['fahrenheit', 'f']:
        return value * 9/5 + 32
    elif from_unit in ['celsius', 'c'] and to_unit in ['kelvin', 'k']:
        return value + 273.15
    elif from_unit in ['kelvin', 'k'] and to_unit in ['celsius', 'c']:
        return value - 273.15

    # Length conversions (to meters, then to target)
    length_to_meters = {
        'meters': 1, 'm': 1, 'meter': 1,
        'feet': 0.3048, 'ft': 0.3048, 'foot': 0.3048,
        'inches': 0.0254, 'in': 0.0254, 'inch': 0.0254,
        'yards': 0.9144, 'yd': 0.9144, 'yard': 0.9144,
        'miles': 1609.34, 'mi': 1609.34, 'mile': 1609.34,
        'kilometers': 1000, 'km': 1000, 'kilometer': 1000,
        'centimeters': 0.01, 'cm': 0.01, 'centimeter': 0.01,
    }

    if from_unit in length_to_meters and to_unit in length_to_meters:
        meters = value * length_to_meters[from_unit]
        return meters / length_to_meters[to_unit]

    # Weight conversions (to grams, then to target)
    weight_to_grams = {
        'grams': 1, 'g': 1, 'gram': 1,
        'kilograms': 1000, 'kg': 1000, 'kilogram': 1000,
        'pounds': 453.592, 'lb': 453.592, 'lbs': 453.592, 'pound': 453.592,
        'ounces': 28.3495, 'oz': 28.3495, 'ounce': 28.3495,
    }

    if from_unit in weight_to_grams and to_unit in weight_to_grams:
        grams = value * weight_to_grams[from_unit]
        return grams / weight_to_grams[to_unit]

    raise ValueError(f"Unsupported conversion: {from_unit} to {to_unit}")

async def _solve_equation_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Handle equation solving."""
    params = context.metadata.get("parameters", {})
    equation = params.get("equation", "")
    variable = params.get("variable", "x")

    try:
        solutions = self._solve_equation(equation, variable)

        if len(solutions) == 0:
            response = f"No solutions found for: {equation}"
        elif len(solutions) == 1:
            response = f"Solution: {variable} = {solutions[0]}"
        else:
            solutions_str = ", ".join(str(s) for s in solutions)
            response = f"Solutions: {variable} = {solutions_str}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={
                "function": "solve_equation",
                "equation": equation,
                "variable": variable,
                "solutions": solutions,
            },
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Error solving equation '{equation}': {str(e)}",
            success=False,
            error=str(e),
        )

def _solve_equation(self, equation: str, variable: str) -> list:
    """Solve mathematical equations."""
    # This is a simplified solver - in practice, you'd use sympy or similar
    import re

    # Handle simple linear equations: ax + b = c
    linear_pattern = rf'(-?\d*\.?\d*)\s*\*?\s*{variable}\s*([+-]\s*\d+\.?\d*)\s*=\s*(-?\d+\.?\d*)'
    match = re.match(linear_pattern, equation.replace(' ', ''))

    if match:
        a = float(match.group(1) or '1')
        b = float(match.group(2).replace(' ', ''))
        c = float(match.group(3))

        if a == 0:
            raise ValueError("Not a linear equation in the variable")

        solution = (c - b) / a
        return [round(solution, 6)]

    # Handle simple quadratic equations: ax^2 + bx + c = 0
    quad_pattern = rf'(-?\d*\.?\d*)\s*\*?\s*{variable}\^?2\s*([+-]\s*\d*\.?\d*)\s*\*?\s*{variable}\s*([+-]\s*\d+\.?\d*)\s*=\s*0'
    match = re.match(quad_pattern, equation.replace(' ', ''))

    if match:
        a = float(match.group(1) or '1')
        b = float(match.group(2).replace(' ', '') or '0')
        c = float(match.group(3).replace(' ', ''))

        discriminant = b**2 - 4*a*c

        if discriminant < 0:
            return []  # No real solutions
        elif discriminant == 0:
            solution = -b / (2*a)
            return [round(solution, 6)]
        else:
            sqrt_discriminant = math.sqrt(discriminant)
            sol1 = (-b + sqrt_discriminant) / (2*a)
            sol2 = (-b - sqrt_discriminant) / (2*a)
            return [round(sol1, 6), round(sol2, 6)]

    raise ValueError("Unsupported equation format")
```

## Advanced AI Function Patterns

### Multi-Step Functions

Some AI functions need to perform multiple steps:

```python
AIFunction(
    name="statistical_analysis",
    description="Perform statistical analysis on a dataset",
    parameters={
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Array of numeric values",
            },
            "analyses": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["mean", "median", "mode", "std_dev", "variance"]
                },
                "description": "Types of analysis to perform",
                "default": ["mean", "median", "std_dev"],
            }
        },
        "required": ["data"],
    },
    handler=self._statistical_analysis_function,
)

async def _statistical_analysis_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Perform comprehensive statistical analysis."""
    params = context.metadata.get("parameters", {})
    data = params.get("data", [])
    analyses = params.get("analyses", ["mean", "median", "std_dev"])

    if not data:
        return CapabilityResult(
            content="No data provided for analysis",
            success=False,
            error="Empty dataset",
        )

    results = {}

    try:
        if "mean" in analyses:
            results["mean"] = sum(data) / len(data)

        if "median" in analyses:
            sorted_data = sorted(data)
            n = len(sorted_data)
            if n % 2 == 0:
                results["median"] = (sorted_data[n//2-1] + sorted_data[n//2]) / 2
            else:
                results["median"] = sorted_data[n//2]

        if "std_dev" in analyses:
            mean = sum(data) / len(data)
            variance = sum((x - mean) ** 2 for x in data) / len(data)
            results["std_dev"] = math.sqrt(variance)

        # Format results
        formatted_results = []
        for analysis, value in results.items():
            formatted_results.append(f"{analysis.replace('_', ' ').title()}: {value:.4f}")

        response = "Statistical Analysis Results:\n" + "\n".join(formatted_results)

        return CapabilityResult(
            content=response,
            success=True,
            metadata={
                "function": "statistical_analysis",
                "dataset_size": len(data),
                "results": results,
            },
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Error performing statistical analysis: {str(e)}",
            success=False,
            error=str(e),
        )
```

### Functions with External API Calls

```python
AIFunction(
    name="currency_convert",
    description="Convert currency amounts using current exchange rates",
    parameters={
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "description": "Amount to convert",
            },
            "from_currency": {
                "type": "string",
                "description": "Source currency code (e.g., 'USD', 'EUR')",
            },
            "to_currency": {
                "type": "string",
                "description": "Target currency code (e.g., 'EUR', 'GBP')",
            }
        },
        "required": ["amount", "from_currency", "to_currency"],
    },
    handler=self._currency_convert_function,
)

async def _currency_convert_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Convert currencies using live exchange rates."""
    params = context.metadata.get("parameters", {})
    amount = params.get("amount")
    from_currency = params.get("from_currency", "").upper()
    to_currency = params.get("to_currency", "").upper()

    try:
        # Get exchange rate (with caching)
        exchange_rate = await self._get_exchange_rate(from_currency, to_currency)
        converted_amount = amount * exchange_rate

        response = f"{amount} {from_currency} = {converted_amount:.2f} {to_currency}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={
                "function": "currency_convert",
                "original_amount": amount,
                "converted_amount": converted_amount,
                "exchange_rate": exchange_rate,
                "from_currency": from_currency,
                "to_currency": to_currency,
            },
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Error converting {amount} {from_currency} to {to_currency}: {str(e)}",
            success=False,
            error=str(e),
        )

async def _get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
    """Get current exchange rate from API."""
    cache_key = f"exchange_rate:{from_currency}:{to_currency}"

    # Check cache first
    if self.cache:
        cached_rate = await self.cache.get(cache_key)
        if cached_rate:
            return float(cached_rate)

    # API call to exchange rate service
    api_key = self.config.get("exchange_api_key")
    if not api_key:
        raise ValueError("Exchange rate API key not configured")

    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"

    response = await self.http_client.get(url)
    response.raise_for_status()

    data = response.json()
    rate = data["rates"].get(to_currency)

    if rate is None:
        raise ValueError(f"Exchange rate not available for {to_currency}")

    # Cache for 1 hour
    if self.cache:
        await self.cache.set(cache_key, str(rate), ttl=3600)

    return float(rate)
```

## Function Parameter Design

### Best Practices

1. **Use descriptive parameter names and descriptions**:

```python
parameters={
    "type": "object",
    "properties": {
        "stock_symbol": {  # Clear, specific name
            "type": "string",
            "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL')",
            "pattern": "^[A-Z]{1,5}$",  # Validation pattern
        },
        "time_period": {
            "type": "string",
            "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y"],
            "description": "Time period for stock data",
            "default": "1mo",
        }
    },
    "required": ["stock_symbol"],
}
```

2. **Provide sensible defaults**:

```python
"date_format": {
    "type": "string",
    "enum": ["ISO", "US", "EU"],
    "default": "ISO",
    "description": "Date format preference",
}
```

3. **Use enums for constrained choices**:

```python
"chart_type": {
    "type": "string",
    "enum": ["line", "bar", "pie", "scatter"],
    "description": "Type of chart to generate",
}
```

4. **Include validation constraints**:

```python
"confidence_level": {
    "type": "number",
    "minimum": 0.01,
    "maximum": 0.99,
    "description": "Statistical confidence level (0.01 to 0.99)",
}
```

### Complex Parameter Schemas

For advanced functions, use nested objects:

```python
AIFunction(
    name="generate_report",
    description="Generate a comprehensive data report",
    parameters={
        "type": "object",
        "properties": {
            "data_source": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["database", "api", "file"],
                    },
                    "connection_string": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["type"],
            },
            "report_config": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["pdf", "html", "excel"],
                        "default": "pdf",
                    },
                    "include_charts": {"type": "boolean", "default": True},
                    "chart_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["bar", "line"],
                    },
                },
            },
        },
        "required": ["data_source"],
    },
    handler=self._generate_report_function,
)
```

## Testing AI Functions

### Unit Tests for AI Functions

```python
import pytest
from unittest.mock import Mock
from calculator_plugin.plugin import Plugin

@pytest.mark.asyncio
async def test_calculate_function():
    """Test the calculate AI function."""
    plugin = Plugin()

    # Mock task and context
    task = Mock()
    context = CapabilityContext(
        task=task,
        metadata={
            "parameters": {
                "expression": "2 + 3 * 4",
                "precision": 2
            }
        }
    )

    # Test the function
    result = await plugin._calculate_function(task, context)

    assert result.success
    assert "2 + 3 * 4 = 14" in result.content
    assert result.metadata["result"] == 14

@pytest.mark.asyncio
async def test_unit_conversion_function():
    """Test the unit conversion AI function."""
    plugin = Plugin()

    task = Mock()
    context = CapabilityContext(
        task=task,
        metadata={
            "parameters": {
                "value": 32,
                "from_unit": "fahrenheit",
                "to_unit": "celsius"
            }
        }
    )

    result = await plugin._convert_units_function(task, context)

    assert result.success
    assert "32 fahrenheit = 0 celsius" in result.content
    assert result.metadata["converted_value"] == 0.0

def test_expression_sanitization():
    """Test expression sanitization for security."""
    plugin = Plugin()

    # Safe expressions
    assert plugin._sanitize_expression("2 + 3") == "2 + 3"
    assert plugin._sanitize_expression("sin(30)") == "math.sin(30)"
    assert plugin._sanitize_expression("2^3") == "2**3"

    # Potentially dangerous expressions should be cleaned
    dangerous = "__import__('os').system('rm -rf /')"
    sanitized = plugin._sanitize_expression(dangerous)
    assert "__import__" not in sanitized
    assert "system" not in sanitized
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_ai_function_registration():
    """Test that AI functions are properly registered."""
    plugin = Plugin()
    ai_functions = plugin.get_ai_functions()

    assert len(ai_functions) == 3

    function_names = [f.name for f in ai_functions]
    assert "calculate" in function_names
    assert "convert_units" in function_names
    assert "solve_equation" in function_names

    # Test function schemas
    calc_function = next(f for f in ai_functions if f.name == "calculate")
    assert "expression" in calc_function.parameters["properties"]
    assert calc_function.parameters["required"] == ["expression"]

@pytest.mark.asyncio
async def test_function_with_llm_integration(llm_mock):
    """Test AI function in full LLM context."""
    # This would test the function as called by an actual LLM
    # Requires setting up AgentUp with your plugin loaded
    pass
```

## Error Handling in AI Functions

### Graceful Error Responses

```python
async def _calculate_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Handle calculations with comprehensive error handling."""
    params = context.metadata.get("parameters", {})
    expression = params.get("expression", "")

    # Validate input
    if not expression.strip():
        return CapabilityResult(
            content="Please provide a mathematical expression to calculate.",
            success=False,
            error="Empty expression",
        )

    try:
        # Attempt calculation
        result = self._safe_eval(expression)

        # Check for special values
        if math.isnan(result):
            return CapabilityResult(
                content=f"The expression '{expression}' resulted in an undefined value (NaN).",
                success=False,
                error="Undefined result",
            )

        if math.isinf(result):
            return CapabilityResult(
                content=f"The expression '{expression}' resulted in infinity.",
                success=False,
                error="Infinite result",
            )

        # Successful calculation
        return CapabilityResult(
            content=f"{expression} = {result}",
            success=True,
            metadata={"expression": expression, "result": result},
        )

    except ZeroDivisionError:
        return CapabilityResult(
            content=f"Cannot divide by zero in expression: {expression}",
            success=False,
            error="Division by zero",
        )

    except SyntaxError:
        return CapabilityResult(
            content=f"Invalid mathematical expression: {expression}",
            success=False,
            error="Syntax error",
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Error calculating '{expression}': Please check the expression format.",
            success=False,
            error=str(e),
        )
```

### Input Validation

```python
def _validate_currency_code(self, currency: str) -> bool:
    """Validate currency code format."""
    import re
    return bool(re.match(r'^[A-Z]{3}$', currency))

def _validate_equation(self, equation: str) -> tuple[bool, str]:
    """Validate equation format."""
    if not equation.strip():
        return False, "Empty equation"

    if '=' not in equation:
        return False, "Equation must contain '=' sign"

    parts = equation.split('=')
    if len(parts) != 2:
        return False, "Equation must have exactly one '=' sign"

    return True, ""
```

## Performance Optimization

### Caching Function Results

```python
async def _expensive_calculation_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Function with result caching."""
    params = context.metadata.get("parameters", {})

    # Create cache key from parameters
    import json
    cache_key = f"calc_expensive:{hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()}"

    # Check cache
    if self.cache:
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return CapabilityResult(
                content=f"{cached_result} (cached)",
                success=True,
                metadata={"cached": True},
            )

    # Perform expensive calculation
    result = await self._perform_expensive_calculation(params)

    # Cache result for 1 hour
    if self.cache:
        await self.cache.set(cache_key, result, ttl=3600)

    return CapabilityResult(
        content=str(result),
        success=True,
        metadata={"cached": False},
    )
```

### Parallel Function Execution

```python
async def _multi_calculation_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Function that performs multiple calculations in parallel."""
    params = context.metadata.get("parameters", {})
    expressions = params.get("expressions", [])

    if not expressions:
        return CapabilityResult(
            content="No expressions provided",
            success=False,
            error="Empty input",
        )

    # Execute calculations in parallel
    tasks = [
        self._calculate_single_expression(expr)
        for expr in expressions
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    successful_results = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append(f"Expression {i+1}: {str(result)}")
        else:
            successful_results.append(f"{expressions[i]} = {result}")

    if successful_results:
        response = "Calculation Results:\n" + "\n".join(successful_results)
        if errors:
            response += "\n\nErrors:\n" + "\n".join(errors)
    else:
        response = "All calculations failed:\n" + "\n".join(errors)

    return CapabilityResult(
        content=response,
        success=len(successful_results) > 0,
        metadata={
            "successful_count": len(successful_results),
            "error_count": len(errors),
        },
    )

async def _calculate_single_expression(self, expression: str) -> float:
    """Calculate a single expression."""
    safe_expr = self._sanitize_expression(expression)
    return eval(safe_expr, {"__builtins__": {}, "math": math})
```

## Advanced Function Features

### Streaming Results

For long-running calculations, you can stream intermediate results:

```python
async def _monte_carlo_simulation(self, task, context: CapabilityContext) -> CapabilityResult:
    """Run Monte Carlo simulation with progress updates."""
    params = context.metadata.get("parameters", {})
    iterations = params.get("iterations", 10000)

    # This would stream results if the agent supports it
    # For now, we'll just return final result

    total = 0
    for i in range(iterations):
        # Simulate some calculation
        total += random.random()

        # Could yield intermediate results here in a streaming implementation
        if i % 1000 == 0:
            progress = (i / iterations) * 100
            # In a streaming implementation: yield f"Progress: {progress:.1f}%"

    result = total / iterations

    return CapabilityResult(
        content=f"Monte Carlo simulation complete. Average: {result:.6f}",
        success=True,
        metadata={
            "iterations": iterations,
            "result": result,
        },
    )
```

### Function Chaining

AI Functions can call other functions:

```python
async def _comprehensive_analysis_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Perform comprehensive analysis by calling multiple functions."""
    params = context.metadata.get("parameters", {})
    data = params.get("data", [])

    # Chain multiple analysis functions
    results = {}

    # Statistical analysis
    stats_context = CapabilityContext(
        task=task,
        metadata={"parameters": {"data": data, "analyses": ["mean", "std_dev"]}}
    )
    stats_result = await self._statistical_analysis_function(task, stats_context)
    results["statistics"] = stats_result.metadata.get("results", {})

    # Trend analysis
    trend_context = CapabilityContext(
        task=task,
        metadata={"parameters": {"data": data}}
    )
    trend_result = await self._trend_analysis_function(task, trend_context)
    results["trend"] = trend_result.metadata.get("trend", "unknown")

    # Generate summary
    summary = f"""Comprehensive Analysis Results:

Statistics:
- Mean: {results['statistics'].get('mean', 'N/A'):.4f}
- Standard Deviation: {results['statistics'].get('std_dev', 'N/A'):.4f}

Trend: {results['trend']}

Sample Size: {len(data)} data points
"""

    return CapabilityResult(
        content=summary,
        success=True,
        metadata={"comprehensive_results": results},
    )
```

This comprehensive guide covers everything you need to build  AI Functions for AgentUp plugins. With these patterns, you can create powerful,  skills that  integrate with LLM workflows and provide natural conversational interfaces to any functionality.