"""Step 3 | Upstream & Integrated Gas: monthly production, downtime events, LNG sales."""
import numpy as np
import pandas as pd
from common import *

MONTHS = pd.date_range(START, END, freq="MS")
CAUSES = ["Planned maintenance", "Unplanned", "Weather", "Third party"]
CAUSE_VARIANTS = {"Planned maintenance": ["planned maintenance", "Planned Maint.", "PLANNED MAINTENANCE "],
                  "Unplanned": ["unplanned", "UNPLANNED", " Unplanned"],
                  "Weather": ["weather", "WEATHER ", "Weather/Storm"],
                  "Third party": ["third party", "3rd party", "THIRD PARTY"]}
LNG_DEST = {"L01": ["JP", "ES", "GB", "IN", "CN"], "L02": ["JP", "KR", "CN", "IN", "GB", "PL"],
            "L03": ["KR", "JP", "IN", "CN"], "L04": ["JP", "KR", "CN"],
            "L05": ["CN", "JP", "KR", "SG"], "L06": ["JP", "KR", "CN"]}
JKM_YEAR = {2020: 4.4, 2021: 18.0, 2022: 34.0, 2023: 14.0, 2024: 11.9, 2025: 11.5}
JKM_SHAPE = [1.15, 1.05, 0.9, 0.85, 0.85, 0.9, 0.95, 1.05, 1.05, 1.05, 1.1, 1.1]
BOE_PER_MT = 8.9e6          # boe of gas per tonne-million LNG (approx.)
MMBTU_PER_MT = 52e6


def downtime(a, r):
    rows, eid = [], 0
    offshore_storm = a.country_code in ("GB", "US", "AU")
    for y in YEARS:
        spec = [("Planned maintenance", 1 + (y % 2 == int(a.asset_id[-1]) % 2), (24, 72)),
                ("Unplanned", r.poisson(7), (2, 60)),
                ("Weather", r.poisson(3 if offshore_storm else 1), (6, 96)),
                ("Third party", r.poisson(2.5 if a.country_code == "NG" else 0.5), (4, 72))]
        for cause, k, (lo, hi) in spec:
            for j in range(int(k)):
                month = r.integers(8, 11) if (cause == "Weather" and a.country_code == "US") else r.integers(1, 13)
                start = pd.Timestamp(y, month, 1) + pd.Timedelta(hours=int(r.integers(0, 24 * 27)))
                hrs = float(r.uniform(lo, hi))
                if cause == "Planned maintenance" and j == 1:
                    hrs = float(r.uniform(240, 480))   # turnaround every other year
                rows.append((a.asset_id, start, start + pd.Timedelta(hours=hrs), round(hrs, 1), cause))
    return rows


def main():
    r = rng(30)
    assets = pd.read_csv(WORK / "assets_clean.csv", parse_dates=["start_date"])

    # ---------------- downtime events
    ev = []
    for a in assets.itertuples():
        ev += downtime(a, r)
    dt = pd.DataFrame(ev, columns=["asset_id", "start_ts", "end_ts", "downtime_hours", "cause"])
    dt = dt[dt.start_ts <= END].sort_values("start_ts").reset_index(drop=True)
    dt.insert(0, "event_id", [f"E{i:05d}" for i in range(1, len(dt) + 1)])
    dt["month"] = dt.start_ts.values.astype("datetime64[M]")
    dt_m = dt.groupby(["asset_id", "month"]).downtime_hours.sum()

    # ---------------- production
    rows = []
    for a in assets.itertuples():
        cap_d = a.capacity_value * BOE_PER_MT / 365 if a.capacity_unit == "Mtpa" else a.capacity_value
        for m in MONTHS:
            if m < a.start_date.to_period("M").to_timestamp():
                continue
            days = m.days_in_month
            yrs = (m - START).days / 365.25
            months_on = (m.year - a.start_date.year) * 12 + m.month - a.start_date.month
            ramp = min(1.0, 0.35 + 0.65 * months_on / 9) if a.start_date >= START else 1.0
            act_decl = (1 - a.decline) ** yrs if a.start_date < START else (1 - a.decline) ** max(0, (m - a.start_date).days / 365.25)
            plan_decl = (1 - a.decline * 0.8) ** yrs if a.start_date < START else (1 - a.decline * 0.8) ** max(0, (m - a.start_date).days / 365.25)
            hrs_down = dt_m.get((a.asset_id, m), 0.0)
            uptime = max(0.35, 1 - hrs_down / (24 * days)) * 0.985
            opec = 0.92 if (a.oil_share > 0.5 and pd.Timestamp("2020-05-01") <= m <= pd.Timestamp("2020-12-01")) else 1.0
            total = cap_d * days * act_decl * ramp * uptime * opec * r.normal(1, 0.025)
            planned = cap_d * days * plan_decl * min(1.0, ramp + 0.1) * 0.95
            oil = total * a.oil_share
            opex = total * a.unit_cost * 1.03 ** yrs + cap_d * 30 * 2.2
            rows.append((m, a.asset_id, a.segment_id, a.country_code, round(oil), round(total - oil),
                         round(total), round(opex, 2), round(planned)))
    prod = pd.DataFrame(rows, columns=["production_month", "asset_id", "segment_id", "country_code", "oil_bbl",
                                       "gas_boe", "total_boe", "opex_usd", "planned_boe"])
    prod["record_updated_at"] = prod.production_month + pd.DateOffset(months=1) + pd.to_timedelta(r.integers(24, 240, len(prod)), "h")
    prod.to_csv(WORK / "production_clean.csv", index=False)

    # ---------------- LNG sales
    lrows = []
    lng = prod[prod.asset_id.str.startswith("L")]
    for p in lng.itertuples():
        mt = p.gas_boe / BOE_PER_MT * 0.97
        dests = LNG_DEST[p.asset_id]
        w = r.dirichlet(np.ones(len(dests)) * 3)
        y, mo = p.production_month.year, p.production_month.month
        b3 = brent(*(p.production_month - pd.DateOffset(months=3)).timetuple()[:2]) if p.production_month >= pd.Timestamp("2020-04-01") else 60
        lt_price = 0.13 * b3 + 0.5
        spot_price = JKM_YEAR[y] * JKM_SHAPE[mo - 1] * r.normal(1, 0.06)
        spot_share = {2020: 0.25, 2021: 0.28, 2022: 0.38, 2023: 0.33, 2024: 0.30, 2025: 0.30}[y]
        for d, wi in zip(dests, w):
            eu = d in ("GB", "ES", "PL")
            ss = min(0.9, spot_share * (1.8 if (eu and y >= 2022) else 1.0))
            for ctype, share, price in [("Long-term", 1 - ss, lt_price), ("Spot", ss, spot_price)]:
                vol = mt * wi * share
                lrows.append((p.production_month, p.asset_id, d, ctype, round(vol, 4), round(vol * MMBTU_PER_MT * price, 2)))
    ls = pd.DataFrame(lrows, columns=["sale_month", "plant_asset_id", "destination_code", "contract_type", "volume_mt", "revenue_usd"])
    ls.to_csv(WORK / "lng_clean.csv", index=False)

    # ---------------- dirt: production
    raw = prod[["production_month", "asset_id", "oil_bbl", "gas_boe", "total_boe", "opex_usd", "planned_boe", "record_updated_at"]].copy()
    fi = np.flatnonzero(r.random(len(raw)) < 0.02)       # small table: 2% late corrections
    old = raw.iloc[fi].copy()
    k = r.uniform(0.85, 1.15, len(fi))
    for col in ["oil_bbl", "gas_boe", "total_boe"]:
        old[col] = (old[col] * k).round()
    raw.loc[raw.index[fi], "record_updated_at"] = raw.record_updated_at.iloc[fi] + pd.to_timedelta(r.integers(5, 25, len(fi)), "D")
    raw = add_duplicates(pd.concat([raw, old], ignore_index=True), r, 0.015)
    n = len(raw)
    neg = np.flatnonzero(r.random(n) < 0.004)
    raw.loc[neg, "total_boe"] = -raw.loc[neg, "total_boe"]
    orph = np.flatnonzero(r.random(n) < 0.004)
    raw.loc[orph, "asset_id"] = "A99"
    raw["production_month"] = fmt_dates(raw.production_month, r, 0.03)
    raw["record_updated_at"] = raw.record_updated_at.dt.strftime("%Y-%m-%d %H:%M:%S")
    raw["opex_usd"] = fmt_num(raw.opex_usd, r, 0.02)
    write(raw, "upstream/production_monthly.csv")

    # ---------------- dirt: downtime
    draw = dt[["event_id", "asset_id", "start_ts", "end_ts", "downtime_hours", "cause"]].copy()
    n = len(draw)
    sw = np.flatnonzero(r.random(n) < 0.004)
    draw.loc[sw, ["start_ts", "end_ts"]] = draw.loc[sw, ["end_ts", "start_ts"]].values
    cv = np.flatnonzero(r.random(n) < 0.05)
    draw.loc[cv, "cause"] = [CAUSE_VARIANTS[c][r.integers(3)] for c in draw.loc[cv, "cause"]]
    orph = np.flatnonzero(r.random(n) < 0.003)
    draw.loc[orph, "asset_id"] = "A99"
    draw = add_duplicates(draw, r, 0.015)
    draw["start_ts"] = fmt_dates(draw.start_ts, r, 0.03, with_time=True)
    draw["end_ts"] = fmt_dates(draw.end_ts, r, 0.03, with_time=True)
    draw["downtime_hours"] = blank(draw.downtime_hours.astype(str), r, 0.02)
    write(draw, "upstream/asset_downtime_events.csv")

    # ---------------- dirt: LNG
    lraw = ls.copy()
    lraw["destination_country"] = messy_country(lraw.destination_code, r, 0.05)
    lraw = lraw.drop(columns="destination_code")
    ct = np.flatnonzero(r.random(len(lraw)) < 0.04)
    lraw.loc[ct, "contract_type"] = [r.choice(["long-term", "LT", "LONG TERM"]) if c == "Long-term" else r.choice(["spot", "SPOT ", "Spot cargo"]) for c in lraw.loc[ct, "contract_type"]]
    lraw = add_duplicates(lraw, r, 0.015)
    lraw["sale_month"] = fmt_dates(lraw.sale_month, r, 0.03)
    lraw["revenue_usd"] = fmt_num(lraw.revenue_usd, r, 0.02)
    lraw = lraw[["sale_month", "plant_asset_id", "destination_country", "contract_type", "volume_mt", "revenue_usd"]]
    write(lraw, "upstream/lng_sales_monthly.csv")

    # quick sanity
    yr = prod.assign(y=prod.production_month.dt.year).groupby(["y", "segment_id"]).total_boe.sum().unstack()
    print((yr.div(pd.Series({y: 366 if y % 4 == 0 else 365 for y in YEARS}), axis=0) / 1000).round(0))
    print(ls.assign(y=ls.sale_month.dt.year).groupby("y")[["volume_mt", "revenue_usd"]].sum().round(1))


if __name__ == "__main__":
    main()
