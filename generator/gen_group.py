"""Step 4 | Group-level facts derived from the operational truth: financials, emissions, targets."""
import numpy as np
import pandas as pd
from common import *

SEG = dict(SEGMENTS)
CP_COUNTRIES = {"NL": 1.0, "DE": 0.7, "US": 0.9, "SG": 0.8, "GB": 0.4}
RES_COUNTRIES = {"GB": 1.0, "NL": 0.8, "DE": 0.7, "US": 0.9, "AU": 0.5}


def load():
    retail = pd.concat([pd.read_csv(WORK / f"retail_monthly_{y}.csv", parse_dates=["month"]) for y in YEARS])
    ev = pd.concat([pd.read_csv(WORK / f"ev_monthly_{y}.csv", parse_dates=["month"]) for y in YEARS])
    prod = pd.read_csv(WORK / "production_clean.csv", parse_dates=["production_month"])
    lng = pd.read_csv(WORK / "lng_clean.csv", parse_dates=["sale_month"])
    assets = pd.read_csv(WORK / "assets_clean.csv")
    return retail, ev, prod, lng, assets


def main():
    r = rng(40)
    retail, ev, prod, lng, assets = load()
    months = pd.date_range(START, END, freq="MS")
    t_of = lambda m: (m - START).days / 365.25
    b_of = lambda m: brent(m.year, m.month)
    fin, emi = [], []

    # ---------- Upstream (segment 1) and Integrated Gas (segment 2) by asset country
    lng_plant_country = assets.set_index("asset_id").country_code
    lng_rev = lng.assign(country_code=lng.plant_asset_id.map(lng_plant_country)).groupby(["sale_month", "country_code"]).agg(
        rev=("revenue_usd", "sum"), mt=("volume_mt", "sum"))
    pc = prod.groupby(["production_month", "segment_id", "country_code"]).agg(
        oil=("oil_bbl", "sum"), gas=("gas_boe", "sum"), total=("total_boe", "sum"), opex=("opex_usd", "sum")).reset_index()
    for p in pc.itertuples():
        m, t = p.production_month, t_of(p.production_month)
        if p.segment_id == 1:
            rev = p.oil * b_of(m) * r.normal(0.97, 0.01) + p.gas * b_of(m) * 0.55
            cost = p.opex + rev * 0.14
            capex = p.total * r.uniform(6, 9)
            s1 = p.total * (0.021 if p.oil > p.gas else 0.012) * 0.965 ** t
            emi += [(m, 1, p.country_code, 1, s1), (m, 1, p.country_code, 2, s1 * 0.08),
                    (m, 1, p.country_code, 3, p.oil * 0.43 + p.gas * 0.33)]
        else:
            lr = lng_rev.loc[(m, p.country_code)] if (m, p.country_code) in lng_rev.index else pd.Series({"rev": 0, "mt": 0})
            rev = lr.rev
            cost = p.opex + rev * 0.38
            capex = p.total * r.uniform(3, 5) + (180e6 if (p.country_code == "CA") else 0)
            mt = lr.mt
            emi += [(m, 2, p.country_code, 1, mt * 1e6 * 0.32 * 0.975 ** t), (m, 2, p.country_code, 2, mt * 1e6 * 0.016),
                    (m, 2, p.country_code, 3, mt * 1e6 * 2.75)]
        fin.append((m, p.segment_id, p.country_code, rev, cost, capex))
    # LNG Canada construction capex before first cargo (no production rows yet)
    for m in months[months < pd.Timestamp("2025-07-01")]:
        fin.append((m, 2, "CA", 0.0, 2.5e6, r.uniform(150e6, 260e6)))

    # ---------- Mobility (segment 3)
    rp = retail.pivot_table(index=["month", "country_code"], columns="product_group",
                            values=["litres", "revenue", "cost"], aggfunc="sum")
    sites = retail.groupby(["month", "country_code"]).sites.max()
    evm = ev.set_index(["month", "country_code"])
    for (m, cc), row in rp.iterrows():
        t = t_of(m)
        ev_rev = evm.revenue.get((m, cc), 0.0)
        ev_sites = evm.ev_sites.get((m, cc), 0)
        n = sites[(m, cc)]
        rev = row[("revenue", "Fuel")] + row[("revenue", "Non-fuel")] + ev_rev
        cost = row[("cost", "Fuel")] + row[("cost", "Non-fuel")] + ev_rev * 0.55 + n * 38000 * 1.025 ** t
        capex = n * 6000 + ev_sites * r.uniform(9000, 14000)
        fin.append((m, 3, cc, rev, cost, capex))
        emi += [(m, 3, cc, 1, n * 1.6 * 0.97 ** t), (m, 3, cc, 2, n * 9.0 * 0.90 ** t),
                (m, 3, cc, 3, row[("litres", "Fuel")] * 0.00245)]

    # ---------- Chemicals & Products (4) and Renewables & Energy Solutions (5)
    for m in months:
        t, pidx = t_of(m), 0.72 + 0.28 * b_of(m) / 71
        margin = {2020: 0.05, 2021: 0.08, 2022: 0.16, 2023: 0.10, 2024: 0.07, 2025: 0.06}[m.year]
        for cc, w in CP_COUNTRIES.items():
            rev = 190e6 * w * pidx * r.normal(1, 0.04) * (0.8 if m.year == 2020 and m.month in (4, 5) else 1)
            fin.append((m, 4, cc, rev, rev * (1 - margin * r.normal(1, 0.08)), 35e6 * w * r.normal(1, 0.15)))
            s1 = 160e3 * w * 0.975 ** t * r.normal(1, 0.03)
            emi += [(m, 4, cc, 1, s1), (m, 4, cc, 2, s1 * 0.15), (m, 4, cc, 3, rev / 1000 * 3.1)]
        for cc, w in RES_COUNTRIES.items():
            spike = 1.6 if m.year == 2022 else 1.0
            rev = 45e6 * w * 1.28 ** t * spike * r.normal(1, 0.06)
            fin.append((m, 5, cc, rev, rev * r.normal(0.93, 0.02), 22e6 * w * 1.22 ** t * r.normal(1, 0.15)))
            emi += [(m, 5, cc, 1, 800 * w), (m, 5, cc, 2, 2200 * w * 0.85 ** t), (m, 5, cc, 3, 16000 * w * 1.2 ** t)]

    f = pd.DataFrame(fin, columns=["month", "segment_id", "country_code", "revenue_usd", "operating_cost_usd", "capex_usd"])
    f["ebitda_usd"] = f.revenue_usd - f.operating_cost_usd
    f.to_csv(WORK / "financials_clean.csv", index=False)
    e = pd.DataFrame(emi, columns=["month", "segment_id", "country_code", "scope", "tco2e"])
    e["tco2e"] = (e.tco2e * r.normal(1, 0.02, len(e))).round(1)
    e.to_csv(WORK / "emissions_clean.csv", index=False)

    # ---------- dirt: financials
    fr = f.copy()
    fr["segment"] = fr.segment_id.map(SEG)
    fr["country"] = messy_country(fr.country_code, r, 0.05)
    bad = np.flatnonzero(r.random(len(fr)) < 0.01)          # EBITDA not equal to revenue - cost
    fr.loc[bad, "ebitda_usd"] = fr.loc[bad, "ebitda_usd"] * r.uniform(0.5, 1.5, len(bad))
    sv = np.flatnonzero(r.random(len(fr)) < 0.02)
    fr.loc[sv, "segment"] = [r.choice([s.upper(), s.lower(), " " + s]) for s in fr.loc[sv, "segment"]]
    fr = add_duplicates(fr, r, 0.015)
    fr["financial_month"] = fmt_dates(fr.month, r, 0.03)
    for col in ["revenue_usd", "operating_cost_usd", "ebitda_usd", "capex_usd"]:
        fr[col] = fmt_num(fr[col], r, 0.02)
    write(fr[["financial_month", "segment", "country", "revenue_usd", "operating_cost_usd", "ebitda_usd", "capex_usd"]],
          "group/financials_monthly.csv")

    # ---------- dirt: emissions
    er = e.copy()
    er["segment"] = er.segment_id.map(SEG)
    er["country"] = messy_country(er.country_code, r, 0.05)
    er["scope"] = "Scope " + er.scope.astype(str)
    sv = np.flatnonzero(r.random(len(er)) < 0.03)
    er.loc[sv, "scope"] = [r.choice([s.replace("Scope ", ""), s.upper(), s.replace(" ", "")]) for s in er.loc[sv, "scope"]]
    er = add_duplicates(er, r, 0.015)
    er["emission_month"] = fmt_dates(er.month, r, 0.03)
    er["tco2e"] = fmt_num(er.tco2e, r, 0.02, decimals=1)
    write(er[["emission_month", "segment", "country", "scope", "tco2e"]], "group/emissions_monthly.csv")

    # ---------- targets (clean, small, business owned)
    ey = e.assign(y=e.month.dt.year)
    s12 = ey[ey.scope < 3].groupby("y").tco2e.sum() / 1e6
    base_s12 = s12[2020] / 0.82                       # fictitious 2016 baseline
    days = pd.Series({y: 366 if y % 4 == 0 else 365 for y in YEARS})
    plan = prod.assign(y=prod.production_month.dt.year).groupby("y").planned_boe.sum() / days / 1000
    fuel = retail[retail.product_group == "Fuel"].assign(y=lambda d: d.month.dt.year).groupby("y").litres.sum() / 1e6
    fy = f.assign(y=f.month.dt.year)
    evr = ev.assign(y=ev.month.dt.year).groupby("y").revenue.sum()
    lc = (fy[fy.segment_id == 5].groupby("y").revenue_usd.sum() + evr) / fy.groupby("y").revenue_usd.sum() * 100
    print("low-carbon share %", lc.round(2).to_dict())
    tg = []
    for y in YEARS:
        tg += [(y, "Production", "kboe/d", round(plan[y], 1)),
               (y, "Scope 1+2 emissions", "MtCO2e", round(base_s12 * (1 - 0.5 * (y - 2016) / 14), 2)),
               (y, "Fuel volume", "ML", round(fuel[y] * r.uniform(0.97, 1.03), 1)),
               (y, "EV charge points", "points", int(250 * 1.42 ** (y - 2020))),
               (y, "Low-carbon revenue share", "%", round(lc[y] * r.uniform(0.97, 1.12), 2))]
    tg += [(2030, "Scope 1+2 emissions", "MtCO2e", round(base_s12 * 0.5, 2)),
           (2030, "EV charge points", "points", 3000), (2030, "Low-carbon revenue share", "%", 25.0)]
    write(pd.DataFrame(tg, columns=["target_year", "metric", "unit", "target_value"]), "group/targets.csv")

    # sanity
    print((f.assign(y=f.month.dt.year).groupby(["y", "segment_id"]).revenue_usd.sum().unstack() / 1e9).round(1))
    print((f.assign(y=f.month.dt.year).groupby("y").ebitda_usd.sum() / 1e9).round(1).to_dict())
    print((ey.groupby(["y", "scope"]).tco2e.sum().unstack() / 1e6).round(1))


if __name__ == "__main__":
    main()
