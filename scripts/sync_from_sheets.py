#!/usr/bin/env python3
"""
Sincroniza Google Sheets públicos com o conteúdo Hugo.

Fonte:
- 07 - Atualizações Hugo
- 08 - Projetos Hugo
- 09 - Grupos Infra

Comportamento seguro:
1. baixa e valida AS TRÊS abas antes de alterar content/;
2. se alguma aba falhar, o script encerra sem apagar o conteúdo existente;
3. somente linhas com Publicar? = SIM são publicadas.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "sheets.json"

REQUIRED = {
    "projects": ["Slug", "Título", "Status", "Modalidades (;)", "Publicar? (SIM/NÃO)"],
    "groups": ["Slug", "Título", "Tipo", "Publicar? (SIM/NÃO)"],
    "updates": ["Data", "Título", "Categoria", "Status", "Publicar? (SIM/NÃO)", "Slug"],
}

UPDATE_IMAGE_FALLBACKS = {
    "inauguracao-laims-2026": "images/updates/laims-2026.svg",
    "vai-e-vem-ipameri-2025": "images/updates/vai-e-vem-2025.svg",
    "trainee-cmoc-2024": "images/updates/trainee-cmoc-2024.svg",
    "estagio-escritorio-catalao-2022": "images/updates/estagio-escritorio-2022.svg",
    "estagio-orcamento-2022": "images/updates/estagio-orcamento-2022.svg",
    "estagio-obra-almoxarifado-2022": "images/updates/estagio-obra-2022.svg",
}

def norm_text(value: object) -> str:
    return str(value or "").strip()

def ascii_slug(value: object) -> str:
    text = unicodedata.normalize("NFD", norm_text(value))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text

def is_yes(value: object) -> bool:
    return norm_text(value).upper() in {"SIM", "S", "YES", "TRUE", "1"}

def split_multi(value: object) -> list[str]:
    text = norm_text(value)
    if not text:
        return []
    sep = ";" if ";" in text else ","
    return [x.strip() for x in text.split(sep) if x.strip()]

def q(value: object) -> str:
    """JSON string is valid YAML scalar syntax."""
    return json.dumps(norm_text(value), ensure_ascii=False)

def qlist(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)

def frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            lines.append(f"{key}: {qlist(value)}")
        else:
            lines.append(f"{key}: {q(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"

def published_url(name: str, config: dict) -> str:
    env_name = {
        "projects": "PROJECTS_CSV_URL",
        "groups": "GROUPS_CSV_URL",
        "updates": "UPDATES_CSV_URL",
    }[name]
    return os.environ.get(env_name, "").strip() or config[name]

def fetch_csv(url: str, attempts: int = 3) -> tuple[list[str], list[dict[str, str]]]:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AntoverSiteSync/1.0)",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=35) as response:
                raw = response.read()
            text = raw.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            headers = [norm_text(h) for h in (reader.fieldnames or [])]
            rows = []
            for raw_row in reader:
                row = {norm_text(k): norm_text(v) for k, v in raw_row.items() if k is not None}
                if any(row.values()):
                    rows.append(row)
            return headers, rows
        except Exception as exc:
            last = exc
            print(f"[tentativa {attempt}/{attempts}] falha ao baixar CSV: {exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Não foi possível baixar {url}: {last}")

def validate_source(name: str, headers: list[str], rows: list[dict[str, str]]) -> None:
    missing = [h for h in REQUIRED[name] if h not in headers]
    if missing:
        raise RuntimeError(f"Aba {name}: cabeçalhos obrigatórios ausentes: {missing}")
    if not rows:
        raise RuntimeError(f"Aba {name}: CSV retornou sem registros.")

def parse_date(value: object) -> str:
    text = norm_text(value)
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}", text):
        return f"{text}-01-01"
    raise ValueError(f"Data inválida: {text!r}")

def normalize_image(value: object) -> str:
    return norm_text(value).lstrip("/") if not norm_text(value).startswith(("http://", "https://")) else norm_text(value)

def project_filters(modalities: list[str]) -> list[str]:
    mapping = {
        "pd&i": "pdi",
        "pdi": "pdi",
        "ensino": "ensino",
        "pesquisa": "pesquisa",
        "extensão": "extensao",
        "extensao": "extensao",
        "social": "social",
    }
    out = []
    for item in modalities:
        key = unicodedata.normalize("NFD", item.lower())
        key_plain = "".join(c for c in key if unicodedata.category(c) != "Mn")
        original = item.lower()
        slug = mapping.get(original) or mapping.get(key_plain) or ascii_slug(item)
        if slug and slug not in out:
            out.append(slug)
    return out

def render_project(row: dict[str, str]) -> tuple[str, str]:
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = row.get("Título", "").strip()
    status = row.get("Status", "").strip() or "Concluído"
    status_slug = "ativo" if ascii_slug(status) == "ativo" else "concluido"
    modalities = split_multi(row.get("Modalidades (;)"))
    tags = split_multi(row.get("Tags (;)"))
    if not tags:
        tags = modalities.copy()

    y0 = norm_text(row.get("Ano Início"))
    y1 = norm_text(row.get("Ano Fim"))
    periodo = ""
    if y0 and y1:
        periodo = f"{y0}–{y1}"
    elif y0:
        periodo = f"{y0}–atual" if status_slug == "ativo" else y0

    year_for_date = y1 or y0 or str(datetime.now().year)
    date = f"{year_for_date}-01-01" if re.fullmatch(r"\d{4}", year_for_date) else datetime.now().strftime("%Y-%m-%d")

    image = normalize_image(row.get("Imagem Capa 16:9 (1600x900)"))
    summary = norm_text(row.get("Resumo Card / Modal"))
    content = norm_text(row.get("Conteúdo Detalhado (Markdown)")) or summary

    fm = {
        "title": title,
        "date": date,
        "draft": False,
        "description": summary,
        "image": image,
        "status": status,
        "status_slug": status_slug,
        "periodo": periodo,
        "modalidades": modalities,
        "filtros": project_filters(modalities),
        "tags": tags,
        "parceiro_principal": norm_text(row.get("Parceiro Principal")),
        "outros_parceiros": norm_text(row.get("Outros Parceiros")),
        "local": norm_text(row.get("Local / Município")),
        "resultados": norm_text(row.get("Resultados / Impactos")),
        "link_externo": norm_text(row.get("Link Externo / Relatório")),
        "image_alt": norm_text(row.get("Texto Alternativo da Imagem")),
        "ordem": int(row["Ordem"]) if norm_text(row.get("Ordem")).isdigit() else None,
    }

    details = [content]
    extra = []
    if fm["parceiro_principal"]:
        extra.append(f"**Parceiro principal:** {fm['parceiro_principal']}")
    if fm["outros_parceiros"]:
        extra.append(f"**Outros parceiros:** {fm['outros_parceiros']}")
    if fm["local"]:
        extra.append(f"**Local:** {fm['local']}")
    if fm["resultados"]:
        extra.append(f"**Resultados / impactos:** {fm['resultados']}")
    if fm["link_externo"]:
        extra.append(f"[Relatório, matéria ou página relacionada]({fm['link_externo']})")
    if extra:
        details.extend(["", "### Informações do projeto", "", "  \n".join(extra)])

    return slug, frontmatter(fm) + "\n" + "\n".join(details).strip() + "\n"

def render_group(row: dict[str, str]) -> tuple[str, str]:
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = norm_text(row.get("Título"))
    image = normalize_image(row.get("Ícone / Logo 1:1 (800x800 ou SVG)"))
    cover = normalize_image(row.get("Imagem Capa 16:9 (1600x900)"))
    tags = split_multi(row.get("Tags (;)"))
    summary = norm_text(row.get("Resumo Card / Modal"))
    content = norm_text(row.get("Conteúdo Detalhado (Markdown)")) or summary
    fm = {
        "title": title,
        "date": f"{datetime.now().year}-01-01",
        "draft": False,
        "description": summary,
        "image": image,
        "cover": cover,
        "tipo": norm_text(row.get("Tipo")),
        "ordem": int(row["Ordem"]) if norm_text(row.get("Ordem")).isdigit() else 999,
        "tags": tags,
        "link_externo": norm_text(row.get("Link Externo")),
    }
    body = content
    if fm["link_externo"]:
        body += f"\n\n[Visitar página institucional]({fm['link_externo']})"
    return slug, frontmatter(fm) + "\n" + body.strip() + "\n"

def render_update(row: dict[str, str]) -> tuple[str, str]:
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = norm_text(row.get("Título"))
    date = parse_date(row.get("Data"))
    tags = split_multi(row.get("Tags"))
    image = normalize_image(row.get("Imagem (URL pública)"))
    if not image:
        image = UPDATE_IMAGE_FALLBACKS.get(slug, "")
    summary = norm_text(row.get("Resumo"))
    content = norm_text(row.get("Conteúdo")) or summary
    category = norm_text(row.get("Categoria"))
    fm = {
        "title": title,
        "date": date,
        "draft": False,
        "description": summary,
        "categories": [category] if category else [],
        "tags": tags,
        "image": image,
        "image_alt": norm_text(row.get("Texto Alternativo da Imagem")),
        "status": norm_text(row.get("Status")),
        "source": norm_text(row.get("Link/Fonte")),
        "cta_url": norm_text(row.get("Link CTA")),
        "cta_text": norm_text(row.get("Texto CTA")),
    }
    body = content
    if fm["cta_url"]:
        label = fm["cta_text"] or "Saiba mais"
        body += f"\n\n[{label}]({fm['cta_url']})"
    if fm["source"]:
        body += f"\n\nFonte: {fm['source']}"
    return slug, frontmatter(fm) + "\n" + body.strip() + "\n"

def write_section(section: str, pages: list[tuple[str, str]], index_text: str) -> None:
    dest = ROOT / "content" / section
    dest.mkdir(parents=True, exist_ok=True)
    # Limpa SOMENTE depois que todas as fontes já foram baixadas e validadas.
    for p in dest.glob("*.md"):
        p.unlink()
    (dest / "_index.md").write_text(index_text, encoding="utf-8")
    for slug, content in pages:
        if not slug:
            continue
        (dest / f"{slug}.md").write_text(content, encoding="utf-8")

def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    datasets: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    # Baixa e valida tudo antes de tocar no conteúdo atual.
    for name in ("projects", "groups", "updates"):
        url = published_url(name, config)
        print(f"Baixando {name}: {url}")
        headers, rows = fetch_csv(url)
        validate_source(name, headers, rows)
        datasets[name] = (headers, rows)
        print(f"  {len(rows)} registros recebidos.")

    project_pages = [
        render_project(row)
        for row in datasets["projects"][1]
        if is_yes(row.get("Publicar? (SIM/NÃO)")) and norm_text(row.get("Título"))
    ]
    group_pages = [
        render_group(row)
        for row in datasets["groups"][1]
        if is_yes(row.get("Publicar? (SIM/NÃO)")) and norm_text(row.get("Título"))
    ]
    update_pages = [
        render_update(row)
        for row in datasets["updates"][1]
        if is_yes(row.get("Publicar? (SIM/NÃO)")) and norm_text(row.get("Título"))
    ]

    if not project_pages:
        raise RuntimeError("Nenhum projeto marcado para publicação.")
    if not group_pages:
        raise RuntimeError("Nenhum grupo/infraestrutura marcado para publicação.")
    if not update_pages:
        raise RuntimeError("Nenhuma atualização marcada para publicação.")

    write_section(
        "projects",
        project_pages,
        '---\ntitle: "Projetos e Parcerias"\ndescription: "Projetos de pesquisa, extensão, ensino, PD&I, ação social e parcerias institucionais."\n---\n',
    )
    write_section(
        "grupos",
        group_pages,
        '---\ntitle: "Grupos e Infraestrutura"\ndescription: "Grupos, centros, laboratórios e infraestrutura de pesquisa e extensão."\n---\n',
    )
    write_section(
        "blogs",
        update_pages,
        '---\ntitle: "Atualizações"\ndescription: "Notícias, vagas, eventos, projetos e publicações."\n---\n',
    )

    print("")
    print("Sincronização concluída:")
    print(f"  Projetos: {len(project_pages)}")
    print(f"  Grupos/Infraestrutura: {len(group_pages)}")
    print(f"  Atualizações: {len(update_pages)}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## Sincronização da Planilha-Mãe\n\n")
            f.write(f"- Projetos: **{len(project_pages)}**\n")
            f.write(f"- Grupos/Infraestrutura: **{len(group_pages)}**\n")
            f.write(f"- Atualizações: **{len(update_pages)}**\n")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
