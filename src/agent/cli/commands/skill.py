"""Skill management commands."""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..registry.client import RegistryClient
from ..registry.installer import SkillInstaller

console = Console()


@click.group()
def skill():
    """Manage skills - search, install, configure."""
    pass


@skill.command()
@click.argument('query', required=False)
@click.option('--category', '-c', help='Filter by category')
@click.option('--tag', '-t', help='Filter by tag')
@click.option('--author', '-a', help='Filter by author')
@click.option('--sort', '-s', 
              type=click.Choice(['relevance', 'downloads', 'rating', 'created', 'updated']),
              default='relevance', help='Sort order')
@click.option('--limit', '-l', type=int, default=20, help='Number of results (max 100)')
@click.option('--page', '-p', type=int, default=1, help='Page number')
def search(query: Optional[str], category: Optional[str], tag: Optional[str], 
           author: Optional[str], sort: str, limit: int, page: int):
    """Search for skills in the registry.
    
    Examples:
        agentup skill search weather              # Search for weather skills
        agentup skill search --category utilities # Browse utilities
        agentup skill search --tag api           # Filter by API tag
    """
    
    async def _search():
        client = RegistryClient()
        
        # Show search parameters
        search_params = []
        if query:
            search_params.append(f"Query: [cyan]{query}[/cyan]")
        if category:
            search_params.append(f"Category: [cyan]{category}[/cyan]")
        if tag:
            search_params.append(f"Tag: [cyan]{tag}[/cyan]")
        if author:
            search_params.append(f"Author: [cyan]{author}[/cyan]")
        
        if search_params:
            console.print("Searching with: " + ", ".join(search_params))
        else:
            console.print("Browsing all skills...")
        
        with console.status("[bold blue]Searching registry...[/bold blue]"):
            try:
                results = await client.search_skills(
                    query=query,
                    category=category,
                    tag=tag,
                    author=author,
                    sort=sort,
                    limit=min(limit, 100),  # Cap at 100
                    page=page
                )
            except Exception as e:
                console.print(f"[red]❌ Error searching skills: {e}[/red]")
                return
        
        if not results.get('skills'):
            console.print("[yellow]No skills found matching your criteria.[/yellow]")
            console.print("\nTry:")
            console.print("  • Using different search terms")
            console.print("  • Browsing categories with: [cyan]agentup skill categories[/cyan]")
            console.print("  • Viewing all skills with: [cyan]agentup skill search[/cyan]")
            return
        
        # Display results in a table
        skills = results['skills']
        pagination = results.get('pagination', {})
        
        table = Table(
            title=f"Found {pagination.get('total', len(skills))} skills",
            box=box.ROUNDED,
            title_style="bold cyan"
        )
        
        table.add_column("Skill ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Description", style="dim")
        table.add_column("Version", style="green", justify="center")
        table.add_column("Downloads", style="blue", justify="right")
        table.add_column("Rating", style="yellow", justify="center")
        
        for skill in skills:
            # Truncate description for table display
            description = skill.get('description', '')
            if len(description) > 50:
                description = description[:47] + "..."
            
            # Format rating
            rating_avg = skill.get('rating_average', 0)
            rating_count = skill.get('rating_count', 0)
            if rating_count > 0:
                rating_display = f"{rating_avg:.1f}★ ({rating_count})"
            else:
                rating_display = "No ratings"
            
            table.add_row(
                skill['skill_id'],
                skill.get('name', skill['skill_id']),
                description,
                skill.get('latest_version', 'N/A'),
                f"{skill.get('download_count', 0):,}",
                rating_display
            )
        
        console.print(table)
        
        # Show pagination info
        if pagination.get('pages', 1) > 1:
            current_page = pagination.get('page', 1)
            total_pages = pagination['pages']
            console.print(f"\n[dim]Page {current_page} of {total_pages}[/dim]")
            
            if current_page < total_pages:
                console.print(f"[dim]Use --page {current_page + 1} to see more results[/dim]")
        
        # Show how to get more info
        console.print("\n[dim]Use [cyan]agentup skill info <skill-id>[/cyan] to see detailed information[/dim]")
        console.print("[dim]Use [cyan]agentup skill install <skill-id>[/cyan] to install a skill[/dim]")
    
    asyncio.run(_search())


@skill.command()
@click.argument('skill_id')
@click.option('--version', '-v', help='Specific version to install')
@click.option('--preview', '-p', is_flag=True, help='Show what would be installed')
@click.option('--force', '-f', is_flag=True, help='Force reinstall if already installed')
def install(skill_id: str, version: Optional[str], preview: bool, force: bool):
    """Install a skill from the registry.
    
    Examples:
        agentup skill install weather-forecast        # Install latest version
        agentup skill install weather-forecast@1.2.0  # Install specific version
        agentup skill install --preview weather-forecast  # Preview installation
    """
    
    # Parse version from skill_id if specified with @
    if '@' in skill_id and version is None:
        skill_id, version = skill_id.split('@', 1)
    
    async def _install():
        installer = SkillInstaller()
        
        try:
            version_to_install = version or "latest"
            
            if preview:
                console.print(f"[cyan]Previewing installation of {skill_id}@{version_to_install}[/cyan]")
            else:
                console.print(f"[cyan]Installing {skill_id}@{version_to_install}[/cyan]")
            
            success = await installer.install_skill(
                skill_id, 
                version_to_install, 
                preview_only=preview,
                force=force
            )
            
            if success and not preview:
                console.print(f"\n[green]✅ Successfully installed {skill_id}[/green]")
                console.print("\n[bold]Next steps:[/bold]")
                console.print("1. Configure any required environment variables")
                console.print(f"2. Check skill details: [cyan]agentup skill info {skill_id}[/cyan]")
                console.print("3. Start your agent to use the new skill")
            elif not success:
                console.print(f"[red]❌ Failed to install {skill_id}[/red]")
            
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Installation of {skill_id} cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Error installing skill: {e}[/red]")
    
    asyncio.run(_install())


@skill.command()
@click.option('--name', '-n', help='Skill name')
@click.option('--id', '-i', help='Skill ID')
@click.option('--description', '-d', help='Skill description')
@click.option('--input-mode', help='Input mode (text/multimodal)')
@click.option('--output-mode', help='Output mode (text/multimodal)')
def create(name: Optional[str], id: Optional[str], description: Optional[str],
           input_mode: Optional[str], output_mode: Optional[str]):
    """Create a new skill for your agent.

    This command helps you add new capabilities to an existing agent project.
    """
    # Import the original add_skill functionality
    from . import add_skill
    
    # Call the original add_skill function with the same parameters
    return add_skill.add_skill.callback(name, id, description, input_mode, output_mode)


@skill.command()
@click.argument('skill_id')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def remove(skill_id: str, confirm: bool):
    """Remove an installed skill."""
    
    async def _remove():
        installer = SkillInstaller()
        
        # Check if skill is installed
        if not installer.is_skill_installed(skill_id):
            console.print(f"[yellow]Skill '{skill_id}' is not installed[/yellow]")
            return
        
        # Confirm removal unless --confirm flag is used
        if not confirm:
            if not click.confirm(f"Remove skill '{skill_id}'?"):
                console.print("Cancelled")
                return
        
        try:
            success = await installer.remove_skill(skill_id)
            if success:
                console.print(f"[green]✅ Removed {skill_id}[/green]")
            else:
                console.print(f"[red]❌ Failed to remove {skill_id}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error removing skill: {e}[/red]")
    
    asyncio.run(_remove())


@skill.command('list')
@click.option('--available', '-a', is_flag=True, help='Show available updates')
@click.option('--enabled-only', '-e', is_flag=True, help='Show only enabled skills')
def list_skills(available: bool, enabled_only: bool):
    """List installed skills."""
    
    async def _list():
        installer = SkillInstaller()
        
        try:
            installed_skills = installer.list_installed_skills()
            
            if not installed_skills:
                console.print("[yellow]No skills installed.[/yellow]")
                console.print("Use [cyan]agentup skill search[/cyan] to find skills to install.")
                return
            
            # Filter enabled skills if requested
            if enabled_only:
                installed_skills = [s for s in installed_skills if s.get('enabled', False)]
                if not installed_skills:
                    console.print("[yellow]No enabled skills found.[/yellow]")
                    return
            
            # Create table
            table = Table(
                title=f"Installed Skills ({len(installed_skills)})",
                box=box.ROUNDED,
                title_style="bold cyan"
            )
            
            table.add_column("Skill ID", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Version", style="green", justify="center")
            table.add_column("Status", style="blue", justify="center")
            table.add_column("Source", style="dim", justify="center")
            
            if available:
                table.add_column("Latest", style="yellow", justify="center")
                table.add_column("Update", style="red", justify="center")
                
                # Check for updates
                console.print("[dim]Checking for updates...[/dim]")
                try:
                    client = RegistryClient()
                    updates = await client.check_for_updates(installed_skills)
                    update_map = {u["skill_id"]: u for u in updates}
                except Exception:
                    console.print("[yellow]Warning: Could not check for updates[/yellow]")
                    update_map = {}
            
            # Sort skills by name
            installed_skills.sort(key=lambda x: x.get('name', '').lower())
            
            for skill in installed_skills:
                status = "✓ Enabled" if skill.get('enabled', False) else "○ Disabled"
                source = skill.get('source', 'unknown')
                
                row = [
                    skill['skill_id'],
                    skill.get('name', skill['skill_id']),
                    skill.get('version', 'unknown'),
                    status,
                    source
                ]
                
                if available:
                    update_info = update_map.get(skill['skill_id'])
                    if update_info and update_info.get('has_update'):
                        row.extend([
                            update_info['latest_version'],
                            "↑ Available"
                        ])
                    else:
                        row.extend(["—", "—"])
                
                table.add_row(*row)
            
            console.print(table)
            
            if available:
                updates_available = len([s for s in installed_skills 
                                       if update_map.get(s['skill_id'], {}).get('has_update')])
                if updates_available > 0:
                    console.print(f"\n[yellow]{updates_available} update(s) available[/yellow]")
                    console.print("Use [cyan]agentup skill update <skill-id>[/cyan] to update individual skills")
            
        except Exception as e:
            console.print(f"[red]❌ Error listing skills: {e}[/red]")
    
    asyncio.run(_list())


@skill.command()
@click.argument('skill_id')
def update(skill_id: str):
    """Update a skill to the latest version."""
    
    async def _update():
        installer = SkillInstaller()
        
        try:
            console.print(f"[cyan]Updating {skill_id}...[/cyan]")
            success = await installer.update_skill(skill_id)
            
            if success:
                console.print(f"[green]✅ Successfully updated {skill_id}[/green]")
            else:
                console.print(f"[red]❌ Failed to update {skill_id}[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Error updating skill: {e}[/red]")
    
    asyncio.run(_update())


@skill.command()
@click.argument('skill_id')
def enable(skill_id: str):
    """Enable a skill in the agent configuration."""
    
    async def _enable():
        installer = SkillInstaller()
        
        try:
            success = await installer.enable_skill(skill_id)
            if not success:
                console.print(f"[red]❌ Failed to enable {skill_id}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error enabling skill: {e}[/red]")
    
    asyncio.run(_enable())


@skill.command()
@click.argument('skill_id')
def disable(skill_id: str):
    """Disable a skill in the agent configuration."""
    
    async def _disable():
        installer = SkillInstaller()
        
        try:
            success = await installer.disable_skill(skill_id)
            if not success:
                console.print(f"[red]❌ Failed to disable {skill_id}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error disabling skill: {e}[/red]")
    
    asyncio.run(_disable())


@skill.command()
@click.argument('skill_id')
def info(skill_id: str):
    """Show detailed information about a skill."""
    
    async def _info():
        client = RegistryClient()
        
        with console.status(f"[bold blue]Fetching skill info for '{skill_id}'...[/bold blue]"):
            try:
                skill_info = await client.get_skill_details(skill_id)
            except Exception as e:
                console.print(f"[red]❌ Error getting skill info: {e}[/red]")
                return
        
        # Create formatted display
        latest = skill_info.get('latest_version', {})
        
        # Build info sections
        info_lines = []
        
        # Basic info
        info_lines.append(f"[bold]Description:[/bold] {skill_info.get('description', 'N/A')}")
        info_lines.append(f"[bold]Author:[/bold] {skill_info.get('author', {}).get('display_name', 'Unknown')}")
        info_lines.append(f"[bold]Category:[/bold] {skill_info.get('category', 'Uncategorized')}")
        info_lines.append(f"[bold]License:[/bold] {skill_info.get('license', 'Unknown')}")
        
        # Tags
        tags = skill_info.get('tags', [])
        if tags:
            tags_formatted = ', '.join(f"[blue]{tag}[/blue]" for tag in tags)
            info_lines.append(f"[bold]Tags:[/bold] {tags_formatted}")
        
        # Version info
        info_lines.append(f"\n[bold]Latest Version:[/bold] {latest.get('version', 'N/A')}")
        published_date = latest.get('published_at', 'Unknown')
        if published_date != 'Unknown':
            published_date = published_date[:10]  # Just date portion
        info_lines.append(f"[bold]Published:[/bold] {published_date}")
        
        # Dependencies
        deps = latest.get('dependencies', {})
        if deps.get('packages'):
            deps_list = ', '.join(deps['packages'])
            info_lines.append(f"\n[bold]Dependencies:[/bold] {deps_list}")
        
        # External APIs
        apis = latest.get('external_apis', [])
        if apis:
            info_lines.append("\n[bold]External APIs Required:[/bold]")
            for api in apis:
                env_var = api.get('env_var', 'N/A')
                required = "Required" if api.get('required', True) else "Optional"
                info_lines.append(f"  • {api['name']} - {env_var} ({required})")
        
        # Middleware config
        middleware = latest.get('middleware_config', [])
        if middleware:
            info_lines.append("\n[bold]Middleware:[/bold]")
            for mw in middleware:
                # Handle both string and dict middleware configs
                if isinstance(mw, str):
                    info_lines.append(f"  • {mw}")
                elif isinstance(mw, dict):
                    mw_type = mw.get('type', 'unknown')
                    if mw_type == 'rate_limit':
                        info_lines.append(f"  • Rate limiting: {mw.get('requests_per_minute', 'N/A')} req/min")
                    elif mw_type == 'cache':
                        info_lines.append(f"  • Caching: {mw.get('ttl', 'N/A')}s TTL")
                    else:
                        info_lines.append(f"  • {mw_type}")
                else:
                    info_lines.append(f"  • {str(mw)}")
        
        # Stats
        stats = skill_info.get('stats', {})
        info_lines.append(f"\n[bold]Downloads:[/bold] {stats.get('download_count', 0):,}")
        
        rating_avg = stats.get('rating_average', 0)
        rating_count = stats.get('rating_count', 0)
        if rating_count > 0:
            info_lines.append(f"[bold]Rating:[/bold] {rating_avg:.1f}★ ({rating_count} reviews)")
        
        # URLs
        if skill_info.get('repository_url'):
            info_lines.append(f"\n[bold]Repository:[/bold] {skill_info['repository_url']}")
        
        if skill_info.get('documentation_url'):
            info_lines.append(f"[bold]Documentation:[/bold] {skill_info['documentation_url']}")
        
        # Create panel
        panel = Panel(
            '\n'.join(info_lines),
            title=f"[bold cyan]{skill_info.get('name', skill_id)}[/bold cyan]",
            border_style="blue",
            padding=(1, 2)
        )
        
        console.print(panel)
        
        # Installation command
        console.print("\n[green]To install this skill:[/green]")
        console.print(f"  [cyan]agentup skill install {skill_id}[/cyan]")
        
        # Version info
        versions = skill_info.get('versions', [])
        if len(versions) > 1:
            console.print(f"\n[dim]Other versions available: {', '.join(v['version'] for v in versions[:5])}[/dim]")
    
    asyncio.run(_info())


@skill.command()
def categories():
    """List all available skill categories."""
    
    async def _categories():
        client = RegistryClient()
        
        with console.status("[bold blue]Fetching categories...[/bold blue]"):
            try:
                categories_list = await client.get_categories()
            except Exception as e:
                console.print(f"[red]❌ Error getting categories: {e}[/red]")
                return
        
        if not categories_list:
            console.print("[yellow]No categories available.[/yellow]")
            return
        
        # Create table
        table = Table(
            title="Skill Categories",
            box=box.ROUNDED,
            title_style="bold cyan"
        )
        
        table.add_column("Category", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Skills", style="blue", justify="right")
        
        # Sort by skill count (most popular first)
        categories_list.sort(key=lambda c: c.get('skill_count', 0), reverse=True)
        
        for category in categories_list:
            table.add_row(
                category.get('name', 'Unknown'),
                category.get('description', 'No description'),
                str(category.get('skill_count', 0))
            )
        
        console.print(table)
        console.print("\n[dim]Use [cyan]agentup skill search --category <name>[/cyan] to browse skills in a category[/dim]")
    
    asyncio.run(_categories())