"""Step 2 | Mobility facts per year: retail sales (daily x site x product) and EV charging (daily x EV site).

Usage: python gen_mobility.py 2020   (one year per run, keeps memory low)
"""
import sys
import numpy as np
import pandas as pd
from common import *

WD_FUEL = {"Motorway": [1.00, 1.00, 1.00, 1.03, 1.15, 1.12, 1.05],
           "Urban": [1.02, 1.02, 1.02, 1.03, 1.08, 0.92, 0.78],
           "Rural": [1.00, 1.00, 1.00, 1.00, 1.05, 1.00, 0.85]}
WD_SHOP = [0.95, 0.95, 0.97, 1.00, 1.08, 1.10, 0.95]
SHOP_BASE = {"Motorway": 5200, "Urban": 3600, "Rural": 1900}
EUROPE = set(CTRY.loc[CTRY.region == "Europe", "country_code"])


def retail(year):
    r = rng(10, year)
    s = pd.read_csv(WORK / "sites_clean.csv", parse_dates=["opening_date", "ev_since_date"])
    c = CTRY.set_index("country_code")
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    nS, nD = len(s), len(dates)
    t = (dates - pd.Timestamp("2020-01-01")).days.values / 365.25
    is_eu = s.country_code.isin(EUROPE).values
    open_ = dates.values[None, :] >= s.opening_date.values[:, None]
    # EV sites lose a little fuel volume once chargers are live (cannibalisation story)
    ev_live = dates.values[None, :] >= s.ev_since_date.fillna(pd.Timestamp("2100-01-01")).values[:, None]
    wd = dates.dayofweek.values
    season = 1 + 0.06 * np.sin(2 * np.pi * (dates.dayofyear.values - 100) / 365)
    cov = covid_factor(dates)
    pidx = price_index(dates)
    trend = np.where(is_eu[:, None], 0.982 ** t[None, :], 1.008 ** t[None, :])
    wdf = np.vstack([np.array(WD_FUEL[f])[wd] for f in s.site_format])
    fuel_day = s.base_litres.values[:, None] * wdf * season * cov * trend * np.where(ev_live, 0.985, 1.0)
    price_c = c.loc[s.country_code, "fuel_price"].values[:, None]
    shop_c = c.loc[s.country_code, "shop_factor"].values[:, None]

    parts = []
    for pid, pname, grp, share, pmult in PRODUCTS:
        avail = np.ones(nS, bool)
        if pid == "P04":
            avail = s.has_lpg.values
        if pid == "P06":
            avail = s.has_car_wash.values
        mask = open_ & avail[:, None]
        noise = r.lognormal(0, 0.10, (nS, nD))
        if grp == "Fuel":
            litres = fuel_day * share * noise
            dmult = 1.08 if (pid == "P02" and year == 2022) else 1.0
            price = price_c * pmult * dmult * pidx[None, :] * r.normal(1, 0.015, (nS, 1))
            rev = litres * price
            margin = (0.14 if pid == "P03" else 0.095) - 0.015 * (pidx[None, :] - 1) + r.normal(0, 0.008, (nS, nD))
            cost = rev * (1 - margin)
            tx = litres / r.normal(38, 3, (nS, nD))
        else:
            base = np.array([SHOP_BASE[f] for f in s.site_format])[:, None] * shop_c
            if pid == "P06":
                base = base * 0.12
            rev = base * 1.045 ** t[None, :] * cov * np.array(WD_SHOP)[wd] * noise
            cost = rev * (1 - (0.55 if pid == "P06" else 0.31) + r.normal(0, 0.01, (nS, nD)))
            litres = np.full((nS, nD), np.nan)
            tx = rev / (12 if pid == "P06" else 9 * np.sqrt(shop_c))
        si, di = np.nonzero(mask)
        parts.append(pd.DataFrame({
            "transaction_date": dates.values[di], "site_id": s.site_id.values[si], "product": pname,
            "product_group": grp, "country_code": s.country_code.values[si],
            "volume_litres": np.round(litres[si, di], 1), "revenue_usd": np.round(rev[si, di], 2),
            "cost_usd": np.round(cost[si, di], 2), "transactions": np.round(tx[si, di]).astype(int)}))
    df = pd.concat(parts, ignore_index=True)
    df["record_updated_at"] = df.transaction_date + pd.Timedelta(hours=26) + pd.to_timedelta(r.integers(0, 240, len(df)), "m")

    # ---- clean monthly aggregate (truth) for financials / emissions / targets
    df["month"] = df.transaction_date.values.astype("datetime64[M]")
    agg = df.groupby(["month", "country_code", "product_group"], as_index=False).agg(
        litres=("volume_litres", "sum"), revenue=("revenue_usd", "sum"), cost=("cost_usd", "sum"))
    sites_m = df.groupby(["month", "country_code"]).site_id.nunique().rename("sites").reset_index()
    agg.merge(sites_m, on=["month", "country_code"]).to_csv(WORK / f"retail_monthly_{year}.csv", index=False)

    # ---- dirt
    raw = df[["transaction_date", "site_id", "product", "volume_litres", "revenue_usd", "cost_usd",
              "transactions", "record_updated_at"]].copy()
    # late corrections: an older, wrong version of 0.5% of fuel rows
    fi = np.flatnonzero((df.product_group.values == "Fuel") & (r.random(len(df)) < 0.005))
    old = raw.iloc[fi].copy()
    k = r.uniform(0.85, 1.15, len(fi))
    for col in ["volume_litres", "revenue_usd", "cost_usd"]:
        old[col] = (old[col] * k).round(2)
    raw.loc[raw.index[fi], "record_updated_at"] = raw.record_updated_at.iloc[fi] + pd.to_timedelta(r.integers(3, 20, len(fi)), "D")
    raw = pd.concat([raw, old], ignore_index=True)
    raw = add_duplicates(raw, r, 0.015)
    n = len(raw)
    # impossible values
    neg = np.flatnonzero((r.random(n) < 0.002) & raw.volume_litres.notna().values)
    raw.loc[neg, "volume_litres"] = -raw.loc[neg, "volume_litres"]
    big = np.flatnonzero((r.random(n) < 0.001) & raw.volume_litres.notna().values)
    raw.loc[big, "volume_litres"] = raw.loc[big, "volume_litres"] * 1000
    # orphans
    orph = np.flatnonzero(r.random(n) < 0.002)
    raw.loc[orph, "site_id"] = ["S9" + str(x).zfill(3) for x in r.integers(0, 999, len(orph))]
    # product name variants
    pv = np.flatnonzero(r.random(n) < 0.02)
    raw.loc[pv, "product"] = [PRODUCT_VARIANTS[p][r.integers(len(PRODUCT_VARIANTS[p]))] for p in raw.loc[pv, "product"]]
    # text formatting
    raw["transaction_date"] = fmt_dates(raw.transaction_date, r, 0.03)
    raw["record_updated_at"] = raw.record_updated_at.dt.strftime("%Y-%m-%d %H:%M:%S")
    raw["volume_litres"] = blank(raw.volume_litres.map(lambda v: "" if pd.isna(v) else f"{v:.1f}"), r, 0.006)
    raw["revenue_usd"] = blank(fmt_num(raw.revenue_usd, r, 0.02), r, 0.004)
    raw["cost_usd"] = fmt_num(raw.cost_usd, r, 0.02)
    write(raw, f"retail_sales/retail_sales_{year}.csv")


def ev(year):
    r = rng(20, year)
    s = pd.read_csv(WORK / "sites_clean.csv", parse_dates=["opening_date", "ev_since_date"])
    s = s[s.ev_since_date.notna()].reset_index(drop=True)
    c = CTRY.set_index("country_code")
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    t = (dates - pd.Timestamp("2020-01-01")).days.values / 365.25
    live = dates.values[None, :] >= s.ev_since_date.values[:, None]
    days_on = (dates.values[None, :] - s.ev_since_date.values[:, None]).astype("timedelta64[D]").astype(float)
    ramp = 0.25 + 0.75 * np.clip(days_on / 150, 0, 1)
    adopt = 0.22 + 0.78 * np.clip(t / 5.9, 0, 1) ** 1.2
    wd = np.array([1.0, 1.0, 1.0, 1.02, 1.1, 1.08, 0.95])[dates.dayofweek.values]
    lam = (s.ev_charge_points.values[:, None] * (1.0 + 5.0 * adopt[None, :]) * ramp
           * c.loc[s.country_code, "ev_factor"].values[:, None] * wd * covid_factor(dates))
    lam = np.where(live, np.clip(lam, 0.1, None), 0.1)
    sessions = r.poisson(lam)
    kwh = np.clip(r.normal(24 + 1.6 * t[None, :], 5, lam.shape), 8, None)
    mwh = sessions * kwh / 1000
    pw = np.where(dates.year == 2022, 1.25, 1.0) * (1 + 0.02 * t)
    rev = mwh * 1000 * c.loc[s.country_code, "ev_price"].values[:, None] * pw[None, :]
    mins = np.clip(r.normal(36 - 1.3 * t[None, :], 6, lam.shape), 10, None)
    si, di = np.nonzero(live)
    df = pd.DataFrame({"charge_date": dates.values[di], "site_id": s.site_id.values[si],
                       "country_code": s.country_code.values[si], "sessions": sessions[si, di],
                       "energy_mwh": np.round(mwh[si, di], 3), "revenue_usd": np.round(rev[si, di], 2),
                       "avg_session_minutes": np.round(mins[si, di], 1)})
    df["month"] = df.charge_date.values.astype("datetime64[M]")
    agg = df.groupby(["month", "country_code"], as_index=False).agg(
        sessions=("sessions", "sum"), mwh=("energy_mwh", "sum"), revenue=("revenue_usd", "sum"),
        ev_sites=("site_id", "nunique"))
    agg.to_csv(WORK / f"ev_monthly_{year}.csv", index=False)

    raw = df[["charge_date", "site_id", "sessions", "energy_mwh", "revenue_usd", "avg_session_minutes"]].copy()
    raw = add_duplicates(raw, r, 0.015)
    n = len(raw)
    fut = np.flatnonzero(r.random(n) < 0.001)
    raw.loc[fut, "charge_date"] = raw.loc[fut, "charge_date"] + pd.DateOffset(years=2)
    orph = np.flatnonzero(r.random(n) < 0.002)
    raw.loc[orph, "site_id"] = ["S9" + str(x).zfill(3) for x in r.integers(0, 999, len(orph))]
    raw["charge_date"] = fmt_dates(raw.charge_date, r, 0.03)
    raw["sessions"] = blank(raw.sessions.astype(str), r, 0.01)
    raw["revenue_usd"] = fmt_num(raw.revenue_usd, r, 0.02)
    write(raw, f"ev_charging/ev_charging_{year}.csv")


if __name__ == "__main__":
    y = int(sys.argv[1])
    retail(y)
    ev(y)
