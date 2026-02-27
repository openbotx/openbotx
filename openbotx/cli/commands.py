import io
import webbrowser
import zipfile
from pathlib import Path

import click
import httpx

from openbotx.version import __version__

TEMPLATE_URL = "https://github.com/openbotx/template-starter/archive/refs/heads/main.zip"


@click.group()
def cli():
    """OpenBotX - AI assistant platform."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Overwrite existing files")
def init(force):
    """Initialize a new OpenBotX project in the current directory."""
    target = Path.cwd()

    if (target / "config.yml").exists() and not force:
        click.echo("Project already initialized. Use --force to overwrite.")
        return

    click.echo("Downloading starter template...")

    try:
        response = httpx.get(TEMPLATE_URL, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except Exception as e:
        click.echo(f"Failed to download template: {e}")
        click.echo("Check your internet connection and try again.")
        return

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        prefix = None
        for name in zf.namelist():
            parts = name.split("/", 1)
            if len(parts) > 1:
                prefix = parts[0]
                break

        extracted = 0
        for info in zf.infolist():
            if info.is_dir():
                continue

            rel_path = info.filename
            if prefix and rel_path.startswith(prefix + "/"):
                rel_path = rel_path[len(prefix) + 1 :]

            if not rel_path:
                continue

            dst = target / rel_path
            if dst.exists() and not force:
                click.echo(f"  skip {rel_path} (exists)")
                continue

            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(info.filename))
            click.echo(f"  created {rel_path}")
            extracted += 1

    click.echo()
    click.echo(f"OpenBotX project initialized ({extracted} files created)")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Copy .env.example to .env and add your API keys")
    click.echo("  2. Edit config.yml to customize your assistant")
    click.echo("  3. Run: openbotx start")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
@click.option("--no-browser", is_flag=True, help="Don't open browser")
def start(host, port, no_browser):
    """Start the OpenBotX server."""
    import uvicorn

    if not no_browser:
        from openbotx.config.loader import load_config

        try:
            cfg = load_config()
            public_url = cfg.server.public_url.rstrip("/") if cfg.server.public_url else ""
        except Exception:
            public_url = ""

        if public_url:
            url = f"{public_url}/app/"
        elif host == "0.0.0.0":
            url = f"http://localhost:{port}/app/"
        else:
            url = f"http://{host}:{port}/app/"

        health_url = url.replace("/app/", "/api/health")

        import threading
        import time

        def _open_when_ready():
            for _ in range(30):
                time.sleep(1)
                try:
                    r = httpx.get(health_url, timeout=2)
                    if r.status_code == 200:
                        webbrowser.open(url)
                        return
                except Exception:
                    pass

        threading.Thread(target=_open_when_ready, daemon=True).start()

    click.echo(f"Starting OpenBotX v{__version__} on {host}:{port}")
    uvicorn.run(
        "openbotx.server.app:app",
        host=host,
        port=port,
        log_level="info",
    )


@cli.command()
def version():
    """Show version."""
    click.echo(f"OpenBotX v{__version__}")
