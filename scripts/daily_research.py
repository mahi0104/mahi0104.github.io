#!/usr/bin/env python3
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

def pick_for_date(d):
    # cycle through topics, skipping 0 already published on 2026-08-21
    idx = d.toordinal() % len(TOPICS)
    if TOPICS[idx][0] == "elevation-heat-island":
        idx = 1
    return TOPICS[idx]

def main():
    d = datetime.date.today()
    if len(sys.argv) > 1:
        d = datetime.date.fromisoformat(sys.argv[1])
    slug_base, title, kpi_line = pick_for_date(d)
    slug = f"{d.isoformat()}-{slug_base}"
    out = pathlib.Path(f"research/{slug}.html")
    if out.exists():
        print(f"Already exists {out}")
        pathlib.Path("linkedin_post.txt").write_text(open("linkedin_post.txt", encoding="utf-8").read() if pathlib.Path("linkedin_post.txt").exists() else title, encoding="utf-8")
        return
    base = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Replace title and h1
    num = (d - datetime.date(2026,8,21)).days + 1
    # Update <title>
    base = re.sub(r"<title>.*?</title>", f"<title>{title} \u2014 Daily Research #{num:02d} | Mahesh Pentu</title>", base)
    base = base.replace("Daily Research \u00b7 #01 \u00b7 21 Aug 2026", f"Daily Research \u00b7 #{num:02d} \u00b7 {d.strftime('%d %b %Y')}")
    # Replace H1 (elevation drives...)
    base = re.sub(r"<h1>.*?</h1>", f"<h1>{title}</h1>", base, count=1)
    # Update canonical
    base = base.replace("research/2026-08-21-elevation-heat-island.html", f"research/{slug}.html")
    # Update KPI line in comment area if present
    # Inject subtitle tweak
    base = base.replace("-0.41\u00b0C per 100m (OLS R\u00b2=0.75", kpi_line)
    out.write_text(base, encoding="utf-8")
    linkedin = f"Daily Research #{num:02d} \u2014 {title}\n\n{kpi_line}\n\nReproducible pipeline + sample data on the site.\n\nRead the full drop:\nhttps://mahi0104.github.io/research/{slug}.html\n\n#SpatialRegression #DataAnalysis #Campania #Python #Reproducible"
    pathlib.Path("linkedin_post.txt").write_text(linkedin, encoding="utf-8")
    print(f"Generated {out} #{num} - {title}")

if __name__ == "__main__":
    main()
