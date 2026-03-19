# HOF Photo Manager

Ferramenta desktop para organizar fotos clínicas de procedimentos estéticos. Detecta cartões SD automaticamente, agrupa fotos por sessão via EXIF e organiza em estrutura de pastas padronizada.

## Funcionalidades

- **Detecção automática de cartões SD** — escaneia drives por pastas DCIM
- **Agrupamento inteligente** — agrupa fotos por proximidade temporal (threshold de 20min) usando data EXIF
- **Preview com thumbnails** — navegação entre fotos, rotação, minimizar/expandir grupos
- **Formulário por grupo** — Professor, Paciente, Procedimento e Etapa (com sync entre grupos selecionados)
- **Filtro por data** — filtra grupos por intervalo de datas
- **Merge de grupos** — mescla grupos selecionados em um só
- **Cópia organizada** — copia para hierarquia `Professor/Paciente/Procedimento/Etapa/{JPG,RAW}`
- **Resolução de conflitos** — dialog para mesclar, renomear ou cancelar em caso de pasta existente
- **Configuração persistente** — listas de professores, procedimentos e etapas editáveis via menu

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

## Requisitos

- Python 3.10+
- Pillow (`pip install Pillow`)

## Uso

```bash
pip install Pillow
python photomanagerHOF.py
```

Ou use o executável standalone `HOF_Photo_Manager.exe` (não requer Python instalado).

## Configuração

O app salva configurações em `config_hofphotomanager.json` no diretório de execução. Listas de professores, procedimentos e etapas podem ser editadas pelo menu **Configurações**.

## Stack

- Python 3.12 + Tkinter
- Pillow (thumbnails e leitura EXIF)
- PyInstaller (build do executável)
