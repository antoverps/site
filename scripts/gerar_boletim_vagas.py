#!/usr/bin/env python3
"""
Gera o Boletim de Vagas de Engenharia Civil.

Fonte das vagas: aba "11 - Boletim Vagas" da planilha-mãe (CSV publicado, chave "vagas"
em data/sheets.json; só linhas com Publicar? = SIM). Se a chave não existir ou a leitura
falhar, usa data/vagas.json. Seções e dicas vêm sempre do JSON.

Saídas:
- content/blogs/boletim-vagas-engenharia-civil.md   (post Hugo, preservado pelo sync: manual: true)
- static/images/updates/boletim-vagas.svg            (capa do post)
- <pasta instagram>/AAAA-MM-DD/                      (post.html, slide-*.html, *.png, legenda.txt)

Uso:
  python scripts/gerar_boletim_vagas.py [--instagram-dir PASTA] [--sem-png]

PNG: renderizado com Microsoft Edge/Chrome headless, se disponível.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vagas.json"
POST = ROOT / "content" / "blogs" / "boletim-vagas-engenharia-civil.md"
COVER = ROOT / "static" / "images" / "updates" / "boletim-vagas.svg"
SITE_URL = "https://antoverps.github.io/site/blogs/boletim-vagas-engenharia-civil/"
DEFAULT_IG = Path(r"C:\Users\sap-09\OneDrive\Fazendo\SITE-APS\instagram-vagas")

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

e = html.escape


def br(d: str) -> str:
    """AAAA-MM-DD -> DD/MM/AAAA (mantém textos livres como estão)."""
    try:
        y, m, dd = d.split("-")
        return f"{dd}/{m}/{y}"
    except Exception:
        return d


def extenso(d: str) -> str:
    y, m, dd = (int(x) for x in d.split("-"))
    return f"{dd} de {MESES[m - 1]} de {y}"


def total(data: dict) -> int:
    return sum(len(s["vagas"]) for s in data["secoes"])


# --------------------------------------------------------------------------- post

def card(v: dict) -> str:
    rows = []
    for label, key in [("Local", "local"), ("Nível / público", "nivel"), ("Regime / salário", "regime"),
                       ("Publicação", "publicada"), ("Inscrições até", "prazo")]:
        if v.get(key):
            val = br(v[key]) if key in ("publicada", "prazo") else v[key]
            rows.append(f'<div><dt>{label}</dt><dd>{e(val)}</dd></div>')
    body = ""
    if v.get("descricao"):
        body += f'<p><strong>Atividades:</strong> {e(v["descricao"])}</p>'
    if v.get("requisitos"):
        body += f'<p><strong>Requisitos:</strong> {e(v["requisitos"])}</p>'
    btns = []
    if v.get("link"):
        btns.append(f'<a class="vg-btn" href="{e(v["link"])}" target="_blank" rel="noopener">{e(v.get("link_label", "Candidatar-se"))} ↗</a>')
    if v.get("email"):
        btns.append(f'<a class="vg-btn vg-btn-alt" href="mailto:{e(v["email"])}">{e(v["email"])}</a>')
    badge = f'<span class="vg-badge">{e(v["destaque"])}</span>' if v.get("destaque") else ""
    nota = f'<p class="vg-note">{e(v["verificacao"])}</p>' if v.get("verificacao") else ""
    return f"""<article class="vg-card">
<header>{badge}<h4>{e(v["cargo"])}</h4><p class="vg-emp">{e(v["empresa"])}</p></header>
<dl class="vg-meta">{''.join(rows)}</dl>
{body}
<div class="vg-actions">{''.join(btns)}</div>
{nota}
</article>"""


CSS = """<style>
.vg-intro{padding:1rem 1.2rem;border-left:4px solid #087944;background:rgba(8,121,68,.07);border-radius:.5rem;margin-bottom:1.5rem}
.vg-summary{display:flex;flex-wrap:wrap;gap:.6rem;margin:0 0 2rem}
.vg-summary a{flex:1 1 180px;text-decoration:none!important;color:inherit!important;border:1px solid rgba(128,128,128,.3);border-radius:.7rem;padding:.8rem 1rem}
.vg-summary b{display:block;font-size:1.6rem;color:#087944;line-height:1.1}
.vg-sec{margin-top:2.5rem}
.vg-sec>p{opacity:.8}
.vg-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;margin-top:1rem}
.vg-card{border:1px solid rgba(128,128,128,.28);border-radius:.8rem;padding:1.1rem 1.2rem;display:flex;flex-direction:column;gap:.5rem;line-height:1.55}
.vg-card h4{margin:.2rem 0 0;font-size:1.08rem}
.vg-emp{margin:0;color:#087944;font-weight:600}
.vg-badge{display:inline-block;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;background:#087944;color:#fff;border-radius:999px;padding:.12rem .55rem}
.vg-meta{display:grid;grid-template-columns:1fr 1fr;gap:.35rem .8rem;margin:.3rem 0;font-size:.86rem}
.vg-meta dt{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;opacity:.6;font-weight:600}
.vg-meta dd{margin:0}
.vg-card p{margin:0;font-size:.92rem}
.vg-actions{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:auto;padding-top:.4rem}
.vg-btn{background:#087944;color:#fff!important;text-decoration:none!important;border-radius:.45rem;padding:.42rem .8rem;font-size:.86rem;font-weight:600}
.vg-btn-alt{background:transparent;color:#087944!important;border:1px solid #087944;word-break:break-all}
.vg-note{font-size:.75rem!important;opacity:.6}
.vg-tips li{margin-bottom:.4rem}
.vg-follow{padding:1.2rem 1.4rem;border:1px solid rgba(8,121,68,.35);border-radius:.8rem;background:rgba(8,121,68,.06)}
@media (max-width:560px){.vg-meta{grid-template-columns:1fr}}
</style>"""


def render_post(data: dict) -> str:
    d = data["atualizado_em"]
    n = total(data)
    resumo = "".join(
        f'<a href="#{s["id"]}"><b>{len(s["vagas"])}</b>{e(s["titulo"])}</a>' for s in data["secoes"]
    )
    secs = []
    for s in data["secoes"]:
        cards = "\n".join(card(v) for v in s["vagas"])
        secs.append(f"""<section class="vg-sec" id="{s['id']}">
<h2>{e(s['titulo'])}</h2>
<p>{e(s.get('subtitulo', ''))}</p>
<div class="vg-grid">
{cards}
</div>
</section>""")
    dicas = "".join(f"<li>{e(t)}</li>" for t in data.get("dicas", []))
    fm = f"""---
title: "Boletim de Vagas — Engenharia Civil"
date: {d}
lastmod: {d}
draft: false
manual: true
description: "{n} vagas ativas em Engenharia Civil — Catalão, Goiás e Brasil. Atualizado toda segunda-feira (última: {br(d)})."
categories:
- Vaga
tags:
- vagas
- engenharia civil
- trainee
- egressos
- Catalão
image: images/updates/boletim-vagas.svg
image_alt: "Boletim de Vagas de Engenharia Civil — {br(d)}"
---
"""
    return fm + f"""
{CSS}

<div class="vg-intro">
<strong>Atualizado em {extenso(d)}.</strong> Levantamento semanal (toda segunda-feira) de vagas em Engenharia Civil, de todos os níveis — obras, saneamento, recursos hídricos, ambiental, barragens, geotecnia e infraestrutura. Prioridade: <strong>Catalão</strong>, depois <strong>Goiás</strong> e <strong>Brasil</strong>. Cada link foi aberto e conferido na data acima; ainda assim, confirme prazo e requisitos na página oficial antes de se candidatar.
</div>

<div class="vg-summary">{resumo}</div>

{''.join(secs)}

<section class="vg-sec vg-follow">
<h2>Acompanhe o boletim toda segunda-feira</h2>
<p>A lista é atualizada semanalmente aqui no site e divulgada no Instagram. Siga o perfil para ver as novas vagas assim que saírem e salve esta página nos favoritos.</p>
<div class="vg-actions"><a class="vg-btn" href="https://www.instagram.com/antoverps/" target="_blank" rel="noopener">Seguir @antoverps no Instagram ↗</a><a class="vg-btn vg-btn-alt" href="{SITE_URL}">Link desta página</a></div>
</section>

<section class="vg-sec">
<h2>Dicas rápidas de candidatura</h2>
<ul class="vg-tips">{dicas}</ul>
</section>

<p class="vg-note" style="margin-top:2rem">Encontrou uma vaga encerrada ou quer divulgar uma oportunidade? Fale comigo pelos contatos do site.</p>
"""


# --------------------------------------------------------------------------- capa SVG

def render_cover(data: dict) -> str:
    n = total(data)
    d = br(data["atualizado_em"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#071b13"/><stop offset="1" stop-color="#087944"/></linearGradient></defs><rect width="1200" height="675" fill="url(#g)"/><g fill="none" stroke="#84d6a7" stroke-width="5" opacity=".55"><path d="M720 520V250l110-70 110 70v270"/><path d="M830 180V110M770 520V330h120v190M690 520h300"/><path d="M1010 520V300h70v220M1010 360h70M1010 420h70"/></g><g fill="#fff" opacity=".9"><circle cx="830" cy="110" r="12"/></g><text x="75" y="200" fill="#bce6cd" font-family="Arial" font-size="28" letter-spacing="3">BOLETIM SEMANAL</text><text x="72" y="290" fill="#fff" font-family="Arial" font-size="78" font-weight="700">Vagas</text><text x="72" y="370" fill="#fff" font-family="Arial" font-size="58" font-weight="700">Engenharia Civil</text><text x="75" y="430" fill="#bce6cd" font-family="Arial" font-size="29">Todos os níveis · Catalão · Goiás · Brasil</text><rect x="75" y="480" width="300" height="64" rx="32" fill="#84d6a7"/><text x="225" y="522" fill="#071b13" font-family="Arial" font-size="28" font-weight="700" text-anchor="middle">{n} vagas ativas</text><text x="78" y="610" fill="#9bcbb0" font-family="Arial" font-size="22">Atualizado em {d} · Prof. Antover · UFCAT</text></svg>
"""


# --------------------------------------------------------------------------- Instagram

IG_BASE = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden}
body{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(150deg,#071b13 0%,#0a3d25 55%,#087944 100%);color:#fff;padding:80px 78px;display:flex;flex-direction:column;position:relative}
.kick{font-size:28px;letter-spacing:6px;color:#84d6a7;font-weight:600}
h1{font-size:118px;line-height:1;font-weight:800;margin-top:22px}
h2{font-size:64px;line-height:1.05;font-weight:800;margin-top:10px}
.sub{font-size:34px;color:#bce6cd;margin-top:22px;line-height:1.3}
.pill{display:inline-block;background:#84d6a7;color:#071b13;font-weight:800;font-size:40px;border-radius:999px;padding:16px 38px;margin-top:40px}
.list{margin-top:44px;display:flex;flex-direction:column;gap:18px}
.item{background:rgba(255,255,255,.08);border:1px solid rgba(132,214,167,.35);border-radius:22px;padding:22px 28px}
.item b{display:block;font-size:31px;line-height:1.2}
.item span{display:block;font-size:24px;color:#bce6cd;margin-top:6px}
.foot{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;font-size:25px;color:#9bcbb0;border-top:2px solid rgba(132,214,167,.3);padding-top:26px}
.foot strong{color:#fff;font-size:30px}
.deco{position:absolute;right:-60px;top:-60px;width:420px;height:420px;border:6px solid rgba(132,214,167,.18);border-radius:50%}
.deco2{position:absolute;right:60px;top:60px;width:180px;height:180px;border:6px solid rgba(132,214,167,.25);border-radius:50%}
.count{position:absolute;right:78px;top:80px;font-size:26px;color:#84d6a7}
</style></head><body><div class="deco"></div><div class="deco2"></div>{body}</body></html>"""


def ig_item(v: dict) -> str:
    extra = v.get("ig_resumo") or v.get("local", "")
    if v.get("prazo"):
        extra += f" · até {br(v['prazo'])}"
    return f'<div class="item"><b>{e(v["cargo"])} — {e(v["empresa"])}</b><span>{e(extra)}</span></div>'


def foot(d: str) -> str:
    return (f'<div class="foot"><div>Links e requisitos completos:<br><strong>link na bio · antoverps.github.io/site</strong></div>'
            f'<div style="text-align:right">Atualizado<br><strong>{br(d)}</strong></div></div>')


def render_ig(data: dict) -> dict[str, str]:
    d = data["atualizado_em"]
    n = total(data)
    secs = data["secoes"]
    pages: dict[str, str] = {}
    # Capa (imagem principal)
    destaques = [v for s in secs for v in s["vagas"] if v.get("destaque")][:4]
    if len(destaques) < 4:
        destaques += [v for s in secs for v in s["vagas"] if v not in destaques][: 4 - len(destaques)]
    body = (f'<div class="kick">BOLETIM SEMANAL DE VAGAS</div>'
            f'<h1>Engenharia<br>Civil</h1>'
            f'<div class="sub">Todos os níveis · obras, saneamento,<br>hídricos, geotecnia e infraestrutura</div>'
            f'<div><span class="pill">{n} vagas ativas</span></div>'
            f'<div class="list">{"".join(ig_item(v) for v in destaques)}</div>' + foot(d))
    pages["01-capa"] = IG_BASE.replace("{body}", body)
    # Um slide por seção (carrossel)
    for i, s in enumerate(secs, start=2):
        vs = s["vagas"]
        shown = vs[:6]
        more = f'<div class="sub" style="font-size:28px;margin-top:18px">+ {len(vs) - 6} vagas no site</div>' if len(vs) > 6 else ""
        body = (f'<div class="count">{i}/{len(secs) + 1}</div>'
                f'<div class="kick">VAGAS · {e(s.get("kick", s["titulo"]).upper())}</div>'
                f'<h2>{e(s["titulo"])}</h2>'
                f'<div class="list" style="margin-top:36px">{"".join(ig_item(v) for v in shown)}</div>{more}' + foot(d))
        pages[f"0{i}-{s['id']}"] = IG_BASE.replace("{body}", body)
    return pages


def render_caption(data: dict) -> str:
    d = data["atualizado_em"]
    n = total(data)
    lines = [
        f"🏗️ BOLETIM DE VAGAS | ENGENHARIA CIVIL — {br(d)}",
        "",
        f"Separei {n} vagas ATIVAS em Engenharia Civil, de todos os níveis — obras, saneamento, recursos hídricos, ambiental, geotecnia e infraestrutura. Todos os links foram conferidos hoje. 👇",
        "",
    ]
    icons = {"catalao": "📍", "goias": "🟢", "brasil": "🇧🇷"}
    tail = [
        "🔗 Descrição, requisitos e link de candidatura de cada vaga: LINK NA BIO (Atualizações → Boletim de Vagas)",
        "",
        "📅 Toda segunda-feira tem boletim novo: siga @antoverps, ative as notificações e compartilhe com colegas da engenharia! 🏗️",
        "",
        "#engenhariacivil #vagas #vagasdeemprego #engenheirocivil #oportunidades #trainee #programadetrainee "
        "#catalao #catalaogo #goias #goiania #saneamento #recursoshidricos #geotecnia #construcaocivil #ufcat #egressos",
    ]

    def short(v: dict) -> str:
        emp = re.sub(r"\s*\(.*?\)", "", v["empresa"])
        prazo = f" · até {br(v['prazo'])[:5]}" if v.get("prazo") else ""
        return f"• {emp} — {v.get('ig_resumo') or v.get('local', '')}{prazo}"

    # Instagram aceita até 2.200 caracteres: reduz o nº de itens por seção até caber.
    for limit in (99, 8, 6, 5, 4, 3):
        body = []
        for s in data["secoes"]:
            body.append(f"{icons.get(s['id'], '•')} {s['titulo'].upper()} ({len(s['vagas'])})")
            body += [short(v) for v in s["vagas"][:limit]]
            if len(s["vagas"]) > limit:
                body.append(f"+ {len(s['vagas']) - limit} no site")
            body.append("")
        text = "\n".join(lines + body + tail) + "\n"
        if len(text) <= 2200:
            return text
    return text


def find_browser() -> str | None:
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
        if Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def to_png(browser: str, html_path: Path, png: Path) -> Path:
    """Renderiza o HTML em PNG. Em alguns ambientes (ex.: shells isolados) o Edge sai com
    código 0 sem gravar nada; nesse caso tenta de novo via PowerShell e, se ainda falhar, erro."""
    import tempfile
    png.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as prof:
        args = ["--headless=new", f"--user-data-dir={prof}", "--no-first-run", "--disable-gpu",
                "--hide-scrollbars", "--force-device-scale-factor=1", "--window-size=1080,1350",
                f"--screenshot={png}", html_path.resolve().as_uri()]
        subprocess.run([browser, *args], capture_output=True, timeout=90)
        if not png.exists() and shutil.which("powershell"):
            lista = ",".join("'" + a.replace("'", "''") + "'" for a in args)
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Start-Process -FilePath '{browser}' -ArgumentList @({lista}) -Wait"],
                           capture_output=True, timeout=120)
    if not png.exists() or png.stat().st_size < 10_000:
        raise RuntimeError(f"Falha ao gerar {png.name}: o navegador não gravou a imagem.")
    return png


# --------------------------------------------------------------------------- planilha

SHEETS = ROOT / "data" / "sheets.json"
SECAO_ID = {"catalao": "catalao", "goias": "goias", "brasil": "brasil"}
# prefixo do cabeçalho na aba "11 - Boletim Vagas" -> chave interna
COLS = [("seção", "secao"), ("empresa", "empresa"), ("cargo", "cargo"), ("local", "local"),
        ("nível", "nivel"), ("regime", "regime"), ("publicação", "publicada"), ("prazo", "prazo"),
        ("atividades", "descricao"), ("requisitos", "requisitos"), ("link da vaga", "link"),
        ("texto do botão", "link_label"), ("e-mail", "email"), ("destaque", "destaque"),
        ("resumo instagram", "ig_resumo"), ("verificado em", "verificado"), ("origem", "origem"),
        ("publicar", "publicar"), ("ordem", "ordem")]


def _ascii(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def iso(d: str) -> str:
    """DD/MM/AAAA (ou D/M/AAAA) -> AAAA-MM-DD; vazio/inválido -> ''."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", d or "")
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", d or "")
    return m[0].strip() if m else ""


def load_from_sheet(base: dict, url: str) -> dict:
    """Substitui as vagas do JSON pelas linhas Publicar=SIM da aba 11 (CSV publicado)."""
    import csv
    import io
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise RuntimeError("CSV de vagas vazio")
    head = [h.strip().lower() for h in rows[0]]
    idx = {}
    for pref, key in COLS:
        for i, h in enumerate(head):
            if h.startswith(pref) and key not in idx:
                idx[key] = i
                break
    missing = {"secao", "empresa", "cargo", "publicar"} - idx.keys()
    if missing:
        raise RuntimeError(f"Colunas ausentes na aba de vagas: {missing}")
    secoes = {s["id"]: {**s, "vagas": []} for s in base["secoes"]}
    datas = []
    for r in rows[1:]:
        v = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
        if _ascii(v.get("publicar", "")) != "sim" or not v.get("cargo"):
            continue
        sid = SECAO_ID.get(_ascii(v["secao"]))
        if sid not in secoes:
            continue
        v["publicada"] = iso(v.get("publicada", ""))
        v["prazo"] = iso(v.get("prazo", ""))
        if v.get("verificado"):
            datas.append(iso(v["verificado"]))
            v["verificacao"] = f"Verificada em {v['verificado']}."
        try:
            v["_ordem"] = float(v.get("ordem") or 999)
        except ValueError:
            v["_ordem"] = 999.0
        secoes[sid]["vagas"].append({k: x for k, x in v.items() if x not in ("", None)})
    for s in secoes.values():
        s["vagas"].sort(key=lambda v: v["_ordem"])
    data = {**base, "secoes": list(secoes.values())}
    datas = [d for d in datas if d]
    if datas:
        data["atualizado_em"] = max(datas)
    return data


def load_data(usar_planilha: bool = True) -> dict:
    base = json.loads(DATA.read_text(encoding="utf-8"))
    url = ""
    if usar_planilha and SHEETS.exists():
        url = json.loads(SHEETS.read_text(encoding="utf-8")).get("vagas", "")
    if not url:
        return base
    try:
        data = load_from_sheet(base, url)
        print(f"Vagas lidas da planilha: {total(data)}")
        return data
    except Exception as exc:  # não derruba o deploy: usa o JSON do repositório
        print(f"AVISO: não foi possível ler a aba de vagas ({exc}); usando data/vagas.json.")
        return base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instagram-dir", default=str(DEFAULT_IG))
    ap.add_argument("--sem-png", action="store_true")
    ap.add_argument("--so-site", action="store_true", help="gera só post e capa (uso no GitHub Actions)")
    ap.add_argument("--sem-planilha", action="store_true", help="ignora a planilha e usa data/vagas.json")
    ap.add_argument("--csv", help="CSV local da aba 11 (exportado na hora), em vez do CSV publicado")
    args = ap.parse_args()

    if args.csv:
        data = load_from_sheet(json.loads(DATA.read_text(encoding="utf-8")), Path(args.csv).resolve().as_uri())
        print(f"Vagas lidas do CSV local: {total(data)}")
    else:
        data = load_data(not args.sem_planilha)
    POST.write_text(render_post(data), encoding="utf-8")
    COVER.write_text(render_cover(data), encoding="utf-8")
    print(f"Post: {POST.relative_to(ROOT)}\nCapa: {COVER.relative_to(ROOT)}")
    if args.so_site:
        print(f"Total de vagas: {total(data)}")
        return 0

    out = Path(args.instagram_dir) / data["atualizado_em"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "legenda.txt").write_text(render_caption(data), encoding="utf-8")
    browser = None if args.sem_png else find_browser()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:  # HTML de desenho fica fora da pasta de postagem
        for name, page in render_ig(data).items():
            hp = Path(tmp) / f"{name}.html"
            hp.write_text(page, encoding="utf-8")
            if browser:
                print("PNG:", to_png(browser, hp, out / f"{name}.png"))
            else:
                (out / f"{name}.html").write_text(page, encoding="utf-8")
    print(f"Instagram: {out}")
    print(f"Total de vagas: {total(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
