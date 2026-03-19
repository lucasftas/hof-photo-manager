"""Constantes globais do HOF Photo Manager."""

from enum import Enum

# --- App ---
APP_VERSION: str = "v18.5"
CONFIG_FILE: str = "config_hofphotomanager.json"
LOG_FILE: str = "debug_detalhado.txt"

# --- Análise ---
GROUP_THRESHOLD_SECS: int = 1200
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".arw")
JPG_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg")

# --- EXIF ---
EXIF_DATETIME_ORIGINAL: int = 36867
EXIF_DATETIME: int = 306
EXIF_DATETIME_FORMAT: str = "%Y:%m:%d %H:%M:%S"

# --- UI ---
WINDOW_TITLE: str = "HOF Photo Manager"
WINDOW_GEOMETRY: str = "1400x650"
WINDOW_MIN_WIDTH: int = 1024
WINDOW_MIN_HEIGHT: int = 650
THUMBNAIL_SIZE: int = 150
PATH_DISPLAY_TRUNCATE: int = 40

# --- Sizes ---
BYTES_PER_GB: int = 1024 ** 3
BYTES_PER_MB: int = 1024 ** 2

# --- Logging ---
LOG_FORMAT: str = "%(asctime)s - [%(levelname)s] [%(threadName)s] - %(message)s"
LOG_DATEFMT: str = "%H:%M:%S"
LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT: int = 3
LOGGER_NAME: str = "AppOrganizador"

# --- File Safety ---
FORBIDDEN_FILENAME_CHARS: str = '<>:"/\\|?*'
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})
MAX_FILENAME_LEN: int = 200

# --- Theme ---
THEME: dict[str, str] = {
    "bg_canvas": "#f5f5f5",
    "bg_header": "#e0e0e0",
    "bg_thumbnail": "#ddd",
    "fg_primary": "#007bff",
    "fg_error": "#d9534f",
    "fg_success": "green",
    "fg_warning": "#b8860b",
    "fg_folder": "blue",
    "fg_muted": "gray",
    "fg_missing": "red",
}


class ConflictAction(Enum):
    """Resultado possível de um diálogo de conflito de pasta."""
    MERGE = "mesclar"
    RENAME = "renomear"
    CANCEL = "cancel"
