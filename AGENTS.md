# Ads Transparency Toolkit — Contexto para Agentes AI

Este documento fornece contexto para agentes AI (Cursor, Copilot, ChatGPT, etc.)
ajudarem o usuário a analisar e baixar anúncios do Google Ads Transparency Center.

## O que é este projeto

Um toolkit CLI que permite:
1. **Analisar** todos os anúncios de um domínio no Ads Transparency Center
2. **Selecionar** quais criativos de vídeo baixar
3. **Baixar** os vídeos em lote como MP4
4. **Fazer upload** dos vídeos baixados para o YouTube via API

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
scripts/analyze.py         → Scraping + análise (gera JSON em reports/)
scripts/download.py        → Download individual (Playwright + yt-dlp)
scripts/batch_download.py  → Download em lote (usa report JSON)
scripts/upload.py          → Upload de vídeos para o YouTube (API v3)
reports/                   → Relatórios JSON (gitignored)
reports/uploads.json       → Log de todos os uploads feitos ao YouTube
downloads/                 → Vídeos MP4 organizados por data/região
downloads/YYYY-MM-DD_XX/   → Subpasta por data do anúncio e código do país
client_secret.json         → Credencial OAuth (gitignored)
.youtube_token.json        → Token de sessão YouTube (gitignored)
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

## Restrições importantes

- O Playwright precisa do Chromium: `playwright install chromium`
- No macOS, defina `PLAYWRIGHT_BROWSERS_PATH` se o browser não for encontrado
- O yt-dlp precisa dos cookies do Chrome; o Chrome deve estar instalado e logado
- A página do Ads Transparency é dinâmica (SPA); o scroll carrega mais resultados progressivamente
- Algumas páginas podem ter muitos anúncios (2000+); use `--max-scroll` para limitar
