"""Render the Power BI page backgrounds (1920x1080 PNG) for the Shell report.
Static text is baked in (page title, navigation labels, KPI labels, chart titles, architecture, footer).
Visuals in Power BI have titles and backgrounds OFF and sit on top of these cards.
Layout grid is the same as the Roche report (portfolio consistency)."""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE / "backgrounds"; OUT.mkdir(parents=True, exist_ok=True)
b64 = lambda p: base64.b64encode((HERE / p).read_bytes()).decode()
LOGO = "data:image/png;base64," + b64("shell_logo.png")
FONTS = "".join(f"@font-face{{font-family:'Inter';font-weight:{w};src:url(data:font/woff2;base64,{b64(f'inter-latin-{w}-normal.woff2')}) format('woff2')}}"
                for w in (400, 500, 600, 700))

# Shell palette on a warm light theme (yellow is an accent/fill, never text on white)
T = dict(bg="#F7F7F5", panel="#FFFFFF", border="#E5E3DD", ink="#1D1D1B", ink2="#5E5E59", muted="#8E8D87",
         red="#DD1D21", yellow="#FBCE07", yellow_soft="#FFF5CC", red_soft="#FCE9E9", green="#1E8E5A")

KPI_X = [48, 357, 667, 976, 1285, 1595]; KPI_W = 277; KPI_Y = 180; KPI_H = 116
ROW2_Y, ROW2_H = 316, 350
ROW3_Y, ROW3_H = 686, 334
TWO = [(48, 900), (972, 900)]
THREE = [(48, 592), (664, 592), (1280, 592)]
NAV = ["Home", "Overview", "Mobility", "Upstream &amp; Gas", "Energy Transition", "Data Pipeline"]
NAV_W, NAV_H, NAV_GAP, NAV_Y = 136, 40, 8, 30
NAV_X0 = 1920 - 48 - 47 - 28 - (len(NAV) * NAV_W + (len(NAV) - 1) * NAV_GAP)
SLICER_X = [48, 290, 532, 774]; SLICER_Y = 124; SLICER_W = 226

FOOTER = ("Developed by <b>João Paúra</b> | Data Engineering &amp; BI portfolio project | "
          "Fictitious data generated in Python, processed in Microsoft Fabric | "
          "Independent project, not affiliated with or endorsed by Shell plc")
FOOTER_R = "linkedin.com/in/joaopaura | github.com/joaopaura"

CSS = f"""{FONTS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1920px;height:1080px;background:{T['bg']};font-family:'Inter',sans-serif;color:{T['ink']};position:relative;overflow:hidden}}
.abs{{position:absolute}}
.title{{left:48px;top:24px;font-size:30px;font-weight:700;letter-spacing:-0.3px}}
.title span{{color:{T['red']}}}
.sub{{left:48px;top:68px;font-size:15px;color:{T['ink2']};width:880px;line-height:1.35;white-space:nowrap}}
.nav{{height:{NAV_H}px;width:{NAV_W}px;border-radius:8px;border:1px solid {T['border']};background:#fff;
      font-size:14px;font-weight:600;display:flex;align-items:center;justify-content:center;color:{T['ink']}}}
.nav.on{{background:{T['red']};border-color:{T['red']};color:#fff}}
.slabel{{font-size:12px;font-weight:600;color:{T['ink2']};text-transform:uppercase;letter-spacing:.6px}}
.card{{background:{T['panel']};border:1px solid {T['border']};border-radius:12px;box-shadow:0 1px 2px rgba(29,29,27,.05)}}
.kpi .l{{position:absolute;left:20px;top:16px;font-size:13px;font-weight:600;color:{T['ink2']}}}
.kpi .bar{{position:absolute;left:0;top:16px;width:4px;height:20px;border-radius:0 3px 3px 0;background:{T['yellow']}}}
.panel .h{{position:absolute;left:24px;top:18px;font-size:17px;font-weight:700}}
.panel .s{{position:absolute;left:24px;top:44px;font-size:12.5px;color:{T['ink2']}}}
.footer{{left:48px;top:1044px;font-size:12px;color:{T['muted']}}}
.footer b{{color:{T['ink2']};font-weight:700}}
.footr{{right:48px;top:1044px;font-size:12px;color:{T['ink2']};font-weight:600}}
.fline{{left:48px;top:1032px;width:1824px;height:1px;background:{T['border']}}}
.stripe{{left:0;top:0;width:1920px;height:6px;background:linear-gradient(90deg,{T['red']} 0 50%,{T['yellow']} 50% 100%)}}
"""


def base(inner: str) -> str:
    return (f"<html><head><style>{CSS}</style></head><body><div class='abs stripe'></div>{inner}"
            f"<div class='abs fline'></div><div class='abs footer'>{FOOTER}</div>"
            f"<div class='abs footr'>{FOOTER_R}</div></body></html>")


def nav(active: int) -> str:
    html = ""
    for i, name in enumerate(NAV):
        x = NAV_X0 + i * (NAV_W + NAV_GAP)
        html += f"<div class='abs nav{' on' if i == active else ''}' style='left:{x}px;top:{NAV_Y}px'>{name}</div>"
    return html + f"<img class='abs' src='{LOGO}' style='right:48px;top:20px;height:58px'>"


def page(p: dict) -> str:
    h = f"<div class='abs title'>{p['title']}</div><div class='abs sub'>{p['sub']}</div>" + nav(p["nav"])
    for x, label in zip(SLICER_X, p["slicers"]):
        h += f"<div class='abs slabel' style='left:{x}px;top:{SLICER_Y - 18}px'>{label}</div>"
    h += f"<div class='abs slabel' style='left:1622px;top:{SLICER_Y - 18}px'>Data as of</div>"
    for x, label in zip(KPI_X, p["kpis"]):
        h += (f"<div class='abs card kpi' style='left:{x}px;top:{KPI_Y}px;width:{KPI_W}px;height:{KPI_H}px'>"
              f"<div class='bar'></div><div class='l'>{label}</div></div>")
    for (x, y, w, hh, title, sub, extra) in p["panels"]:
        h += (f"<div class='abs card panel' style='left:{x}px;top:{y}px;width:{w}px;height:{hh}px'>"
              f"<div class='h'>{title}</div><div class='s'>{sub}</div>{extra}</div>")
    return base(h)


def arch() -> str:
    box = ("display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;"
           "border-radius:10px;font-size:13px;font-weight:600;padding:8px;line-height:1.3")

    def b(x, y, w, hh, t, s, fill, color=T["ink"]):
        return (f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{hh}px;{box};background:{fill};color:{color}'>"
                f"{t}<span style='font-size:11px;font-weight:500;opacity:.85;margin-top:3px'>{s}</span></div>")

    def arrow(x, y, w):
        return (f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:2px;background:#A9A79F'></div>"
                f"<div class='abs' style='left:{x + w - 7}px;top:{y - 4}px;width:0;height:0;border-left:8px solid #A9A79F;"
                f"border-top:5px solid transparent;border-bottom:5px solid transparent'></div>")
    W, G = 146, 26
    X = [24 + i * (W + G) for i in range(7)]
    s = ""
    s += b(X[0], 84, W, 172, "Source files", "Python generator<br>23 dirty CSVs<br>4.46M rows", "#F1F0EC")
    s += b(X[1], 84, W, 172, "Lakehouse", "OneLake Files<br>landing zone<br>raw/*", T["yellow_soft"])
    s += b(X[2], 84, W, 172, "Pipeline", "Lookup + ForEach<br>metadata-driven<br>Copy activity", T["yellow_soft"])
    s += b(X[3], 84, W, 172, "Bronze", "SQL Database<br>NVARCHAR landing<br>+ source file", "#F1F0EC")
    s += b(X[4], 84, W, 172, "Silver", "T-SQL procedures<br>parse, validate,<br>dedup, MERGE", T["red_soft"])
    s += b(X[5], 84, W, 172, "Gold", "Star schema<br>6 dims, 8 facts<br>1 transaction", T["red_soft"])
    s += b(X[6], 84, 106, 172, "Power BI", "Import mode<br>6 pages", T["red"], "#FFFFFF")
    for i in range(6):
        s += arrow(X[i] + W, 170, G)
    s += b(24, 272, 1160, 44, "etl.run_log | etl.rejected_rows (JSON) | etl.dq_results (32 checks) | Fabric Git integration | GitHub", "", "#F7F7F5")
    return s


PAGES = {
    "02_overview": dict(
        nav=1, title="Executive Overview <span>|</span> Group performance",
        sub="Revenue, EBITDA, production, fuel sales and emissions across five business segments, 2020 to 2025 | USD",
        slicers=["Year", "Region", "Segment", ""],
        kpis=["Revenue", "EBITDA", "EBITDA margin", "Production (kboe/d)", "Fuel volume sold", "Scope 1+2 emissions"],
        panels=[(TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H, "Revenue and EBITDA margin", "USD bn by segment per year, EBITDA margin on the right axis", ""),
                (TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H, "Revenue mix by segment", "Share of revenue in the selected period", ""),
                (TWO[0][0], ROW3_Y, TWO[0][1], ROW3_H, "EBITDA by country", "Top 10 countries, USD bn, selected period", ""),
                (TWO[1][0], ROW3_Y, TWO[1][1], ROW3_H, "Targets scorecard", "Selected year actuals against business targets", "")]),
    "03_mobility": dict(
        nav=2, title="Mobility <span>|</span> Retail network",
        sub="Daily fuel, convenience and car wash sales at 400 Shell-branded sites in 12 markets | USD, million litres",
        slicers=["Year", "Region", "Country", "Site format"],
        kpis=["Fuel volume", "Fuel revenue", "Non-fuel revenue", "Margin per litre", "Active sites", "Transactions"],
        panels=[(TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H, "Fuel volume trend", "Million litres per month, current vs prior year", ""),
                (TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H, "Site network", "Sites by gross margin | bubble size = fuel volume", ""),
                (THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H, "Gross margin by product", "Fuel vs non-fuel, USD m", ""),
                (THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H, "Fuel volume by country", "Million litres and change vs prior year", ""),
                (THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H, "Top 10 sites", "Gross margin in the selected period", "")]),
    "04_upstream": dict(
        nav=3, title="Upstream &amp; Integrated Gas <span>|</span> Production",
        sub="Monthly production of 19 oil and gas fields and 6 LNG plants, asset downtime and LNG sales by destination",
        slicers=["Year", "Segment", "Asset type", "Country"],
        kpis=["Production (kboe/d)", "Production vs plan", "Operating cost per boe", "Asset uptime", "LNG sold", "Spot LNG share"],
        panels=[(TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H, "Production vs plan", "Thousand barrels of oil equivalent per day, actual vs plan", ""),
                (TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H, "Production by asset", "kboe/d in the selected period and variance vs plan", ""),
                (THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H, "Downtime by cause", "Hours per year, planned vs unplanned", ""),
                (THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H, "LNG sales by destination", "Million tonnes, long-term vs spot", ""),
                (THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H, "LNG price realisation", "USD per MMBtu, long-term vs spot", "")]),
    "05_energy_transition": dict(
        nav=4, title="Energy Transition <span>|</span> EV charging and emissions",
        sub="EV charging rollout, low-carbon revenue and greenhouse gas emissions against 2030 targets",
        slicers=["Year", "Region", "Country", ""],
        kpis=["EV charge points", "Charging sessions", "Energy delivered", "EV charging revenue", "Low-carbon revenue share", "Scope 1+2 vs 2020"],
        panels=[(TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H, "EV charging growth", "Charging sessions and MWh delivered per month", ""),
                (TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H, "Scope 1+2 emissions vs target", "MtCO2e per year and path to the 2030 target (50% vs 2016)", ""),
                (THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H, "Emissions by scope", "MtCO2e in the selected period", ""),
                (THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H, "EV charge points by country", "Installed points and share of EV hubs", ""),
                (THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H, "Low-carbon revenue share", "Share of group revenue per year vs target", "")]),
    "06_data_pipeline": dict(
        nav=5, title="Data Pipeline &amp; Quality <span>|</span> Microsoft Fabric",
        sub="Dirty CSV files loaded by a Fabric pipeline into a SQL database and cleaned in T-SQL across bronze, silver and gold",
        slicers=["Run date", "Layer", "", ""],
        kpis=["Pipeline runs", "Rows landed (bronze)", "Rows rejected", "Reject rate", "Data quality checks passed", "Last run duration"],
        panels=[(TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H, "Rows by table and layer", "Rows read, loaded and rejected per step, latest run", ""),
                (TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H, "Rejected rows by reason", "Silver validation rules, latest run", ""),
                (48, ROW3_Y, 1208, ROW3_H, "Architecture", "End-to-end flow on Microsoft Fabric", arch()),
                (THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H, "Data quality checks", "Expected vs actual, latest run", "")]),
}


def cover() -> str:
    h = f"<img class='abs' src='{LOGO}' style='left:1430px;top:44px;height:230px'>"
    h += (f"<div class='abs' style='left:48px;top:180px;font-size:14px;font-weight:700;color:{T['red']};letter-spacing:1.4px'>"
          "PORTFOLIO PROJECT | ENERGY DATA ENGINEERING</div>")
    h += "<div class='abs' style='left:48px;top:212px;font-size:60px;font-weight:700;letter-spacing:-1.2px;line-height:1.05'>Shell Energy<br>Analytics Platform</div>"
    h += (f"<div class='abs' style='left:48px;top:360px;width:1040px;font-size:19px;color:{T['ink2']};line-height:1.5'>"
          "End-to-end SQL and BI project on Microsoft Fabric: dirty operational files are loaded by a pipeline, "
          "cleaned with T&#8209;SQL into a star schema and analysed across retail, upstream, LNG, EV charging and emissions.</div>")
    for i, label in enumerate(["Raw rows processed", "Rows rejected and logged", "Data quality checks passed"]):
        x = 48 + i * 364
        h += (f"<div class='abs card kpi' style='left:{x}px;top:500px;width:340px;height:140px'>"
              f"<div class='bar'></div><div class='l'>{label}</div></div>")
    chips = ["Microsoft Fabric", "Data Factory pipeline", "Fabric SQL Database", "T-SQL", "Lakehouse", "Python", "DAX", "Power BI"]
    x = 48
    for c in chips:
        w = 28 + len(c) * 9
        h += (f"<div class='abs' style='left:{x}px;top:690px;height:36px;width:{w}px;border-radius:18px;background:{T['yellow_soft']};"
              f"color:{T['ink']};font-size:14px;font-weight:600;display:flex;align-items:center;justify-content:center'>{c}</div>")
        x += w + 10
    facts = [("4.46M", "raw rows landed from 23 CSV files"), ("20", "stored procedures and 3 parsing functions"),
             ("$0.00", "revenue difference silver vs gold"), ("Daily", "scheduled Fabric pipeline")]
    for i, (big, small) in enumerate(facts):
        x = 48 + i * 262
        h += (f"<div class='abs' style='left:{x}px;top:770px;width:240px'><div style='font-size:30px;font-weight:700;color:{T['ink']}'>{big}</div>"
              f"<div style='font-size:13.5px;color:{T['ink2']};margin-top:4px'>{small}</div></div>")
    cards = [("Executive Overview", "Revenue, EBITDA, production, fuel and emissions vs targets"),
             ("Mobility", "Fuel and convenience sales, margin per litre and site network"),
             ("Upstream &amp; Gas", "Production vs plan, asset downtime and LNG sales"),
             ("Energy Transition", "EV charging rollout, low-carbon revenue and emissions"),
             ("Data Pipeline", "Runs, rejected rows by reason and data quality checks")]
    for i, (name, desc) in enumerate(cards):
        x = 1180 + (i % 2) * 358; y = 300 + (i // 2) * 170
        h += (f"<div class='abs card' style='left:{x}px;top:{y}px;width:334px;height:150px'>"
              f"<div class='abs' style='left:24px;top:20px;width:36px;height:4px;border-radius:2px;background:{T['yellow']}'></div>"
              f"<div class='abs' style='left:24px;top:36px;font-size:21px;font-weight:700'>{name}</div>"
              f"<div class='abs' style='left:24px;top:70px;width:286px;font-size:13.5px;color:{T['ink2']};line-height:1.45'>{desc}</div>"
              f"<div class='abs' style='left:24px;top:116px;font-size:14px;font-weight:700;color:{T['red']}'>Open page &#8594;</div></div>")
    h += (f"<div class='abs' style='left:1538px;top:640px;width:334px;font-size:12.5px;color:{T['muted']};line-height:1.5'>"
          "All figures are fictitious and generated for portfolio purposes. They do not represent Shell plc reporting. "
          "The Shell logo is used only to identify the case study.</div>")
    return base(h)


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1920, "height": 1080})
        docs = {"01_home": cover(), **{k: page(v) for k, v in PAGES.items()}}
        for name, html in docs.items():
            pg.set_content(html); pg.wait_for_timeout(400)
            pg.screenshot(path=str(OUT / f"{name}.png"))
            print("rendered", name)
        browser.close()
