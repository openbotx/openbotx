import difflib
from typing import Any

from openbotx.helpers.path import PathResolver
from openbotx.tools.base import Tool


class ReadFileTool(Tool):
    """Read the contents of a file. Use offset to continue reading truncated files."""

    name = "read_file"
    description = "Read the contents of a file. Use offset to continue reading truncated files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to read"},
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Use to continue truncated reads.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. Defaults to entire file.",
            },
        },
        "required": ["path"],
    }

    _MAX_READ_BYTES = 50 * 1024  # 50KB per read

    def __init__(self, resolver: PathResolver):
        self._resolver = resolver

    async def execute(self, path: str, offset: int = 1, limit: int = 0, **kwargs: Any) -> str:
        try:
            file_path = self._resolver.resolve(path)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            all_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
            total_lines = len(all_lines)

            start = max(0, offset - 1)
            if start >= total_lines:
                return f"Error: offset {offset} exceeds file length ({total_lines} lines)."

            lines = all_lines[start:]
            if limit > 0:
                lines = lines[:limit]

            output = ""
            output_lines = 0
            for line in lines:
                if len(output.encode("utf-8")) + len(line.encode("utf-8")) > self._MAX_READ_BYTES:
                    break
                output += line
                output_lines += 1

            if output_lines == 0 and lines:
                output = lines[0]
                output_lines = 1

            shown_end = start + output_lines
            remaining = total_lines - shown_end

            if remaining > 0:
                next_offset = shown_end + 1
                return (
                    f"{output}\n\n[Showing lines {offset}-{shown_end} of {total_lines}. "
                    f"{remaining} more lines. Use offset={next_offset} to continue.]"
                )
            return output
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file at the given path. Creates parent directories if needed."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to write to"},
            "content": {"type": "string", "description": "The content to write"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, resolver: PathResolver):
        self._resolver = resolver

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = self._resolver.resolve(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {e}"


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Edit a file by replacing old_text with new_text. "
        "The old_text must exist exactly in the file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to edit"},
            "old_text": {
                "type": "string",
                "description": "The exact text to find and replace",
            },
            "new_text": {
                "type": "string",
                "description": "The text to replace with",
            },
        },
        "required": ["path", "old_text", "new_text"],
    }

    def __init__(self, resolver: PathResolver):
        self._resolver = resolver

    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = self._resolver.resolve(path)
            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return self._not_found_message(old_text, content, path)

            count = content.count(old_text)
            if count > 1:
                return (
                    f"Warning: old_text appears {count} times. "
                    "Please provide more context to make it unique."
                )

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            return f"Successfully edited {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {e}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return (
                f"Error: old_text not found in {path}.\n"
                f"Best match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
            )
        return (
            f"Error: old_text not found in {path}. No similar text found. Verify the file content."
        )


class ListDirTool(Tool):
    name = "list_dir"
    description = "List the contents of a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The directory path to list",
            },
        },
        "required": ["path"],
    }

    def __init__(self, resolver: PathResolver):
        self._resolver = resolver

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = self._resolver.resolve(path)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "[dir] " if item.is_dir() else "[file] "
                items.append(f"{prefix}{item.name}")

            if not items:
                return f"Directory {path} is empty"
            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {e}"
