# HOF Photo Manager

Ferramenta desktop para organizar fotos clínicas de procedimentos estéticos. Detecta cartões SD automaticamente, agrupa fotos por sessão via EXIF e organiza em estrutura de pastas padronizada.

## Download

[**Baixar HOF_Photo_Manager.exe (ultima versao)**](https://github.com/lucasftas/hof-photo-manager/releases/latest)

> Não requer Python instalado — executável standalone para Windows.

## Funcionalidades

- **Detecção automática de cartões SD** — escaneia drives por pastas DCIM
- **Agrupamento inteligente** — agrupa fotos por proximidade temporal usando data EXIF
- **Timeline visual** — miniaturas de todas as fotos com indicadores de mudança EXIF
- **Divisores visuais** — ferramenta tesoura para dividir grupos com preview em tempo real
- **Threshold ajustavel** — de 1min a 60min por grupo individual
- **Duas colunas** — esquerda (não tratados) e direita (tratados em árvore por paciente)
- **Auto-sugestão de etapa** — Pré para o mais antigo, Pós imediato para o mais recente
- **Preview com thumbnails** — navegação entre fotos, rotação, minimizar/expandir grupos
- **Formulário por grupo** — Professor, Paciente, Procedimento e Etapa
- **Cópia organizada** — copia para hierarquia `Professor/Paciente/Procedimento/Etapa/{JPG,RAW}`
- **Resolução de conflitos** — auto-merge em caso de pasta existente
- **Sessão persistente** — fontes e destino salvos entre sessões
- **Configuração persistente** — listas de professores, procedimentos e etapas editáveis

## Estrutura de Pastas Gerada

```
Destino/
└── Professor/
    └── Paciente/
        └── Procedimento/
            └── Etapa/
                ├── JPG/
                │   └── paciente - proc - etapa - foto.jpg
                └── RAW/
                    └── paciente - proc - etapa - foto.arw
```

## Desenvolvimento

```bash
pip install -r requirements.txt
python photomanagerHOF.py
```

### Build

```bash
python -m PyInstaller --onefile --windowed --name HOF_Photo_Manager --add-data "src/ui.html;src" --exclude-module tkinter photomanagerHOF.py
```

### Estrutura do Projeto

```
photomanagerHOF.py      # Entry point (pywebview)
src/
├── __init__.py
├── constants.py        # Constantes, EXIF tags, enums
├── config.py           # ConfigManager com validação
├── models.py           # FotoItem, GrupoPaciente
├── utils.py            # safe_name(), logging
├── processing.py       # Threads de análise e cópia
├── webview_api.py      # API bridge Python ↔ JavaScript
└── ui.html             # Frontend HTML/CSS/JS
```

## Stack

- Python 3.12 + PyWebView
- Pillow (thumbnails e leitura EXIF)
- PyInstaller (build do executável)
