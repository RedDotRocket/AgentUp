# """Render Jinja2 templates for testing."""

# import click
# import shutil
# from pathlib import Path
# from typing import dict, Any, Optional
# import json
# import subprocess
# from jinja2 import Environment, FileSystemLoader, select_autoescape


# def load_template_context(context_file: Optional[Path] = None) -> dict[str, Any]:
#     """Load template context from file or use defaults."""
#     default_context = {
#         "project_name": "TestProject",
#         "project_name_snake": "test_project",
#         "project_name_title": "TestProject",
#         "description": "A test project for template rendering",
#         "has_middleware": True,
#         "has_multimodal": True,
#         "has_services": True,
#         "has_state": True,
#         "has_function_dispatcher": True,
#         "has_llm_providers": True,
#         "has_monitoring": True,
#         "has_mcp": True,
#         "author": "Test Author",
#         "email": "test@example.com",
#     }

#     if context_file and context_file.exists():
#         with open(context_file, 'r') as f:
#             custom_context = json.load(f)
#             default_context.update(custom_context)

#     return default_context


# def render_template(template_path: Path, context: dict[str, Any], output_dir: Path) -> Path:
#     """Render a single template file."""
#     # Get the templates root directory
#     templates_root = template_path
#     while templates_root.name != "templates" and templates_root.parent != templates_root:
#         templates_root = templates_root.parent

#     if templates_root.name != "templates":
#         raise ValueError(f"Could not find 'templates' directory in path: {template_path}")

#     # Setup Jinja2 environment with the templates root
#     env = Environment(
#         loader=FileSystemLoader(templates_root),
#         autoescape=select_autoescape(),
#         trim_blocks=True,
#         lstrip_blocks=True,
#     )

#     # Get relative path from templates root
#     relative_template_path = template_path.relative_to(templates_root)

#     # Load and render template
#     template = env.get_template(str(relative_template_path))
#     rendered = template.render(**context)

#     # Determine output path - preserve directory structure
#     output_file = output_dir / str(relative_template_path).replace('.j2', '')

#     # Create parent directories
#     output_file.parent.mkdir(parents=True, exist_ok=True)

#     # Write rendered content
#     with open(output_file, 'w') as f:
#         f.write(rendered)

#     return output_file


# def validate_python_file(file_path: Path) -> bool:
#     """Validate Python file can be compiled."""
#     if not file_path.suffix == '.py':
#         return True

#     try:
#         with open(file_path, 'r') as f:
#             code = f.read()
#         compile(code, str(file_path), 'exec')
#         return True
#     except SyntaxError as e:
#         click.echo(f"❌ Syntax error in {file_path}: {e}", err=True)
#         return False


# def format_python_files(output_dir: Path) -> None:
#     """Format Python files with black/ruff if available."""
#     python_files = list(output_dir.rglob("*.py"))

#     # Try black first
#     try:
#         subprocess.run(
#             ["black", "--quiet"] + [str(f) for f in python_files],
#             check=True,
#             capture_output=True
#         )
#         click.echo("✅ Formatted with black")
#     except (subprocess.CalledProcessError, FileNotFoundError):
#         # Try ruff format
#         try:
#             subprocess.run(
#                 ["ruff", "format", "--quiet"] + [str(f) for f in python_files],
#                 check=True,
#                 capture_output=True
#             )
#             click.echo("✅ Formatted with ruff")
#         except (subprocess.CalledProcessError, FileNotFoundError):
#             click.echo("⚠️  No formatter available (black or ruff)")


# @click.command()
# @click.option(
#     '--templates-dir',
#     type=click.Path(exists=True, path_type=Path),
#     default=Path(__file__).parent.parent.parent / "templates",
#     help='Directory containing .j2 templates'
# )
# @click.option(
#     '--output-dir',
#     type=click.Path(path_type=Path),
#     default=Path("rendered-test"),
#     help='Output directory for rendered files'
# )
# @click.option(
#     '--context-file',
#     type=click.Path(exists=True, path_type=Path),
#     help='JSON file with template context'
# )
# @click.option(
#     '--clean/--no-clean',
#     default=True,
#     help='Clean output directory before rendering'
# )
# @click.option(
#     '--validate/--no-validate',
#     default=True,
#     help='Validate generated Python files'
# )
# @click.option(
#     '--format/--no-format',
#     default=True,
#     help='Format generated Python files'
# )
# @click.option(
#     '--keep/--no-keep',
#     default=False,
#     help='Keep rendered files after completion'
# )
# def render_templates(
#     templates_dir: Path,
#     output_dir: Path,
#     context_file: Optional[Path],
#     clean: bool,
#     validate: bool,
#     format: bool,
#     keep: bool
# ):
#     """Render Jinja2 templates for testing.

#     This command:
#     1. Loads all .j2 files from the templates directory
#     2. Renders them with the provided context
#     3. Saves output as regular files (e.g., .py)
#     4. Optionally validates and formats Python files
#     5. Can be used for unit testing generated code
#     """
#     click.echo(f"🔧 Rendering templates from {templates_dir}")

#     # Clean output directory if requested
#     if clean and output_dir.exists():
#         shutil.rmtree(output_dir)
#         click.echo(f"🧹 Cleaned {output_dir}")

#     # Create output directory
#     output_dir.mkdir(parents=True, exist_ok=True)

#     # Load context
#     context = load_template_context(context_file)
#     click.echo(f"📋 Using context: {context['project_name']}")

#     # Find all .j2 templates
#     template_files = list(templates_dir.rglob("*.j2"))
#     if not template_files:
#         click.echo("❌ No .j2 templates found!", err=True)
#         raise click.Abort()

#     click.echo(f"📄 Found {len(template_files)} templates")

#     # Render each template
#     rendered_files = []
#     errors = []

#     for template_file in template_files:
#         try:
#             output_file = render_template(template_file, context, output_dir)
#             rendered_files.append(output_file)

#             # Validate Python files
#             if validate and output_file.suffix == '.py':
#                 if not validate_python_file(output_file):
#                     errors.append(output_file)

#         except Exception as e:
#             click.echo(f"❌ Error rendering {template_file.name}: {e}", err=True)
#             errors.append(template_file)

#     click.echo(f"✅ Rendered {len(rendered_files)} files")

#     # Format Python files if requested
#     if format and not errors:
#         format_python_files(output_dir)

#     # Report results
#     if errors:
#         click.echo(f"❌ {len(errors)} files had errors", err=True)
#         if not keep:
#             shutil.rmtree(output_dir)
#         raise click.Abort()

#     # Save manifest for testing
#     manifest = {
#         "templates_dir": str(templates_dir),
#         "output_dir": str(output_dir),
#         "context": context,
#         "rendered_files": [str(f.relative_to(output_dir)) for f in rendered_files]
#     }

#     manifest_file = output_dir / "_manifest.json"
#     with open(manifest_file, 'w') as f:
#         json.dump(manifest, f, indent=2)

#     click.echo(f"📝 Saved manifest to {manifest_file}")

#     # Clean up if not keeping files
#     if not keep:
#         click.echo(f"🧹 Cleaning up {output_dir} (use --keep to preserve)")
#         shutil.rmtree(output_dir)
#     else:
#         click.echo(f"📁 Rendered files saved to {output_dir}")


# if __name__ == "__main__":
#     render_templates()
