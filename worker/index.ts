/**
 * byg-mcp på Cloudflare: en Worker foran en container med MCP-serveren.
 *
 * - Kun stien /mcp/<BYG_MCP_HTTP_TOKEN> sendes videre. Alt andet får 404 uden at vække containeren,
 *   så tilfældige scanninger hverken koster noget eller når serveren.
 * - Nøgler ligger som secrets på Workeren og gives til containeren som miljøvariabler ved opstart.
 * - Containeren sover efter 15 minutter uden kald. Første kald derefter tager nogle sekunder.
 */
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  BYG_MCP: DurableObjectNamespace<BygMcp>;
  BYG_MCP_HTTP_TOKEN: string;
  DATAFORDELER_API_KEY?: string;
  DATAFORSYNINGEN_TOKEN?: string;
  EMO_BRUGERNAVN?: string;
  EMO_ADGANGSKODE?: string;
}

export class BygMcp extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "15m";

  constructor(ctx: ConstructorParameters<typeof Container<Env>>[0], env: Env) {
    super(ctx, env);
    const vars: Record<string, string> = { BYG_MCP_HTTP_TOKEN: env.BYG_MCP_HTTP_TOKEN };
    for (const k of ["DATAFORDELER_API_KEY", "DATAFORSYNINGEN_TOKEN", "EMO_BRUGERNAVN", "EMO_ADGANGSKODE"] as const) {
      const v = env[k];
      if (v) vars[k] = v;
    }
    this.envVars = vars;
  }
}

const IKKE_FUNDET = () => new Response("Not found", { status: 404 });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const token = env.BYG_MCP_HTTP_TOKEN ?? "";
    if (token.length < 32) {
      return new Response("Serveren er ikke konfigureret (BYG_MCP_HTTP_TOKEN mangler).", { status: 503 });
    }
    const { pathname } = new URL(request.url);
    const sti = `/mcp/${token}`;
    if (pathname !== sti && pathname !== `${sti}/`) return IKKE_FUNDET();

    // Én navngiven instans: serveren er uden sessioner, så alle kald kan gå til samme container.
    return getContainer(env.BYG_MCP, "byg-mcp").fetch(request);
  },
};
