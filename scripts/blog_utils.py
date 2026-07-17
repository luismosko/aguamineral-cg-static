#!/usr/bin/env python3
"""
blog_utils.py | v1.0.0
Utilitários compartilhados do blog do aguamineralcampogrande.com.br.

DEFAULT-DENY: só posts PUBLICADOS (robots "index") entram no índice, no
sitemap.xml e no llms.txt. Rascunhos (noindex) ficam fora de tudo.

Expõe: ROOT, MESES, MESES_ABBR, date_br, add_sitemap(slug),
       regenerar_listagem(), atualizar_llms().
"""
import os, re, json, datetime, html as _html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://aguamineralcampogrande.com.br"

MESES = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto',
         'setembro','outubro','novembro','dezembro']
MESES_ABBR = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
              7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}

AUTO_INI = "<!-- AUTO-INICIO -->"
AUTO_FIM = "<!-- AUTO-FIM -->"


def date_br(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} de {MESES_ABBR[d.month]}. de {d.year}"


# ── extrair metadados de um post gerado/curado ───────────────────────────────
def _meta_do_post(path):
    h = open(path, encoding="utf-8").read()
    # só publicados
    rob = re.search(r'<meta name="robots" content="([^"]*)"', h)
    if rob and "noindex" in rob.group(1):
        return None
    def g(pat, default=""):
        m = re.search(pat, h, re.S)
        return m.group(1).strip() if m else default
    title = g(r'<h1>(.*?)</h1>') or g(r'<title>(.*?)</title>').split("—")[0].strip()
    title = re.sub(r'<[^>]+>', '', title)
    desc  = g(r'<meta name="description" content="(.*?)"')
    emoji = g(r'<span class="emoji">(.*?)</span>') or "💧"
    cat   = g(r'<span class="cat-badge">(.*?)</span>') or "Água & Saúde"
    read  = g(r'⏱️\s*([^<·]+?)\s*(?:de leitura)?</span>') or "4 min"
    read  = read.replace("de leitura", "").strip()
    # data: preferir datePublished do JSON-LD
    date = g(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})')
    if not date:
        date = datetime.date.today().isoformat()
    return dict(title=title, desc=desc, emoji=emoji, cat=cat, read=read, date=date)


def _listar_posts():
    """Retorna [(slug, meta)] de posts publicados, ordenado por data desc."""
    blog = os.path.join(ROOT, "blog")
    out = []
    for slug in os.listdir(blog):
        idx = os.path.join(blog, slug, "index.html")
        if slug == "index.html" or not os.path.isfile(idx):
            continue
        m = _meta_do_post(idx)
        if m:
            out.append((slug, m))
    out.sort(key=lambda x: x[1]["date"], reverse=True)
    return out


def _card(slug, m):
    return (f'      <a class="blog-card" href="/blog/{slug}/">\n'
            f'        <div class="thumb">{m["emoji"]}</div>\n'
            f'        <div class="card-body">\n'
            f'          <span class="cat-badge">{_html.escape(m["cat"])}</span>\n'
            f'          <h2>{_html.escape(m["title"])}</h2>\n'
            f'          <p>{_html.escape(m["desc"])}</p>\n'
            f'          <div class="card-meta"><span>{date_br(m["date"])} · {m["read"]}</span>'
            f'<span class="read-more">Ler →</span></div>\n'
            f'        </div>\n'
            f'      </a>')


def regenerar_listagem():
    """Reconstrói o grid de cards do /blog/index.html a partir das pastas.
    Idempotente. Instala marcadores AUTO na 1ª vez."""
    idx_path = os.path.join(ROOT, "blog", "index.html")
    idx = open(idx_path, encoding="utf-8").read()

    if AUTO_INI not in idx:
        # instala marcadores no lugar do conteúdo do .blog-grid
        m = re.search(r'(<div class="blog-grid">)(.*?)(\n  </div>)', idx, re.S)
        if not m:
            raise SystemExit("blog/index.html: não achei <div class=\"blog-grid\">")
        idx = idx[:m.start(2)] + f'\n{AUTO_INI}\n{AUTO_FIM}\n  ' + idx[m.end(2):]
        open(idx_path, "w", encoding="utf-8").write(idx)

    cards = "\n".join(_card(s, m) for s, m in _listar_posts())
    novo = re.sub(re.escape(AUTO_INI) + r".*?" + re.escape(AUTO_FIM),
                  f"{AUTO_INI}\n{cards}\n{AUTO_FIM}", idx, flags=re.S)
    open(idx_path, "w", encoding="utf-8").write(novo)


def add_sitemap(slug):
    """Adiciona a URL do post ao sitemap.xml (antes de </urlset>) se não existir."""
    sm_path = os.path.join(ROOT, "sitemap.xml")
    sm = open(sm_path, encoding="utf-8").read()
    loc = f"{BASE}/blog/{slug}/"
    if loc not in sm:
        hoje = datetime.date.today().isoformat()
        entry = (f'  <url><loc>{loc}</loc><lastmod>{hoje}</lastmod>'
                 f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n</urlset>')
        sm = sm.replace("</urlset>", entry, 1)
        open(sm_path, "w", encoding="utf-8").write(sm)


def atualizar_llms(slug, title, desc):
    """Adiciona o post na seção ## Blog do llms.txt (se ainda não estiver)."""
    p = os.path.join(ROOT, "llms.txt")
    if not os.path.exists(p):
        return
    txt = open(p, encoding="utf-8").read()
    linha = f"- [{title}]({BASE}/blog/{slug}/): {desc}"
    if f"/blog/{slug}/)" in txt:
        return
    if "## Blog" in txt:
        txt = txt.rstrip() + "\n" + linha + "\n"
    else:
        txt = txt.rstrip() + "\n\n## Blog\n" + linha + "\n"
    open(p, "w", encoding="utf-8").write(txt)
