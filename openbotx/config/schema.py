from pathlib import Path

from pydantic import BaseModel, Field, PrivateAttr


class BotConfig(BaseModel):
    name: str = "OpenBotX"
    description: str = "Your personal AI assistant"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class ModelParams(BaseModel):
    max_tokens: int = 8192
    temperature: float = 0.1
    max_iterations: int = 40
    memory_window: int = 100


class AgentConfig(BaseModel):
    workspace: str = "./workspace"
    model: str = "anthropic/claude-sonnet-4-20250514"
    params: ModelParams = Field(default_factory=ModelParams)


class ImageConfig(BaseModel):
    provider: str = "gemini"
    model: str = "imagen-3.0-generate-002"
    api_key: str = ""


class AuthConfig(BaseModel):
    username: str = "admin"
    password: str = "admin"
    secret_key: str = ""


class ProviderConfig(BaseModel):
    api_key: str = ""
    api_base: str | None = None
    params: dict[str, str] = Field(default_factory=dict)


class TelegramConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = Field(default_factory=list)
    proxy: str | None = None
    reply_to_message: bool = False


class ChannelsConfig(BaseModel):
    send_progress: bool = True
    send_tool_hints: bool = False
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class WebSearchConfig(BaseModel):
    api_key: str = ""
    max_results: int = 5


class ExecToolConfig(BaseModel):
    timeout: int = 60


class ToolsConfig(BaseModel):
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = True


class StorageConfig(BaseModel):
    type: str = "local"
    local_path: str = "./workspace"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""


class CronConfig(BaseModel):
    enabled: bool = True


class Config(BaseModel):
    _config_path: Path | None = PrivateAttr(default=None)

    bot: BotConfig = Field(default_factory=BotConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    agents: dict[str, AgentConfig] = Field(
        default_factory=lambda: {"main": AgentConfig()}
    )
    image: ImageConfig = Field(default_factory=ImageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    cron: CronConfig = Field(default_factory=CronConfig)

    def get_agent(self, name: str = "main") -> AgentConfig:
        return self.agents.get(name, self.agents["main"])

    @property
    def main_agent(self) -> AgentConfig:
        return self.agents.get("main", AgentConfig())

    @property
    def workspace_path(self) -> Path:
        return Path(self.main_agent.workspace).expanduser().resolve()

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        from openbotx.providers.registry import PROVIDERS

        target = model or self.main_agent.model
        prefix = target.split("/", 1)[0].lower() if "/" in target else ""

        if prefix:
            for spec in PROVIDERS:
                if prefix == spec.name.lower() and spec.name in self.providers:
                    cfg = self.providers[spec.name]
                    if cfg.api_key:
                        return cfg

        target_lower = target.lower()
        for spec in PROVIDERS:
            if spec.name in self.providers and any(
                kw.lower() in target_lower for kw in spec.keywords
            ):
                cfg = self.providers[spec.name]
                if cfg.api_key:
                    return cfg

        for cfg in self.providers.values():
            if cfg.api_key:
                return cfg
        return None

    def get_provider_name(self, model: str | None = None) -> str | None:
        from openbotx.providers.registry import PROVIDERS

        target = model or self.main_agent.model
        prefix = target.split("/", 1)[0].lower() if "/" in target else ""

        if prefix:
            for spec in PROVIDERS:
                if prefix == spec.name.lower() and spec.name in self.providers:
                    cfg = self.providers[spec.name]
                    if cfg.api_key:
                        return spec.name

        target_lower = target.lower()
        for spec in PROVIDERS:
            if spec.name in self.providers and any(
                kw.lower() in target_lower for kw in spec.keywords
            ):
                cfg = self.providers[spec.name]
                if cfg.api_key:
                    return spec.name

        for name, cfg in self.providers.items():
            if cfg.api_key:
                return name
        return None
