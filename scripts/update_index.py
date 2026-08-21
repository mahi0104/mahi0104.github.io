import pathlib, re, datetime
idx = pathlib.Path("research/index.html")
sm = pathlib.Path("sitemap.xml")
files = sorted([p for p in pathlib.Path("research").glob("*.html") if p.name != "index.html"], reverse=True)
# rebuild sitemap - add missing
if sm.exists():
    txt = sm.read_text(encoding="utf-8")
    for p in files:
        url = f"https://mahi0104.github.io/research/{p.name}"
        if url not in txt:
            txt = txt.replace("</urlset>", f"  <url><loc>{url}</loc><lastmod>{datetime.date.today().isoformat()}</lastmod><priority>0.9</priority></url>\n</urlset>")
    sm.write_text(txt, encoding="utf-8")
    print("sitemap updated")
# ensure archive lists all - naive: if card missing, append
html = idx.read_text(encoding="utf-8")
changed=False
for p in files:
    if p.name not in html:
        # create minimal card
        title = p.stem[11:].replace("-", " ").title()
        card = f'<a class="card" href="{p.name}"><div class="meta">{p.stem[:10]}</div><h3>{title}</h3><p style="color:var(--bone-dim);font-size:14px;margin:8px 0">Daily Research - {title}</p></a>\n'
        # insert before the last </div></main> approx
        if "</div></main>" in html:
            html = html.replace("</div></main>", card + "</div></main>", 1)
        else:
            html += card
        changed=True
if changed:
    idx.write_text(html, encoding="utf-8")
    print("index updated")
else:
    print("index already complete")
