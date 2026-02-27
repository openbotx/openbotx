from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_serializer


class BotConfig(BaseModel):
    name: str = "OpenBotX"
    description: str = "Your personal AI assistant"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    public_url: str = ""


class AgentParams(BaseModel):
    max_iterations: int = 40
    memory_window: int = 100


class AgentConfig(BaseModel):
    name: str = ""
    workspace: str = "./workspace"
    model: str = ""
    description: str = ""
    instructions: str = ""
    tools: list[str] = Field(default_factory=list)
    model_params: dict = Field(default_factory=dict)
    agent_params: AgentParams = Field(default_factory=AgentParams)

    @field_validator("workspace", mode="before")
    @classmethod
    def default_workspace(cls, v: str | None) -> str:
        if not v or not v.strip():
            return "./workspace"
        return v

    def resolve_workspace(self, project_path: Path) -> Path:
        """Resolve workspace path relative to project root."""
        p = Path(self.workspace).expanduser()
        if not p.is_absolute():
            p = project_path / p
        return p.resolve()


class ProviderConfig(BaseModel):
    name: str = ""
    api_key: str = ""
    api_base: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)
    model_params: dict = Field(default_factory=dict)


class ImageConfig(BaseModel):
    model: str = ""
    provider: ProviderConfig = Field(default_factory=ProviderConfig)


class AuthConfig(BaseModel):
    username: str = ""
    password: str = ""
    secret_key: str = ""


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


_AUTH_FIELDS_BY_TYPE = {
    "oauth1": {"type", "consumer_key", "consumer_secret", "access_token", "access_token_secret"},
    "basic": {"type", "username", "password"},
    "bearer": {"type", "token"},
}


class AuthProfileConfig(BaseModel):
    type: str = ""  # "oauth1", "basic", "bearer"
    # oauth1
    consumer_key: str = ""
    consumer_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    # basic
    username: str = ""
    password: str = ""
    # bearer
    token: str = ""

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        auth_type = data.get("type", "") if isinstance(data, dict) else self.type
        fields = _AUTH_FIELDS_BY_TYPE.get(auth_type)
        if fields and isinstance(data, dict):
            return {k: v for k, v in data.items() if k in fields}
        return data


class HttpClientConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    auth_profiles: dict[str, AuthProfileConfig] = Field(default_factory=dict)


class GeneralToolsConfig(BaseModel):
    restrict_to_workspace: bool = True


class ToolsConfig(BaseModel):
    general: GeneralToolsConfig = Field(default_factory=GeneralToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    http_client: HttpClientConfig = Field(default_factory=HttpClientConfig)


class StorageConfig(BaseModel):
    type: str = "local"
    local_path: str = "./workspace"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""


class HeartbeatConfig(BaseModel):
    enabled: bool = True
    interval: int = 1800


class CronConfig(BaseModel):
    enabled: bool = True


class ClassifierConfig(BaseModel):
    model: str = ""


class Config(BaseModel):
    _config_path: Path | None = PrivateAttr(default=None)

    bot: BotConfig = Field(default_factory=BotConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    agents: dict[str, AgentConfig] = Field(default_factory=lambda: {"main": AgentConfig()})
    image: ImageConfig = Field(default_factory=ImageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)

    @property
    def main_agent(self) -> AgentConfig:
        return self.agents.get("main", AgentConfig())

    @property
    def default_agent(self) -> AgentConfig:
        return next(iter(self.agents.values()))

    @property
    def workspace_path(self) -> Path:
        return self.default_agent.resolve_workspace(self.project_path)

    @property
    def project_path(self) -> Path:
        if self._config_path:
            return self._config_path.parent.resolve()
        return Path.cwd().resolve()

    def _resolve_provider(self, model: str | None = None) -> tuple[str, ProviderConfig] | None:
        from openbotx.providers.registry import PROVIDERS

        target = model or self.main_agent.model
        prefix = target.split("/", 1)[0].lower() if "/" in target else ""

        if prefix:
            for spec in PROVIDERS:
                if prefix == spec.name.lower() and spec.name in self.providers:
                    cfg = self.providers[spec.name]
                    if cfg.api_key:
                        return spec.name, cfg

        target_lower = target.lower()
        for spec in PROVIDERS:
            if spec.name in self.providers and any(
                kw.lower() in target_lower for kw in spec.keywords
            ):
                cfg = self.providers[spec.name]
                if cfg.api_key:
                    return spec.name, cfg

        for name, cfg in self.providers.items():
            if cfg.api_key:
                return name, cfg
        return None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        result = self._resolve_provider(model)
        return result[1] if result else None

    def get_provider_name(self, model: str | None = None) -> str | None:
        result = self._resolve_provider(model)
        return result[0] if result else None
