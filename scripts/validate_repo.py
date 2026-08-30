#!/usr/bin/env python3
from pathlib import Path
import re, sys

errors = []
root = Path(__file__).resolve().parents[1]

for p in (root / 'layouts').rglob('*.html'):
    text = p.read_text(encoding='utf-8')
    # Ignore CSS/JS bodies; only lint the Hugo/HTML template area.
    template_text = re.sub(r'<script\b[^>]*>.*?</script>', '', text, flags=re.S | re.I)
    template_text = re.sub(r'<style\b[^>]*>.*?</style>', '', template_text, flags=re.S | re.I)
    bad_patterns = [
        r'(?<!\{)\{\s*\$',
        r'(?<!\{)\{\s*(?:range|with|if|else|end)\b',
    ]
    for pattern in bad_patterns:
        hits = re.findall(pattern, template_text)
        if hits:
            errors.append(f'{p.relative_to(root)}: possível ação Hugo com chave simples.')
            break
    if template_text.count('{{') != template_text.count('}}'):
        errors.append(f'{p.relative_to(root)}: aberturas e fechamentos de ações Hugo não conferem.')

projects = root / 'content' / 'projects'
required = ['status:', 'status_slug:', 'tags:', 'filtros:', 'periodo:']
if not projects.exists():
    errors.append('content/projects não existe.')
else:
    for p in projects.glob('*.md'):
        if p.name == '_index.md':
            continue
        text = p.read_text(encoding='utf-8')
        for key in required:
            if key not in text:
                errors.append(f'{p.relative_to(root)}: campo obrigatório ausente: {key}')

workflow = (root / '.github' / 'workflows' / 'deploy.yml').read_text(encoding='utf-8')
if 'hugo-version: "latest"' in workflow or "hugo-version: 'latest'" in workflow:
    errors.append('deploy.yml não deve usar Hugo latest; fixe uma versão compatível.')

if errors:
    print('VALIDAÇÃO FALHOU')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print('Validação estrutural local: OK')
