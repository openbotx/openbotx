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
    def __init__(self, project_path: Path | None = None, workspace: Path | None = None):
        self._workspace = workspace
        self._workspace_skills_dir = workspace / "skills" if workspace else None
        self._builtin_skills_dir = Path(__file__).parent.parent / "skills"
        self._project_skills_dir = project_path / "skills" if project_path else None

    def _scan_skills_dir(self, base: Path, skills: dict[str, Path]) -> None:
        """Scan a skills directory for flat and nested skill layouts."""
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            # direct: skills/skill-name/SKILL.md
            skill_file = entry / SKILL_FILENAME
            if skill_file.exists():
                skills[entry.name] = skill_file
                continue
            # nested: skills/source/skill-name/SKILL.md
            for nested in sorted(entry.iterdir()):
                nested_file = nested / SKILL_FILENAME
                if nested.is_dir() and nested_file.exists():
                    skills[f"{entry.name}/{nested.name}"] = nested_file

    def _discover_skills(self) -> dict[str, Path]:
        skills: dict[str, Path] = {}

        # tier 1: builtin (lowest priority)
        if self._builtin_skills_dir.is_dir():
            for skill_dir in sorted(self._builtin_skills_dir.iterdir()):
                skill_file = skill_dir / SKILL_FILENAME
                if skill_dir.is_dir() and skill_file.exists():
                    skills[skill_dir.name] = skill_file

        # tier 2: project skills (overrides builtin)
        if self._project_skills_dir:
            self._scan_skills_dir(self._project_skills_dir, skills)

        # tier 3: agent workspace skills (highest priority)
        if self._workspace_skills_dir:
            self._scan_skills_dir(self._workspace_skills_dir, skills)

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

    def _resolve_source(self, path: Path) -> str:
        if path.is_relative_to(self._builtin_skills_dir):
            return "builtin"
        if self._project_skills_dir and path.is_relative_to(self._project_skills_dir):
            return "project"
        return "workspace"

    def list_skills(self) -> list[dict[str, Any]]:
        result = []
        for key, path in self._discover_skills().items():
            try:
                content = path.read_text(encoding="utf-8")
                metadata, _ = self._parse_frontmatter(content)
                requires = metadata.get("requires", {})
                available = self._check_requirements(requires) if requires else True
                source = self._resolve_source(path)
                publisher = key.split("/")[0] if "/" in key else ""
                result.append(
                    {
                        "name": key,
                        "description": metadata.get("description", ""),
                        "available": available,
                        "always": bool(metadata.get("always", False)),
                        "source": source,
                        "publisher": publisher,
                        "location": str(path),
                    }
                )
            except Exception as e:
                logger.warning("failed to load skill %s: %s", key, e)
        result.sort(key=lambda s: s["name"].split("/")[-1])
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

    def load_skill_raw(self, name: str) -> dict[str, Any] | None:
        """Load a skill's raw content (with frontmatter) and metadata."""
        skills = self._discover_skills()
        path = skills.get(name)
        if not path:
            return None

        try:
            content = path.read_text(encoding="utf-8")
            source = self._resolve_source(path)
            return {"name": name, "content": content, "source": source}
        except Exception as e:
            logger.warning("failed to load skill %s: %s", name, e)
            return None

    def save_skill(self, name: str, content: str) -> str | None:
        """Save content to a project skill's SKILL.md. Returns error string or None on success."""
        skills = self._discover_skills()
        path = skills.get(name)
        if not path:
            return "Skill not found"

        if path.is_relative_to(self._builtin_skills_dir):
            return "Cannot edit builtin skills"

        try:
            path.write_text(content, encoding="utf-8")
            return None
        except Exception as e:
            logger.warning("failed to save skill %s: %s", name, e)
            return str(e)

    def delete_skill(self, name: str) -> str | None:
        """Delete a project skill directory. Returns error string or None on success."""
        skills = self._discover_skills()
        path = skills.get(name)
        if not path:
            return "Skill not found"

        if path.is_relative_to(self._builtin_skills_dir):
            return "Cannot delete builtin skills"

        try:
            skill_dir = path.parent
            shutil.rmtree(skill_dir)

            # clean up empty parent directories
            if self._project_skills_dir and path.is_relative_to(self._project_skills_dir):
                base_dir = self._project_skills_dir
            else:
                base_dir = self._workspace_skills_dir

            parent = skill_dir.parent
            while parent != base_dir and parent.is_dir():
                if any(parent.iterdir()):
                    break
                parent.rmdir()
                parent = parent.parent

            return None
        except Exception as e:
            logger.warning("failed to delete skill %s: %s", name, e)
            return str(e)

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
