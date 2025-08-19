"""CLI styling and formatting utilities for AgentUp commands."""

import click
from questionary import Style

# Questionary style for interactive prompts
custom_style = Style(
    [
        ("qmark", "fg:#5f819d bold"),
        ("question", "bold"),
        ("answer", "fg:#85678f bold"),
        ("pointer", "fg:#5f819d bold"),
        ("highlighted", "fg:#5f819d bold"),
        ("selected", "fg:#85678f"),
        ("separator", "fg:#cc6666"),
        ("instruction", "fg:#969896"),
        ("text", ""),
    ]
)


def print_header(title: str, subtitle: str | None = None) -> None:
    """Print a styled header with separator lines."""
    click.secho("─" * 50, fg="white", dim=True)
    click.secho(title, fg="cyan", bold=True)
    click.secho("─" * 50, fg="white", dim=True)
    if subtitle:
        click.secho(subtitle + "\n", fg="white")


def print_success_footer(message: str, location: str | None = None, docs_url: str | None = None) -> None:
    """Print a styled success message with optional location and documentation link."""
    click.secho("\n" + "─" * 50, fg="white", dim=True)
    click.secho(message, fg="green", bold=True)
    click.secho("─" * 50, fg="white", dim=True)

    if location:
        click.secho(f"\nLocation: {location}", fg="cyan")

    if docs_url:
        click.secho("\nRead the documentation to get started:", fg="white", bold=True)
        click.secho(docs_url, fg="blue", underline=True)


def print_error(message: str) -> None:
    """Print a styled error message."""
    click.secho(f"Error: {message}", fg="red")
