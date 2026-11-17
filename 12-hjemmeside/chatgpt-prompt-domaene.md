# Prompt til ChatGPT (agent i Chrome): domæne, hjemmeside og tunnel til byg-mcp

Kopiér alt mellem de to linjer nedenfor ind i ChatGPT. Udfyld først de tre felter i **[KLAMMER]**.

---

Du skal hjælpe mig med at registrere et .dk-domæne og sætte det op til mit projekt **byg-mcp**. Arbejd i min Chrome-browser, hvor jeg allerede er logget ind på **simply.com** og **dash.cloudflare.com**. Svar på dansk.

## Mål

1. Et nyt .dk-domæne, købt hos Simply.com.
2. Domænets DNS administreres af Cloudflare (gratis plan).
3. Hjemmesiden ligger på `https://<domæne>` og `https://www.<domæne>` via Cloudflare Pages.
4. MCP-serveren kan nås på `https://mcp.<domæne>` via en Cloudflare Tunnel til min pc (`http://127.0.0.1:8765`).

## Mine valg

- Ønskede domænenavne i prioriteret rækkefølge: **[fx byg-mcp.dk, bygmcp.dk, bygdata.dk]**
- Maksimal pris for domænet første år: **[fx 150 kr. inkl. moms]**
- Navn på Cloudflare Pages-projektet: **byg-mcp**

## Regler (vigtigt)

- **Stop og spørg mig, før du betaler, bekræfter et køb eller accepterer vilkår.** Vis mig domænenavn, pris pr. år og fornyelsespris, og vent på mit "ja".
- **Indtast aldrig adgangskoder, kortoplysninger, MitID eller koder fra SMS eller e-mail.** Beder en side om det, så stop og bed mig gøre det selv.
- **Validering af .dk-domæner hos Punktum dk** (fx med MitID) er min opgave. Fortæl mig, når det er nødvendigt, og vent.
- **Ændr intet på mit eksisterende domæne gadeconsultants.com** eller mine andre domæner og produkter hos Simply.com eller Cloudflare. Rør kun det nye domæne.
- **Skriv aldrig tokens, tunnelnøgler eller API-nøgler i chatten.** Viser Cloudflare en kommando med et token, så bed mig kopiere den selv direkte fra siden.
- **Vælg altid den mest privatlivsvenlige løsning** i cookie-bannere. Tilvælg ingen ekstra betalte tjenester (e-mail, webhotel, SSL-pakker, privacy-tilkøb osv.).
- Hvis noget ser anderledes ud end beskrevet, eller du er i tvivl, så stop og beskriv, hvad du ser.

## Trin

### 1. Find et ledigt domæne
- Søg på simply.com efter mine ønskede navne, i den rækkefølge jeg har angivet.
- Vis mig en tabel over hvert navn: ledigt ja/nej, pris første år og pris ved fornyelse.
- **Vent på, at jeg vælger et navn.**

### 2. Køb domænet hos Simply.com
- Læg **kun domænet** i kurven, uden webhotel eller andre tilkøb.
- Gå til kassen, og **stop før betalingen**. Vis mig, hvad kurven indeholder og den samlede pris.
- Jeg betaler og validerer selv hos Punktum dk. Fortsæt, når jeg skriver "betalt".

### 3. Tilføj domænet i Cloudflare
- I Cloudflare: **Add a domain**, indtast det nye domæne, og vælg **Free**-planen.
- Hvis Cloudflare importerer DNS-poster fra Simply, så slet poster, der peger på Simplys webhotel. Domænet skal ikke bruge dem.
- Notér de **to navneservere**, Cloudflare tildeler (fx `xxx.ns.cloudflare.com`).

### 4. Skift navneservere hos Simply.com
- Hos Simply.com: åbn **det nye domæne**, find navneservere eller DNS, og vælg eksterne navneservere.
- Indsæt Cloudflares to navneservere i stedet for ns1-ns3.simply.com.
- Vis mig ændringen, før du gemmer, og gem derefter.
- Gå tilbage til Cloudflare og klik **Check nameservers**. Det kan tage fra minutter til et par timer, før domænet bliver **Active**. Fortsæt med trin 5 imens.

### 5. Hjemmesiden på Cloudflare Pages
- I Cloudflare: **Workers & Pages → Create → Pages → Upload assets** (Direct Upload).
- Projektnavn: `byg-mcp`.
- **Jeg uploader selv filen.** Bed mig vælge mappen `12-hjemmeside\site` i projektmappen. Den indeholder `index.html`. Vent, indtil jeg har uploadet og deployet.
- Under projektets **Custom domains**: tilføj `<domæne>` og `www.<domæne>`. Når domænet er aktivt i Cloudflare, opretter Cloudflare selv DNS-posterne.
- Bekræft, at `https://<domæne>` viser siden "byg-mcp".

### 6. Tunnel til MCP-serveren
- I Cloudflare: **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Navn: `byg-mcp`. Har Zero Trust brug for at oprette en organisation, så vælg den gratis plan, og **stop, før du indtaster betalingsoplysninger**. Spørg mig, hvis der kræves et kort.
- Under **Install and run a connector**: vælg **Windows**. Siden viser en kommando, der starter med `cloudflared.exe service install` og efterfølges af et token. **Kopiér den ikke ind i chatten.** Bed mig køre den selv i en administrator-terminal. `cloudflared` er allerede installeret på min pc.
- Vent, til connectoren står som **Healthy**.
- Tilføj en **Public hostname**:
  - Subdomain: `mcp`
  - Domain: det nye domæne
  - Type: `HTTP`
  - URL: `127.0.0.1:8765`
- Gem.

### 7. Sikkerhed og HTTPS
- **SSL/TLS** for domænet: sæt krypteringstilstanden til **Full**.
- **Edge Certificates**: slå **Always Use HTTPS** til.
- **DNSSEC**: slå til i Cloudflare. Vis mig DS-posten, og hjælp mig med at indsætte den hos Simply.com for det nye domæne, hvis Simply ikke gør det automatisk.
- Opsæt **ikke** Cloudflare Access eller login foran `mcp.<domæne>`. Serveren har sin egen beskyttelse.

### 8. Afrapportering
Skriv til sidst en kort oversigt:
- Det registrerede domæne, prisen og fornyelsesdatoen.
- Cloudflare-navneserverne og domænets status (Pending eller Active).
- URL'en til hjemmesiden og om den virker.
- Tunnelens status og om `mcp.<domæne>` er oprettet.
- Hvad der mangler, eller hvad jeg selv skal gøre.

Skriv ingen tokens eller nøgler i oversigten.

---

## Når ChatGPT er færdig (til Claude Code)

Bed Claude Code om at:
1. starte serveren med `uv run byg-mcp --http` og teste `https://mcp.<domæne>/` udefra. Svaret skal være 404, fordi stien ikke er den hemmelige.
2. hjælpe med at tilføje connectoren i claude.ai med URL'en `https://mcp.<domæne>/mcp/<BYG_MCP_HTTP_TOKEN>`.
3. opdatere hjemmesiden med det rigtige domæne og deploye igen.
