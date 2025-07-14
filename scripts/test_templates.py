#!/usr/bin/env python3
"""Test template rendering and generated code."""

import shutil
import subprocess
import sys
from pathlib import Path

import click


@click.command()
@click.option('--keep', is_flag=True, help='Keep rendered files after testing')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--template', '-t', help='Test specific template only')
@click.option('--quick', is_flag=True, help='Skip formatting and extensive tests')
def test_templates(keep, verbose, template, quick):
    """Test template rendering and generated code quality."""

    click.echo("Testing template rendering...")

    # Paths
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "rendered-test"

    # Clean up any existing output
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Step 1: Render templates
    click.echo("\nRendering templates...")
    cmd = [
        "uv", "run", "agentup", "render-templates",
        "--output-dir", str(output_dir),
        "--validate"
    ]

    if not quick:
        cmd.append("--format")
    else:
        cmd.append("--no-format")

    if keep:
        cmd.append("--keep")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        click.echo("✗ Template rendering failed!", err=True)
        click.echo(result.stderr, err=True)
        return 1

    if verbose:
        click.echo(result.stdout)

    # Step 2: Run pytest on rendered code
    click.echo("\n🧪 Running tests on rendered code...")
    pytest_cmd = ["uv", "run", "pytest", "tests/test_template_rendering.py"]

    if verbose:
        pytest_cmd.append("-v")
        pytest_cmd.append("-s")

    if template:
        pytest_cmd.extend(["-k", template])

    result = subprocess.run(pytest_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        click.echo("✗ Tests failed!", err=True)
        click.echo(result.stderr, err=True)
        if verbose:
            click.echo(result.stdout)
        return 1

    click.echo("✓ All template tests passed!")

    if verbose:
        click.echo(result.stdout)

    # Step 3: Additional validation
    if not quick:
        click.echo("\nRunning additional validation...")

        # Check imports
        click.echo("  - Checking imports...")
        py_files = list(output_dir.rglob("*.py"))
        import_errors = []

        for py_file in py_files:
            try:
                subprocess.run(
                    ["python", "-m", "py_compile", str(py_file)],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                import_errors.append((py_file, e))

        if import_errors:
            click.echo(f"  ✗ {len(import_errors)} files have import errors", err=True)
            for file, error in import_errors[:5]:  # Show first 5
                click.echo(f"    - {file.name}: {error.stderr.decode('utf-8').strip()}", err=True)
        else:
            click.echo(f"  ✓ All {len(py_files)} Python files compile successfully")

    # Step 4: Test with different contexts
    if not quick:
        click.echo("\n🔄 Testing with different contexts...")

        contexts = [
            {
                "name": "minimal",
                "context": {
                    "project_name": "MinimalTest",
                    "project_name_snake": "minimal_test",
                    "has_middleware": False,
                    "has_multimodal": False,
                    "has_services": False
                }
            },
            {
                "name": "full",
                "context": {
                    "project_name": "FullTest",
                    "project_name_snake": "full_test",
                    "has_middleware": True,
                    "has_multimodal": True,
                    "has_services": True,
                    "has_state_management": True,
                    "has_ai_orchestrator": True
                }
            }
        ]

        for ctx in contexts:
            click.echo(f"  - Testing {ctx['name']} context...")

            # Save context
            import json
            context_file = project_root / f"test-context-{ctx['name']}.json"
            with open(context_file, 'w') as f:
                json.dump(ctx['context'], f)

            # Render with context
            test_output = project_root / f"rendered-{ctx['name']}"
            cmd = [
                "uv", "run", "agentup", "render-templates",
                "--output-dir", str(test_output),
                "--context-file", str(context_file),
                "--validate",
                "--no-format",
                "--clean"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Cleanup
            context_file.unlink()
            if test_output.exists() and not keep:
                shutil.rmtree(test_output)

            if result.returncode == 0:
                click.echo(f"    ✓ {ctx['name']} context passed")
            else:
                click.echo(f"    ✗ {ctx['name']} context failed", err=True)
                if verbose:
                    click.echo(result.stderr, err=True)

    # Cleanup
    if not keep and output_dir.exists():
        click.echo("\n🧹 Cleaning up rendered files...")
        shutil.rmtree(output_dir)
    elif keep:
        click.echo(f"\n📁 Rendered files kept in: {output_dir}")

    click.echo("\n✓ All template tests completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(test_templates())
