# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

## [Unreleased] — Migração para PyWebView

### Adicionado
- Interface web com HTML/CSS/JavaScript via `pywebview` (`src/ui.html`)
- API bridge Python-JavaScript (`src/webview_api.py`)
- Dependência `pywebview>=4.0` no `requirements.txt`

### Removido
- Interface Tkinter (`src/app.py`) — substituída pela interface web
- Dependência implícita de Tkinter

### Alterado
- `photomanagerHOF.py` — entry point agora inicializa janela pywebview
- `src/constants.py` — ajustes para suportar nova interface
- `.gitignore` — regras adicionais para artefatos de build e IDE

---

## [0.2.0] — 2025-XX-XX — Modularização

> Commit: `c50df16`

### Alterado
- Refatoração completa do código monolítico em módulos separados
- Type hints adicionados em todo o codebase
- Tratamento de erros adequado com try/except
- Thread safety implementada com filas de comunicação

### Estrutura de módulos criada
- `src/constants.py` — constantes, temas, enums
- `src/config.py` — ConfigManager com validação de schema
- `src/models.py` — dataclasses FotoItem e GrupoPaciente
- `src/utils.py` — safe_name(), logging com RotatingFileHandler, thumbnails
- `src/dialogs.py` — ConflictDialog e editores modais
- `src/processing.py` — threads de análise e cópia
- `src/app.py` — AppOrganizador (UI principal Tkinter)

---

## [0.1.0] — 2025-XX-XX — Release Inicial

> Commit: `c45c18a`

### Adicionado
- Detecção automática de cartões SD (scan de pastas DCIM)
- Agrupamento inteligente por proximidade temporal (threshold 20min) via EXIF
- Preview com thumbnails, rotação e navegação entre fotos
- Formulário por grupo: Professor, Paciente, Procedimento, Etapa
- Filtro de grupos por intervalo de datas
- Merge de grupos selecionados
- Cópia organizada para hierarquia `Professor/Paciente/Procedimento/Etapa/{JPG,RAW}`
- Resolução de conflitos (mesclar, renomear ou cancelar)
- Configuração persistente em JSON (professores, procedimentos, etapas)
- Movimentação de originais para lixeira após processamento
- Executável standalone via PyInstaller
