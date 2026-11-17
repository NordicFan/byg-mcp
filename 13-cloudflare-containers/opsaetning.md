# byg-mcp på Cloudflare Containers

MCP-serveren kører hos Cloudflare, så din pc ikke er server. GitHub Actions bygger containeren og deployer den med `wrangler deploy`, hver gang der pushes til `main`. Det kræver repo-secret `CLOUDFLARE_API_TOKEN`.

```
claude.ai ──HTTPS──> mcp.byg-mcp.dk ──> Worker "byg-mcp" ──> container (byg-mcp --http, port 8080)
                                         │
                                         └─ kun /mcp/<BYG_MCP_HTTP_TOKEN> sendes videre, alt andet giver 404
```

| Fil | Indhold |
|---|---|
| `Dockerfile` | Python 3.11 + uv. Starter `byg-mcp --http` uden sessioner på port 8080. Ingen nøgler i billedet |
| `worker/index.ts` | Worker med containeren. Tjekker stien og sender nøgler videre som miljøvariabler. Containeren sover efter 15 min. uden kald |
| `wrangler.jsonc` | Instanstype `basic` (1/4 vCPU, 1 GiB), højst 1 instans |
| `.github/workflows/tests.yml` | Enhedstests og typetjek, derefter build og deploy (kun på `main`, og kun når tokenet findes) |

**Pris:** Workers Paid koster 5 $/md. Med 15 minutters søvn ligger personlig brug langt inden for det inkluderede forbrug (25 GiB-timer hukommelse og 375 vCPU-minutter pr. måned).

## Det skal du gøre (én gang)

### 1. Opgradér til Workers Paid
Cloudflare → **Workers & Pages → Plans** → vælg **Workers Paid** (5 $/md.) og betal.

### 2. Opret et API-token (i Chrome)
Åbn https://dash.cloudflare.com/profile/api-tokens → **Create Token** → **Edit Cloudflare Workers** → **Use template**:
- **Permissions:** tilføj **Account → Containers → Edit** (hvis den findes).
- **Account Resources:** din konto. **Zone Resources:** `byg-mcp.dk`.
- **Continue to summary → Create Token → Copy.** Tokenet vises kun én gang.

### 3. Læg tokenet i GitHub
Åbn https://github.com/NordicFan/byg-mcp/settings/secrets/actions/new (logget ind som NordicFan):
- Name: `CLOUDFLARE_API_TOKEN`, Secret: tokenet → **Add secret**.

Næste push til `main`, eller *Actions → Tests og deploy → Run workflow*, bygger og deployer. Første build tager 5-10 minutter.

### 4. Læg nøglerne i Workeren
Cloudflare → **Workers & Pages → byg-mcp → Settings → Variables and Secrets → Add**. Vælg typen **Secret** for hver af disse:

| Navn | Værdi |
|---|---|
| `BYG_MCP_HTTP_TOKEN` | Samme værdi som i `.env`. Så forbliver connector-URL'en den samme |
| `DATAFORDELER_API_KEY` | Fra `.env` |
| `DATAFORSYNINGEN_TOKEN` | Fra `.env` |
| `EMO_BRUGERNAVN` | Fra `.env` |
| `EMO_ADGANGSKODE` | Fra `.env` |

Indtil `BYG_MCP_HTTP_TOKEN` er sat, svarer Workeren med 503.

### 5. Flyt mcp.byg-mcp.dk fra pc'en til Cloudflare
Gøres sammen med Claude Code, når containeren virker på `byg-mcp.<konto>.workers.dev`:
1. Slet tunnelens rute `mcp.byg-mcp.dk` (Tunnels → byg-mcp → Routes).
2. Aktivér `routes` i `wrangler.jsonc`, og push. Så overtager Workeren `mcp.byg-mcp.dk`.
3. På pc'en, i PowerShell som administrator: `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" service uninstall`
4. Slet tunnelen `byg-mcp` i Cloudflare.

## Drift

- **Opdatering:** Push til `main`, så bygger og deployer GitHub Actions automatisk.
- **Logs:** Cloudflare → Workers & Pages → byg-mcp → Logs. Nøgler maskeres, og stien med hemmeligheden logges ikke af serveren.
- **Ny hemmelig sti:** Ændr `BYG_MCP_HTTP_TOKEN` i Workerens secrets, og opdatér connector-URL'en i claude.ai.
- **Første kald efter en pause** tager 5-15 sek., fordi containeren skal starte.
- **Uden sessioner:** Containeren kører med `BYG_MCP_STATELESS=1`, så hvert kald står alene. Det er nødvendigt, fordi containeren kan sove mellem kald.
