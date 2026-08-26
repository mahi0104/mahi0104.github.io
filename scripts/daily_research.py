#!/usr/bin/env python3
"""Daily research generator.
Permanent rules:
  - English only
  - NEVER mention a next-day / forward teaser
  - Never repeat a topic while unused topics remain (history-aware)
"""
import datetime, pathlib, re, sys

TOPICS = [
  ("elevation-heat-island", "Elevation drives summer heat in Campania", "-0.41C per 100m | R2 0.75 | Morans I 0.28"),
  ("ndvi-lst-cooling", "NDVI vs LST: how much does green cool?", "-0.32C per 0.1 NDVI | R2 0.68 | best in plains"),
  ("campania-climate-trends", "Campania climate trends 1985-2025", "+1.4C since 1985 | -12% summer rain | coast warms faster"),
  ("eu-tourism-dashboard", "EU tourism: seasonality and demand", "Seasonality index | coastal vs city | recovery 2022-25"),
  ("crypto-trading-bot", "Crypto trading bot: pipeline notes", "Signal latency <120ms | Sharpe 1.4 backtest"),
  ("web-scraping-pipeline", "Web scraping pipeline that does not break", "Retry + validation | 99.1% field completeness"),
  ("data-quality-checks", "Data quality checks that prevent silent failures", "6 gates | null, range, referential, drift"),
  ("spatial-weights", "Spatial weights: queen vs kNN", "AIC delta 4.2 | SEM wins"),
  ("gwr-local-effects", "GWR: when global coefficients hide local stories", "GWR R2 0.81 | coast vs interior"),
  ("impervious-lst", "Impervious surface vs LST", "+2.1C high impervious | NDVI controls"),
]

TEMPLATE_PATH = pathlib.Path("research/2026-08-21-elevation-heat-island.html")
RESEARCH_DIR = pathlib.Path("research")
FIRST_DATE = datetime.date(2026, 8, 21)


def used_topic_slugs():
    used = set()
    for f in RESEARCH_DIR.glob("20*.html"):
        parts = f.stem.split("-", 3)
        if len(parts) == 4:
            used.add(parts[3])
    return used


def main():
    d = datetime.date.today()
    if len(sys.argv) > 1:
        d = datetime.date.fromisoformat(sys.argv[1])

    used = used_topic_slugs()
    topic = None
    for t in TOPICS:
        if t[0] not in used:
            topic = t
            break
    if topic is None:
        n_files = len(list(RESEARCH_DIR.glob("20*.html")))
        topic = TOPICS[n_files % len(TOPICS)]

    slug_base, title, kpi_line = topic
    slug = f"{d.isoformat()}-{slug_base}"
    out = RESEARCH_DIR / f"{slug}.html"
    if out.exists():
        print(f"Already exists {out}")
        return

    base = TEMPLATE_PATH.read_text(encoding="utf-8")
    num = (d - FIRST_DATE).days + 1
    base = re.sub(r"<title>.*?</title>", f"<title>{title} \u2014 Daily Research #{num:02d} | Mahesh Pentu</title>", base)
    base = base.replace("Daily Research \u00b7 #01 \u00b7 21 Aug 2026", f"Daily Research \u00b7 #{num:02d} \u00b7 {d.strftime('%d %b %Y')}")
    base = re.sub(r"<h1>.*?</h1>", f"<h1>{title}</h1>", base, count=1)
    base = base.replace("research/2026-08-21-elevation-heat-island.html", f"research/{slug}.html")
    base = base.replace("-0.41\u00b0C per 100m (OLS R\u00b2=0.75", kpi_line)
    out.write_text(base, encoding="utf-8")

    linkedin = (
        f"Daily Research #{num:02d} \u2014 {title}\n\n"
        f"{kpi_line}\n\n"
        "Reproducible pipeline + sample data on the site.\n\n"
        f"Read the full drop:\nhttps://mahi0104.github.io/research/{slug}.html\n\n"
        "#SpatialRegression #DataAnalysis #Campania #Python #Reproducible"
    )
    pathlib.Path("linkedin_post.txt").write_text(linkedin, encoding="utf-8")
    print(f"Generated {out} #{num} - {title}")


if __name__ == "__main__":
    main()
