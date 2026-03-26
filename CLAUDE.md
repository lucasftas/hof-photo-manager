# CLAUDE.md

## Regras do Projeto

### Gatilho "filé"
Quando o usuario disser **"filé"**, executar automaticamente:
1. Commitar todas as mudanças pendentes com mensagem descritiva
2. Push para o GitHub (origin/master)
3. Criar uma nova **GitHub Release** com:
   - Tag versionada (incrementar patch: v0.1.0 → v0.1.1 → v0.2.0 etc.)
   - Release notes em portugues com bullet points das mudanças
   - Compilar o executável via PyInstaller e anexar o `.exe` como asset da release
4. Atualizar o CHANGELOG.md com as mudanças da nova versão

### Build
```bash
python -m PyInstaller --onefile --windowed --name HOF_Photo_Manager --add-data "src/ui.html;src" photomanagerHOF.py
```
O executável fica em `dist/HOF_Photo_Manager.exe`.

### Stack
- Python 3.12 + PyWebView + Pillow
- Frontend: HTML/CSS/JS em `src/ui.html`
- Backend API: `src/webview_api.py`
- Entry point: `photomanagerHOF.py`

### Idioma
- Codigo: ingles (nomes de variaveis, funcoes, commits)
- UI e documentacao: portugues brasileiro
- Release notes: portugues brasileiro
