"""Gerenciamento de configuração com validação de schema."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.constants import CONFIG_FILE, LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

DEFAULT_CONFIG: dict[str, Any] = {
    "config_version": 1,
    "professores": ["Wagner Baseggio", "Camila Dias", "Patrícia Ghezzi"],
    "etapas": ["Pré", "Pós imediato", "15 dias", "30 dias"],
    "procedimentos": [
        "Full Face", "Preenchimento Facial", "Rinomodelação",
        "Preenchimento de Mento", "Preenchimento de Mandíbula",
        "Preenchimento de Malar", "Preenchimento de Lábios",
        "Preenchimento de Olheiras", "Bioestimuladores de Colágeno",
        "Profhilo", "Toxina Botulínica (Botox)", "Skinbooster",
        "Peeling", "Microagulhamento", "Ultraformer",
        "Fios de Sustentação", "Fios de PDO", "Limpeza de Pele",
        "Máscaras Faciais", "Hidratação Facial Profunda",
        "Face Lift (Ritidoplastia)", "Blefaroplastia",
    ],
    "last_dest_dir": "",
    "last_fontes": [],
    "last_rotation": 0,
}

_EXPECTED_KEYS: dict[str, type] = {
    "professores": list,
    "etapas": list,
    "procedimentos": list,
    "last_dest_dir": str,
    "last_fontes": list,
    "last_rotation": int,
}


def _validate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Garante que todas as keys esperadas existem com o tipo correto."""
    for key, expected_type in _EXPECTED_KEYS.items():
        if key not in data or not isinstance(data[key], expected_type):
            logger.warning(f"Config key '{key}' ausente ou inválida, usando default.")
            data[key] = DEFAULT_CONFIG[key]
    return data


class ConfigManager:
    """Gerencia leitura e escrita do arquivo de configuração JSON."""

    @staticmethod
    def load() -> dict[str, Any]:
        """Carrega configurações do arquivo, mesclando com defaults."""
        logger.debug("Carregando configurações...")
        config_path = Path(CONFIG_FILE)

        if config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                merged = {**DEFAULT_CONFIG, **raw}
                return _validate_config(merged)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Erro ao ler config: {e}")

        return dict(DEFAULT_CONFIG)

    @staticmethod
    def save(data: dict[str, Any]) -> None:
        """Salva configurações no arquivo JSON."""
        try:
            Path(CONFIG_FILE).write_text(
                json.dumps(data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Erro ao salvar config: {e}")
