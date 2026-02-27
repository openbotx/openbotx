#!/usr/bin/env python3
"""OpenBotX CLI entrypoint."""

import sys
from pathlib import Path

# Add the current directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent))

from openbotx.cli.commands import cli

if __name__ == "__main__":
    cli()
