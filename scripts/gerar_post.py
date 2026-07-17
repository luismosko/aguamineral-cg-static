#!/usr/bin/env python3
"""
gerar_post.py | v1.0.0
Gerador diário de posts do blog do aguamineralcampogrande.com.br.
Adaptado do sistema do Mosko Gás (mesma arquitetura, default-deny).

DEFAULT-DENY / SEGURANÇA (allowlist explícita):
  - Post NASCE como RASCUNHO (robots noindex, fora do sitemap/llms/índice).
    Só é publicado com PUBLICAR=1 (o cron passa PUBLICAR=1).
  - Preço NUNCA é inventado: vem de scripts/preco_config.json (fonte da verdade).
    Se um dia houver um Worker izGLP de preço, basta setar IZGLP_PRECO_URL.
  - Guard-rail de anti-temas: barra tema fora da allowlist (ex.: "como fazer água
    mineral caseira", pH de marca concorrente).
  - Link editorial pra money-page, FAQ e CTA são INJETADOS de forma determinística.

Uso:
    ANTHROPIC_API_KEY=sk-ant-xxx python3 scripts/gerar_post.py          # 1 rascunho
    ANTHROPIC_API_KEY=... PUBLICAR=1 python3 scripts/gerar_post.py      # já publica
    python3 scripts/gerar_post.py --dry-run                            # sem API (amostra)
"""
import os, re, sys, json, datetime, urllib.request, html as _html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blog_utils import regenerar_listagem, add_sitemap, atualizar_llms, ROOT, date_br  # noqa

API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL     = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5").strip()
PUBLICAR  = os.environ.get("PUBLICAR", "").strip() == "1"
IZGLP_URL = os.environ.get("IZGLP_PRECO_URL", "").strip()

WPP = "5567991310665"
WPP_MSG = "Ol%C3%A1%2C%20quero%20pedir%20%C3%A1gua%20mineral"
WPP_SVG = ('<svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099'
           '-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463'
           '-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347'
           '.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207'
           '-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04'
           ' 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262'
           '.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289'
           '.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg>')

# ── money-pages reais por categoria (allowlist de destino do link editorial) ──
MONEY = {
    "galao":    ("/galao-20-litros/",       "galão de água mineral 20 litros em Campo Grande"),
    "garrafao": ("/garrafao-5-litros/",     "garrafão de 5 litros em Campo Grande"),
    "gas":      ("/garrafa-1-5l-com-gas/",  "água mineral com gás em Campo Grande"),
    "empresas": ("/galao-20-litros/",       "água mineral para empresas em Campo Grande"),
    "geral":    ("/galao-20-litros/",       "galão de água mineral em Campo Grande"),
}
CAT_LABEL = {"galao": "Galão & Entrega", "garrafao": "Garrafão", "gas": "Água com Gás",
             "empresas": "Para Empresas", "geral": "Água & Saúde"}

# ── guard-rail: temas barrados (defense-in-depth) ────────────────────────────
ANTITEMAS = [
    r"como\s+(fazer|produzir|fabricar)\s+[aá]gua\s+mineral",
    r"[aá]gua\s+mineral\s+caseira", r"purificar\s+[aá]gua\s+em\s+casa",
    r"ph\s+da?\s+[aá]gua\s+mineral\s+(crystal|indai|bonafont|minalba|s[aã]o\s+louren)",
    r"marca\s+concorrente", r"destilar\s+[aá]gua",
]

BAIRROS = ("Carandá Bosque, Centro, Jardim dos Estados, Tiradentes, Aero Rancho, "
           "Mata do Jacinto, Universitário, Coophavila, Vila Rica, Chácara Cachoeira, "
           "Coronel Antonino e toda Campo Grande/MS")


def get_price():
    """Preço da verdade: IZGLP (se configurado) -> config. Nunca inventa."""
    if IZGLP_URL:
        try:
            with urllib.request.urlopen(IZGLP_URL, timeout=20) as r:
                d = json.loads(r.read().decode())
            return f'{float(d["refil"]):.2f}'.replace(".", ","), \
                   f'{float(d["vasilhame"]):.2f}'.replace(".", ","), "IZGLP"
        except Exception as e:
            print(f"  ! IZGLP indisponível ({e}); usando config", file=sys.stderr)
    cfg = os.path.join(ROOT, "scripts", "preco_config.json")
    if os.path.exists(cfg):
        d = json.load(open(cfg))
        return d["refil"], d["vasilhame"], "config"
    print("ERRO: sem preço (preco_config.json ausente).", file=sys.stderr)
    sys.exit(1)


def proximo_tema():
    fila = json.load(open(os.path.join(ROOT, "scripts", "fila_temas.json"), encoding="utf-8"))
    for t in fila:
        slug = t["slug"]
        if any(re.search(p, (t["tema"] + " " + slug).lower()) for p in ANTITEMAS):
            print(f"  ⨯ guard-rail barrou tema: {slug}", file=sys.stderr); continue
        if not os.path.isdir(os.path.join(ROOT, "blog", slug)):
            return t
    return None


SYSTEM = """Você é redator SEO local da Água Mineral Campo Grande — distribuidora de água mineral da marca Por do Sol em Campo Grande/MS. WhatsApp (67) 99131-0665. Rua Olímpio Klafke, 635 – Mata do Jacinto. Seg–Sáb 7h às 18h30. Mais de 150 avaliações 4,9★ no Google. Vende galão 20L (refil e com vasilhame), garrafão 5L, garrafas 500ml e 1,5L (com e sem gás), soda e copos, com entrega rápida.

Escreva um artigo de blog em pt-BR, tom claro e útil, para o tema dado. Regras OBRIGATÓRIAS:
- Foco em quem VAI COMPRAR/CONSUMIR água em Campo Grande. Nada de "como fazer água mineral caseira", nada de citar marca concorrente.
- NÃO invente preço. Se citar preço, use EXATAMENTE os valores fornecidos (refil/vasilhame).
- NÃO invente dados médicos, estatísticas ou estudos. Fale de forma geral e responsável; recomende procurar um profissional em temas de saúde.
- 1200 a 1800 palavras. Subtítulos <h2>/<h3>. Parágrafos curtos.
- OBRIGATÓRIO: inclua ao menos 1 elemento escaneável no corpo — uma tabela HTML (<table>) OU um checklist OU uma lista numerada. Prefira tabela quando houver comparação/faixas.
- Números SEMPRE comprometidos: dê a faixa concreta (ex.: '2 a 3 litros'), nunca só 'varia muito'.
- Mencione bairros de Campo Grande quando fizer sentido.

Responda SOMENTE com JSON válido (sem markdown, sem crases), no formato:
{"title":"...","meta_description":"... (máx 155 chars, com Campo Grande)","corpo_html":"<p>...</p><h2>...</h2>...","faq":[{"q":"...","a":"..."}, ...7+...]}
corpo_html = só o miolo (NÃO inclua <h1>, NÃO inclua a FAQ, NÃO inclua CTA — isso é injetado depois)."""


def chamar_claude(tema, cat, refil, vasilhame):
    body = json.dumps({
        "model": MODEL, "max_tokens": 8000, "system": SYSTEM,
        "messages": [{"role": "user", "content":
            f"TEMA: {tema}\nCATEGORIA: {cat}\nPREÇO GALÃO REFIL: R$ {refil}\n"
            f"PREÇO GALÃO COM VASILHAME: R$ {vasilhame}\nBAIRROS: {BAIRROS}\nGere o artigo."}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read().decode())
    txt = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    if "{" in txt and "}" in txt:
        txt = txt[txt.index("{"):txt.rindex("}") + 1]
    return json.loads(txt)


def faq_html(faq):
    itens = "\n".join(
        f'        <div class="faq-item"><button class="faq-btn">{_html.escape(f["q"])}</button>'
        f'<div class="faq-content"><p>{f["a"]}</p></div></div>' for f in faq)
    return f'      <h2>Perguntas frequentes</h2>\n      <div class="faq-list">\n{itens}\n      </div>'


def render(art, slug, cat, emoji, refil, vasilhame, tpl):
    title = art["title"].strip()
    desc = art["meta_description"].strip()
    money_url, money_ancora = MONEY[cat]
    hoje = datetime.date.today()
    data_iso = hoje.isoformat()
    data_pt = date_br(data_iso)
    words = len(re.sub(r"<[^>]+>", " ", art["corpo_html"]).split())
    readmin = max(2, round(words / 200))

    editorial = (f'      <p>Se você já quer resolver agora, veja nossa página de '
                 f'<a href="{money_url}">{money_ancora}</a> — pedido rápido pelo WhatsApp.</p>')
    cta = (f'    <div class="article-cta">\n'
           f'      <p>Precisa de água mineral em Campo Grande? A gente entrega rápido.</p>\n'
           f'      <p style="font-size:15px;font-weight:500;color:var(--cinza-sub);margin-bottom:18px">'
           f'Galão 20L a partir de <strong>R$ {refil}</strong> (refil) · '
           f'<strong>R$ {vasilhame}</strong> com vasilhame</p>\n'
           f'      <a class="btn-wpp" href="https://wa.me/{WPP}?text={WPP_MSG}" target="_blank" '
           f'rel="noopener">{WPP_SVG} Pedir pelo WhatsApp</a>\n    </div>')

    article = f'''<article>
    <div class="article-hero">
      <span class="cat-badge">{CAT_LABEL[cat]}</span>
      <span class="emoji">{emoji}</span>
      <h1>{_html.escape(title)}</h1>
      <div class="article-meta"><span>📅 {data_pt}</span><span>⏱️ {readmin} min de leitura</span><span>💧 Água Mineral Campo Grande</span></div>
    </div>
    <div class="article-body">
{art["corpo_html"]}
{editorial}
{faq_html(art["faq"])}
    </div>
{cta}
    <div class="article-nav"><a href="/blog/">← Voltar para o Blog</a></div>
  </article>'''

    url = f"https://aguamineralcampogrande.com.br/blog/{slug}/"
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "BlogPosting", "headline": title, "description": desc,
         "image": "https://aguamineralcampogrande.com.br/images/logo.webp",
         "datePublished": data_iso, "dateModified": data_iso, "inLanguage": "pt-BR",
         "author": {"@type": "Organization", "name": "Água Mineral Campo Grande"},
         "publisher": {"@type": "Organization", "name": "Água Mineral Campo Grande",
                       "logo": {"@type": "ImageObject", "url": "https://aguamineralcampogrande.com.br/images/logo.webp"}},
         "mainEntityOfPage": {"@type": "WebPage", "@id": url}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://aguamineralcampogrande.com.br/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": "https://aguamineralcampogrande.com.br/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url}]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", f["a"])}}
            for f in art["faq"]]}]}
    schema_block = '<script type="application/ld+json">\n' + json.dumps(schema, ensure_ascii=False) + "\n</script>"

    robots = "index, follow" if PUBLICAR else "noindex, nofollow"
    return (tpl
        .replace("{{SLUG}}", slug).replace("{{SEO_TITLE}}", _html.escape(title))
        .replace("{{META_DESC}}", desc.replace('"', "'"))
        .replace("{{ROBOTS}}", robots).replace("{{TITLE}}", _html.escape(title))
        .replace("{{ARTICLE}}", article).replace("{{SCHEMA}}", schema_block)), title, desc


def main():
    dry = "--dry-run" in sys.argv
    refil, vasilhame, fonte = get_price()
    print(f"preço: refil R$ {refil} / vasilhame R$ {vasilhame} (fonte: {fonte})")
    tema = proximo_tema()
    if not tema:
        print("fila vazia (todos os temas já gerados)."); return
    print(f"tema: {tema['slug']} [{tema['categoria']}]")

    if dry:
        art = json.load(open(os.path.join(ROOT, "scripts", "amostra_dry_run.json"), encoding="utf-8"))
    else:
        if not API_KEY:
            print("ERRO: defina ANTHROPIC_API_KEY (ou use --dry-run).", file=sys.stderr); sys.exit(1)
        art = chamar_claude(tema["tema"], tema["categoria"], refil, vasilhame)

    tpl = open(os.path.join(ROOT, "scripts", "template-post.html"), encoding="utf-8").read()
    slug = tema["slug"]
    out, title, desc = render(art, slug, tema["categoria"], tema["emoji"], refil, vasilhame, tpl)
    d = os.path.join(ROOT, "blog", slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(out)

    if PUBLICAR:
        add_sitemap(slug)
        atualizar_llms(slug, title, desc)
    regenerar_listagem()
    estado = "PUBLICADO" if PUBLICAR else "RASCUNHO (noindex)"
    print(f"✓ /blog/{slug}/ gerado como {estado}")

    gho = os.environ.get("GITHUB_OUTPUT")
    if gho and PUBLICAR:
        with open(gho, "a", encoding="utf-8") as g:
            g.write(f"slug={slug}\n")
            g.write(f"title={title}\n")
            g.write(f"url=https://aguamineralcampogrande.com.br/blog/{slug}/\n")
            g.write("published=1\n")


if __name__ == "__main__":
    main()
