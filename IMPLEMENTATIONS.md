# Implementations

Detalhes técnicos das funcionalidades implementadas no HOF Photo Manager.

## Arquitetura

```
photomanagerHOF.py          # Entry point — inicializa pywebview
src/
├── __init__.py
├── constants.py            # Constantes globais, tags EXIF, temas
├── config.py               # ConfigManager com validação de schema JSON
├── models.py               # Dataclasses: FotoItem, GrupoPaciente
├── utils.py                # safe_name(), logging, geração de thumbnails
├── dialogs.py              # Diálogos modais (conflitos, editores)
├── processing.py           # Threads de análise e cópia em background
├── webview_api.py          # API bridge Python ↔ JavaScript
└── ui.html                 # Frontend HTML/CSS/JS
```

## Stack Tecnológica

| Componente | Tecnologia | Versão |
|---|---|---|
| Linguagem | Python | 3.12 |
| GUI | PyWebView | ≥ 4.0 |
| Imagens | Pillow | ≥ 9.0 |
| Build | PyInstaller | — |

## Funcionalidades Implementadas

### 1. Detecção de SD Card
- **Arquivo**: `src/webview_api.py`
- Escaneia todas as letras de drive (Windows) ou `/Volumes` (macOS)
- Identifica SD cards pela presença da pasta `DCIM`
- Listagem recursiva de arquivos JPG/ARW/CR2/NEF/RAF

### 2. Agrupamento Temporal de Fotos
- **Arquivo**: `src/processing.py`
- Lê data/hora EXIF de cada foto via Pillow
- Agrupa fotos com intervalo ≤ 20 minutos entre si
- Ordena grupos cronologicamente
- Suporte a merge manual de grupos

### 3. Interface Web (PyWebView)
- **Arquivos**: `src/ui.html`, `src/webview_api.py`
- Frontend em HTML/CSS/JS comunicando com backend Python
- Thumbnails gerados em background com base64
- Rotação de imagens (0°, 90°, 180°, 270°)
- Navegação entre fotos dentro de cada grupo
- Formulário por grupo com dropdowns populados da configuração
- Filtro por intervalo de datas

### 4. Processamento de Cópia
- **Arquivo**: `src/processing.py`
- Thread separada para não bloquear a UI
- Copia para hierarquia: `Professor/Paciente/Procedimento/Etapa/{JPG,RAW}`
- Renomeia arquivos: `paciente - procedimento - etapa - NNN.ext`
- Resolução de conflitos: mesclar, renomear ou cancelar
- Barra de progresso com feedback em tempo real

### 5. Configuração Persistente
- **Arquivo**: `src/config.py`
- JSON com schema validation
- Listas editáveis: professores, procedimentos, etapas
- Persiste último diretório de destino e rotação
- Arquivo: `config_hofphotomanager.json`

### 6. Modelos de Dados
- **Arquivo**: `src/models.py`
- `FotoItem`: dataclass com path, data EXIF, extensão, thumbnail cache
- `GrupoPaciente`: dataclass com lista de fotos, metadados do formulário, timestamps

### 7. Utilitários
- **Arquivo**: `src/utils.py`
- `safe_name()`: sanitiza nomes de arquivo/pasta (remove caracteres inválidos)
- Logging com `RotatingFileHandler` (arquivo: `debug_detalhado.txt`)
- Geração de thumbnails com cache

### 8. Constantes e Temas
- **Arquivo**: `src/constants.py`
- Tags EXIF mapeadas (DateTimeOriginal, DateTimeDigitized)
- Extensões suportadas: JPG, JPEG, ARW, CR2, NEF, RAF
- Threshold de agrupamento: 20 minutos
- Cores e tema da interface

## Status de Desenvolvimento

| Feature | Status |
|---|---|
| Detecção de SD Card | Implementado |
| Agrupamento por EXIF | Implementado |
| Preview/Thumbnails | Implementado |
| Formulário por grupo | Implementado |
| Filtro por data | Implementado |
| Merge de grupos | Implementado |
| Cópia organizada | Implementado |
| Resolução de conflitos | Implementado |
| Configuração persistente | Implementado |
| Interface PyWebView | Implementado (não commitado) |
| Testes automatizados | Pendente |
| Suporte multi-idioma | Pendente |
| Dark mode | Pendente |
