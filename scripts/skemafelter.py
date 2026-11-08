"""Vis felter (navn: type) for GraphQL-typer i et hentet Datafordeler-skema.
Brug: python scripts/skemafelter.py skema.graphql Type1 [Type2 ...]   ('?' lister typer)"""
import re, sys
txt = open(sys.argv[1], encoding="utf-8").read()
txt = re.sub(r'"""[\s\S]*?"""', "", txt)
txt = re.sub(r'"[^"\n]*"', "", txt)
if sys.argv[2] == "?":
    print(" ".join(sorted(set(re.findall(r"^type (\w+)", txt, re.M)) - {"Query"})))
    sys.exit()
for t in sys.argv[2:]:
    m = re.search(rf"^type {t} (?:implements \w+ )?\{{([\s\S]*?)^\}}", txt, re.M)
    if not m:
        print(f"## {t}: ikke fundet"); continue
    felter = [re.sub(r"\s*@\w+(\([^)]*\))?", "", l).strip() for l in m.group(1).splitlines() if l.strip()]
    felter = [f for f in felter if not f.startswith(("datafordeler", "forretnings", "registrering", "virkning", "id_namespace"))]
    print(f"## {t}\n  " + ", ".join(felter))
