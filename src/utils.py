"""Utilitários: sanitização de nomes, setup de logging e criação de thumbnails."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from PIL import Image, ImageTk

from src.constants import (
    FORBIDDEN_FILENAME_CHARS,
    LOG_BACKUP_COUNT,
    LOG_DATEFMT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_MAX_BYTES,
    LOGGER_NAME,
    MAX_FILENAME_LEN,
    THUMBNAIL_SIZE,
    WINDOWS_RESERVED_NAMES,
)


def setup_logging() -> logging.Logger:
    """Configura logging com RotatingFileHandler e console handler."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if not root_logger.handlers:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
        root_logger.addHandler(console_handler)

    return logging.getLogger(LOGGER_NAME)


def safe_name(s: str) -> str:
    """Sanitiza string para uso seguro como nome de arquivo/pasta no Windows.

    Remove caracteres proibidos, nomes reservados do Windows, e trunca
    para respeitar o limite de path do NTFS.
    """
    if not s:
        return "sem_nome"

    cleaned = "".join(c for c in s if c not in FORBIDDEN_FILENAME_CHARS)
    cleaned = cleaned.strip().rstrip(".")

    if not cleaned:
        return "sem_nome"

    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    if len(cleaned) > MAX_FILENAME_LEN:
        cleaned = cleaned[:MAX_FILENAME_LEN]

    return cleaned


def criar_thumbnail(
    path: str | Path, angulo: int = 0, size: int = THUMBNAIL_SIZE
) -> Optional[ImageTk.PhotoImage]:
    """Cria thumbnail de uma imagem com rotação opcional.

    Returns:
        PhotoImage pronto para uso em Tkinter, ou None em caso de erro.
    """
    try:
        img = Image.open(path)
        if angulo != 0:
            img = img.rotate(angulo, expand=True)
        img.thumbnail((size, size))
        return ImageTk.PhotoImage(img)
    except (OSError, Image.UnidentifiedImageError, ValueError) as e:
        logging.getLogger(LOGGER_NAME).debug(f"Erro ao criar thumbnail de {path}: {e}")
        return None
