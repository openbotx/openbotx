from dataclasses import dataclass
from pathlib import Path

from openbotx.config.schema import AgentConfig, ImageConfig, ToolsConfig
from openbotx.helpers.path import PathResolver
from openbotx.storage.base import StorageProvider


@dataclass
class ProjectContext:
    """Runtime context for the project — paths, configs, and shared services."""

    project_path: Path
    public_dir: Path
    public_url: str

    tools: ToolsConfig
    image: ImageConfig

    storage: StorageProvider | None = None

    def create_resolver(self, agent_cfg: AgentConfig) -> PathResolver:
        workspace = agent_cfg.resolve_workspace(self.project_path)
        allowed_dirs = (
            [workspace, self.public_dir] if self.tools.general.restrict_to_workspace else None
        )
        return PathResolver(workspace=workspace, allowed_dirs=allowed_dirs)
