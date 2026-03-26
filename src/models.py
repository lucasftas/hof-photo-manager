"""Modelos de dados: FotoItem e GrupoPaciente."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from typing import Any

from src.constants import BYTES_PER_GB, BYTES_PER_MB, JPG_EXTENSIONS, LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


@dataclass
class FotoItem:
    """Representa uma foto individual com metadados."""

    caminho: str
    data_captura: datetime
    exif_hints: dict[str, Any] = field(default_factory=dict)
    nome_arquivo: str = field(init=False)
    extensao: str = field(init=False)
    nome_base: str = field(init=False)
    tamanho: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        path = Path(self.caminho)
        self.nome_arquivo = path.name
        self.extensao = path.suffix.lower()
        self.nome_base = path.stem
        try:
            self.tamanho = path.stat().st_size
        except OSError as e:
            logger.debug(f"Não foi possível obter tamanho de {self.caminho}: {e}")
            self.tamanho = 0


class GrupoPaciente:
    """Agrupa fotos de um mesmo paciente/sessão por proximidade temporal."""

    def __init__(self, id_grupo: int, primeira_foto: FotoItem, rotacao: int = 0) -> None:
        self.id: int = id_grupo
        self.fotos: list[FotoItem] = [primeira_foto]
        self.inicio: datetime = primeira_foto.data_captura
        self.fim: datetime = primeira_foto.data_captura
        self.selecionado: bool = False
        self.minimized: bool = False
        self.dados_form: dict[str, str] = {
            "prof": "", "paciente": "", "proc": "", "etapa": ""
        }
        self.preview_index: int = 0
        self.fotos_visuais: list[FotoItem] = []
        self.rotacao: int = rotacao
        self._atualizar_cache_visual()

    def _atualizar_cache_visual(self) -> None:
        """Recalcula lista de fotos visuais (preferindo JPG sobre RAW)."""
        if not self.fotos:
            return

        self.fotos.sort(key=lambda x: x.data_captura)
        self.inicio = self.fotos[0].data_captura
        self.fim = self.fotos[-1].data_captura

        mapa_fotos: dict[str, list[FotoItem]] = {}
        ordem_bases: list[str] = []
        for f in self.fotos:
            if f.nome_base not in mapa_fotos:
                mapa_fotos[f.nome_base] = []
                ordem_bases.append(f.nome_base)
            mapa_fotos[f.nome_base].append(f)

        self.fotos_visuais = []
        for base in ordem_bases:
            versoes = mapa_fotos[base]
            jpg = next((x for x in versoes if x.extensao in JPG_EXTENSIONS), None)
            self.fotos_visuais.append(jpg if jpg else versoes[0])

        self.preview_index = len(self.fotos_visuais) // 2

    def adicionar_foto(self, foto: FotoItem) -> None:
        """Adiciona uma foto ao grupo e recalcula o cache visual."""
        self.fotos.append(foto)
        self._atualizar_cache_visual()

    def absorver_grupo(self, outro_grupo: GrupoPaciente) -> None:
        """Mescla outro grupo neste, absorvendo todas as fotos."""
        self.fotos.extend(outro_grupo.fotos)
        self._atualizar_cache_visual()

    @property
    def total_fotos(self) -> int:
        return len(self.fotos)

    @property
    def total_clicks(self) -> int:
        return len(self.fotos_visuais)

    @property
    def periodo_dia(self) -> str:
        return "MANHÃ" if self.inicio.hour < 12 else "TARDE"

    @property
    def data_formatada(self) -> str:
        return self.inicio.strftime("%d/%m/%Y")

    @property
    def data_obj_dia(self) -> datetime:
        return datetime(self.inicio.year, self.inicio.month, self.inicio.day)

    @property
    def tamanho_bytes(self) -> int:
        return sum(f.tamanho for f in self.fotos)

    @property
    def tamanho_str(self) -> str:
        b = self.tamanho_bytes
        if b >= BYTES_PER_GB:
            return f"{b / BYTES_PER_GB:.2f} GB"
        return f"{b / BYTES_PER_MB:.1f} MB"

    def get_foto_capa(self) -> Optional[FotoItem]:
        """Retorna a foto usada como capa/preview do grupo."""
        if not self.fotos_visuais:
            return None
        idx = max(0, min(self.preview_index, len(self.fotos_visuais) - 1))
        return self.fotos_visuais[idx]

    def dividir_em(self, visual_index: int, novo_id: int) -> Optional[GrupoPaciente]:
        """Divide o grupo na posição visual_index.

        Retorna o novo grupo (fotos após o índice) ou None se impossível.
        O grupo atual fica com as fotos até visual_index (inclusive).
        """
        if visual_index < 0 or visual_index >= len(self.fotos_visuais) - 1:
            return None

        # Get the base names for the split point
        fotos_antes_bases = {f.nome_base for f in self.fotos_visuais[:visual_index + 1]}

        fotos_a = [f for f in self.fotos if f.nome_base in fotos_antes_bases]
        fotos_b = [f for f in self.fotos if f.nome_base not in fotos_antes_bases]

        if not fotos_a or not fotos_b:
            return None

        # Update current group
        self.fotos = fotos_a
        self._atualizar_cache_visual()

        # Create new group
        novo = GrupoPaciente(novo_id, fotos_b[0], rotacao=self.rotacao)
        for f in fotos_b[1:]:
            novo.fotos.append(f)
        novo._atualizar_cache_visual()

        return novo
