import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

from openbotx.config.schema import Config


def _expand_env_vars(data):
    """Recursively expand ${VAR} patterns in config values."""
    if isinstance(data, str):
        return re.sub(
            r"\$\{([^}]+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            data,
        )
    if isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env_vars(v) for v in data]
    return data


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from YAML file."""
    load_dotenv()

    path = config_path or Path("config.yml")
    if not path.exists():
        return Config()

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data = _expand_env_vars(data)
    config = Config.model_validate(data)
    config._config_path = path
    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to YAML file."""
    path = config_path or Path("config.yml")
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", exclude_defaults=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
