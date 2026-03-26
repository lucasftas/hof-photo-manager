"""API bridge entre o frontend HTML/JS e o backend Python via pywebview."""

from __future__ import annotations

import base64
import io
import logging
import os
import shutil
import threading
from datetime import datetime
from queue import Empty, Queue
from typing import Any, Optional

from PIL import Image

from src.config import ConfigManager
from src.constants import (
    BYTES_PER_GB,
    ConflictAction,
    LOGGER_NAME,
    THUMBNAIL_SIZE,
)
from src.models import FotoItem, GrupoPaciente
from src.processing import detectar_cartoes_sd, thread_analise, thread_processamento

logger = logging.getLogger(LOGGER_NAME)


def _thumbnail_b64(path: str, angulo: int = 0, size: int = THUMBNAIL_SIZE) -> str:
    """Gera thumbnail como base64 para enviar ao frontend."""
    try:
        img = Image.open(path)
        if angulo != 0:
            img = img.rotate(angulo, expand=True)
        img.thumbnail((size, size))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


class Api:
    """Expõe métodos Python para o JavaScript via pywebview."""

    def __init__(self, window_ref: list) -> None:
        self._window_ref = window_ref
        self.config: dict[str, Any] = ConfigManager.load()
        self.grupos_pacientes: list[GrupoPaciente] = []
        self._grupos_por_id: dict[int, GrupoPaciente] = {}
        self.fontes_origem: list[str] = list(self.config.get("last_fontes", []))
        self.dest_dir: str = self.config.get("last_dest_dir", "")
        self.stop_event = threading.Event()
        self._ui_queue: Queue[dict[str, Any]] = Queue()

    @property
    def _window(self):
        return self._window_ref[0] if self._window_ref else None

    # ---------------------------------------------------------- Init
    def get_initial_state(self) -> dict:
        """Retorna estado inicial para o frontend ao carregar."""
        return {
            "dest_dir": self.dest_dir,
            "fontes_count": len(self.fontes_origem),
            "fontes_paths": list(self.fontes_origem),
            "professores": self.config.get("professores", []),
            "procedimentos": self.config.get("procedimentos", []),
            "etapas": self.config.get("etapas", []),
        }

    # ---------------------------------------------------------- Fontes
    def _save_fontes(self) -> None:
        self.config["last_fontes"] = list(self.fontes_origem)
        ConfigManager.save(self.config)

    def detectar_cartoes(self) -> dict:
        drives = detectar_cartoes_sd()
        for d in drives:
            if d not in self.fontes_origem:
                self.fontes_origem.append(d)
        self._save_fontes()
        return {"count": len(self.fontes_origem), "paths": list(self.fontes_origem)}

    def adicionar_pasta(self) -> dict:
        w = self._window
        if not w:
            return {"count": len(self.fontes_origem), "paths": list(self.fontes_origem)}
        start = self.fontes_origem[-1] if self.fontes_origem else (self.dest_dir or "")
        result = w.create_file_dialog(dialog_type=20, directory=start)  # FOLDER_DIALOG
        if result and len(result) > 0:
            p = result[0] if isinstance(result, (list, tuple)) else str(result)
            if p and p not in self.fontes_origem:
                # Check if nested inside existing source
                is_nested = any(
                    os.path.commonpath([p, existing]) == existing
                    for existing in self.fontes_origem
                )
                if not is_nested:
                    self.fontes_origem.append(p)
                    self._save_fontes()
        return {"count": len(self.fontes_origem), "paths": list(self.fontes_origem)}

    def remover_fonte(self, index: int) -> dict:
        """Remove uma fonte pelo índice."""
        if 0 <= index < len(self.fontes_origem):
            self.fontes_origem.pop(index)
            self._save_fontes()
        return {"count": len(self.fontes_origem), "paths": list(self.fontes_origem)}

    def selecionar_destino(self) -> dict:
        w = self._window
        if not w:
            return {"path": ""}
        result = w.create_file_dialog(dialog_type=20, directory=self.dest_dir or "")
        if result and len(result) > 0:
            p = result[0] if isinstance(result, (list, tuple)) else str(result)
            if p:
                self.dest_dir = p
                self.config["last_dest_dir"] = p
                ConfigManager.save(self.config)
                return {"path": p}
        return {"path": ""}

    # ---------------------------------------------------------- Análise
    def iniciar_analise(self) -> dict:
        if not self.fontes_origem:
            return {"error": "Nenhuma fonte selecionada"}

        result_container: dict[str, Any] = {}
        done_event = threading.Event()

        def on_success(grupos: list[GrupoPaciente]) -> None:
            self.grupos_pacientes = grupos
            self._grupos_por_id = {g.id: g for g in grupos}
            result_container["grupos"] = self._serialize_grupos()
            result_container["datas"] = self._get_datas()
            result_container["timeline"] = self.get_timeline_data()
            result_container["professores"] = self.config.get("professores", [])
            result_container["procedimentos"] = self.config.get("procedimentos", [])
            result_container["etapas"] = self.config.get("etapas", [])

        def on_empty() -> None:
            result_container["error"] = "Sem fotos encontradas."

        def on_error(msg: str) -> None:
            result_container["error"] = f"Erro: {msg}"

        def on_finish() -> None:
            done_event.set()

        self.stop_event.clear()
        t = threading.Thread(
            target=thread_analise,
            args=(self.fontes_origem, self.stop_event, self.config,
                  on_success, on_empty, on_error, on_finish),
            daemon=True,
        )
        t.start()
        done_event.wait(timeout=300)

        return result_container

    def _serialize_grupos(self) -> list[dict]:
        """Converte grupos para JSON serializável para o frontend."""
        result = []
        for g in self.grupos_pacientes:
            capa = g.get_foto_capa()
            thumb = _thumbnail_b64(capa.caminho, g.rotacao) if capa else ""
            fonte_path = ""
            if g.fotos:
                fonte_path = os.path.dirname(g.fotos[0].caminho)
            result.append({
                "id": g.id,
                "data_formatada": g.data_formatada,
                "periodo": g.periodo_dia,
                "hora": g.inicio.strftime("%H:%M"),
                "inicio_iso": g.inicio.isoformat(),
                "total_clicks": g.total_clicks,
                "total_fotos": g.total_fotos,
                "tamanho_str": g.tamanho_str,
                "tamanho_bytes": g.tamanho_bytes,
                "selecionado": g.selecionado,
                "minimized": g.minimized,
                "preview_index": g.preview_index,
                "thumbnail_b64": thumb,
                "dados_form": dict(g.dados_form),
                "fonte_path": fonte_path,
            })
        return result

    def _get_datas(self) -> list[str]:
        datas = sorted(set(g.data_obj_dia for g in self.grupos_pacientes), reverse=True)
        return [d.strftime("%d/%m/%Y") for d in datas]

    def get_timeline_data(self) -> list[dict]:
        """Retorna dados para a timeline sem thumbnails (rapido)."""
        items = []
        for g in self.grupos_pacientes:
            if g.dados_form.get("paciente"):
                continue
            for i, f in enumerate(g.fotos_visuais):
                items.append({
                    "gid": g.id,
                    "foto_index": i,
                    "hora": f.data_captura.strftime("%H:%M:%S"),
                    "nome": f.nome_base,
                    "hints": f.exif_hints,
                })
        return items

    def get_timeline_thumbs(self, start: int, count: int) -> list[dict]:
        """Carrega thumbnails da timeline em lotes."""
        items = []
        idx = 0
        for g in self.grupos_pacientes:
            if g.dados_form.get("paciente"):
                continue
            for f in g.fotos_visuais:
                if idx >= start and idx < start + count:
                    items.append({
                        "idx": idx,
                        "thumb": _thumbnail_b64(f.caminho, g.rotacao, size=50),
                    })
                idx += 1
                if idx >= start + count:
                    return items
        return items

    def _rebuild_ids(self) -> None:
        """Reassign sequential IDs and rebuild lookup."""
        for i, g in enumerate(self.grupos_pacientes):
            g.id = i + 1
        self._grupos_por_id = {g.id: g for g in self.grupos_pacientes}

    def dividir_grupo(self, gid: int, visual_index: int) -> dict:
        """Divide um grupo na posição visual_index."""
        g = self._grupos_por_id.get(gid)
        if not g:
            return {"error": "Grupo não encontrado"}

        novo_id = max(gg.id for gg in self.grupos_pacientes) + 1
        novo = g.dividir_em(visual_index, novo_id)
        if not novo:
            return {"error": "Impossível dividir nesta posição"}

        # Insert new group after the original
        idx = self.grupos_pacientes.index(g)
        self.grupos_pacientes.insert(idx + 1, novo)
        self._rebuild_ids()

        return {
            "grupos": self._serialize_grupos(),
            "datas": self._get_datas(),
            "timeline": self.get_timeline_data(),
        }

    def reagrupar_grupo(self, gid: int, threshold_secs: int) -> dict:
        """Re-agrupa as fotos de um grupo com um threshold diferente."""
        g = self._grupos_por_id.get(gid)
        if not g:
            return {"error": "Grupo não encontrado"}

        fotos = sorted(g.fotos, key=lambda x: x.data_captura)
        if len(fotos) < 2:
            return {"grupos": self._serialize_grupos()}

        # Build new sub-groups
        idx = self.grupos_pacientes.index(g)
        self.grupos_pacientes.remove(g)

        new_groups = []
        curr = GrupoPaciente(1, fotos[0], rotacao=g.rotacao)
        new_groups.append(curr)

        for i in range(1, len(fotos)):
            diff = (fotos[i].data_captura - fotos[i - 1].data_captura).total_seconds()
            if diff > threshold_secs:
                curr._atualizar_cache_visual()
                curr = GrupoPaciente(1, fotos[i], rotacao=g.rotacao)
                new_groups.append(curr)
            else:
                curr.fotos.append(fotos[i])
        curr._atualizar_cache_visual()

        # Insert at original position
        for i, ng in enumerate(new_groups):
            self.grupos_pacientes.insert(idx + i, ng)

        self._rebuild_ids()

        return {
            "grupos": self._serialize_grupos(),
            "datas": self._get_datas(),
            "timeline": self.get_timeline_data(),
        }

    def aplicar_divisores(self, divisores: list[dict]) -> dict:
        """Aplica multiplos splits de uma vez. Cada divisor: {gid, foto_index}.

        Processa splits do mesmo grupo do maior foto_index para o menor,
        sem rebuild de IDs entre splits (evita invalidar referências).
        """
        # Group splits by gid, sort foto_index descending within each
        by_gid: dict[int, list[int]] = {}
        for div in divisores:
            by_gid.setdefault(div["gid"], []).append(div["foto_index"])
        for gid in by_gid:
            by_gid[gid].sort(reverse=True)

        total = len(divisores)
        done = 0

        for gid, indices in by_gid.items():
            g = self._grupos_por_id.get(gid)
            if not g:
                continue
            for foto_index in indices:
                novo_id = max(gg.id for gg in self.grupos_pacientes) + 1
                novo = g.dividir_em(foto_index, novo_id)
                if novo:
                    idx = self.grupos_pacientes.index(g)
                    self.grupos_pacientes.insert(idx + 1, novo)
                    # Don't rebuild IDs yet — keep original refs valid
                    self._grupos_por_id[novo_id] = novo
                done += 1
                self._ui_queue.put({"type": "div_progress", "done": done, "total": total})

        self._rebuild_ids()

        return {
            "grupos": self._serialize_grupos(),
            "datas": self._get_datas(),
            "timeline": self.get_timeline_data(),
        }

    def merge_grupos(self, gid_a: int, gid_b: int) -> dict:
        """Junta dois grupos adjacentes (remove divisor)."""
        ga = self._grupos_por_id.get(gid_a)
        gb = self._grupos_por_id.get(gid_b)
        if not ga or not gb:
            return {"error": "Grupo não encontrado"}

        ga.absorver_grupo(gb)
        self.grupos_pacientes.remove(gb)
        self._rebuild_ids()

        return {
            "grupos": self._serialize_grupos(),
            "datas": self._get_datas(),
            "timeline": self.get_timeline_data(),
        }

    # ---------------------------------------------------------- Fields
    def update_field(self, gid: int, key: str, value: str) -> None:
        g = self._grupos_por_id.get(gid)
        if g:
            g.dados_form[key] = value

    def toggle_select(self, gid: int, checked: bool) -> None:
        g = self._grupos_por_id.get(gid)
        if g:
            g.selecionado = checked

    # ---------------------------------------------------------- Fotos
    def mudar_foto(self, gid: int, delta: int) -> Optional[dict]:
        g = self._grupos_por_id.get(gid)
        if not g or not g.fotos_visuais:
            return None
        g.preview_index = (g.preview_index + delta) % len(g.fotos_visuais)
        capa = g.get_foto_capa()
        if not capa:
            return None
        return {
            "index": g.preview_index,
            "thumbnail_b64": _thumbnail_b64(capa.caminho, g.rotacao),
        }

    def rotacionar(self, gid: int, delta: int) -> Optional[dict]:
        g = self._grupos_por_id.get(gid)
        if not g:
            return None
        g.rotacao = (g.rotacao + delta) % 360
        if self.config.get("last_rotation") != g.rotacao:
            self.config["last_rotation"] = g.rotacao
            ConfigManager.save(self.config)
        capa = g.get_foto_capa()
        if not capa:
            return None
        return {"thumbnail_b64": _thumbnail_b64(capa.caminho, g.rotacao)}

    # ---------------------------------------------------------- Stats
    def get_estatisticas(self) -> Optional[str]:
        if not self.grupos_pacientes:
            return "Analise fotos primeiro."
        total = len(self.grupos_pacientes)
        fotos = sum(g.total_fotos for g in self.grupos_pacientes)
        tratados = sum(1 for g in self.grupos_pacientes if g.dados_form["paciente"])
        gb = sum(g.tamanho_bytes for g in self.grupos_pacientes) / BYTES_PER_GB
        return (
            f"Grupos: {total}\n"
            f"Tratados: {tratados}\n"
            f"Fotos: {fotos}\n"
            f"Tamanho: {gb:.2f} GB"
        )

    # ---------------------------------------------------------- Tratamento
    def tratar_selecionados(self, paciente: str = "", prof: str = "", proc: str = "") -> dict:
        """Aplica dados de paciente/prof/proc aos grupos selecionados."""
        sels = [g for g in self.grupos_pacientes if g.selecionado]
        if not sels:
            return {"grupos": self._serialize_grupos()}

        for s in sels:
            s.dados_form["paciente"] = paciente
            s.dados_form["prof"] = prof
            s.dados_form["proc"] = proc
            s.selecionado = False  # Deselect after treatment

        # Save new professor/procedure to config if not present
        if prof and prof not in self.config.get("professores", []):
            self.config.setdefault("professores", []).append(prof)
            ConfigManager.save(self.config)

        if proc and proc not in self.config.get("procedimentos", []):
            self.config.setdefault("procedimentos", []).append(proc)
            ConfigManager.save(self.config)

        return {
            "grupos": self._serialize_grupos(),
            "professores": self.config.get("professores", []),
            "procedimentos": self.config.get("procedimentos", []),
        }

    # ---------------------------------------------------------- Processing
    def iniciar_processamento(self) -> dict:
        """Copia grupos tratados (com paciente preenchido) para destino."""
        to_process = [g for g in self.grupos_pacientes if g.dados_form["paciente"].strip()]
        total_files = sum(len(g.fotos) for g in to_process)

        if total_files == 0:
            return {"error": "Nenhum grupo tratado para copiar.", "total": 0}

        if not self.dest_dir:
            return {"error": "Nenhum destino definido.", "total": 0}

        self.stop_event.clear()
        self._ui_queue = Queue()

        threading.Thread(
            target=thread_processamento,
            args=(to_process, self.dest_dir, self.stop_event,
                  self._ask_conflict, self._ui_queue),
            daemon=True,
        ).start()

        return {"total": total_files}

    def mover_para_lixo(self) -> dict:
        """Move arquivos originais dos grupos tratados para pasta escolhida."""
        w = self._window
        if not w:
            return {"error": "Janela indisponivel.", "total": 0}

        # Pick trash folder
        result = w.create_file_dialog(dialog_type=20, directory=self.dest_dir or "")
        if not result or len(result) == 0:
            return {"total": 0}

        trash_dir = result[0] if isinstance(result, (list, tuple)) else str(result)
        if not trash_dir:
            return {"total": 0}

        to_process = [g for g in self.grupos_pacientes if g.dados_form["paciente"].strip()]
        total_files = sum(len(g.fotos) for g in to_process)

        if total_files == 0:
            return {"error": "Nenhum grupo tratado.", "total": 0}

        self.stop_event.clear()
        self._ui_queue = Queue()

        threading.Thread(
            target=self._thread_mover_lixo,
            args=(to_process, trash_dir),
            daemon=True,
        ).start()

        return {"total": total_files}

    def _thread_mover_lixo(
        self, grupos: list[GrupoPaciente], trash_dir: str
    ) -> None:
        """Move arquivos originais para pasta de lixo (thread separada)."""
        sucesso = 0
        erros = 0

        def _log(msg: str, tag: str = "info") -> None:
            self._ui_queue.put({"type": "log", "msg": msg, "tag": tag})

        for g in grupos:
            if self.stop_event.is_set():
                break

            for f in g.fotos:
                if self.stop_event.is_set():
                    break

                target = os.path.join(trash_dir, f.nome_arquivo)
                # Handle name collision
                if os.path.exists(target):
                    base, ext = os.path.splitext(f.nome_arquivo)
                    ts = int(datetime.now().timestamp())
                    target = os.path.join(trash_dir, f"{base}_{ts}{ext}")

                try:
                    shutil.move(f.caminho, target)
                    sucesso += 1
                    self._ui_queue.put({"type": "progress", "step": 1})
                    _log(f"Movido: {f.nome_arquivo}", "ok")
                except OSError as e:
                    erros += 1
                    _log(f"Erro: {f.nome_arquivo} - {e}", "err")
                    logger.error(f"Erro mover {f.caminho}: {e}")

        logger.info(f"Mover lixo concluido. Sucesso: {sucesso}, Erros: {erros}")
        self._ui_queue.put({"type": "done", "sucesso": sucesso, "erros": erros})

    def poll_progress(self) -> list[dict]:
        msgs = []
        try:
            for _ in range(100):
                msgs.append(self._ui_queue.get_nowait())
        except Empty:
            pass
        return msgs

    def cancelar_processo(self) -> None:
        self.stop_event.set()

    def _ask_conflict(self, tipo: str, nome: str, caminho: str) -> tuple[ConflictAction, Optional[str]]:
        """Conflito de pasta — auto-mescla no modo webview."""
        logger.info(f"Conflito {tipo} '{nome}' — auto-mesclando.")
        return (ConflictAction.MERGE, None)
