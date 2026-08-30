#!/usr/bin/env python3
from pathlib import Path
import re, sys, yaml

errors = []
root = Path(__file__).resolve().parents[1]

for p in (root / "layouts").rglob("*.html"):
    text = p.read_text(encoding="utf-8")
    if 'partial "icon"' in text or "partial 'icon'" in text:
        errors.append(f'{p.relative_to(root)}: usa partial "icon", inexistente no Hugo Profile v4.06.')
    template_text = re.sub(r'<script\b[^>]*>.*?</script>', '', text, flags=re.S | re.I)
    template_text = re.sub(r'<style\b[^>]*>.*?</style>', '', template_text, flags=re.S | re.I)
    bad_patterns = [
        r'(?<!\{)\{\s*\$',
        r'(?<!\{)\{\s*(?:range|with|if|else|end)\b',
    ]
    for pattern in bad_patterns:
        if re.findall(pattern, template_text):
            errors.append(f'{p.relative_to(root)}: possível ação Hugo com chave simples.')
            break
    if template_text.count("{{") != template_text.count("}}"):
        errors.append(f'{p.relative_to(root)}: aberturas e fechamentos de ações Hugo não conferem.')

projects = root / "content" / "projects"
required_project = ["status:", "status_slug:", "tags:", "filtros:", "periodo:"]
if not projects.exists():
    errors.append("content/projects não existe.")
else:
    for p in projects.glob("*.md"):
        if p.name == "_index.md":
            continue
        text = p.read_text(encoding="utf-8")
        for key in required_project:
            if key not in text:
                errors.append(f'{p.relative_to(root)}: campo obrigatório ausente: {key}')

for section in ["projects", "blogs", "grupos"]:
    folder = root / "content" / section
    if folder.exists():
        for p in folder.glob("*.md"):
            if p.name == "_index.md":
                continue
            text = p.read_text(encoding="utf-8")
            if text.startswith("---"):
                try:
                    yaml.safe_load(text.split("---", 2)[1])
                except Exception as e:
                    errors.append(f'{p.relative_to(root)}: front matter YAML inválido: {e}')

workflow_path = root / ".github" / "workflows" / "deploy.yml"
if workflow_path.exists():
    workflow = workflow_path.read_text(encoding="utf-8")
    if 'hugo-version: "latest"' in workflow or "hugo-version: 'latest'" in workflow:
        errors.append("deploy.yml não deve usar Hugo latest; fixe uma versão compatível.")

if errors:
    print("VALIDAÇÃO FALHOU")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("Validação estrutural local: OK")
