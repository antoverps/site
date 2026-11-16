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

# ---------------------------------------------------------------------------
# Idiomas: pt-br (padrão, pasta content/), en (content_en/) e es (content_es/).
# Colunas traduzidas na planilha: "Título EN", "Resumo EN", "Conteúdo EN (Markdown)" etc.
# Célula traduzida vazia => usa o texto em português.
# ---------------------------------------------------------------------------
LANGS = {"pt": "content", "en": "content_en", "es": "content_es"}

LABELS = {
    "pt": {"partner": "Parceiro principal", "others": "Outros parceiros", "local": "Local",
           "results": "Resultados / impactos", "report": "Relatório, matéria ou página relacionada",
           "info": "Informações do projeto", "visit": "Visitar página institucional",
           "more": "Saiba mais", "source": "Fonte", "present": "atual"},
    "en": {"partner": "Main partner", "others": "Other partners", "local": "Location",
           "results": "Results / impacts", "report": "Report, news story or related page",
           "info": "Project information", "visit": "Visit the institutional page",
           "more": "Learn more", "source": "Source", "present": "present"},
    "es": {"partner": "Socio principal", "others": "Otros socios", "local": "Ubicación",
           "results": "Resultados / impactos", "report": "Informe, noticia o página relacionada",
           "info": "Información del proyecto", "visit": "Visitar la página institucional",
           "more": "Más información", "source": "Fuente", "present": "actual"},
}

SECTION_INDEX = {
    "projects": {
        "pt": ("Projetos e Parcerias", "Projetos de pesquisa, extensão, ensino, PD&I, ação social e parcerias institucionais."),
        "en": ("Projects and Partnerships", "Research, outreach, teaching, R&D&I, social action projects and institutional partnerships."),
        "es": ("Proyectos y Alianzas", "Proyectos de investigación, extensión, enseñanza, I+D+i, acción social y alianzas institucionales."),
    },
    "grupos": {
        "pt": ("Grupos e Infraestrutura", "Grupos, centros, laboratórios e infraestrutura de pesquisa e extensão."),
        "en": ("Groups and Infrastructure", "Groups, centers, laboratories and research and outreach infrastructure."),
        "es": ("Grupos e Infraestructura", "Grupos, centros, laboratorios e infraestructura de investigación y extensión."),
    },
    "blogs": {
        "pt": ("Atualizações", "Notícias, vagas, eventos, projetos e publicações."),
        "en": ("News", "News, job openings, events, projects and publications."),
        "es": ("Novedades", "Noticias, vacantes, eventos, proyectos y publicaciones."),
    },
}

# Termos curtos (status, modalidades, tags, categorias, locais), traduzidos por dicionário.
# Chave em minúsculas. Termo sem tradução aparece como está na planilha.
TERMS = {
    "ativo": ("Ongoing", "En curso"), "concluído": ("Completed", "Concluido"), "concluido": ("Completed", "Concluido"),
    "ensino": ("Teaching", "Enseñanza"), "pesquisa": ("Research", "Investigación"), "extensão": ("Outreach", "Extensión"),
    "social": ("Social", "Social"), "pd&i": ("R&D&I", "I+D+i"),
    "mineração": ("mining", "minería"), "sustentabilidade": ("sustainability", "sostenibilidad"),
    "conservação de solo e água": ("soil and water conservation", "conservación de suelo y agua"),
    "planejamento urbano": ("urban planning", "planificación urbana"), "prefeitura": ("municipal government", "municipalidad"),
    "território": ("territory", "territorio"), "recursos hídricos": ("water resources", "recursos hídricos"),
    "uso do solo": ("land use", "uso del suelo"), "geotecnologias": ("geotechnologies", "geotecnologías"),
    "aloterita": ("alloterite", "aloterita"), "construção sustentável": ("sustainable construction", "construcción sostenible"),
    "concreto permeável": ("pervious concrete", "concreto permeable"), "ia": ("AI", "IA"),
    "efluentes": ("wastewater", "efluentes"), "tratamento": ("treatment", "tratamiento"),
    "biogás": ("biogas", "biogás"), "energia": ("energy", "energía"), "biomassa": ("biomass", "biomasa"),
    "rcc": ("CDW", "RCD"), "rcd": ("CDW", "RCD"), "evento": ("event", "evento"),
    "engenharia civil": ("civil engineering", "ingeniería civil"),
    "engenharia sustentável": ("Sustainable engineering", "Ingeniería sostenible"),
    "projetos aplicados": ("Applied projects", "Proyectos aplicados"),
    "inteligência artificial": ("Artificial intelligence", "Inteligencia artificial"),
    "modelagem": ("Modeling", "Modelación"), "simulação": ("Simulation", "Simulación"),
    "formação": ("Training", "Formación"), "engenharia": ("Engineering", "Ingeniería"),
    "escritório": ("Office", "Oficina"), "projetos": ("Projects", "Proyectos"),
    "infraestrutura": ("infrastructure", "infraestructura"),
    "diagnóstico ambiental": ("environmental assessment", "diagnóstico ambiental"),
    "notícia": ("News", "Noticia"), "projeto": ("Project", "Proyecto"), "vaga": ("Job opening", "Vacante"),
    "evento regional": ("Regional event", "Evento regional"),
}


def term(value: str, lang: str) -> str:
    if lang == "pt":
        return value
    hit = TERMS.get(value.strip().lower())
    return hit[0 if lang == "en" else 1] if hit else value


def pick(row: dict, base: str, translated: str, lang: str) -> str:
    """Coluna traduzida ("<nome> EN/ES") quando preenchida; senão, a coluna em português."""
    if lang != "pt":
        value = norm_text(row.get(translated.format(L=lang.upper())))
        if value:
            return value
    return norm_text(row.get(base))


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

def render_project(row: dict[str, str], lang: str = "pt") -> tuple[str, str]:
    L = LABELS[lang]
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = pick(row, "Título", "Título {L}", lang)
    status_pt = row.get("Status", "").strip() or "Concluído"
    status_slug = "ativo" if ascii_slug(status_pt) == "ativo" else "concluido"
    status = term(status_pt, lang)
    modalities = split_multi(row.get("Modalidades (;)"))
    tags = split_multi(row.get("Tags (;)"))
    if not tags:
        tags = modalities.copy()
    tags = [term(t, lang) for t in tags]

    y0 = norm_text(row.get("Ano Início"))
    y1 = norm_text(row.get("Ano Fim"))
    periodo = ""
    if y0 and y1:
        periodo = f"{y0}–{y1}"
    elif y0:
        periodo = f"{y0}–{L['present']}" if status_slug == "ativo" else y0

    # IMPORTANTE:
    # O campo `date` é usado internamente pelo Hugo para decidir se uma página
    # já pode ser publicada. Usar Ano Fim fazia projetos ativos com término
    # em 2027/2029/2031 serem tratados como conteúdo futuro e removidos do build.
    # Para projetos, a data técnica deve representar o início do projeto.
    year_for_date = y0 or str(datetime.now().year)
    date = f"{year_for_date}-01-01" if re.fullmatch(r"\d{4}", year_for_date) else datetime.now().strftime("%Y-%m-%d")

    image = normalize_image(row.get("Imagem Capa 16:9 (1600x900)"))
    summary = pick(row, "Resumo Card / Modal", "Resumo {L}", lang)
    content = pick(row, "Conteúdo Detalhado (Markdown)", "Conteúdo {L} (Markdown)", lang) or summary

    fm = {
        "title": title,
        "date": date,
        "draft": False,
        "description": summary,
        "image": image,
        "status": status,
        "status_slug": status_slug,
        "periodo": periodo,
        "modalidades": [term(m, lang) for m in modalities],
        "filtros": project_filters(modalities),
        "tags": tags,
        "parceiro_principal": norm_text(row.get("Parceiro Principal")),
        "outros_parceiros": norm_text(row.get("Outros Parceiros")),
        "local": term(norm_text(row.get("Local / Município")), lang),
        "resultados": norm_text(row.get("Resultados / Impactos")),
        "link_externo": norm_text(row.get("Link Externo / Relatório")),
        "image_alt": title if lang != "pt" else norm_text(row.get("Texto Alternativo da Imagem")),
        "ordem": int(row["Ordem"]) if norm_text(row.get("Ordem")).isdigit() else None,
    }

    details = [content]
    extra = []
    if fm["parceiro_principal"]:
        extra.append(f"**{L['partner']}:** {fm['parceiro_principal']}")
    if fm["outros_parceiros"]:
        extra.append(f"**{L['others']}:** {fm['outros_parceiros']}")
    if fm["local"]:
        extra.append(f"**{L['local']}:** {fm['local']}")
    if fm["resultados"]:
        extra.append(f"**{L['results']}:** {fm['resultados']}")
    if fm["link_externo"]:
        extra.append(f"[{L['report']}]({fm['link_externo']})")
    if extra:
        details.extend(["", f"### {L['info']}", "", "  \n".join(extra)])

    return slug, frontmatter(fm) + "\n" + "\n".join(details).strip() + "\n"

def render_group(row: dict[str, str], lang: str = "pt") -> tuple[str, str]:
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = norm_text(row.get("Título"))
    image = normalize_image(row.get("Ícone / Logo 1:1 (800x800 ou SVG)"))
    cover = normalize_image(row.get("Imagem Capa 16:9 (1600x900)"))
    tags = [term(t, lang) for t in split_multi(row.get("Tags (;)"))]
    summary = pick(row, "Resumo Card / Modal", "Resumo {L}", lang)
    content = pick(row, "Conteúdo Detalhado (Markdown)", "Conteúdo {L} (Markdown)", lang)
    if lang != "pt" and not norm_text(row.get(f"Conteúdo {lang.upper()} (Markdown)")) and norm_text(row.get(f"Resumo {lang.upper()}")):
        content = ""  # sem conteúdo traduzido: usa o resumo traduzido, não o texto longo em português
    content = content or summary
    fm = {
        "title": title,
        "date": f"{datetime.now().year}-01-01",
        "draft": False,
        "description": summary,
        "image": image,
        "cover": cover,
        "tipo": pick(row, "Tipo", "Tipo {L}", lang),
        "ordem": int(row["Ordem"]) if norm_text(row.get("Ordem")).isdigit() else 999,
        "tags": tags,
        "link_externo": norm_text(row.get("Link Externo")),
    }
    body = content
    if fm["link_externo"]:
        body += f"\n\n[{LABELS[lang]['visit']}]({fm['link_externo']})"
    return slug, frontmatter(fm) + "\n" + body.strip() + "\n"

def render_update(row: dict[str, str], lang: str = "pt") -> tuple[str, str]:
    slug = ascii_slug(row.get("Slug") or row.get("Título"))
    title = pick(row, "Título", "Título {L}", lang)
    date = parse_date(row.get("Data"))
    tags = [term(t, lang) for t in split_multi(row.get("Tags"))]
    image = normalize_image(row.get("Imagem (URL pública)"))
    if not image:
        image = UPDATE_IMAGE_FALLBACKS.get(slug, "")
    summary = pick(row, "Resumo", "Resumo {L}", lang)
    content = pick(row, "Conteúdo", "Conteúdo {L}", lang) or summary
    category = term(norm_text(row.get("Categoria")), lang)
    fm = {
        "title": title,
        "date": date,
        "draft": False,
        "description": summary,
        "categories": [category] if category else [],
        "tags": tags,
        "image": image,
        "image_alt": title if lang != "pt" else norm_text(row.get("Texto Alternativo da Imagem")),
        "status": norm_text(row.get("Status")),
        "source": norm_text(row.get("Link/Fonte")),
        "cta_url": norm_text(row.get("Link CTA")),
        "cta_text": norm_text(row.get("Texto CTA")),
    }
    body = content
    if fm["cta_url"]:
        label = fm["cta_text"] or LABELS[lang]["more"]
        body += f"\n\n[{label}]({fm['cta_url']})"
    if fm["source"]:
        body += f"\n\n{LABELS[lang]['source']}: {fm['source']}"
    return slug, frontmatter(fm) + "\n" + body.strip() + "\n"

def write_section(section: str, pages: list[tuple[str, str]], index_text: str, content_dir: str = "content") -> None:
    dest = ROOT / content_dir / section
    dest.mkdir(parents=True, exist_ok=True)
    # Limpa SOMENTE depois que todas as fontes já foram baixadas e validadas.
    # Preserva páginas mantidas fora da planilha (front matter com "manual: true"),
    # como o Boletim de Vagas atualizado semanalmente.
    for p in dest.glob("*.md"):
        head = p.read_text(encoding="utf-8").split("---", 2)
        if len(head) == 3 and re.search(r"^manual:\s*true\s*$", head[1], re.M):
            continue
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

    def published(name: str) -> list[dict[str, str]]:
        return [
            row for row in datasets[name][1]
            if is_yes(row.get("Publicar? (SIM/NÃO)")) and norm_text(row.get("Título"))
        ]

    project_pages = published("projects")
    group_pages = published("groups")
    update_pages = published("updates")

    if not project_pages:
        raise RuntimeError("Nenhum projeto marcado para publicação.")
    if not group_pages:
        raise RuntimeError("Nenhum grupo/infraestrutura marcado para publicação.")
    if not update_pages:
        raise RuntimeError("Nenhuma atualização marcada para publicação.")

    sections = [
        ("projects", render_project, project_pages),
        ("grupos", render_group, group_pages),
        ("blogs", render_update, update_pages),
    ]
    for lang, content_dir in LANGS.items():
        for section, render, rows in sections:
            pages = [render(row, lang) for row in rows]
            title, description = SECTION_INDEX[section][lang]
            index_text = f"---\ntitle: {q(title)}\ndescription: {q(description)}\n---\n"
            write_section(section, pages, index_text, content_dir)

    print("")
    print("Sincronização concluída:")
    print(f"  Projetos: {len(project_pages)}")
    print(f"  Grupos/Infraestrutura: {len(group_pages)}")
    print(f"  Atualizações: {len(update_pages)}")
    print(f"  Idiomas: {', '.join(LANGS)}")

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
