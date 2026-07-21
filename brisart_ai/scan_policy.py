"""Drive scanning policy for BrisartAI."""

from __future__ import annotations

from pathlib import Path

DEFAULT_MAX_FILE_BYTES = 10_000_000

DEFAULT_EXCLUDED_DIR_NAMES = {
    "$recycle.bin", ".cache", ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", "appdata", "application data", "cache", "cookies",
    "local settings", "node_modules", "onedrivetemp", "program files",
    "program files (x86)", "programdata", "recovery", "system volume information",
    "temp", "tmp", "windows", "dist", "build", ".mypy_cache", ".pytest_cache",
}

DEFAULT_EXCLUDED_FILE_NAMES = {"ntuser.dat", "hiberfil.sys", "pagefile.sys", "swapfile.sys"}

DEFAULT_INCLUDED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".py", ".pyw", ".html", ".htm",
    ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".toml",
    ".xml", ".svg", ".yaml", ".yml", ".json", ".jsonl", ".ndjson",
    ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".java", ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".sql", ".tex",
    ".rtf", ".srt", ".vtt", ".properties", ".env", ".docx", ".pptx",
    ".xlsx", ".odt", ".pdf",
}


def should_skip_dir(path: Path, include_hidden: bool = False) -> bool:
    name = path.name.lower()
    if not include_hidden and name.startswith("."):
        return True
    return name in DEFAULT_EXCLUDED_DIR_NAMES


def should_skip_file(path: Path, include_hidden: bool = False, max_bytes: int = DEFAULT_MAX_FILE_BYTES) -> bool:
    name = path.name.lower()
    if not include_hidden and name.startswith(".") and name not in {".env", ".gitignore"}:
        return True
    if name in DEFAULT_EXCLUDED_FILE_NAMES:
        return True
    known_extensionless = name in {"dockerfile", "makefile", "license", "readme", "changelog"}
    if path.suffix.lower() not in DEFAULT_INCLUDED_EXTENSIONS and not known_extensionless:
        return True
    try:
        if path.stat().st_size > max_bytes:
            return True
    except OSError:
        return True
    return False
