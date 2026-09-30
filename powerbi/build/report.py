"""Builds the Shell report pages (PBIR): backgrounds, navigation, slicers, KPI cards and charts."""
import hashlib, json, shutil
from pathlib import Path

OUT = Path("/home/claude/out/Shell_Energy_Analytics.Report")
BG = Path("/home/claude/shell_pbi/backgrounds")
THEME = Path("/home/claude/shell_pbi/shell_theme.json")
SCHEMA_V = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.12.0/schema.json"
RED, YEL, GREY, GREEN, TEAL, ORANGE, LGREY = "#DD1D21", "#FBCE07", "#5E5E59", "#1E8E5A", "#0097A9", "#EB8705", "#B9B7B0"

hid = lambda *k: hashlib.sha1("|".join(map(str, k)).encode()).hexdigest()[:20]
lit = lambda v: {"expr": {"Literal": {"Value": v}}}
col_ = lambda c: {"solid": {"color": lit(f"'{c}'")}}
colm = lambda m: {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": m}}}}}
C = lambda e, p: {"Column": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}}
Me = lambda p: {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": p}}
F = lambda f: C(*f.split(".", 1)) if not f.startswith("[") else Me(f[1:-1])   # "dim_date.year" or "[Revenue]"


def qref(f):
    return f"_Measures.{f[1:-1]}" if f.startswith("[") else f


def proj(f, active=False):
    p = {"field": F(f), "queryRef": qref(f), "nativeQueryRef": qref(f).split(".", 1)[1]}
    if active:
        p["active"] = True
    return p


def scope_sel(f, value):
    e, p = f.split(".", 1)
    return {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": C(e, p), "Right": {"Literal": {"Value": value}}}}}]}


class Page:
    def __init__(self, key, name, bg):
        self.key, self.name, self.bg, self.visuals, self.inter, self.z = key, name, bg, [], [], 1000
        self.id = hid("page", key)

    def add(self, kind, x, y, w, h, visual, name=None):
        self.z += 100
        vid = name or hid(self.key, kind, x, y, len(self.visuals))
        visual.setdefault("visualContainerObjects", {}).setdefault("title", [{"properties": {"show": lit("false"), "text": lit(f"'{kind}'")}}])
        visual["drillFilterOtherVisuals"] = True
        fc = visual.pop("filterConfig", None)
        c = {"$schema": SCHEMA_V, "name": vid,
             "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": len(self.visuals)},
             "visual": visual}
        if fc:
            c["filterConfig"] = fc
        self.visuals.append(c)
        return vid


# ------------------------------------------------------------------ visual builders
def card(pg, x, y, w, h, m, ref=None, ref_title="vs PY", ref_colour=None, value_colour=None, size=None):
    mm = f"_Measures.{m}"
    obj = {"label": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
           "outline": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
           "divider": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
           "fillCustom": [{"properties": {"show": lit("false")}}],
           "value": [{"properties": {"labelDisplayUnits": lit("1D")}, "selector": {"metadata": mm}}]}
    if size:
        obj["value"].append({"properties": {"fontSize": lit(f"{size}D")}, "selector": {"id": "default"}})
    if value_colour:
        obj["value"].append({"properties": {"fontColor": colm(value_colour)},
                             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 0}}], "metadata": mm}})
    if ref:
        rid = "field-" + hid("ref", pg.key, m)[:8] + "-0000-0000-0000-" + hid("ref2", pg.key, m)[:12]
        obj["referenceLabel"] = [{"properties": {"value": {"expr": Me(ref)}},
                                  "selector": {"data": [{"dataViewWildcard": {"matchingOption": 0}}], "metadata": mm, "id": rid, "order": 0}}]
        obj["referenceLabelTitle"] = [{"properties": {"titleContentType": lit("'custom'"), "titleText": lit(f"'{ref_title}'")},
                                       "selector": {"metadata": mm, "id": rid}}]
        obj["referenceLabelValue"] = [{"properties": {"valueFontSize": lit("10D"), "valueFontColor": col_(GREY)}, "selector": {"id": "default"}}]
        if ref_colour:
            obj["referenceLabelValue"].insert(0, {"properties": {"valueFontColor": colm(ref_colour)},
                                                  "selector": {"data": [{"dataViewWildcard": {"matchingOption": 0}}], "metadata": mm, "id": rid}})
    v = {"visualType": "cardVisual", "query": {"queryState": {"Data": {"projections": [proj(f"[{m}]")]}}}, "objects": obj,
         "visualContainerObjects": {"padding": [{"properties": {"right": lit("0D"), "left": lit("4D"), "top": lit("0D")}}]}}
    return pg.add(f"Card {m}", x, y, w, h, v)


def slicer(pg, x, y, f, default=None, only=None):
    v = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proj(f, True)]}}},
         "objects": {"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                     "selection": [{"properties": {"selectAllCheckboxEnabled": lit("true")}}],
                     "items": [{"properties": {"textSize": lit("11D")}}]},
         "visualContainerObjects": {"background": [{"properties": {"show": lit("true")}}],
                                    "border": [{"properties": {"show": lit("true"), "color": col_("#E5E3DD"), "radius": lit("8D")}}]}}
    e, p = f.split(".", 1)
    if default is not None:
        v["objects"]["general"] = [{"properties": {"filter": {"filter": {"Version": 2, "From": [{"Name": "d", "Entity": e, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": p}}],
                                            "Values": [[{"Literal": {"Value": default}}]]}}}]}}}}]
    if only:
        v["filterConfig"] = {"filters": [{"name": hid("flt", pg.key, f), "field": C(e, p), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "d", "Entity": e, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": p}}],
                                                       "Values": [[{"Literal": {"Value": o}}] for o in only]}}}]}}]}
    return pg.add(f"Slicer {p}", x, y, 226, 36, v)


def nav_button(pg, x, y, w, h, target_id, label, hover=True):
    fill = [{"properties": {"show": lit("true")}},
            {"properties": {"fillColor": col_(RED), "transparency": lit("92D" if hover else "100D")}, "selector": {"id": "hover"}},
            {"properties": {"transparency": lit("100D")}, "selector": {"id": "default"}},
            {"properties": {"transparency": lit("85D")}, "selector": {"id": "selected"}}]
    v = {"visualType": "actionButton",
         "objects": {"icon": [{"properties": {"shapeType": lit("'blank'")}, "selector": {"id": "default"}}, {"properties": {"show": lit("false")}}],
                     "fill": fill, "outline": [{"properties": {"show": lit("false")}}]},
         "visualContainerObjects": {"visualLink": [{"properties": {"show": lit("true"), "type": lit("'PageNavigation'"),
                                                                   "navigationSection": lit(f"'{target_id}'"),
                                                                   "tooltip": lit(f"'Go to {label}'")}}],
                                    "title": [{"properties": {"show": lit("false"), "text": lit(f"'Nav {label}'")}}],
                                    "background": [{"properties": {"show": lit("false")}}],
                                    "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}],
                                    "visualHeader": [{"properties": {"show": lit("false")}}]}}
    return pg.add(f"Nav {label}", x, y, w, h, v)


def chart(pg, vtype, x, y, w, h, cat, ys, series=None, y2=None, tooltips=None, colours=None, sort=None,
          labels=True, value_axis=False, categorical=False, legend=True, label_units=None, extra=None, name=None):
    qs = {"Category": {"projections": [proj(cat, True)]}, "Y": {"projections": [proj(f) for f in ys]}}
    if series:
        qs["Series"] = {"projections": [proj(series)]}
    if y2:
        qs["Y2"] = {"projections": [proj(f) for f in y2]}
    if tooltips:
        qs["Tooltips"] = {"projections": [proj(f) for f in tooltips]}
    q = {"queryState": qs}
    if sort == "desc":
        q["sortDefinition"] = {"sort": [{"field": F(ys[0]), "direction": "Descending"}], "isDefaultSort": True}
    elif sort == "cat":
        q["sortDefinition"] = {"sort": [{"field": F(cat), "direction": "Ascending"}]}
    obj = {"labels": [{"properties": {"show": lit("true" if labels else "false")}}],
           "valueAxis": [{"properties": {"show": lit("true" if value_axis else "false")}}],
           "legend": [{"properties": {"show": lit("true" if legend else "false"), "position": lit("'TopLeft'")}}]}
    if label_units:
        obj["labels"][0]["properties"]["labelDisplayUnits"] = lit(label_units)
    if categorical:
        obj["categoryAxis"] = [{"properties": {"axisType": lit("'Categorical'")}}]
    if colours:
        obj["dataPoint"] = []
        for key, c in colours.items():
            if key.startswith("["):
                obj["dataPoint"].append({"properties": {"fill": col_(c)}, "selector": {"metadata": qref(key)}})
            else:   # "table.column=value"
                f, val = key.split("=", 1)
                obj["dataPoint"].append({"properties": {"fill": col_(c)}, "selector": scope_sel(f, val)})
    if extra:
        for k, v in extra.items():
            obj.setdefault(k, []).extend(v)
    return pg.add(name or f"{vtype} {cat}", x, y, w, h, {"visualType": vtype, "query": q, "objects": obj})


def table(pg, x, y, w, h, fields, headers, latest_entity=None):
    projs = []
    for f, hdr in zip(fields, headers):
        p = proj(f)
        p["displayName"] = hdr
        projs.append(p)
    v = {"visualType": "tableEx", "query": {"queryState": {"Values": {"projections": projs}}},
         "objects": {"columnHeaders": [{"properties": {"fontSize": lit("10D")}}], "values": [{"properties": {"fontSize": lit("10D")}}]}}
    if latest_entity:
        v["filterConfig"] = {"filters": [{"name": hid("latest", pg.key, latest_entity), "field": C(latest_entity, "is_latest_run"), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": latest_entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": "is_latest_run"}}],
                                                       "Values": [[{"Literal": {"Value": "true"}}]]}}}]}}]}
    return pg.add("Table", x, y, w, h, v)


def azure_map(pg, x, y, w, h):
    q = {"queryState": {"Category": {"projections": [proj("dim_site.site_label", True)]},
                        "X": {"projections": [{"field": {"Aggregation": {"Expression": C("dim_site", "longitude"), "Function": 0}},
                                               "queryRef": "Sum(dim_site.longitude)", "nativeQueryRef": "longitude"}]},
                        "Y": {"projections": [{"field": {"Aggregation": {"Expression": C("dim_site", "latitude"), "Function": 0}},
                                               "queryRef": "Sum(dim_site.latitude)", "nativeQueryRef": "latitude"}]},
                        "Size": {"projections": [proj("[Fuel Volume ML]")]},
                        "Tooltips": {"projections": [proj("[Retail Gross Margin]"), proj("[Margin per Litre]")]}}}
    obj = {"mapControls": [{"properties": {"autoZoom": lit("true"), "showNavigationControls": lit("false"), "showStylePicker": lit("false")}}],
           "bubbleLayer": [{"properties": {"bubbleStrokeWidth": lit("0L")}}],
           "dataPoint": [{"properties": {"fill": col_(RED)}}],
           "legend": [{"properties": {"show": lit("false")}}]}
    return pg.add("Map sites", x, y, w, h, {"visualType": "azureMap", "query": q, "objects": obj})


# ------------------------------------------------------------------ layout constants (same grid as backgrounds.py)
KPI_X = [48, 357, 667, 976, 1285, 1595]; KPI_Y, KPI_W = 180, 277
ROW2_Y, ROW2_H, ROW3_Y, ROW3_H = 316, 350, 686, 334
TWO = [(48, 900), (972, 900)]; THREE = [(48, 592), (664, 592), (1280, 592)]
SLICER_X, SLICER_Y = [48, 290, 532, 774], 124
NAV_W, NAV_GAP, NAV_Y = 136, 8, 30
NAV_X0 = 1920 - 48 - 47 - 28 - (6 * NAV_W + 5 * NAV_GAP)
YEARS = [f"{y}L" for y in range(2020, 2026)]

PAGES = [Page("home", "Home", "01_home"), Page("overview", "Executive Overview", "02_overview"), Page("mobility", "Mobility", "03_mobility"),
         Page("upstream", "Upstream & Gas", "04_upstream"), Page("energy", "Energy Transition", "05_energy_transition"),
         Page("pipeline", "Data Pipeline", "06_data_pipeline")]
P = {p.key: p for p in PAGES}


def inner(panel):   # chart area inside a background panel
    x, y, w, h = panel
    return x + 12, y + 64, w - 24, h - 74


def kpis(pg, specs):
    for x, s in zip(KPI_X, specs):
        m, ref, title, rc, vc = (list(s) + [None] * 5)[:5]
        card(pg, x + 12, KPI_Y + 34, KPI_W - 24, 76, m, ref, title or "vs PY", rc, vc)


def header(pg, active, slicers):
    for i, p in enumerate(PAGES):
        if i != active:
            nav_button(pg, NAV_X0 + i * (NAV_W + NAV_GAP), NAV_Y, NAV_W, 40, p.id, p.name)
    ids = []
    for x, s in zip(SLICER_X, slicers):
        if s:
            ids.append(slicer(pg, x, SLICER_Y, *s))
    card(pg, 1614, SLICER_Y - 6, 258, 44, "Data As Of", size=16)
    return ids


def no_filter(pg, sources, targets):
    for s in sources:
        for t in targets:
            pg.inter.append({"source": s, "target": t, "type": "NoFilter"})


YEAR = ("dim_date.year", "2025L", YEARS)
REGION = ("dim_country.region",)

# ------------------------------------------------------------------ Home
pg = P["home"]
for i, (m, ref, title, rc) in enumerate([("Rows Landed", None, None, None), ("Rows Rejected", "Reject Rate", "reject rate", "Neutral Colour"),
                                          ("DQ Checks Passed", "DQ Checks Failed", "failed", "DQ Failed Colour")]):
    card(pg, 48 + i * 364 + 14, 540, 312, 92, m, ref, title, rc, size=40)
for i, p in enumerate(PAGES[1:]):
    nav_button(pg, 1180 + (i % 2) * 358, 300 + (i // 2) * 170, 334, 150, p.id, p.name)

# ------------------------------------------------------------------ Executive Overview
pg = P["overview"]
sl = header(pg, 1, [YEAR, REGION, ("dim_segment.segment_name",)])
kpis(pg, [("Revenue ($bn)", "Revenue YoY %", None, "Revenue YoY % Colour"),
          ("EBITDA ($bn)", "EBITDA YoY %", None, "EBITDA YoY % Colour"),
          ("EBITDA Margin", "EBITDA Margin vs PY", None, "EBITDA Margin vs PY Colour"),
          ("Production kboe/d", "Production kboe/d YoY %", None, "Production kboe/d YoY % Colour"),
          ("Fuel Volume ML", "Fuel Volume ML YoY %", None, "Fuel Volume ML YoY % Colour"),
          ("Scope 1+2 Mt", "Scope 1+2 Mt YoY %", None, "Scope 1+2 Mt YoY % Colour")])
trend = chart(pg, "lineClusteredColumnComboChart", *inner((TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H)), "dim_date.year",
              ["[Revenue ($bn)]", "[EBITDA ($bn)]"], y2=["[EBITDA Margin]"], categorical=True, sort="cat",
              colours={"[Revenue ($bn)]": RED, "[EBITDA ($bn)]": YEL, "[EBITDA Margin]": GREY})
chart(pg, "clusteredBarChart", *inner((TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H)), "dim_segment.segment_name", ["[Revenue Share %]"],
      tooltips=["[Revenue ($bn)]", "[EBITDA Margin]"], sort="desc", legend=False,
      colours={f"dim_segment.segment_name='{s}'": c for s, c in [("Upstream", RED), ("Integrated Gas", YEL), ("Mobility", ORANGE),
                                                                 ("Chemicals & Products", GREY), ("Renewables & Energy Solutions", GREEN)]})
chart(pg, "clusteredBarChart", *inner((TWO[0][0], ROW3_Y, TWO[0][1], ROW3_H)), "dim_country.country_name", ["[EBITDA Top 10]"],
      tooltips=["[Revenue]", "[EBITDA Margin]"], sort="desc", legend=False, colours={"[EBITDA Top 10]": RED}, label_units="1000000000D")
table(pg, *inner((TWO[1][0], ROW3_Y, TWO[1][1], ROW3_H)), ["fact_targets.metric", "[Actual]", "[Target]", "[Target Achievement]", "[Target Status]"],
      ["Metric", "Actual", "Target", "Achievement", "Status"])
no_filter(pg, sl[:1], [trend])

# ------------------------------------------------------------------ Mobility
pg = P["mobility"]
sl = header(pg, 2, [YEAR, REGION, ("dim_country.country_name",), ("dim_site.site_format",)])
kpis(pg, [("Fuel Volume ML", "Fuel Volume ML YoY %", None, "Fuel Volume ML YoY % Colour"),
          ("Fuel Revenue ($bn)", "Fuel Revenue ($bn) YoY %", None, "Fuel Revenue ($bn) YoY % Colour"),
          ("Non-fuel Revenue ($m)", "Non-fuel Revenue ($m) YoY %", None, "Non-fuel Revenue ($m) YoY % Colour"),
          ("Margin per Litre", "Margin per Litre YoY %", None, "Margin per Litre YoY % Colour"),
          ("Active Sites", "Active Sites vs PY", None, "Active Sites vs PY Colour"),
          ("Transactions (M)", "Transactions (M) YoY %", None, "Transactions (M) YoY % Colour")])
chart(pg, "lineChart", *inner((TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H)), "dim_date.month_start", ["[Fuel Volume ML]", "[Fuel Volume ML PY]"],
      labels=False, value_axis=True, colours={"[Fuel Volume ML]": RED, "[Fuel Volume ML PY]": LGREY}, sort="cat")
azure_map(pg, *inner((TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H)))
chart(pg, "clusteredBarChart", *inner((THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H)), "dim_product.product_name", ["[Retail Gross Margin]"],
      tooltips=["[Margin per Litre]"], sort="desc", legend=False, label_units="1000000D",
      colours={f"dim_product.product_name='{p}'": c for p, c in [("Unleaded 95", RED), ("Diesel", RED), ("V-Power", RED), ("LPG", RED),
                                                                 ("Shop", YEL), ("Car Wash", YEL)]})
chart(pg, "clusteredBarChart", *inner((THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H)), "dim_country.country_name", ["[Fuel Volume ML]"],
      tooltips=["[Fuel Volume ML YoY %]"], sort="desc", legend=False, colours={"[Fuel Volume ML]": RED})
chart(pg, "clusteredBarChart", *inner((THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H)), "dim_site.site_label", ["[Site Margin Top 10]"],
      tooltips=["[Fuel Volume ML]"], sort="desc", legend=False, colours={"[Site Margin Top 10]": YEL}, label_units="1000000D")

# ------------------------------------------------------------------ Upstream & Integrated Gas
pg = P["upstream"]
sl = header(pg, 3, [YEAR, ("dim_segment.segment_name", None, ["'Upstream'", "'Integrated Gas'"]), ("dim_asset.asset_type",), ("dim_country.country_name",)])
kpis(pg, [("Production kboe/d", "Production kboe/d YoY %", None, "Production kboe/d YoY % Colour"),
          ("Production vs Plan %", "Planned kboe/d", "plan kboe/d", "Neutral Colour", "Production vs Plan % Colour"),
          ("Opex per boe", "Opex per boe YoY %", None, "Opex per boe YoY % Colour"),
          ("Asset Uptime", "Asset Uptime vs PY", None, "Asset Uptime vs PY Colour"),
          ("LNG Sold Mt", "LNG Sold Mt YoY %", None, "LNG Sold Mt YoY % Colour"),
          ("Spot LNG Share", "Spot LNG Share vs PY", None, "Neutral Colour")])
chart(pg, "lineChart", *inner((TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H)), "dim_date.month_start", ["[Production kboe/d]", "[Planned kboe/d]"],
      labels=False, value_axis=True, colours={"[Production kboe/d]": RED, "[Planned kboe/d]": LGREY}, sort="cat")
chart(pg, "clusteredBarChart", *inner((TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H)), "dim_asset.asset_name", ["[Production Top 12]"],
      tooltips=["[Production vs Plan %]", "[Asset Uptime]"], sort="desc", legend=False, colours={"[Production Top 12]": RED})
dt = chart(pg, "columnChart", *inner((THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H)), "dim_date.year", ["[Downtime Hours]"], series="fact_asset_downtime.cause",
           categorical=True, sort="cat", labels=False, value_axis=True,
           colours={f"fact_asset_downtime.cause='{c}'": v for c, v in [("Planned maintenance", LGREY), ("Unplanned", RED), ("Weather", TEAL), ("Third party", YEL)]})
chart(pg, "barChart", *inner((THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H)), "dim_country.country_name", ["[LNG Sold by Destination]"],
      series="fact_lng_sales.contract_type", sort="desc", labels=False, value_axis=True,
      colours={"fact_lng_sales.contract_type='Long-term'": RED, "fact_lng_sales.contract_type='Spot'": YEL})
lp = chart(pg, "lineChart", *inner((THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H)), "dim_date.year", ["[LNG Price USD/MMBtu]"],
           series="fact_lng_sales.contract_type", categorical=True, sort="cat",
           colours={"fact_lng_sales.contract_type='Long-term'": RED, "fact_lng_sales.contract_type='Spot'": YEL})
no_filter(pg, sl[:1], [dt, lp])

# ------------------------------------------------------------------ Energy Transition
pg = P["energy"]
sl = header(pg, 4, [YEAR, REGION, ("dim_country.country_name",)])
kpis(pg, [("EV Charge Points", "EV Charge Points YoY %", None, "EV Charge Points YoY % Colour"),
          ("EV Sessions (M)", "EV Sessions (M) YoY %", None, "EV Sessions (M) YoY % Colour"),
          ("Energy Delivered GWh", "Energy Delivered GWh YoY %", None, "Energy Delivered GWh YoY % Colour"),
          ("EV Revenue ($m)", "EV Revenue ($m) YoY %", None, "EV Revenue ($m) YoY % Colour"),
          ("Low-Carbon Revenue Share", "Low-Carbon Revenue Share vs PY", None, "Low-Carbon Revenue Share vs PY Colour"),
          ("Scope 1+2 vs 2020", "Scope 1+2 Mt", "Scope 1+2", "Neutral Colour", "Scope 1+2 vs 2020 Colour")])
ev = chart(pg, "lineClusteredColumnComboChart", *inner((TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H)), "dim_date.month_start", ["[EV Sessions]"],
           y2=["[Energy Delivered MWh]"], labels=False, value_axis=True, sort="cat",
           colours={"[EV Sessions]": YEL, "[Energy Delivered MWh]": GREEN})
em = chart(pg, "lineChart", *inner((TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H)), "dim_date.year", ["[Scope 1+2 Mt]", "[Scope 1+2 Target Mt]"],
           categorical=True, sort="cat", colours={"[Scope 1+2 Mt]": RED, "[Scope 1+2 Target Mt]": LGREY},
           extra={"lineStyles": [{"properties": {"lineStyle": lit("'dashed'")}, "selector": {"metadata": "_Measures.Scope 1+2 Target Mt"}}]})
chart(pg, "clusteredBarChart", *inner((THREE[0][0], ROW3_Y, THREE[0][1], ROW3_H)), "fact_emissions.scope_label", ["[Emissions Mt]"], sort="cat",
      legend=False, colours={"fact_emissions.scope_label='Scope 1'": RED, "fact_emissions.scope_label='Scope 2'": ORANGE,
                             "fact_emissions.scope_label='Scope 3'": LGREY})
chart(pg, "clusteredBarChart", *inner((THREE[1][0], ROW3_Y, THREE[1][1], ROW3_H)), "dim_country.country_name", ["[EV Charge Points]"],
      tooltips=["[EV Hub Share]"], sort="desc", legend=False, colours={"[EV Charge Points]": GREEN})
lc = chart(pg, "lineChart", *inner((THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H)), "dim_date.year", ["[Low-Carbon Revenue Share]", "[Low-Carbon Share Target]"],
           categorical=True, sort="cat", colours={"[Low-Carbon Revenue Share]": GREEN, "[Low-Carbon Share Target]": LGREY},
           extra={"lineStyles": [{"properties": {"lineStyle": lit("'dashed'")}, "selector": {"metadata": "_Measures.Low-Carbon Share Target"}}]})
no_filter(pg, sl[:1], [ev, em, lc])

# ------------------------------------------------------------------ Data Pipeline & Quality
pg = P["pipeline"]
header(pg, 5, [])
kpis(pg, [("Pipeline Runs",), ("Rows Landed",), ("Rows Rejected",), ("Reject Rate",),
          ("DQ Checks Passed", "DQ Checks Failed", "failed", "DQ Failed Colour"), ("Last Run Duration",)])
chart(pg, "barChart", *inner((TWO[0][0], ROW2_Y, TWO[0][1], ROW2_H)), "vw_pipeline_runs.object_name", ["[Rows Passed Validation]", "[Rows Rejected]"],
      sort="desc", labels=False, value_axis=True, colours={"[Rows Passed Validation]": LGREY, "[Rows Rejected]": RED})
chart(pg, "clusteredBarChart", *inner((TWO[1][0], ROW2_Y, TWO[1][1], ROW2_H)), "vw_rejections.reject_reason", ["[Rejected Rows (latest)]"],
      series="vw_rejections.table_name", sort="desc", labels=False, value_axis=True)
table(pg, *inner((THREE[2][0], ROW3_Y, THREE[2][1], ROW3_H)),
      ["vw_dq_results.check_name", "vw_dq_results.table_name", "vw_dq_results.expected_value", "vw_dq_results.actual_value", "vw_dq_results.result"],
      ["Check", "Table", "Expected", "Actual", "Result"], latest_entity="vw_dq_results")

# ------------------------------------------------------------------ write
shutil.rmtree(OUT, ignore_errors=True)
defn = OUT / "definition"
res = OUT / "StaticResources" / "RegisteredResources"
res.mkdir(parents=True)
shutil.copy(THEME, res / "shell_theme.json")
items = [{"name": "shell_theme.json", "path": "shell_theme.json", "type": "CustomTheme"}]
for p in PAGES:
    shutil.copy(BG / f"{p.bg}.png", res / f"{p.bg}.png")
    items.append({"name": f"{p.bg}.png", "path": f"{p.bg}.png", "type": "Image"})
    pdir = defn / "pages" / p.id
    (pdir / "visuals").mkdir(parents=True)
    page = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": p.id, "displayName": p.name, "displayOption": "FitToPage", "height": 1080, "width": 1920,
            "objects": {"background": [{"properties": {"image": {"image": {
                "name": lit(f"'{p.bg}.png'"),
                "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": f"{p.bg}.png"}}},
                "scaling": lit("'Normal'")}}, "transparency": lit("0D")}}]}}
    if p.inter:
        page["visualInteractions"] = p.inter
    (pdir / "page.json").write_text(json.dumps(page, indent=2), encoding="utf-8")
    for v in p.visuals:
        (pdir / "visuals" / v["name"]).mkdir()
        (pdir / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
(defn / "pages" / "pages.json").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "pageOrder": [p.id for p in PAGES], "activePageName": PAGES[0].id}, indent=2), encoding="utf-8")

rep = json.loads(Path("/home/claude/tpl/Shell/shell-fabric-sql-analytics/powerbi/Shell_Energy_Analytics.Report/definition/report.json").read_text())
rep["themeCollection"]["customTheme"] = {"name": "shell_theme.json", "reportVersionAtImport": rep["themeCollection"]["baseTheme"]["reportVersionAtImport"],
                                         "type": "RegisteredResources"}
rep["resourcePackages"] = [r for r in rep["resourcePackages"] if r["type"] != "RegisteredResources"] + \
                          [{"name": "RegisteredResources", "type": "RegisteredResources", "items": items}]
rep.setdefault("objects", {})["outspacePane"] = [{"properties": {"expanded": lit("false")}}]
(defn / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
shutil.copy("/home/claude/tpl/Shell/shell-fabric-sql-analytics/powerbi/Shell_Energy_Analytics.Report/definition/version.json", defn / "version.json")
print({p.name: len(p.visuals) for p in PAGES})
