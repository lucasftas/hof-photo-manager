# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

## [0.5.0] — 2026-03-26 — Timeline, Divisores Visuais e Deteccao EXIF

### Adicionado
- Timeline com miniaturas progressivas entre sidebar e grupos
- Ferramenta tesoura para marcar divisores visuais entre fotos
- Aplicacao em lote de multiplas divisoes com barra de progresso
- Deteccao de mudancas EXIF (ISO, abertura, focal, white balance) entre fotos consecutivas
- Merge de grupos adjacentes (X no separador da timeline)
- Threshold ajustavel por grupo (1min a 60min)
- Botao "Dividir aqui" na preview de cada grupo
- UI bloqueada durante geracao de miniaturas, liberada ao concluir
- Toast separado "Gerando miniaturas..." durante carregamento da timeline

### Alterado
- Removida dependencia de tkinter (utils.py e build)
- Leitura EXIF expandida com tags extras no processing.py
- FotoItem agora armazena exif_hints
- GrupoPaciente com metodo dividir_em para splits seguros

---

## [0.4.0] — 2026-03-26 — Sessao Persistente + Confirmacao de Copia

### Adicionado
- Modal de boas-vindas ao abrir o app com caminhos da sessao anterior
- Persistencia das pastas de origem entre sessoes (`last_fontes` na config)
- Botao "Adicionar / Alterar Origem" no modal de startup
- Modal de confirmacao antes de iniciar copia (mostra destino, permite alterar)
- Analise automatica ao clicar "Continuar" no startup
- Dialogos de pasta abrem no ultimo caminho usado

---

## [0.3.1] — 2026-03-26

### Adicionado
- Auto-sugestao de etapa ao selecionar grupos: "Pre" para o mais antigo, "Pos imediato" para o mais recente
- Validacao obrigatoria de etapa ao confirmar tratamento

---

## [0.3.0] — 2026-03-26 — PyWebView + UX Tratados

### Adicionado
- Interface web com HTML/CSS/JavaScript via `pywebview` (`src/ui.html`)
- API bridge Python-JavaScript (`src/webview_api.py`)
- Dependência `pywebview>=4.0` no `requirements.txt`
- Layout de duas colunas: esquerda (não tratados) e direita (tratados em árvore por paciente)
- Árvore de pacientes com expand/collapse estilo Windows Explorer
- Botão de edição (lápis) na raiz da árvore — edita nome/prof/proc de todos os subgrupos
- Botão de desfazer na raiz — devolve todos os subgrupos para a esquerda
- Botão de desfazer individual em cada subgrupo
- Tags de etapa inline em cada subgrupo tratado
- Preview com navegação de fotos ao clicar em subgrupo tratado
- Toast notifications para análise e tratamento
- ESC para desselecionar grupos e fechar modais/previews
- CLAUDE.md com regras do projeto

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
