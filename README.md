# Ads Transparency Toolkit

Ferramenta CLI para analisar e baixar vídeos de anúncios do [Google Ads Transparency Center](https://adstransparency.google.com/).

Permite investigar quais anúncios um domínio está veiculando, identificar padrões de repetição, e baixar os criativos de vídeo em lote.

## Pré-requisitos

| Ferramenta | Instalação |
|------------|-----------|
| **Python 3.10+** | [python.org](https://www.python.org/) |
| **Playwright** | `pip install playwright && playwright install chromium` |
| **yt-dlp** | `brew install yt-dlp` ou [github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| **ffmpeg** | `brew install ffmpeg` (opcional, para conversão de codec) |
| **Google Chrome** | Necessário para cookies de autenticação do YouTube |

## Instalação rápida

```bash
git clone https://github.com/vitormaciel3124-create/ads-transparency-toolkit.git
cd ads-transparency-toolkit
pip install -r requirements.txt
playwright install chromium
```

## Como usar

### 1. Analisar anúncios de um domínio

```bash
python3 scripts/analyze.py --domain robloxos.com --region US --date Yesterday
```

Ou passando a URL completa:

```bash
python3 scripts/analyze.py "https://adstransparency.google.com/?region=US&domain=robloxos.com&format=VIDEO&preset-date=Yesterday"
```

O script vai:
- Abrir a página do Ads Transparency
- Fazer scroll para carregar todos os anúncios
- Extrair dados de cada criativo (anunciante, formato, verificação)
- Imprimir um relatório com análise completa
- Salvar um JSON em `reports/` para uso posterior

**Parâmetros:**

| Flag | Descrição | Default |
|------|-----------|---------|
| `--domain` | Domínio para pesquisar | — |
| `--region` | Código do país (US, BR, GB, DE, etc.) | `US` |
| `--date` | Período (`Yesterday`, `Last 7 days`, `Last 30 days`) | `Yesterday` |
| `--format` | Formato: `VIDEO`, `IMAGE`, `TEXT` | `VIDEO` |
| `--max-scroll` | Limite de scrolls para carregar anúncios | `50` |

### 2. Baixar criativos selecionados

Após rodar o `analyze.py`, use o relatório JSON para baixar em lote:

```bash
# Baixar criativos específicos por índice
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423_170000.json --select 1,2,3

# Baixar um range
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423_170000.json --select 1-5

# Baixar os 10 primeiros
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423_170000.json --top 10

# Baixar todos
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423_170000.json --all
```

Os vídeos são salvos em `downloads/` no formato MP4 (H.264), compatível com QuickTime.

### 3. Baixar um vídeo individual

Se você já tem a URL de um criativo específico ou video ID do YouTube:

```bash
# URL do Ads Transparency
python3 scripts/download.py "https://adstransparency.google.com/advertiser/AR.../creative/CR...?region=US&format=VIDEO"

# URL do YouTube
python3 scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Video ID direto
python3 scripts/download.py VIDEO_ID
```

## Estrutura do projeto

```
ads-transparency-toolkit/
├── README.md              ← Este arquivo
├── AGENTS.md              ← Contexto para agentes AI (Cursor, Copilot)
├── requirements.txt       ← Dependências Python
├── scripts/
│   ├── analyze.py         ← Scraping + análise de anúncios
│   ├── download.py        ← Download individual de vídeos
│   └── batch_download.py  ← Download em lote via relatório
├── reports/               ← Relatórios JSON gerados (gitignored)
└── downloads/             ← Vídeos baixados (gitignored)
```

## Como funciona

1. **analyze.py** usa Playwright (Chromium headless) para abrir a página de listagem do Ads Transparency, fazer scroll para carregar todos os cards, e extrair URLs + metadados de cada criativo.

2. **download.py** abre a página de um criativo individual, encontra o iframe do YouTube embedado, extrai o Video ID e metadados (título, canal, se é Short) via o elemento `ytmVideoInfoVideoTitle` dentro do iframe, e usa `yt-dlp` para baixar o vídeo com cookies do Chrome.

3. **batch_download.py** lê o relatório JSON e chama `download.py` para cada criativo selecionado.

Os vídeos são baixados preferencialmente em H.264 (compatível com QuickTime/macOS). Se o YouTube servir em AV1/VP9, o script converte automaticamente com ffmpeg.

## Regiões disponíveis

Alguns códigos comuns: `US`, `BR`, `GB`, `DE`, `FR`, `ES`, `IT`, `JP`, `AU`, `CA`, `MX`, `AR`, `CL`, `CO`, `PT`, `IN`.

Lista completa: use o seletor de país no [Ads Transparency Center](https://adstransparency.google.com/).

## Notas

- O yt-dlp usa cookies do Chrome para autenticação no YouTube. Mantenha o Chrome logado na sua conta Google.
- O Playwright precisa do Chromium instalado via `playwright install chromium`.
- Os relatórios e downloads são gitignored para não poluir o repositório.
