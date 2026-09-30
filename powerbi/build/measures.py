"""_Measures table for the Shell report. Every measure has a description (///) and a display folder."""
import uuid
from pathlib import Path
tag = lambda: str(uuid.uuid4())
M = []   # (folder, name, expr, fmt, description)
GREEN, RED, GREY = "#1E8E5A", "#DD1D21", "#5E5E59"
PCT = "+0.0%;-0.0%;0.0%"
PP = "+0.0 pp;-0.0 pp;0.0 pp"


def add(folder, name, expr, fmt=None, desc=""):
    M.append((folder, name, expr, fmt, desc))


def py(folder, base, fmt=None, kind="pct", higher_better=True):
    """prior year + change + colour for a base measure"""
    add(folder, f"{base} PY", f"CALCULATE ( [{base}], SAMEPERIODLASTYEAR ( dim_date[date] ) )", fmt, f"{base} in the same period of the prior year.")
    if kind == "pct":
        add(folder, f"{base} YoY %", f"IF ( ISBLANK ( [{base} PY] ), BLANK (), DIVIDE ( [{base}] - [{base} PY], [{base} PY] ) )", PCT, f"Change of {base} vs prior year.")
        chg = f"{base} YoY %"
    elif kind == "pp":
        add(folder, f"{base} vs PY", f"IF ( ISBLANK ( [{base} PY] ), BLANK (), ( [{base}] - [{base} PY] ) * 100 )", PP, f"Change of {base} vs prior year in percentage points.")
        chg = f"{base} vs PY"
    else:
        add(folder, f"{base} vs PY", f"IF ( ISBLANK ( [{base} PY] ), BLANK (), [{base}] - [{base} PY] )", "+#,0;-#,0;0", f"Change of {base} vs prior year.")
        chg = f"{base} vs PY"
    good, bad = (GREEN, RED) if higher_better else (RED, GREEN)
    add("99 Formatting", f"{chg} Colour", f'IF ( [{chg}] >= 0, "{good}", "{bad}" )', None, "Font colour for the change label.")


# ---------------------------------------------------------------- 00 Base
add("00 Base", "Data As Of", 'FORMAT ( CALCULATE ( MAX ( vw_pipeline_runs[ended_at] ), REMOVEFILTERS () ), "dd mmm yyyy", "en-US" )', None, "Last pipeline step that finished in Fabric.")
add("00 Base", "Last Data Year", "INT ( CALCULATE ( MAX ( fact_financials[date_key] ), REMOVEFILTERS () ) / 10000 )", "0", "Last year with data (2025).")
add("00 Base", "Selected Year", "MIN ( MAX ( dim_date[year] ), [Last Data Year] )", "0", "Year in the filter context, capped at the last year with data.")
add("99 Formatting", "Neutral Colour", f'"{GREY}"', None, "Neutral font colour.")

# ---------------------------------------------------------------- 01 Overview (financials)
add("01 Overview", "Revenue", "SUM ( fact_financials[revenue_usd] )", "$#,0", "Group revenue, USD.")
add("01 Overview", "Revenue ($bn)", "DIVIDE ( [Revenue], 1e9 )", "$#,0.0\\b\\n", "Group revenue in USD billion.")
py("01 Overview", "Revenue", "$#,0")
add("01 Overview", "EBITDA", "SUM ( fact_financials[ebitda_usd] )", "$#,0", "EBITDA recalculated in silver as revenue minus operating cost.")
add("01 Overview", "EBITDA ($bn)", "DIVIDE ( [EBITDA], 1e9 )", "$#,0.0\\b\\n", "EBITDA in USD billion.")
py("01 Overview", "EBITDA", "$#,0")
add("01 Overview", "EBITDA Margin", "DIVIDE ( [EBITDA], [Revenue] )", "0.0%", "EBITDA as a share of revenue.")
py("01 Overview", "EBITDA Margin", "0.0%", kind="pp")
add("01 Overview", "Capex", "SUM ( fact_financials[capex_usd] )", "$#,0", "Capital expenditure, USD.")
add("01 Overview", "Revenue Share %", "DIVIDE ( [Revenue], CALCULATE ( [Revenue], ALLSELECTED ( dim_segment ) ) )", "0.0%", "Share of revenue among the selected segments.")
add("01 Overview", "EBITDA Top 10", "IF ( RANKX ( ALLSELECTED ( dim_country[country_name] ), [EBITDA],, DESC ) <= 10, [EBITDA] )", "$#,0", "EBITDA for the 10 largest countries.")

# ---------------------------------------------------------------- 02 Mobility
add("02 Mobility", "Fuel Volume ML", "DIVIDE ( SUM ( fact_retail_sales[volume_litres] ), 1e6 )", "#,0\\ \\M\\L", "Fuel sold in million litres.")
py("02 Mobility", "Fuel Volume ML", "#,0\\ \\M\\L")
add("02 Mobility", "Fuel Revenue", 'CALCULATE ( SUM ( fact_retail_sales[revenue_usd] ), dim_product[product_group] = "Fuel" )', "$#,0", "Fuel revenue, USD.")
add("02 Mobility", "Fuel Revenue ($bn)", "DIVIDE ( [Fuel Revenue], 1e9 )", "$#,0.00\\b\\n", "Fuel revenue in USD billion.")
py("02 Mobility", "Fuel Revenue ($bn)", "$#,0.00\\b\\n")
add("02 Mobility", "Non-fuel Revenue", 'CALCULATE ( SUM ( fact_retail_sales[revenue_usd] ), dim_product[product_group] = "Non-fuel" )', "$#,0", "Shop and car wash revenue, USD.")
add("02 Mobility", "Non-fuel Revenue ($m)", "DIVIDE ( [Non-fuel Revenue], 1e6 )", "$#,0\\m", "Shop and car wash revenue in USD million.")
py("02 Mobility", "Non-fuel Revenue ($m)", "$#,0\\m")
add("02 Mobility", "Retail Gross Margin", "SUM ( fact_retail_sales[gross_margin_usd] )", "$#,0", "Revenue minus cost of goods, USD.")
add("02 Mobility", "Fuel Gross Margin", 'CALCULATE ( [Retail Gross Margin], dim_product[product_group] = "Fuel" )', "$#,0", "Gross margin on fuel, USD.")
add("02 Mobility", "Margin per Litre", "DIVIDE ( [Fuel Gross Margin], SUM ( fact_retail_sales[volume_litres] ) )", "$0.000", "Fuel gross margin per litre, USD.")
py("02 Mobility", "Margin per Litre", "$0.000")
add("02 Mobility", "Active Sites", "DISTINCTCOUNT ( fact_retail_sales[site_id] )", "#,0", "Sites with sales in the period.")
py("02 Mobility", "Active Sites", "#,0", kind="abs")
add("02 Mobility", "Transactions (M)", "DIVIDE ( SUM ( fact_retail_sales[transactions] ), 1e6 )", "#,0.0\\M", "Customer transactions in millions.")
py("02 Mobility", "Transactions (M)", "#,0.0\\M")
add("02 Mobility", "Site Margin Top 10", "IF ( RANKX ( ALLSELECTED ( dim_site[site_label] ), [Retail Gross Margin],, DESC ) <= 10, [Retail Gross Margin] )", "$#,0", "Gross margin for the 10 best sites.")

# ---------------------------------------------------------------- 03 Upstream & Integrated Gas
add("03 Upstream", "Production boe", "SUM ( fact_production[total_boe] )", "#,0", "Barrels of oil equivalent produced.")
add("03 Upstream", "Days Produced", "SUMX ( VALUES ( fact_production[date_key] ), CALCULATE ( MAX ( fact_production[days_in_month] ) ) )", "#,0", "Calendar days covered by the monthly production rows.")
add("03 Upstream", "Production kboe/d", "DIVIDE ( [Production boe], [Days Produced] ) / 1000", "#,0", "Average production, thousand boe per day.")
py("03 Upstream", "Production kboe/d", "#,0")
add("03 Upstream", "Planned kboe/d", "DIVIDE ( SUM ( fact_production[planned_boe] ), [Days Produced] ) / 1000", "#,0", "Planned production, thousand boe per day.")
add("03 Upstream", "Production vs Plan %", "IF ( ISBLANK ( [Planned kboe/d] ), BLANK (), DIVIDE ( [Production kboe/d], [Planned kboe/d] ) - 1 )", PCT, "Actual vs planned production.")
add("99 Formatting", "Production vs Plan % Colour", f'IF ( [Production vs Plan %] >= 0, "{GREEN}", "{RED}" )', None, "Font colour.")
add("03 Upstream", "Production Top 12", "IF ( RANKX ( ALLSELECTED ( dim_asset[asset_name] ), [Production kboe/d],, DESC ) <= 12, [Production kboe/d] )", "#,0", "Production of the 12 largest assets.")
add("03 Upstream", "Opex per boe", "DIVIDE ( SUM ( fact_production[opex_usd] ), [Production boe] )", "$#,0.00", "Operating cost per barrel of oil equivalent, USD.")
py("03 Upstream", "Opex per boe", "$#,0.00", higher_better=False)
add("03 Upstream", "Asset Uptime", "1 - DIVIDE ( SUM ( fact_production[downtime_hours] ), SUMX ( fact_production, 24 * fact_production[days_in_month] ) )", "0.0%", "Share of hours the assets were running.")
py("03 Upstream", "Asset Uptime", "0.0%", kind="pp")
add("03 Upstream", "Downtime Hours", "SUM ( fact_asset_downtime[downtime_hours] )", "#,0", "Hours of asset downtime.")
add("03 Upstream", "LNG Sold Mt", "SUM ( fact_lng_sales[volume_mt] )", "#,0.0\\ \\M\\t", "LNG sold in million tonnes.")
py("03 Upstream", "LNG Sold Mt", "#,0.0\\ \\M\\t")
add("03 Upstream", "Spot LNG Share", 'DIVIDE ( CALCULATE ( [LNG Sold Mt], fact_lng_sales[contract_type] = "Spot" ), [LNG Sold Mt] )', "0.0%", "Share of LNG sold on the spot market.")
py("03 Upstream", "Spot LNG Share", "0.0%", kind="pp")
add("03 Upstream", "LNG Revenue", "SUM ( fact_lng_sales[revenue_usd] )", "$#,0", "LNG revenue, USD.")
add("03 Upstream", "LNG Price USD/MMBtu", "DIVIDE ( [LNG Revenue], [LNG Sold Mt] * 52000000 )", "$#,0.00", "Realised LNG price per MMBtu (1 Mt = 52 million MMBtu).")
add("03 Upstream", "LNG Sold by Destination",
    "CALCULATE ( [LNG Sold Mt], USERELATIONSHIP ( fact_lng_sales[destination_country_code], dim_country[country_code] ), CROSSFILTER ( fact_lng_sales[plant_asset_id], dim_asset[asset_id], None ) )",
    "#,0.0\\ \\M\\t", "LNG sold by destination country (inactive relationship).")

# ---------------------------------------------------------------- 04 Energy transition
EVD = "VAR d = MIN ( MAX ( dim_date[date] ), DATE ( [Last Data Year], 12, 31 ) ) "
add("04 Energy Transition", "EV Charge Points",
    EVD + "RETURN SUMX ( FILTER ( dim_site, NOT ISBLANK ( dim_site[ev_since_date] ) && dim_site[ev_since_date] <= d ), dim_site[ev_charge_points] )",
    "#,0", "EV charge points installed at the end of the period.")
py("04 Energy Transition", "EV Charge Points", "#,0")
add("04 Energy Transition", "EV Hub Share",
    EVD + "RETURN DIVIDE ( COUNTROWS ( FILTER ( dim_site, NOT ISBLANK ( dim_site[ev_since_date] ) && dim_site[ev_since_date] <= d ) ), COUNTROWS ( dim_site ) )",
    "0.0%", "Share of sites with EV charging at the end of the period.")
add("04 Energy Transition", "EV Sessions", "SUM ( fact_ev_charging[sessions] )", "#,0", "EV charging sessions.")
add("04 Energy Transition", "EV Sessions (M)", "DIVIDE ( [EV Sessions], 1e6 )", "#,0.00\\M", "EV charging sessions in millions.")
py("04 Energy Transition", "EV Sessions (M)", "#,0.00\\M")
add("04 Energy Transition", "Energy Delivered GWh", "DIVIDE ( SUM ( fact_ev_charging[energy_mwh] ), 1000 )", "#,0.0\\ \\G\\W\\h", "Electricity delivered to EVs, GWh.")
py("04 Energy Transition", "Energy Delivered GWh", "#,0.0\\ \\G\\W\\h")
add("04 Energy Transition", "Energy Delivered MWh", "SUM ( fact_ev_charging[energy_mwh] )", "#,0", "Electricity delivered to EVs, MWh.")
add("04 Energy Transition", "EV Revenue", "SUM ( fact_ev_charging[revenue_usd] )", "$#,0", "EV charging revenue, USD.")
add("04 Energy Transition", "EV Revenue ($m)", "DIVIDE ( [EV Revenue], 1e6 )", "$#,0.0\\m", "EV charging revenue in USD million.")
py("04 Energy Transition", "EV Revenue ($m)", "$#,0.0\\m")
add("04 Energy Transition", "Low-Carbon Revenue Share",
    "DIVIDE ( CALCULATE ( [Revenue], dim_segment[is_low_carbon] = TRUE () ) + [EV Revenue], [Revenue] )", "0.0%",
    "Renewables & Energy Solutions revenue plus EV charging revenue as a share of group revenue.")
py("04 Energy Transition", "Low-Carbon Revenue Share", "0.0%", kind="pp")
add("04 Energy Transition", "Low-Carbon Share Target",
    'DIVIDE ( CALCULATE ( SUM ( fact_targets[target_value] ), fact_targets[metric] = "Low-carbon revenue share", TREATAS ( VALUES ( dim_date[year] ), fact_targets[target_year] ) ), 100 )',
    "0.0%", "Business target for the low-carbon revenue share.")
add("04 Energy Transition", "Emissions Mt", "DIVIDE ( SUM ( fact_emissions[tco2e] ), 1e6 )", "#,0.0\\ \\M\\t", "Greenhouse gas emissions, MtCO2e.")
add("04 Energy Transition", "Scope 1+2 Mt", "DIVIDE ( CALCULATE ( SUM ( fact_emissions[tco2e] ), fact_emissions[scope] IN { 1, 2 } ), 1e6 )", "#,0.0\\ \\M\\t", "Operational emissions (Scope 1 and 2), MtCO2e.")
py("04 Energy Transition", "Scope 1+2 Mt", "#,0.0\\ \\M\\t", higher_better=False)
add("04 Energy Transition", "Scope 3 Mt", "DIVIDE ( CALCULATE ( SUM ( fact_emissions[tco2e] ), fact_emissions[scope] = 3 ), 1e6 )", "#,0.0\\ \\M\\t", "Emissions from use of sold products (Scope 3), MtCO2e.")
add("04 Energy Transition", "Scope 1+2 Target Mt",
    'CALCULATE ( SUM ( fact_targets[target_value] ), fact_targets[metric] = "Scope 1+2 emissions", TREATAS ( VALUES ( dim_date[year] ), fact_targets[target_year] ) )',
    "#,0.0\\ \\M\\t", "Scope 1+2 target path to 2030 (50% below 2016).")
add("04 Energy Transition", "Scope 1+2 vs 2020",
    "VAR y = [Selected Year] VAR cur = CALCULATE ( [Scope 1+2 Mt], REMOVEFILTERS ( dim_date ), dim_date[year] = y ) "
    "VAR base = CALCULATE ( [Scope 1+2 Mt], REMOVEFILTERS ( dim_date ), dim_date[year] = 2020 ) RETURN DIVIDE ( cur - base, base )",
    PCT, "Scope 1+2 emissions of the selected year vs 2020.")
add("99 Formatting", "Scope 1+2 vs 2020 Colour", f'IF ( [Scope 1+2 vs 2020] <= 0, "{GREEN}", "{RED}" )', None, "Font colour.")

# ---------------------------------------------------------------- 05 Targets scorecard
add("05 Targets", "Target Value", "VAR y = [Selected Year] RETURN CALCULATE ( SUM ( fact_targets[target_value] ), fact_targets[target_year] = y )", "#,0.0", "Target for the selected year.")
add("05 Targets", "Actual Value",
    'VAR m = SELECTEDVALUE ( fact_targets[metric] ) VAR y = [Selected Year] RETURN CALCULATE ( SWITCH ( m, "Production", [Production kboe/d], '
    '"Scope 1+2 emissions", [Scope 1+2 Mt], "Fuel volume", [Fuel Volume ML], "EV charge points", [EV Charge Points], '
    '"Low-carbon revenue share", [Low-Carbon Revenue Share] * 100 ), REMOVEFILTERS ( dim_date ), dim_date[year] = y )',
    "#,0.0", "Actual value of the target metric in the selected year.")
add("05 Targets", "Target Achievement",
    'VAR m = SELECTEDVALUE ( fact_targets[metric] ) RETURN IF ( m = "Scope 1+2 emissions", DIVIDE ( [Target Value], [Actual Value] ), DIVIDE ( [Actual Value], [Target Value] ) )',
    "0%", "Actual vs target (for emissions, lower is better).")
add("05 Targets", "Target Status",
    'IF ( ISBLANK ( [Target Achievement] ), BLANK (), IF ( [Target Achievement] >= 1, "On track", IF ( [Target Achievement] >= 0.95, "Close", "Behind" ) ) )',
    None, "Status label.")
add("99 Formatting", "Target Status Colour", f'SWITCH ( TRUE (), [Target Achievement] >= 1, "{GREEN}", [Target Achievement] >= 0.95, "#EB8705", "{RED}" )', None, "Font colour.")
UNIT = ('SWITCH ( m, "Production", FORMAT ( v, "#,0" ) & " kboe/d", "Scope 1+2 emissions", FORMAT ( v, "0.0" ) & " Mt", '
        '"Fuel volume", FORMAT ( v, "#,0" ) & " ML", "EV charge points", FORMAT ( v, "#,0" ), "Low-carbon revenue share", FORMAT ( v, "0.0" ) & "%" )')
add("05 Targets", "Actual", "VAR m = SELECTEDVALUE ( fact_targets[metric] ) VAR v = [Actual Value] RETURN " + UNIT, None, "Actual with unit.")
add("05 Targets", "Target", "VAR m = SELECTEDVALUE ( fact_targets[metric] ) VAR v = [Target Value] RETURN " + UNIT, None, "Target with unit.")

# ---------------------------------------------------------------- 06 Data pipeline
LAT = "vw_pipeline_runs[is_latest_run] = TRUE ()"
add("06 Pipeline", "Pipeline Runs", 'CALCULATE ( DISTINCTCOUNT ( vw_pipeline_runs[pipeline_run_id] ), LEFT ( vw_pipeline_runs[pipeline_run_id], 6 ) <> "manual" )', "#,0", "Runs of the Fabric pipeline (manual test runs excluded).")
add("06 Pipeline", "Rows Landed", f'CALCULATE ( SUM ( vw_pipeline_runs[rows_read] ), vw_pipeline_runs[step] = "bronze", {LAT} )', "#,0", "Rows copied into bronze in the latest run.")
add("06 Pipeline", "Silver Rows Read", f'CALCULATE ( SUM ( vw_pipeline_runs[rows_read] ), vw_pipeline_runs[step] = "silver", {LAT} )', "#,0", "Rows validated in silver in the latest run.")
add("06 Pipeline", "Rows Rejected", f'CALCULATE ( SUM ( vw_pipeline_runs[rows_rejected] ), vw_pipeline_runs[step] = "silver", {LAT} )', "#,0", "Rows rejected by silver validation in the latest run.")
add("06 Pipeline", "Rows Passed Validation", "[Silver Rows Read] - [Rows Rejected]", "#,0", "Rows that passed validation (before deduplication).")
add("06 Pipeline", "Reject Rate", "DIVIDE ( [Rows Rejected], [Silver Rows Read] )", "0.00%", "Rejected rows as a share of rows validated.")
add("06 Pipeline", "DQ Checks Total", "CALCULATE ( COUNTROWS ( vw_dq_results ), vw_dq_results[is_latest_run] = TRUE () )", "#,0", "Data quality checks in the latest run.")
add("06 Pipeline", "DQ Checks Failed", "CALCULATE ( COUNTROWS ( vw_dq_results ), vw_dq_results[is_latest_run] = TRUE (), vw_dq_results[passed] = FALSE () ) + 0", "#,0", "Failed checks in the latest run.")
add("06 Pipeline", "DQ Checks Passed", 'FORMAT ( [DQ Checks Total] - [DQ Checks Failed], "0" ) & " / " & FORMAT ( [DQ Checks Total], "0" )', None, "Passed vs total checks in the latest run.")
add("99 Formatting", "DQ Failed Colour", f'IF ( [DQ Checks Failed] > 0, "#EB8705", "{GREEN}" )', None, "Font colour.")
add("06 Pipeline", "Last Run Duration",
    f"VAR s = CALCULATE ( MIN ( vw_pipeline_runs[started_at] ), {LAT} ) VAR e = CALCULATE ( MAX ( vw_pipeline_runs[ended_at] ), {LAT} ) "
    'VAR sec = DATEDIFF ( s, e, SECOND ) RETURN INT ( sec / 60 ) & " min " & FORMAT ( MOD ( sec, 60 ), "00" ) & " s"', None,
    "Time from the first to the last logged step of the latest run.")
add("06 Pipeline", "Rejected Rows (latest)", "CALCULATE ( SUM ( vw_rejections[rejected_rows] ), vw_rejections[is_latest_run] = TRUE () )", "#,0", "Rejected rows by reason in the latest run.")


def write(path: Path):
    s = f"table _Measures\n\tlineageTag: {tag()}\n\n"
    for folder, name, expr, fmt, desc in M:
        n = f"'{name}'"
        s += f"\t/// {desc}\n\tmeasure {n} = {expr}\n"
        if fmt:
            s += f"\t\tformatString: {fmt}\n"
        s += f"\t\tdisplayFolder: {folder}\n\t\tlineageTag: {tag()}\n\n"
    s += ('\tpartition _Measures = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n'
          '\t\t\t\t  Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Column1 = _t]),\n'
          '\t\t\t\t    #"Removed Columns" = Table.RemoveColumns(Source,{"Column1"})\n\t\t\t\tin\n\t\t\t\t  #"Removed Columns"\n\n'
          '\tannotation PBI_NavigationStepName = Navigation\n\n\tannotation PBI_ResultType = Table\n\n')
    path.write_text(s, encoding="utf-8")
    return [x[1] for x in M]


if __name__ == "__main__":
    names = write(Path("/home/claude/out/Shell_Energy_Analytics.SemanticModel/definition/tables/_Measures.tmdl"))
    print(len(names), "measures")
