"""Configuration loading and management for OpenBotX."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from openbotx.helpers.logger import get_logger
from openbotx.models.enums import (
    DatabaseType,
    LogFormat,
    LogLevel,
    StorageType,
    TranscriptionProviderType,
    TTSProviderType,
)

logger = get_logger("config")


class BotConfig(BaseModel):
    """Bot identity configuration."""

    name: str = "OpenBotX"
    description: str = "AI Assistant with skills and tools"


class DatabaseConfig(BaseModel):
    """Single config for all database types. Each provider uses only the fields it needs."""

    type: DatabaseType = DatabaseType.SQLITE
    path: str = "./db/openbotx.db"
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None

    def get_database_config(self) -> dict[str, Any]:
        """Get config dict for the database provider. Provider uses only the keys it needs."""
        return self.model_dump()


class LocalStorageConfig(BaseModel):
    """Local storage configuration."""

    path: str = "./media"


class S3StorageConfig(BaseModel):
    """S3 storage configuration."""

    bucket: str = ""
    region: str = "us-east-1"
    access_key: str = ""
    secret_key: str = ""


class StorageConfig(BaseModel):
    """Storage configuration."""

    type: StorageType = StorageType.LOCAL
    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig)
    s3: S3StorageConfig = Field(default_factory=S3StorageConfig)

    def get_storage_config(self) -> dict[str, Any]:
        """Get storage provider configuration.

        Returns:
            Configuration dict for the storage provider, or empty dict if unknown type
        """
        if self.type == StorageType.LOCAL:
            return self.local.model_dump()
        elif self.type == StorageType.S3:
            return self.s3.model_dump()

        # Unknown storage type
        logger.error(f"Unknown storage type: {self.type}")
        return {}


def _normalize_llm_base_url(url: str | None) -> str | None:
    """Strip trailing slash and /chat/completions from LLM base URL."""
    if not url or not url.strip():
        return None
    u = url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions"):
        if u.endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
            break
    return u or None


class LLMConfig(BaseModel):
    """LLM configuration.

    All fields beyond provider, model, base_url and api_key are passed to
    PydanticAI's ModelSettings (e.g., max_tokens, temperature, top_p).

    When base_url and api_key are set, the agent uses an OpenAI-compatible
    endpoint (same request/response format as OpenAI) with that URL and token.
    """

    model_config = {"extra": "allow"}

    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None

    @field_validator("base_url", mode="after")
    @classmethod
    def _normalize_base_url(cls, v: str | None) -> str | None:
        return _normalize_llm_base_url(v) if v else None


class CLIGatewayConfig(BaseModel):
    """CLI gateway configuration."""

    enabled: bool = True


class WebSocketGatewayConfig(BaseModel):
    """WebSocket gateway configuration."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8765


class TelegramGatewayConfig(BaseModel):
    """Telegram gateway configuration."""

    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = Field(default_factory=list)


class GatewaysConfig(BaseModel):
    """Gateways configuration."""

    cli: CLIGatewayConfig = Field(default_factory=CLIGatewayConfig)
    websocket: WebSocketGatewayConfig = Field(default_factory=WebSocketGatewayConfig)
    telegram: TelegramGatewayConfig = Field(default_factory=TelegramGatewayConfig)


class RelayConfig(BaseModel):
    """Browser relay configuration."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 18792


class APIConfig(BaseModel):
    """API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class TranscriptionConfig(BaseModel):
    """Transcription configuration."""

    provider: TranscriptionProviderType = TranscriptionProviderType.WHISPER
    model: str = "base"


class TTSConfig(BaseModel):
    """TTS configuration."""

    provider: TTSProviderType = TTSProviderType.OPENAI
    voice: str = "alloy"


class MCPServerConfig(BaseModel):
    """MCP server configuration."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    """MCP configuration."""

    servers: list[MCPServerConfig] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    """Security configuration."""

    prompt_injection_detection: bool = True
    tool_approval_required: bool = False
    max_tokens_per_request: int = 100000
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    file: str = "./logs/openbotx.log"
    max_size_mb: int = 100
    backup_count: int = 5


class PathsConfig(BaseModel):
    """Paths configuration."""

    skills: str = "./skills"
    memory: str = "./memory"
    media: str = "./media"
    logs: str = "./logs"
    db: str = "./db"
    # Optional workspace for bootstrap files (nanobot-style: AGENTS.md, SOUL.md, USER.md, TOOLS.md)
    workspace: str = ""


class Config(BaseModel):
    """Main configuration model."""

    version: str = "0.0.1"
    bot: BotConfig = Field(default_factory=BotConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    llm: LLMConfig
    gateways: GatewaysConfig = Field(default_factory=GatewaysConfig)
    relay: RelayConfig = Field(default_factory=RelayConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values."""
    if isinstance(value, str):
        # Match ${VAR_NAME} pattern
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)
        for match in matches:
            env_value = os.environ.get(match, "")
            value = value.replace(f"${{{match}}}", env_value)
        return value
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_config(
    config_path: str | Path = "config.yml",
    env_path: str | Path | None = ".env",
) -> Config:
    """Load configuration from YAML file with environment variable expansion.

    Args:
        config_path: Path to config.yml file
        env_path: Path to .env file (optional)

    Returns:
        Config object with loaded configuration
    """
    # Load environment variables from .env file
    if env_path:
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(config_file) as f:
        raw_config = yaml.safe_load(f) or {}

    # Expand environment variables
    expanded_config = _expand_env_vars(raw_config)

    return Config(**expanded_config)


def ensure_directories(config: Config) -> None:
    """Ensure all configured directories exist.

    Args:
        config: Configuration object
    """
    paths = [
        config.paths.skills,
        config.paths.memory,
        config.paths.media,
        config.paths.logs,
        config.paths.db,
    ]
    if config.paths.workspace:
        paths.append(config.paths.workspace)

    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global config instance."""
    global _config
    _config = config
