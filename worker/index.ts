/**
 * byg-mcp på Cloudflare: en Worker foran to containere med MCP-serveren.
 *
 * - /mcp/<BYG_MCP_HTTP_TOKEN> → offentlig instans (BygMcp) uden energimærker og uden EMOData-login.
 * - /mcp/<BYG_MCP_EJER_TOKEN> → ejerens egen instans (BygMcpEjer) med alle værktøjer inkl. energimærker.
 *   EMOData-adgangen er personlig og bruges derfor kun her.
 * - /mcp/<personligt token> → offentlig instans. Tokens står i secret BYG_MCP_BRUGERE som "navn:token,navn:token".
 *   Hver tester har sin egen adresse og kan lukkes ude enkeltvis ved at fjerne sit token. Navnene logges ikke.
 * - Alt andet får 404 uden at vække en container, så tilfældige scanninger hverken koster noget eller når serveren.
 * - Nøgler ligger som secrets på Workeren og gives til containeren som miljøvariabler ved opstart.
 * - Containerne sover efter 15 minutter uden kald. Første kald derefter tager nogle sekunder.
 */
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  BYG_MCP: DurableObjectNamespace<BygMcp>;
  BYG_MCP_EJER: DurableObjectNamespace<BygMcpEjer>;
  BYG_MCP_HTTP_TOKEN: string;
  BYG_MCP_EJER_TOKEN?: string;
  BYG_MCP_BRUGERE?: string;
  DATAFORDELER_API_KEY?: string;
  DATAFORSYNINGEN_TOKEN?: string;
  EMO_BRUGERNAVN?: string;
  EMO_ADGANGSKODE?: string;
}

function faelles(env: Env): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const k of ["DATAFORDELER_API_KEY", "DATAFORSYNINGEN_TOKEN"] as const) {
    const v = env[k];
    if (v) vars[k] = v;
  }
  return vars;
}

/** Offentlig instans: energimaerke er skjult (BYG_MCP_SKJUL_VAERKTOEJER i Dockerfile), intet EMO-login. */
export class BygMcp extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "15m";

  constructor(ctx: ConstructorParameters<typeof Container<Env>>[0], env: Env) {
    super(ctx, env);
    this.envVars = { ...faelles(env), BYG_MCP_HTTP_TOKEN: env.BYG_MCP_HTTP_TOKEN };
  }
}

/** Ejerens instans: alle værktøjer og ejerens personlige EMOData-login. */
export class BygMcpEjer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "15m";

  constructor(ctx: ConstructorParameters<typeof Container<Env>>[0], env: Env) {
    super(ctx, env);
    const vars: Record<string, string> = {
      ...faelles(env),
      BYG_MCP_HTTP_TOKEN: env.BYG_MCP_EJER_TOKEN ?? "",
      BYG_MCP_SKJUL_VAERKTOEJER: "",
    };
    if (env.EMO_BRUGERNAVN) vars.EMO_BRUGERNAVN = env.EMO_BRUGERNAVN;
    if (env.EMO_ADGANGSKODE) vars.EMO_ADGANGSKODE = env.EMO_ADGANGSKODE;
    this.envVars = vars;
  }
}

const IKKE_FUNDET = () => new Response("Not found", { status: 404 });

function passer(pathname: string, token: string | undefined): boolean {
  if (!token || token.length < 32) return false;
  const sti = `/mcp/${token}`;
  return pathname === sti || pathname === `${sti}/`;
}

/** "navn:token,navn:token" → [token, token]. Navnet er kun til ejerens overblik. */
function brugertokens(liste: string | undefined): string[] {
  return (liste ?? "")
    .split(",")
    .map((par) => par.slice(par.indexOf(":") + 1).trim())
    .filter((t) => t.length >= 32);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if ((env.BYG_MCP_HTTP_TOKEN ?? "").length < 32) {
      return new Response("Serveren er ikke konfigureret (BYG_MCP_HTTP_TOKEN mangler).", { status: 503 });
    }
    const { pathname } = new URL(request.url);

    // Serverne er uden sessioner, så alle kald til samme adresse kan gå til én navngiven instans.
    if (passer(pathname, env.BYG_MCP_EJER_TOKEN)) return getContainer(env.BYG_MCP_EJER, "ejer").fetch(request);
    if (passer(pathname, env.BYG_MCP_HTTP_TOKEN)) return getContainer(env.BYG_MCP, "byg-mcp").fetch(request);

    // Personlige tokens: skriv stien om til containerens egen sti, så serveren kun kender ét token.
    if (brugertokens(env.BYG_MCP_BRUGERE).some((t) => passer(pathname, t))) {
      const url = new URL(request.url);
      url.pathname = `/mcp/${env.BYG_MCP_HTTP_TOKEN}`;
      return getContainer(env.BYG_MCP, "byg-mcp").fetch(new Request(url, request));
    }
    return IKKE_FUNDET();
  },
};
