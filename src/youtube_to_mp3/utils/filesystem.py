"""Filesystem utilities for cross-platform compatibility."""

import platform
import subprocess
from pathlib import Path
from typing import Optional


def get_music_directory() -> Path:
    """Get the default music directory for the current platform."""
    system = platform.system()

    if system == "Windows":
        # Windows: C:\Users\<username>\Music
        return Path.home() / "Music"
    elif system == "Darwin":  # macOS
        # macOS: /Users/<username>/Music
        return Path.home() / "Music"
    else:  # Linux and others
        # Linux: /home/<username>/Music or XDG_MUSIC_DIR
        xdg_music = get_xdg_music_dir()
        if xdg_music:
            return xdg_music
        return Path.home() / "Music"


def get_xdg_music_dir() -> Optional[Path]:
    """Get the XDG music directory from user-dirs.dirs."""
    try:
        user_dirs_file = Path.home() / ".config" / "user-dirs.dirs"
        if user_dirs_file.exists():
            content = user_dirs_file.read_text()
            for line in content.splitlines():
                if line.startswith("XDG_MUSIC_DIR"):
                    # Extract path from "XDG_MUSIC_DIR="$HOME/Music""
                    path_part = line.split("=", 1)[1].strip('"')
                    path = Path(path_part.replace("$HOME", str(Path.home())))
                    if path.exists():
                        return path
    except Exception:
        pass
    return None


def ensure_directory(path: Path) -> None:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for the current filesystem."""
    # Characters that are problematic on most filesystems
    invalid_chars = '<>:"/\\|?*'

    # Replace invalid characters with underscores
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, "_")

    # Remove or replace other problematic characters
    import re

    sanitized = re.sub(r"[^\w\s\-\.]", "_", sanitized)

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")

    # Ensure it's not empty
    if not sanitized:
        sanitized = "untitled"

    return sanitized


def get_unique_filename(directory: Path, filename: str) -> str:
    """Get a unique filename in the given directory."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    candidate = filename

    while (directory / candidate).exists():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1

    return candidate


def open_folder(path: Path) -> bool:
    """Open the given folder in the system's file explorer."""
    try:
        path = path.expanduser().resolve()
        if not path.exists():
            return False

        system = platform.system()

        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            subprocess.run(["explorer", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception:
        return False


def open_file(file_path: Path) -> bool:
    """Open the folder containing the file and select/highlight the file."""
    try:
        file_path = file_path.expanduser().resolve()
        if not file_path.exists():
            return False

        system = platform.system()

        if system == "Darwin":  # macOS
            # Use 'open -R' to reveal file in Finder
            subprocess.run(["open", "-R", str(file_path)], check=False)
        elif system == "Windows":
            # Use 'explorer /select,' to select file in Explorer
            subprocess.run(["explorer", "/select,", str(file_path)], check=False)
        else:  # Linux and other Unix-like systems
            # xdg-open doesn't support selecting files, so open the containing folder
            # and try some alternative approaches
            folder_path = file_path.parent
            _open_folder_with_file_selection_linux(folder_path, file_path)
        return True
    except Exception:
        return False


def _open_folder_with_file_selection_linux(folder_path: Path, file_path: Path) -> None:
    """Try to open folder and select file on Linux systems."""
    # Try different file managers that support selection
    file_managers = [
        ("nautilus", ["nautilus", "--select", str(file_path)]),  # GNOME Files
        ("dolphin", ["dolphin", "--select", str(file_path)]),     # KDE Dolphin
        ("thunar", ["thunar", str(folder_path)]),                 # XFCE Thunar (no select support)
        ("nemo", ["nemo", "--no-desktop", str(folder_path)]),     # Cinnamon Nemo (limited support)
    ]

    for manager_cmd, args in file_managers:
        try:
            # Check if the file manager is available
            result = subprocess.run(
                ["which", manager_cmd],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                subprocess.run(args, check=False)
                return
        except Exception:
            continue

    # Fallback: just open the folder
    subprocess.run(["xdg-open", str(folder_path)], check=False)
