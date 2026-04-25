# Ads Transparency Toolkit — Contexto para Agentes AI

Este documento fornece contexto para agentes AI (Cursor, Copilot, ChatGPT, etc.)
ajudarem o usuário a analisar e baixar anúncios do Google Ads Transparency Center
e da Meta Ads Library (Facebook/Instagram).

## O que é este projeto

Um toolkit CLI que permite:
1. **Analisar** todos os anúncios de um domínio no Google Ads Transparency Center
2. **Analisar** anúncios de vídeo na Meta Ads Library (Facebook/Instagram)
3. **Selecionar** quais criativos de vídeo baixar
4. **Baixar** os vídeos em lote como MP4
5. **Fazer upload** dos vídeos baixados para o YouTube via API

## Fluxo de trabalho padrão

Quando o usuário pedir para analisar anúncios de um domínio, siga este fluxo:

### Passo 1: Análise

Execute `scripts/analyze.py` com os parâmetros do usuário:

```bash
# Obrigatório definir PLAYWRIGHT_BROWSERS_PATH no macOS
export PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright"

python3 scripts/analyze.py --domain DOMINIO --region REGIAO --date PERIODO
```

Parâmetros:
- `--domain`: domínio alvo (ex: robloxos.com)
- `--region`: código do país, default US (ex: BR, GB, DE)
- `--date`: período, default Yesterday (opções: Yesterday, "Last 7 days", "Last 30 days")
- `--format`: tipo de criativo, default VIDEO (opções: VIDEO, IMAGE, TEXT)
- `--max-scroll`: quantos scrolls fazer para carregar anúncios, default 50

O script gera um relatório JSON em `reports/` e imprime a análise no terminal.

### Passo 2: Apresentar análise ao usuário

O relatório contém:
- Total de anúncios encontrados
- Ranking de anunciantes por volume
- Criativos repetidos
- Distribuição por formato
- Lista numerada de todos os criativos

Apresente um resumo e pergunte ao usuário quais criativos deseja baixar.

### Passo 3: Download

Use `scripts/batch_download.py` com a seleção do usuário:

```bash
export PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright"

# Índices específicos
python3 scripts/batch_download.py --report reports/ARQUIVO.json --select 1,2,3

# Range
python3 scripts/batch_download.py --report reports/ARQUIVO.json --select 1-5

# Top N
python3 scripts/batch_download.py --report reports/ARQUIVO.json --top 10

# Todos
python3 scripts/batch_download.py --report reports/ARQUIVO.json --all
```

Para um criativo individual, use:

```bash
python3 scripts/download.py "URL_DO_CRIATIVO"
```

### Passo 4: Upload para o YouTube

Use `scripts/upload.py` para enviar os vídeos baixados ao YouTube:

```bash
# Upload de todos os vídeos da pasta downloads/
python3 scripts/upload.py

# Upload de arquivos específicos
python3 scripts/upload.py downloads/video1.mp4 downloads/video2.mp4

# Upload como público
python3 scripts/upload.py --privacy public

# Upload como Shorts
python3 scripts/upload.py --shorts

# Dry run (listar sem enviar)
python3 scripts/upload.py --dry-run
```

Requer `client_secret.json` na raiz do projeto (credencial OAuth 2.0 do Google Cloud Console).
Na primeira execução, abrirá o navegador para autorização.

## Organização dos downloads

Os vídeos são salvos em subpastas de `downloads/` no formato `YYYY-MM-DD_REGION`:

```
downloads/
├── 2026-04-22_US/     → Anúncios de 22/04/2026 nos EUA
│   ├── video1.mp4
│   └── video2.mp4
├── 2026-04-22_BR/     → Anúncios de 22/04/2026 no Brasil
│   └── video3.mp4
└── 2026-04-23_GB/     → Anúncios de 23/04/2026 no Reino Unido
    └── video4.mp4
```

O `batch_download.py` cria automaticamente a pasta correta com base nos parâmetros
do relatório (região e data). O `upload.py` lê a pasta para extrair `ad_date` e `region`
e registra tudo em `reports/uploads.json`.

## Formato do uploads.json

```json
{
  "uploads": [
    {
      "uploaded_at": "2026-04-23T18:04:30",
      "file": "video.mp4",
      "folder": "2026-04-22_US",
      "title": "Titulo do Video",
      "privacy": "unlisted",
      "ad_date": "2026-04-22",
      "region": "US",
      "success": true,
      "video_id": "abc123",
      "url": "https://youtu.be/abc123"
    }
  ],
  "stats": {"total_uploaded": 10, "total_failed": 2},
  "last_updated": "2026-04-23T18:05:00"
}
```

Este JSON é a base de dados que outros agentes podem consultar para testar/validar criativos.

## Estrutura dos arquivos

```
scripts/analyze.py          → Google: Scraping + análise (gera JSON em reports/)
scripts/analyze_mcp.py      → Google: Mesma análise, conecta ao Chrome do MCP via CDP
scripts/download.py         → Google: Download individual (Playwright + yt-dlp)
scripts/batch_download.py   → Google: Download em lote (usa report JSON)
scripts/meta_analyze.py     → Meta: Salva relatório + análise (recebe dados do MCP, sem Playwright)
scripts/meta_download.py    → Meta: Download de URLs CDN (requests + yt-dlp, sem browser)
scripts/meta_mcp_snippets.js → Meta: JS snippets para MCP evaluate_script (scroll, extração)
scripts/upload.py           → Upload de vídeos para o YouTube (API v3)
scripts/mcp_snippets.js     → Snippets JS para MCP evaluate_script (scroll, extração, análise)
reports/                    → Relatórios JSON (gitignored)
reports/uploads.json        → Log de todos os uploads feitos ao YouTube
downloads/                  → Vídeos MP4 organizados por data/região
downloads/YYYY-MM-DD_XX/    → Subpasta Google por data do anúncio e código do país
downloads/YYYY-MM-DD_XX_meta/ → Subpasta Meta por data da coleta e código do país
client_secret.json          → Credencial OAuth (gitignored)
.youtube_token.json         → Token de sessão YouTube (gitignored)
```

## Formato do relatório JSON

```json
{
  "generated_at": "2026-04-23T17:00:00",
  "analysis": {
    "summary": {
      "total_found": 42,
      "unique_creatives": 38,
      "repeated_creatives": 3,
      "advertisers_count": 5
    },
    "top_advertisers": [...],
    "repeated_creatives": [...],
    "format_distribution": {"videocam": 42},
    "search_params": {"domain": "...", "region": "US", "date": "Yesterday"}
  },
  "creatives": [
    {
      "creative_id": "CR...",
      "advertiser_id": "AR...",
      "advertiser_name": "Nome do Anunciante",
      "url": "https://adstransparency.google.com/advertiser/AR.../creative/CR...",
      "format": "videocam",
      "verified": true
    }
  ]
}
```

## Como funciona o download de vídeos

O Ads Transparency Center embute vídeos do YouTube via iframes. O fluxo de download é:

1. Playwright abre a URL do criativo
2. Encontra o iframe `youtube.com/embed/VIDEO_ID`
3. Dentro do iframe, extrai metadados via `a.ytmVideoInfoVideoTitle` (título, canal, se é Short)
4. yt-dlp baixa o vídeo do YouTube usando cookies do Chrome
5. Se o codec for AV1/VP9, converte para H.264 via ffmpeg

## Dependências do sistema

- Python 3.10+ com playwright instalado
- yt-dlp (brew install yt-dlp)
- ffmpeg (brew install ffmpeg) — para conversão automática de codec
- Google Chrome logado (necessário para cookies do yt-dlp)
- google-api-python-client, google-auth, google-auth-oauthlib (para upload YouTube)

## Chrome DevTools MCP (modo interativo)

O Cursor tem acesso ao Chrome DevTools MCP Server, que permite ao agente controlar
um Chrome real diretamente. O agente pode usar as ferramentas MCP para:

1. **Navegar** → `navigate_page` abre qualquer URL no Ads Transparency
2. **Scroll + extração** → `evaluate_script` roda JS para scroll e extração de dados
3. **Screenshots** → `take_screenshot` mostra visualmente a página ao agente
4. **Debug de rede** → `list_network_requests` / `get_network_request` inspecionam requests
5. **Lighthouse** → `lighthouse_audit` audita performance/acessibilidade de landing pages
6. **Extrair video IDs** → `list_network_requests` com filter "youtube.com/embed/"

Os snippets JS reutilizáveis estão em `scripts/mcp_snippets.js`:
- `expandAndScroll` → clica "See all ads" e faz scroll progressivo
- `extractCreatives` → extrai todos os criativos carregados
- `analyzeCreatives` → extrai + análise completa (replica analyze.py)
- `getPageStats` → stats rápidos do estado da página
- `extractVideoId` → tenta extrair video IDs via performance entries

### Workflow MCP para análise

```bash
# O agente faz tudo via MCP tools, sem rodar scripts:
# 1. navigate_page → URL do Ads Transparency
# 2. evaluate_script → expandAndScroll (carrega criativos)
# 3. take_screenshot → visualizar estado
# 4. evaluate_script → analyzeCreatives (extrai + analisa)
# 5. Apresenta resultado ao usuário
```

### analyze_mcp.py (híbrido CLI + MCP)

Para uso via terminal (sem ser pelo agente), `analyze_mcp.py` conecta ao Chrome
do MCP via CDP em vez de lançar Playwright standalone:

```bash
python3 scripts/analyze_mcp.py --domain robloxos.com --region US --date Yesterday
python3 scripts/analyze_mcp.py --cdp-url http://127.0.0.1:9222 --domain example.com
```

O script auto-detecta o endpoint CDP do MCP. Se não encontrar, faz fallback
para Playwright standalone (mesmo comportamento do analyze.py).

## Meta Ads Library (Facebook/Instagram)

### Arquitetura: MCP DevTools + Python leve

A análise Meta usa **zero Playwright**. O agente controla o Chrome real via MCP DevTools
e o Python só cuida de salvar relatórios e baixar URLs prontas.

```
scripts/meta_mcp_snippets.js → JS snippets para MCP evaluate_script (scroll, extração)
scripts/meta_analyze.py      → Salva relatório JSON + imprime análise (recebe dados do MCP)
scripts/meta_download.py     → Download de URLs CDN (requests + yt-dlp fallback, sem browser)
```

### Workflow MCP para Meta Ads (o agente segue este fluxo)

```bash
# 1. Gerar URL → meta_analyze.py --build-url
python3 scripts/meta_analyze.py --build-url --query "nike" --country US

# 2. navigate_page → URL gerada
# 3. evaluate_script → dismissCookieConsent
# 4. evaluate_script → scrollAndLoad (scroll progressivo, carrega vídeos)
# 5. take_screenshot → verificar estado visual
# 6. evaluate_script → extractAds (extrai todos os vídeos com metadados)
# 7. Agente salva JSON via meta_analyze.py:
echo '{"ads": [...]}' | python3 scripts/meta_analyze.py --from-stdin -q "nike" -c US
# 8. Apresenta relatório ao usuário
# 9. Download:
python3 scripts/meta_download.py --report reports/meta_nike_US_*.json --all
```

### Snippets MCP disponíveis (meta_mcp_snippets.js)

- `dismissCookieConsent` → fecha banner de cookies
- `scrollAndLoad` → scroll progressivo para carregar mais anúncios (40 scrolls, para ao estabilizar)
- `extractAds` → extrai vídeos com Library ID, nome do anunciante, data, status, URL CDN
- `getPageStats` → stats rápidos (total de vídeos, scroll position)
- `getVideoUrlFromAdPage` → extrai URL do vídeo de uma página individual de anúncio
- `tryHdAndGetUrl` → tenta HD + extrai URL (para download em qualidade máxima)
- `selectAllAndGetUrls` → coleta todas as URLs de vídeo da página (bulk export)

### Download

```bash
# A partir do relatório gerado pelo agente
python3 scripts/meta_download.py --report reports/meta_nike_US_20260425.json --all
python3 scripts/meta_download.py --report reports/meta_nike_US_20260425.json --top 5
python3 scripts/meta_download.py --report reports/meta_nike_US_20260425.json --select 1-10

# URLs CDN diretas (passadas pelo agente após MCP extract)
python3 scripts/meta_download.py --urls "https://video.xx.fbcdn.net/..." "https://..."

# Por Library ID (usa yt-dlp, sem MCP)
python3 scripts/meta_download.py --library-id 1234567890

# Apenas CSV, sem download
python3 scripts/meta_download.py --report reports/meta_*.json --all --csv-only
```

O download:
1. Tenta baixar diretamente da CDN (`*.fbcdn.net`) com `urllib` — sem browser
2. Fallback: `yt-dlp --cookies-from-browser chrome` na URL do anúncio
3. Salva em `downloads/YYYY-MM-DD_COUNTRY_meta/`

Convenção de nomes: `meta_{library_id}_{advertiser}_{MMDD}_{index}.mp4`

### Para o agente obter URL fresca de um anúncio individual

Se a URL CDN no relatório expirou, o agente pode:
1. `navigate_page` → `https://www.facebook.com/ads/library/?id=LIBRARY_ID`
2. `evaluate_script` → `tryHdAndGetUrl` (tenta HD + retorna URL fresca)
3. Passar a URL para `meta_download.py --urls "URL_FRESCA"`

### Como funciona tecnicamente

A Meta Ads Library serve vídeos de `*.fbcdn.net` (CDN Facebook):
- URL típica: `https://video.fdm1-1.fna.fbcdn.net/v/HASH/video.mp4?_nc_cat=...`
- URLs são **signed** (expiram em horas) — por isso o workflow MCP é ideal (URL fresca → download imediato)
- Vídeos `blob:` / `data:` são descartados
- O player Facebook tem qualidade SD/HD/1080p; o snippet `tryHdAndGetUrl` tenta aplicar HD automaticamente

### Extensão Chrome (referência)

A pasta `fb-ads-library-downloader` contém uma extensão Manifest V3 com a mesma lógica.
Os snippets MCP replicam o `content/inject.js` da extensão de forma automatizada pelo agente.

### Pasta de destino Meta

```
downloads/
├── 2026-04-25_US_meta/     → Anúncios Meta coletados em 25/04/2026 dos EUA
│   ├── meta_123456_Nike_0425_001.mp4
│   └── meta_789012_Adidas_0425_002.mp4
└── 2026-04-25_BR_meta/
    └── meta_345678_Roblox_0425_001.mp4
```

## Restrições importantes

### Google Ads Transparency
- O Playwright precisa do Chromium: `playwright install chromium`
- No macOS, defina `PLAYWRIGHT_BROWSERS_PATH` se o browser não for encontrado
- A página do Ads Transparency é dinâmica (SPA); o scroll carrega mais resultados progressivamente
- Algumas páginas podem ter muitos anúncios (2000+); use `--max-scroll` para limitar

### Meta Ads Library
- **Não precisa de Playwright** — tudo via MCP DevTools + Python leve
- O Chrome MCP deve estar conectado (o agente usa o Chrome real do usuário)
- URLs CDN da Meta expiram; baixar logo após extração ou usar o agente para obter URL fresca
- Sem login no Facebook, alguns anúncios podem não carregar

### Geral
- O yt-dlp precisa dos cookies do Chrome; o Chrome deve estar instalado e logado
