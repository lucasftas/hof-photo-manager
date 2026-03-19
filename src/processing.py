"""Threads de análise de fotos e processamento de cópia."""

from __future__ import annotations

import logging
import os
import shutil
import string
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Optional

from PIL import Image

from src.constants import (
    BYTES_PER_GB,
    ConflictAction,
    EXIF_DATETIME,
    EXIF_DATETIME_FORMAT,
    EXIF_DATETIME_ORIGINAL,
    GROUP_THRESHOLD_SECS,
    JPG_EXTENSIONS,
    LOGGER_NAME,
    SUPPORTED_EXTENSIONS,
)
from src.models import FotoItem, GrupoPaciente
from src.utils import safe_name

logger = logging.getLogger(LOGGER_NAME)


def thread_analise(
    fontes_origem: list[str],
    stop_event: threading.Event,
    config: dict[str, Any],
    on_success: Callable[[list[GrupoPaciente]], None],
    on_empty: Callable[[], None],
    on_error: Callable[[str], None],
    on_finish: Callable[[], None],
) -> None:
    """Analisa fontes de fotos e agrupa por proximidade temporal.

    Executa em thread separada. Callbacks são chamados via root.after()
    pelo chamador.
    """
    try:
        arquivos: list[FotoItem] = []

        for fonte in fontes_origem:
            logger.debug(f"Analisando fonte: {fonte}")
            if stop_event.is_set():
                break
            for root_dir, _, files in os.walk(fonte):
                for f in files:
                    if stop_event.is_set():
                        break
                    if not f.lower().endswith(SUPPORTED_EXTENSIONS):
                        continue
                    full = os.path.join(root_dir, f)
                    try:
                        dt = datetime.fromtimestamp(os.path.getmtime(full))
                        if f.lower().endswith(JPG_EXTENSIONS):
                            try:
                                img = Image.open(full)
                                exif = img._getexif()
                                if exif:
                                    s = exif.get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME)
                                    if s:
                                        dt = datetime.strptime(s, EXIF_DATETIME_FORMAT)
                            except (OSError, AttributeError, KeyError, ValueError) as e:
                                logger.debug(f"EXIF indisponível para {f}: {e}")
                        arquivos.append(FotoItem(full, dt))
                    except OSError as e:
                        logger.error(f"Erro lendo {f}: {e}")

        logger.info(f"Arquivos encontrados: {len(arquivos)}")

        if not arquivos:
            on_empty()
            return

        arquivos.sort(key=lambda x: x.data_captura)
        rot_padrao = config.get("last_rotation", 0)

        temp_grupos: list[GrupoPaciente] = []
        curr = GrupoPaciente(1, arquivos[0], rotacao=rot_padrao)
        temp_grupos.append(curr)

        for i in range(1, len(arquivos)):
            if stop_event.is_set():
                break
            foto = arquivos[i]
            prev = arquivos[i - 1]
            if (foto.data_captura - prev.data_captura).total_seconds() > GROUP_THRESHOLD_SECS:
                curr._atualizar_cache_visual()
                curr = GrupoPaciente(len(temp_grupos) + 1, foto, rotacao=rot_padrao)
                temp_grupos.append(curr)
            else:
                curr.adicionar_foto(foto)
        curr._atualizar_cache_visual()

        temp_grupos.sort(key=lambda g: g.inicio, reverse=True)
        logger.info(f"Grupos criados: {len(temp_grupos)}")
        on_success(temp_grupos)

    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        on_error(str(e))
    finally:
        on_finish()


def thread_processamento(
    grupos: list[GrupoPaciente],
    dest_dir: str,
    stop_event: threading.Event,
    ask_conflict: Callable[[str, str, str], tuple[ConflictAction, Optional[str]]],
    ui_queue: Queue[dict[str, Any]],
) -> None:
    """Processa cópia de fotos para estrutura de pastas organizada.

    Executa em thread separada. Comunica com UI via ui_queue.

    Formato das mensagens na queue:
        {"type": "log", "msg": str, "tag": str}
        {"type": "progress", "step": int}
        {"type": "done", "sucesso": int, "erros": int}
    """
    sucesso = 0
    erros = 0
    pastas_aprovadas: set[str] = set()

    def _log(msg: str, tag: str = "info") -> None:
        ui_queue.put({"type": "log", "msg": msg, "tag": tag})

    def _ensure_path_with_conflict(
        base_path: str, nome: str, tipo: str
    ) -> Optional[str]:
        """Cria pasta, perguntando ao usuário em caso de conflito.

        Returns:
            Caminho final da pasta, ou None se cancelado.
        """
        nonlocal pastas_aprovadas

        if base_path in pastas_aprovadas or not os.path.exists(base_path):
            if not os.path.exists(base_path):
                os.makedirs(base_path)
                logger.debug(f"Pasta {tipo} criada: {base_path}")
            pastas_aprovadas.add(base_path)
            return base_path

        logger.info(f"Conflito {tipo} '{nome}' detectado. Perguntando...")
        acao, novo = ask_conflict(tipo, nome, base_path)
        logger.info(f"Decisão {tipo}: {acao.value}")

        if acao == ConflictAction.CANCEL:
            stop_event.set()
            return None
        elif acao == ConflictAction.RENAME and novo:
            nome = safe_name(novo)
            base_path = str(Path(base_path).parent / nome)

        if not os.path.exists(base_path):
            os.makedirs(base_path)
            logger.debug(f"Pasta {tipo} criada: {base_path}")

        pastas_aprovadas.add(base_path)
        return base_path

    for g in grupos:
        if stop_event.is_set():
            break

        logger.info(f"--- Processando Grupo ID {g.id} ---")

        prof = safe_name(g.dados_form["prof"]) or "Sem_Professor"
        pac = safe_name(g.dados_form["paciente"])
        proc = safe_name(g.dados_form["proc"]) or "Geral"
        etapa = safe_name(g.dados_form["etapa"]) or "Unica"

        # Professor
        try:
            base_prof = _ensure_path_with_conflict(
                os.path.join(dest_dir, prof), prof, "Professor"
            )
        except OSError as e:
            _log(f"Erro criar pasta professor: {e}", "err")
            continue
        if not base_prof:
            break

        # Paciente
        try:
            base_pac = _ensure_path_with_conflict(
                os.path.join(base_prof, pac), pac, "Paciente"
            )
        except OSError as e:
            _log(f"Erro criar pasta paciente: {e}", "err")
            continue
        if not base_pac:
            break

        # Procedimento
        try:
            base_proc = _ensure_path_with_conflict(
                os.path.join(base_pac, proc), proc, "Procedimento"
            )
        except OSError as e:
            _log(f"Erro criar pasta procedimento: {e}", "err")
            continue
        if not base_proc:
            break

        # Etapa
        try:
            base_etapa = _ensure_path_with_conflict(
                os.path.join(base_proc, etapa), etapa, "Etapa"
            )
        except OSError as e:
            _log(f"Erro criar pasta etapa: {e}", "err")
            continue
        if not base_etapa:
            break

        # Subpastas JPG/RAW
        try:
            os.makedirs(os.path.join(base_etapa, "JPG"), exist_ok=True)
            os.makedirs(os.path.join(base_etapa, "RAW"), exist_ok=True)
        except OSError as e:
            _log(f"Erro criar subpastas: {e}", "err")
            erros += 1
            continue

        # Cópia dos arquivos
        for f in g.fotos:
            if stop_event.is_set():
                break

            dest_folder = "JPG" if f.extensao in JPG_EXTENSIONS else "RAW"
            final_path = os.path.join(base_etapa, dest_folder)
            new_name = f"{pac} - {proc} - {etapa} - {f.nome_arquivo}"
            target = os.path.join(final_path, new_name)

            if os.path.exists(target):
                ts = int(datetime.now().timestamp())
                new_name = f"{pac} - {proc} - {etapa} - {ts}_{f.nome_arquivo}"
                target = os.path.join(final_path, new_name)

            try:
                shutil.copy2(f.caminho, target)
                sucesso += 1
                ui_queue.put({"type": "progress", "step": 1})
                _log(f"OK: {f.nome_arquivo}", "ok")
            except OSError as e:
                erros += 1
                logger.error(f"Erro copy {f.caminho}: {e}")
                _log(f"Erro: {f.nome_arquivo}", "err")

    logger.info(f"Fim. Sucesso: {sucesso}, Erros: {erros}")
    ui_queue.put({"type": "done", "sucesso": sucesso, "erros": erros})


def detectar_cartoes_sd() -> list[str]:
    """Detecta pastas DCIM em drives montados (Windows e macOS)."""
    drives: list[str] = []
    if os.name == "nt":
        drives = [
            f"{d}:\\DCIM"
            for d in string.ascii_uppercase
            if os.path.exists(f"{d}:\\DCIM")
        ]
    elif os.path.exists("/Volumes"):
        for d in os.listdir("/Volumes"):
            p = os.path.join("/Volumes", d, "DCIM")
            if os.path.exists(p):
                drives.append(p)
    return drives
