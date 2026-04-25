# Ads Transparency Toolkit

Ferramenta CLI para analisar e baixar vídeos de anúncios do [Google Ads Transparency Center](https://adstransparency.google.com/) e da [Meta Ads Library](https://www.facebook.com/ads/library/) (Facebook/Instagram).

Permite investigar quais anúncios um domínio ou tema está veiculando, identificar padrões de repetição, e baixar os criativos de vídeo em lote.

## Pré-requisitos

| Ferramenta | Instalação | Usado por |
|------------|-----------|-----------|
| **Python 3.10+** | [python.org](https://www.python.org/) | Todos os scripts |
| **Playwright** | `pip install playwright && playwright install chromium` | Google Ads (analyze/download) |
| **yt-dlp** | `brew install yt-dlp` | Google Ads download, Meta fallback |
| **ffmpeg** | `brew install ffmpeg` | Conversão de codec (opcional) |
| **Google Chrome** | Logado — necessário para cookies do yt-dlp | Ambas plataformas |
| **Chrome DevTools MCP** | Configurado no Cursor | Meta Ads (via agente) |

## Instalação rápida

```bash
git clone https://github.com/vitormaciel3124-create/ads-transparency-toolkit.git
cd ads-transparency-toolkit
pip install -r requirements.txt
playwright install chromium
```

## Plataformas suportadas

### Google Ads Transparency Center

Scraping via Playwright headless — analisa anúncios por domínio, baixa vídeos do YouTube embedado.

### Meta Ads Library (Facebook/Instagram)

Arquitetura **sem Playwright** — o agente AI (Cursor) controla o Chrome real via MCP DevTools, e o Python só salva relatórios e baixa URLs da CDN.

---

## Google Ads — Como usar

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
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423.json --select 1,2,3

# Baixar um range
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423.json --select 1-5

# Baixar os 10 primeiros
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423.json --top 10

# Baixar todos
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423.json --all

# Apenas gerar CSV com URLs (sem download)
python3 scripts/batch_download.py --report reports/robloxos_com_US_20260423.json --all --csv-only
```

### 3. Baixar um vídeo individual

```bash
python3 scripts/download.py "https://adstransparency.google.com/advertiser/AR.../creative/CR..."
python3 scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID"
python3 scripts/download.py VIDEO_ID
```

---

## Meta Ads Library — Como usar

A Meta Ads Library usa uma arquitetura diferente: o **agente AI** (Cursor com MCP) controla o Chrome para navegar e extrair dados, e scripts Python leves cuidam do resto.

### 1. Analisar anúncios (via agente AI)

O fluxo é feito pelo agente no Cursor. Basta pedir:
> "Analisa os anúncios de vídeo de reelshort.com na Meta Ads Library"

O agente vai:
1. Navegar na Meta Ads Library via MCP DevTools
2. Fazer scroll para carregar anúncios de vídeo
3. Extrair todos os criativos (Library ID, anunciante, URLs, datas)
4. Salvar relatório JSON em `reports/`
5. Apresentar o resumo

### 2. Baixar criativos

Após a análise, o download pode ser feito via CLI:

```bash
# Todos os criativos
python3 scripts/meta_download.py --report reports/meta_reelshort_US_20260425.json --all

# Top 5
python3 scripts/meta_download.py --report reports/meta_reelshort_US_20260425.json --top 5

# Seleção por índice
python3 scripts/meta_download.py --report reports/meta_reelshort_US_20260425.json --select 1-10

# URLs CDN diretas
python3 scripts/meta_download.py --urls "https://video.xx.fbcdn.net/..." "https://..."

# Por Library ID (sem relatório)
python3 scripts/meta_download.py --library-id 1234567890
```

### 3. Uso manual (sem agente)

Também é possível gerar a URL e processar dados manualmente:

```bash
# Gerar URL para abrir no browser
python3 scripts/meta_analyze.py --build-url --query "nike" --country US

# Salvar relatório a partir de JSON extraído
echo '{"ads": [...]}' | python3 scripts/meta_analyze.py --from-stdin -q "nike" -c US
```

---

## Upload para o YouTube

```bash
python3 scripts/upload.py                          # Todos da pasta downloads/
python3 scripts/upload.py downloads/video1.mp4     # Arquivos específicos
python3 scripts/upload.py --privacy public         # Como público
python3 scripts/upload.py --shorts                 # Como Shorts
python3 scripts/upload.py --dry-run                # Listar sem enviar
```

Requer `client_secret.json` (credencial OAuth do Google Cloud Console).

---

## Estrutura do projeto

```
ads-transparency-toolkit/
├── README.md                       ← Este arquivo
├── AGENTS.md                       ← Contexto para agentes AI (Cursor, Copilot)
├── requirements.txt                ← Dependências Python
├── scripts/
│   ├── analyze.py                  ← Google: scraping + análise
│   ├── analyze_mcp.py              ← Google: análise via Chrome MCP (CDP)
│   ├── download.py                 ← Google: download individual
│   ├── batch_download.py           ← Google: download em lote
│   ├── mcp_snippets.js             ← Google: JS snippets para MCP
│   ├── meta_analyze.py             ← Meta: salva relatório (recebe dados do MCP)
│   ├── meta_download.py            ← Meta: download de URLs CDN
│   ├── meta_mcp_snippets.js        ← Meta: JS snippets para MCP
│   └── upload.py                   ← Upload para YouTube (API v3)
├── csv/                            ← CSVs com URLs extraídas
├── reports/                        ← Relatórios JSON (gitignored)
└── downloads/                      ← Vídeos MP4 (gitignored)
```

## Como funciona

### Google Ads Transparency
1. **analyze.py** usa Playwright (Chromium headless) para scraping da página de listagem, scroll progressivo, e extração de URLs + metadados.
2. **download.py** abre o criativo, encontra o iframe YouTube embedado, extrai Video ID via `ytmVideoInfoVideoTitle`, e baixa com `yt-dlp` + cookies do Chrome.
3. **batch_download.py** orquestra o download em lote a partir do relatório JSON, gera CSV com todas as URLs.

### Meta Ads Library
1. O agente usa **MCP DevTools** para controlar o Chrome real do usuário (já logado no Facebook).
2. **meta_mcp_snippets.js** contém os scripts JS que o agente executa via `evaluate_script` (scroll, extração de vídeos, tentativa de HD).
3. **meta_analyze.py** recebe os dados extraídos e salva o relatório JSON.
4. **meta_download.py** baixa os MP4 diretamente da CDN do Facebook (`*.fbcdn.net`) com `urllib` — sem browser.

## Regiões disponíveis

Alguns códigos comuns: `US`, `BR`, `GB`, `DE`, `FR`, `ES`, `IT`, `JP`, `AU`, `CA`, `MX`, `AR`, `CL`, `CO`, `PT`, `IN`.

## Notas

- O yt-dlp usa cookies do Chrome para autenticação no YouTube. Mantenha o Chrome logado.
- URLs CDN da Meta expiram em horas — baixe logo após a extração.
- Os relatórios, downloads e CSVs de dados são gitignored para não poluir o repositório.
