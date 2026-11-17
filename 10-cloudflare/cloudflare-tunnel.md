# byg-mcp i claude.ai via Cloudflare Tunnel (gratis)

Med denne opsætning kan du bruge byg-mcp i Claude i browseren og på mobilen. Serveren kører på din pc, og Cloudflare giver den en fast HTTPS-adresse, `https://byg-mcp.oobforge.com`. Den virker kun, når pc'en er tændt, og både serveren og tunnelen kører.

## Sådan hænger det sammen

```
claude.ai ──HTTPS──> Cloudflare ──tunnel──> cloudflared på din pc ──> byg-mcp --http (127.0.0.1:8765)
```

- **Ingen åbne porte på din router.** Tunnelen går udad fra pc'en.
- Serveren lytter kun på `127.0.0.1`, så andre på dit netværk kan ikke nå den direkte.
- **Adgangskontrol:** MCP-endpointet ligger på en hemmelig sti, `/mcp/<BYG_MCP_HTTP_TOKEN>`. Alle andre stier giver 404. Hemmeligheden står i `.env`, som aldrig committes, og den logges ikke.
- Nøglerne til Datafordeleren og Dataforsyningen bliver på din pc.

**Behandl hele connector-URL'en som en adgangskode.** Alle, der kender den, kan bruge serveren og dermed din kvote hos Datafordeleren og Dataforsyningen.

## Engangsopsætning

Kør kommandoerne i en terminal (PowerShell) i projektmappen.

### 1. Installér cloudflared

```bash
winget install --id Cloudflare.cloudflared
```

Luk og åbn terminalen bagefter, så `cloudflared` kan findes.

### 2. Log ind på Cloudflare

```bash
cloudflared tunnel login
```

Browseren åbner. Vælg domænet **oobforge.com**. Der gemmes et certifikat i `%USERPROFILE%\.cloudflared\`.

### 3. Opret tunnelen og DNS-navnet

```bash
cloudflared tunnel create byg-mcp
```

```bash
cloudflared tunnel route dns byg-mcp byg-mcp.oobforge.com
```

Den første kommando skriver et tunnel-ID (en UUID) og laver filen `%USERPROFILE%\.cloudflared\<ID>.json`. Den indeholder tunnelens hemmelighed og må ikke deles. Den anden kommando opretter en CNAME-post i Cloudflare-DNS.

### 4. Lav konfigurationsfilen

Opret `%USERPROFILE%\.cloudflared\config.yml` med dette indhold. Erstat `<ID>` med tunnel-ID'et:

```yaml
tunnel: <ID>
credentials-file: C:\Users\peter\.cloudflared\<ID>.json

ingress:
  - hostname: byg-mcp.oobforge.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

### 5. Tjek hemmeligheden i .env

`.env` skal have en linje `BYG_MCP_HTTP_TOKEN=...` på mindst 32 tegn. Den er allerede oprettet. Vil du lave en ny:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Start (hver gang)

Brug to terminaler.

```bash
uv run byg-mcp --http
```

```bash
cloudflared tunnel run byg-mcp
```

Tjek at der er hul igennem. Det giver **404**, som er det forventede svar, fordi stien ikke er den hemmelige:

```bash
curl -s -o NUL -w "%{http_code}" https://byg-mcp.oobforge.com/
```

## Tilføj som connector i claude.ai

1. Gå til **claude.ai → Indstillinger → Connectors → Add custom connector**.
2. Navn: `byg-dk`.
3. URL: `https://byg-mcp.oobforge.com/mcp/<din BYG_MCP_HTTP_TOKEN fra .env>`
4. Lad OAuth-felterne stå tomme, og gem.
5. Slå connectoren til i en chat via værktøjsmenuen. Den er nu også tilgængelig i Claude-appen på mobilen.

## Valgfrit: start automatisk

- **Tunnelen som Windows-tjeneste:** kør `cloudflared service install` i en administrator-terminal. Tjenesten læser `config.yml` fra systemprofilen. Se Cloudflares dokumentation, hvis den ikke finder filen.
- **Serveren ved login:** opret en opgave i Opgavestyring (Task Scheduler) med programmet `uv`, argumenterne `run byg-mcp --http` og startmappen sat til projektmappen.

## Ny hemmelighed eller luk ned

- **Lækket URL:** lav en ny `BYG_MCP_HTTP_TOKEN` i `.env`, genstart `byg-mcp --http`, og opdatér connectorens URL i claude.ai. Den gamle URL holder straks op med at virke.
- **Luk helt:** `cloudflared tunnel delete byg-mcp` og slet CNAME-posten i Cloudflare-DNS.

## Begrænsninger

- **`vejrfil` og `kort_udsnit` gemmer filer på pc'en.** I claude.ai får du linket eller billedet, men den lokale sti kan du kun bruge på pc'en.
- **Den hemmelige sti er enkel adgangskontrol, ikke login pr. bruger.** Skal andre end dig have adgang, er Cloudflare Access med OAuth det næste skridt.
