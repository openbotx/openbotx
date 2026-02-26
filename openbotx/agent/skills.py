import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillsLoader:
    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._workspace_skills_dir = workspace / "skills"
        self._builtin_skills_dir = Path(__file__).parent.parent / "skills"

    def _discover_skills(self) -> dict[str, Path]:
        skills: dict[str, Path] = {}

        if self._builtin_skills_dir.is_dir():
            for skill_dir in sorted(self._builtin_skills_dir.iterdir()):
                skill_file = skill_dir / SKILL_FILENAME
                if skill_dir.is_dir() and skill_file.exists():
                    skills[skill_dir.name] = skill_file

        if self._workspace_skills_dir.is_dir():
            for skill_dir in sorted(self._workspace_skills_dir.iterdir()):
                skill_file = skill_dir / SKILL_FILENAME
                if skill_dir.is_dir() and skill_file.exists():
                    skills[skill_dir.name] = skill_file

        return skills

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        match = FRONTMATTER_RE.match(content)
        if not match:
            return {}, content

        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            metadata = {}

        body = content[match.end() :]
        return metadata, body

    @staticmethod
    def _check_requirements(requires: dict[str, Any]) -> bool:
        bins = requires.get("bins", [])
        if isinstance(bins, str):
            bins = [bins]
        for b in bins:
            if not shutil.which(b):
                return False

        env_vars = requires.get("env", [])
        if isinstance(env_vars, str):
            env_vars = [env_vars]
        for var in env_vars:
            if not os.environ.get(var):
                return False

        return True

    def list_skills(self) -> list[dict[str, Any]]:
        result = []
        for name, path in self._discover_skills().items():
            try:
                content = path.read_text(encoding="utf-8")
                metadata, _ = self._parse_frontmatter(content)
                requires = metadata.get("requires", {})
                available = self._check_requirements(requires) if requires else True
                source = "builtin" if path.is_relative_to(self._builtin_skills_dir) else "project"
                result.append(
                    {
                        "name": metadata.get("name", name),
                        "description": metadata.get("description", ""),
                        "available": available,
                        "always": bool(metadata.get("always", False)),
                        "source": source,
                        "location": str(path),
                    }
                )
            except Exception as e:
                logger.warning("failed to load skill %s: %s", name, e)
        result.sort(key=lambda s: s["name"])
        return result

    def load_skill(self, name: str) -> str | None:
        skills = self._discover_skills()
        path = skills.get(name)
        if not path:
            return None

        try:
            content = path.read_text(encoding="utf-8")
            _, body = self._parse_frontmatter(content)
            return body.strip()
        except Exception as e:
            logger.warning("failed to load skill %s: %s", name, e)
            return None

    def get_always_skills(self) -> list[tuple[str, str]]:
        result = []
        for name, path in self._discover_skills().items():
            try:
                content = path.read_text(encoding="utf-8")
                metadata, body = self._parse_frontmatter(content)
                if not metadata.get("always", False):
                    continue
                requires = metadata.get("requires", {})
                if requires and not self._check_requirements(requires):
                    continue
                result.append((metadata.get("name", name), body.strip()))
            except Exception as e:
                logger.warning("failed to load always-skill %s: %s", name, e)
        return result

    def build_skills_summary(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""

        lines = ["<available_skills>"]
        for s in skills:
            status = "available" if s["available"] else "unavailable"
            always_tag = ' always="true"' if s["always"] else ""
            lines.append(
                f"  <skill{always_tag}>"
                f"<name>{s['name']}</name>"
                f"<description>{s['description']}</description>"
                f"<location>{s['location']}</location>"
                f"<status>{status}</status>"
                f"</skill>"
            )
        lines.append("</available_skills>")
        return "\n".join(lines)
