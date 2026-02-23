"""CLI commands for OpenBotX."""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from openbotx.helpers.browser_cleanup import close_browser_tools

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

console = Console()


@click.group()
@click.version_option(prog_name="OpenBotX")
def cli() -> None:
    """OpenBotX - Personal AI Assistant"""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", default=8000, help="API port")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
@click.option("--cli-mode", is_flag=True, help="Start in interactive CLI mode")
def start(host: str, port: int, reload: bool, cli_mode: bool) -> None:
    """Start the OpenBotX server."""
    from openbotx.helpers.config import ensure_directories, load_config
    from openbotx.helpers.logger import setup_logging

    console.print("[bold green]Starting OpenBotX...[/bold green]")

    # Load config
    config = load_config()
    ensure_directories(config)

    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_format=config.logging.format,
        log_file=config.logging.file,
    )

    if cli_mode:
        # Start in CLI interactive mode
        asyncio.run(_run_cli_mode(config))
    else:
        # Start API server
        import uvicorn

        from openbotx.helpers.gateway_loader import get_enabled_gateways

        console.print(f"[blue]API server starting on http://{host}:{port}[/blue]")

        # Show enabled gateways
        enabled_gateways = get_enabled_gateways(config)
        if enabled_gateways:
            gateway_names = [g["display"] for g in enabled_gateways]
            console.print(f"[cyan]Enabled gateways: {', '.join(gateway_names)}[/cyan]")

        uvicorn.run(
            "openbotx.api.main:app",
            host=host,
            port=port,
            reload=reload,
        )


async def _run_cli_mode(config) -> None:  # type: ignore
    """Run in interactive CLI mode."""
    from openbotx.core.orchestrator import get_orchestrator
    from openbotx.helpers.gateway_loader import stop_all_gateways
    from openbotx.helpers.provider_loader import (
        initialize_providers,
        stop_all_providers,
    )
    from openbotx.providers.base import get_provider_registry
    from openbotx.providers.gateway.cli import CLIGateway

    console.print("[bold]Initializing OpenBotX in CLI mode...[/bold]")

    # Initialize all providers (storage, transcription, etc.)
    await initialize_providers(config)

    # Initialize orchestrator
    orchestrator = get_orchestrator()
    await orchestrator.initialize()
    await orchestrator.start()

    # Get provider registry
    registry = get_provider_registry()

    # Create and start CLI gateway (forced for CLI mode)
    cli_gateway = CLIGateway()
    await cli_gateway.initialize()
    await cli_gateway.start()

    # Set message handler
    cli_gateway.set_message_handler(lambda msg: orchestrator.enqueue_message(msg))

    # Register gateway
    registry.register(cli_gateway)

    # Start background services
    from openbotx.helpers.background_loader import (
        start_background_services,
        stop_background_services,
    )

    await start_background_services(config)

    try:
        await cli_gateway.run_interactive()
    finally:
        await stop_background_services()
        await close_browser_tools()
        await stop_all_gateways()
        await orchestrator.stop()
        await stop_all_providers()


@cli.command()
def status() -> None:
    """Show OpenBotX status."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()
    url = f"http://{config.api.host}:{config.api.port}/health"

    try:
        response = httpx.get(url, timeout=5)
        data = response.json()

        table = Table(title="OpenBotX Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Status", data.get("status", "unknown"))
        table.add_row("Version", data.get("version", "unknown"))
        table.add_row("Uptime", f"{data.get('uptime_seconds', 0):.0f} seconds")

        console.print(table)

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def version() -> None:
    """Show OpenBotX version."""
    from openbotx.version import __version__

    console.print(f"OpenBotX version [bold]{__version__}[/bold]")


@cli.group()
def skills() -> None:
    """Manage skills."""
    pass


@skills.command("list")
def list_skills() -> None:
    """List all skills."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()
    url = f"http://{config.api.host}:{config.api.port}/api/skills"

    try:
        response = httpx.get(url, timeout=10)
        data = response.json()

        table = Table(title="Skills")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description")
        table.add_column("Triggers")

        for skill in data.get("skills", []):
            table.add_row(
                skill["id"],
                skill["name"],
                (
                    skill["description"][:50] + "..."
                    if len(skill["description"]) > 50
                    else skill["description"]
                ),
                ", ".join(skill.get("triggers", [])[:3]),
            )

        console.print(table)
        console.print(f"\nTotal: {data.get('total', 0)} skills")

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running. Start it with 'openbotx start'[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@skills.command("reload")
def reload_skills() -> None:
    """Reload skills from disk."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()
    url = f"http://{config.api.host}:{config.api.port}/api/skills/reload"

    try:
        response = httpx.post(url, timeout=10)
        data = response.json()
        console.print(f"[green]{data.get('message', 'Skills reloaded')}[/green]")

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.group()
def jobs() -> None:
    """Manage scheduled jobs."""
    pass


@jobs.command("list")
def list_jobs() -> None:
    """List all scheduled jobs."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()

    try:
        # Get cron jobs
        cron_url = f"http://{config.api.host}:{config.api.port}/api/scheduler/cron"
        cron_response = httpx.get(cron_url, timeout=10)
        cron_data = cron_response.json()

        # Get scheduled jobs
        schedule_url = f"http://{config.api.host}:{config.api.port}/api/scheduler/schedule"
        schedule_response = httpx.get(schedule_url, timeout=10)
        schedule_data = schedule_response.json()

        table = Table(title="Scheduled Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Type")
        table.add_column("Schedule")
        table.add_column("Status")

        for job in cron_data.get("jobs", []):
            table.add_row(
                job["id"][:8],
                job["name"],
                "cron",
                job.get("cron_expression", ""),
                job["status"],
            )

        for job in schedule_data.get("jobs", []):
            table.add_row(
                job["id"][:8],
                job["name"],
                "scheduled",
                str(job.get("scheduled_at", ""))[:19],
                job["status"],
            )

        console.print(table)

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.group()
def providers() -> None:
    """Manage providers."""
    pass


@providers.command("list")
def list_providers() -> None:
    """List all providers."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()
    url = f"http://{config.api.host}:{config.api.port}/api/providers"

    try:
        response = httpx.get(url, timeout=10)
        data = response.json()

        table = Table(title="Providers")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Status")
        table.add_column("Healthy")

        for provider in data.get("providers", []):
            healthy = "✓" if provider["healthy"] else "✗"
            healthy_style = "green" if provider["healthy"] else "red"
            table.add_row(
                provider["name"],
                provider["type"],
                provider["status"],
                f"[{healthy_style}]{healthy}[/{healthy_style}]",
            )

        console.print(table)

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("message")
@click.option("--channel", default="cli", help="Channel ID")
def send(message: str, channel: str) -> None:
    """Send a message to OpenBotX."""
    import httpx

    from openbotx.helpers.config import get_config

    config = get_config()
    url = f"http://{config.api.host}:{config.api.port}/api/messages"

    try:
        response = httpx.post(
            url,
            json={
                "channel_id": channel,
                "text": message,
                "gateway": "http",
            },
            timeout=30,
        )
        data = response.json()

        console.print("[green]Message sent[/green]")
        console.print(f"ID: {data.get('id', 'unknown')}")
        console.print(f"Correlation ID: {data.get('correlation_id', 'unknown')}")

    except httpx.ConnectError:
        console.print("[red]OpenBotX is not running[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def config() -> None:
    """Show current configuration."""
    from openbotx.helpers.config import get_config

    config = get_config()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", config.version)
    table.add_row("Bot Name", config.bot.name)
    table.add_row("Database Type", config.database.type.value)
    table.add_row("Storage Type", config.storage.type.value)
    table.add_row("LLM Provider", config.llm.provider)
    table.add_row("LLM Model", config.llm.model)
    table.add_row("API Host", config.api.host)
    table.add_row("API Port", str(config.api.port))
    table.add_row("CLI Gateway", "enabled" if config.gateways.cli.enabled else "disabled")
    table.add_row(
        "WebSocket Gateway",
        "enabled" if config.gateways.websocket.enabled else "disabled",
    )
    table.add_row(
        "Telegram Gateway",
        "enabled" if config.gateways.telegram.enabled else "disabled",
    )
    table.add_row("Log Level", config.logging.level.value)

    console.print(table)


@cli.command()
def browser() -> None:
    """Open Chrome with OpenBotX profile for pre-login setup."""
    import subprocess

    from openbotx.tools.cdp_tool import _get_chrome_binary

    profile_dir = Path.home() / ".openbotx-chrome-profile"
    profile_dir.mkdir(exist_ok=True)

    try:
        chrome_binary = _get_chrome_binary()
        args = [
            chrome_binary,
            f"--user-data-dir={profile_dir}",
            "--remote-debugging-port=9222",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        console.print("[bold green]Opening Chrome with OpenBotX profile...[/bold green]")
        console.print(f"[blue]Profile: {profile_dir}[/blue]")
        console.print(f"[dim]Remote debugging: http://localhost:9222[/dim]")

        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        console.print("[green]Chrome opened. You can now login to sites.[/green]")
        console.print(
            "[yellow]Note: Close Chrome when done to avoid conflicts with CDP tools.[/yellow]"
        )

    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Failed to open Chrome: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.argument("template", default="starter")
@click.option("--force", is_flag=True, help="Overwrite existing files")
def init(template: str, force: bool) -> None:
    """Initialize a new OpenBotX project from a template.

    TEMPLATE is the name of the template to use (default: starter).
    Templates are downloaded from https://github.com/openbotx/template-{name}
    """
    import io
    import shutil
    import tempfile
    import zipfile

    import httpx

    cwd = Path.cwd()

    # Check if directory is not empty
    if any(cwd.iterdir()) and not force:
        console.print("[yellow]Directory is not empty.[/yellow]")
        console.print("Use [cyan]--force[/cyan] to overwrite existing files.")
        raise SystemExit(1)

    # Build template URL
    template_name = f"template-{template}"
    zip_url = f"https://github.com/openbotx/{template_name}/archive/refs/heads/main.zip"

    console.print(
        f"[bold blue]Initializing OpenBotX project from template '{template}'...[/bold blue]"
    )
    console.print(f"[dim]Downloading from {zip_url}[/dim]")

    try:
        # Download the zip file
        with console.status("[bold green]Downloading template..."):
            response = httpx.get(zip_url, follow_redirects=True, timeout=30)

        if response.status_code == 404:
            console.print(f"[red]Template '{template}' not found.[/red]")
            console.print(f"[dim]URL: {zip_url}[/dim]")
            console.print("\n[yellow]Available templates:[/yellow]")
            console.print("  - starter (default)")
            raise SystemExit(1)

        response.raise_for_status()

        # Extract to a temporary directory first
        with console.status("[bold green]Extracting template..."):
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                # Extract zip
                with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                    zf.extractall(tmp_path)

                # Find the extracted folder (usually template-name-main/)
                extracted_dirs = list(tmp_path.iterdir())
                if not extracted_dirs:
                    console.print("[red]Empty template archive.[/red]")
                    raise SystemExit(1)

                source_dir = extracted_dirs[0]

                # Copy contents to current directory
                for item in source_dir.iterdir():
                    dest = cwd / item.name
                    if dest.exists():
                        if force:
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        else:
                            console.print(
                                f"  [yellow]Skipped[/yellow] {item.name} (already exists)"
                            )
                            continue

                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    console.print(f"  [green]Created[/green] {item.name}")

        console.print()
        console.print("[bold green]Project initialized![/bold green]")
        console.print()
        console.print("[yellow]Next steps:[/yellow]")
        console.print("  1. Add your LLM API key to [cyan].env[/cyan]")
        console.print("  2. Edit [cyan]config.yml[/cyan] and configure LLM settings")
        console.print("  3. Run [cyan]openbotx start --cli-mode[/cyan] to start chatting")

    except httpx.RequestError as e:
        console.print(f"[red]Failed to download template: {e}[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
