"""Builds the Shell semantic model (TMDL): clean table names, relationships, date table, calculated columns, measures."""
import re, uuid, shutil
from pathlib import Path

SRC = Path("/home/claude/tpl/Shell/shell-fabric-sql-analytics/powerbi/Shell_Energy_Analytics.SemanticModel/definition")
OUT = Path("/home/claude/out/Shell_Energy_Analytics.SemanticModel/definition")
tag = lambda: str(uuid.uuid4())

shutil.rmtree(OUT.parent, ignore_errors=True)
shutil.copytree(SRC.parent, OUT.parent, ignore=shutil.ignore_patterns("cache.abf"))
tables = OUT / "tables"

# ---------------------------------------------------------------- 1. rename 'gold x' -> x
for f in list(tables.glob("gold *.tmdl")):
    new = f.name.replace("gold ", "")
    name = new[:-5]
    s = f.read_text(encoding="utf-8")
    s = s.replace(f"table 'gold {name}'", f"table {name}").replace(f"partition 'gold {name}' = m", f"partition {name} = m")
    (tables / new).write_text(s, encoding="utf-8"); f.unlink()
m = (OUT / "model.tmdl").read_text(encoding="utf-8")
m = re.sub(r"ref table 'gold ([a-z_]+)'", r"ref table \1", m).replace('"gold ', '"')
m = m.replace("ref table vw_rejections", "ref table vw_rejections\nref table fact_asset_downtime\nref table _Measures")
m = m.replace('"vw_rejections"]', '"vw_rejections","fact_asset_downtime","_Measures"]')
(OUT / "model.tmdl").write_text(m, encoding="utf-8")

# ---------------------------------------------------------------- 2. missing table fact_asset_downtime
SERVER = "3tcypxrxblrelj4kg5eeqfadx4-324w3lxlhikuphnygt574zztqi.database.fabric.microsoft.com,1433"
DB = "sqldb_shell-71695bad-0418-46a7-b764-75a571b683c1"
cols = [("event_id", "string", None, "none"), ("date_key", "int64", "0", "none"), ("asset_id", "string", None, "none"),
        ("start_ts", "dateTime", "General Date", "none"), ("end_ts", "dateTime", "General Date", "none"),
        ("downtime_hours", "double", "#,0.0", "sum"), ("cause", "string", None, "none"), ("is_planned", "boolean", '"""TRUE"";""TRUE"";""FALSE"""', "none")]
t = f"table fact_asset_downtime\n\tlineageTag: {tag()}\n\n"
for c, dt, fmt, sb in cols:
    t += f"\tcolumn {c}\n\t\tdataType: {dt}\n" + (f"\t\tformatString: {fmt}\n" if fmt else "") + \
         f"\t\tlineageTag: {tag()}\n\t\tsummarizeBy: {sb}\n\t\tsourceColumn: {c}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
t += (f"\tpartition fact_asset_downtime = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
      f"\t\t\t\t  Source = Sql.Database(\"{SERVER}\", \"{DB}\"),\n"
      f"\t\t\t\t  #\"Navigation 1\" = Source{{[Schema = \"gold\", Item = \"fact_asset_downtime\"]}}[Data]\n"
      f"\t\t\t\tin\n\t\t\t\t  #\"Navigation 1\"\n\n\tannotation PBI_ResultType = Table\n\n")
(tables / "fact_asset_downtime.tmdl").write_text(t, encoding="utf-8")


# ---------------------------------------------------------------- 3. column tweaks
def edit_col(s, col, add=None, replace=None):
    """add lines after the dataType line of `column col`; replace = (old, new) inside that column block"""
    pat = re.compile(rf"(\tcolumn {re.escape(col)}\n)(.*?)(?=\n\t(?:column|partition|measure|annotation)|\Z)", re.S)
    mm = pat.search(s)
    assert mm, col
    block = mm.group(2)
    if replace:
        block = block.replace(*replace)
    if add:
        block = re.sub(r"(\t\tdataType: [^\n]+\n)", lambda x: x.group(1) + "".join(f"\t\t{a}\n" for a in add), block, count=1)
    return s[:mm.start(2)] + block + s[mm.end(2):]


for f in tables.glob("dim_*.tmdl"):
    s = f.read_text(encoding="utf-8").replace("summarizeBy: sum", "summarizeBy: none")
    f.write_text(s, encoding="utf-8")

d = (tables / "dim_date.tmdl").read_text(encoding="utf-8")
d = d.replace("table dim_date\n\tlineageTag:", "table dim_date\n\tdataCategory: Time\n\tlineageTag:", 1)
d = edit_col(d, "date", add=["isKey"])
d = edit_col(d, "date", replace=("formatString: Long Date", "formatString: dd mmm yyyy"))
d = edit_col(d, "month_start", replace=("formatString: Long Date", "formatString: mmm yyyy"))
for col, by in [("month_name", "month_number"), ("month_short", "month_number"), ("year_month_label", "year_month"), ("day_name", "day_of_week")]:
    d = edit_col(d, col, add=[f"sortByColumn: {by}"])
(tables / "dim_date.tmdl").write_text(d, encoding="utf-8")

HIDE = {"date_key", "site_id", "product_id", "asset_id", "plant_asset_id", "destination_country_code", "segment_id", "country_code"}
for f in tables.glob("fact_*.tmdl"):
    s = f.read_text(encoding="utf-8")
    for c in HIDE:
        if f"\tcolumn {c}\n" in s:
            s = edit_col(s, c, add=["isHidden"])
    f.write_text(s, encoding="utf-8")


def calc_col(file, name, expr, dtype="boolean", fmt=None):
    f = tables / file
    s = f.read_text(encoding="utf-8")
    block = f"\tcolumn {name} = {expr}\n\t\tdataType: {dtype}\n" + (f"\t\tformatString: {fmt}\n" if fmt else "") + \
            f"\t\tlineageTag: {tag()}\n\t\tsummarizeBy: none\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    s = s.replace("\tpartition ", block + "\tpartition ", 1)
    f.write_text(s, encoding="utf-8")


BOOL = '"""TRUE"";""TRUE"";""FALSE"""'
LATEST = ("VAR t = FILTER ( ALL ( vw_pipeline_runs[step], vw_pipeline_runs[started_at], vw_pipeline_runs[pipeline_run_id] ), vw_pipeline_runs[step] = \"dq\" ) "
          "VAR lastRun = CONCATENATEX ( TOPN ( 1, t, vw_pipeline_runs[started_at], DESC ), vw_pipeline_runs[pipeline_run_id] ) RETURN ")
calc_col("vw_pipeline_runs.tmdl", "is_latest_run", LATEST + "vw_pipeline_runs[pipeline_run_id] = lastRun", fmt=BOOL)
calc_col("vw_rejections.tmdl", "is_latest_run", LATEST + "vw_rejections[pipeline_run_id] = lastRun", fmt=BOOL)
calc_col("vw_dq_results.tmdl", "is_latest_run", LATEST + "vw_dq_results[pipeline_run_id] = lastRun", fmt=BOOL)
calc_col("dim_site.tmdl", "site_label", 'dim_site[site_name] & " (" & dim_site[site_id] & ")"', dtype="string")

# ---------------------------------------------------------------- 4. relationships
REL = [("fact_retail_sales", "date_key", "dim_date", "date_key"), ("fact_retail_sales", "site_id", "dim_site", "site_id"),
       ("fact_retail_sales", "product_id", "dim_product", "product_id"),
       ("fact_ev_charging", "date_key", "dim_date", "date_key"), ("fact_ev_charging", "site_id", "dim_site", "site_id"),
       ("fact_production", "date_key", "dim_date", "date_key"), ("fact_production", "asset_id", "dim_asset", "asset_id"),
       ("fact_asset_downtime", "date_key", "dim_date", "date_key"), ("fact_asset_downtime", "asset_id", "dim_asset", "asset_id"),
       ("fact_lng_sales", "date_key", "dim_date", "date_key"), ("fact_lng_sales", "plant_asset_id", "dim_asset", "asset_id"),
       ("fact_lng_sales", "destination_country_code", "dim_country", "country_code", False),
       ("fact_financials", "date_key", "dim_date", "date_key"), ("fact_financials", "segment_id", "dim_segment", "segment_id"),
       ("fact_financials", "country_code", "dim_country", "country_code"),
       ("fact_emissions", "date_key", "dim_date", "date_key"), ("fact_emissions", "segment_id", "dim_segment", "segment_id"),
       ("fact_emissions", "country_code", "dim_country", "country_code"),
       ("dim_site", "country_code", "dim_country", "country_code"),
       ("dim_asset", "country_code", "dim_country", "country_code"), ("dim_asset", "segment_id", "dim_segment", "segment_id")]
r = ""
for x in REL:
    ft, fc, tt, tc = x[:4]
    r += f"relationship {tag()}\n" + ("\tisActive: false\n" if len(x) > 4 and not x[4] else "") + \
         f"\tfromColumn: {ft}.{fc}\n\ttoColumn: {tt}.{tc}\n\n"
(OUT / "relationships.tmdl").write_text(r, encoding="utf-8")
