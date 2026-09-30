"""Step 1 | master data: countries, segments, products, sites, assets."""
import numpy as np
import pandas as pd
from common import *

STREETS = ["High Street", "Ring Road", "Station Road", "Park Avenue", "Harbour Way", "Airport Road",
           "Market Square", "North Gate", "Riverside", "Motorway Services", "Central", "West End"]

ASSETS = [  # id, name, type, country, segment, start, capacity, unit, oil_share, unit_cost, decline
    ("A01", "North Sea Alpha", "Oil field", "GB", 1, "2004-06-01", 55000, "boe/d", 0.80, 16, 0.07),
    ("A02", "North Sea Kestrel", "Oil field", "GB", 1, "2011-03-01", 38000, "boe/d", 0.75, 18, 0.08),
    ("A03", "Gulf Deepwater Atlas", "Oil field", "US", 1, "2014-09-01", 120000, "boe/d", 0.85, 9, 0.05),
    ("A04", "Gulf Deepwater Orion", "Oil field", "US", 1, "2017-02-01", 95000, "boe/d", 0.82, 10, 0.05),
    ("A05", "Gulf Deepwater Vega", "Oil field", "US", 1, "2023-07-01", 60000, "boe/d", 0.88, 8, 0.02),
    ("A06", "Santos Pre-salt Lira", "Oil field", "BR", 1, "2016-11-01", 140000, "boe/d", 0.90, 6, 0.03),
    ("A07", "Santos Pre-salt Aurora", "Oil field", "BR", 1, "2022-04-01", 110000, "boe/d", 0.90, 6, 0.02),
    ("A08", "Niger Delta Onshore", "Oil field", "NG", 1, "1998-01-01", 70000, "boe/d", 0.70, 14, 0.06),
    ("A09", "Oman Block Sahara", "Oil field", "OM", 1, "2009-05-01", 90000, "boe/d", 0.75, 11, 0.04),
    ("A10", "Caspian Karak", "Oil field", "KZ", 1, "2012-08-01", 65000, "boe/d", 0.60, 12, 0.04),
    ("A11", "Dutch North Gas", "Gas field", "NL", 1, "1995-01-01", 45000, "boe/d", 0.05, 7, 0.14),
    ("A12", "West Delta Gas", "Gas field", "EG", 1, "2013-04-01", 80000, "boe/d", 0.10, 5, 0.05),
    ("A13", "Oman Gas Block 10", "Gas field", "OM", 1, "2019-01-01", 60000, "boe/d", 0.08, 6, 0.03),
    ("A14", "Sabah Deep Gas", "Gas field", "MY", 1, "2015-10-01", 75000, "boe/d", 0.15, 8, 0.05),
    ("A15", "Nigeria Offshore Gas", "Gas field", "NG", 1, "2010-06-01", 50000, "boe/d", 0.20, 9, 0.05),
    ("A16", "Karak Condensate", "Gas field", "KZ", 1, "2012-08-01", 55000, "boe/d", 0.30, 10, 0.04),
    ("A17", "Northwest Shelf Gas", "Gas field", "AU", 1, "2008-03-01", 85000, "boe/d", 0.10, 7, 0.05),
    ("A18", "Qatar North Gas", "Gas field", "QA", 1, "2011-01-01", 100000, "boe/d", 0.10, 4, 0.02),
    ("A19", "Campos Gas Hub", "Gas field", "BR", 1, "2021-02-01", 40000, "boe/d", 0.20, 7, 0.02),
    ("L01", "Bonny Coast LNG", "LNG plant", "NG", 2, "2002-01-01", 8.0, "Mtpa", 0.0, 3.5, 0.01),
    ("L02", "Ras Qatar LNG", "LNG plant", "QA", 2, "2011-01-01", 7.8, "Mtpa", 0.0, 2.5, 0.00),
    ("L03", "Sur Oman LNG", "LNG plant", "OM", 2, "2006-01-01", 6.0, "Mtpa", 0.0, 3.0, 0.01),
    ("L04", "Timor Floating LNG", "LNG plant", "AU", 2, "2019-06-01", 3.6, "Mtpa", 0.0, 6.0, 0.00),
    ("L05", "Queensland Coast LNG", "LNG plant", "AU", 2, "2015-01-01", 8.5, "Mtpa", 0.0, 4.5, 0.01),
    ("L06", "Pacific North LNG", "LNG plant", "CA", 2, "2025-07-01", 14.0, "Mtpa", 0.0, 4.0, 0.00),
]
ASSET_COLS = ["asset_id", "asset_name", "asset_type", "country_code", "segment_id", "start_date",
              "capacity_value", "capacity_unit", "oil_share", "unit_cost", "decline"]


def build_sites():
    r = rng(1)
    rows, n = [], 0
    for c in CTRY.itertuples():
        for _ in range(c.sites):
            n += 1
            city, lat, lon = CITIES[c.country_code][r.integers(len(CITIES[c.country_code]))]
            fmt = r.choice(["Motorway", "Urban", "Rural"], p=[0.2, 0.5, 0.3])
            if r.random() < 0.08:
                opening = pd.Timestamp("2020-01-01") + pd.Timedelta(days=int(r.integers(0, 2008)))
            else:
                opening = pd.Timestamp("1995-01-01") + pd.Timedelta(days=int(r.integers(0, 9100)))
            p_ev = min(0.85, 0.35 * c.ev_factor + 0.10) * (1.25 if fmt == "Motorway" else 1)
            ev_since = pd.NaT
            if r.random() < p_ev:
                if r.random() < 0.10:
                    ev_since = pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(r.integers(0, 730)))
                else:  # rollout accelerates over time
                    ev_since = pd.Timestamp("2020-01-01") + pd.Timedelta(days=int(2150 * r.random() ** 0.7))
                ev_since = max(ev_since, opening + pd.Timedelta(days=30))
                if ev_since > END:
                    ev_since = pd.NaT
            rows.append(dict(
                site_id=f"S{n:04d}",
                site_name=f"Shell {city} {STREETS[r.integers(len(STREETS))]}",
                city=city, country_code=c.country_code,
                latitude=round(lat + r.normal(0, 0.12), 5), longitude=round(lon + r.normal(0, 0.15), 5),
                site_format=fmt, opening_date=opening.normalize(),
                has_ev_charging="Y" if pd.notna(ev_since) else "N",
                ev_since_date=ev_since.normalize() if pd.notna(ev_since) else pd.NaT,
                ev_charge_points=int(r.integers(2, 13)) if pd.notna(ev_since) else 0,
                has_lpg=r.random() < (0.45 if c.region == "Europe" else 0.15),
                has_car_wash=r.random() < 0.6,
                base_litres=float({"Motorway": 26000, "Urban": 14000, "Rural": 8000}[fmt] * r.lognormal(0, 0.3)
                                  * {"US": 1.3, "CA": 1.1}.get(c.country_code, 1.0)),
            ))
    return pd.DataFrame(rows)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    r = rng(2)
    # ---- clean-ish reference files
    write(CTRY[["country_code", "country_name", "region"]], "master/countries.csv")
    write(pd.DataFrame(SEGMENTS, columns=["segment_id", "segment_name"]), "master/segments.csv")
    write(pd.DataFrame([p[:3] for p in PRODUCTS], columns=["product_id", "product_name", "product_group"]),
          "master/products.csv")

    # ---- sites (dirty)
    s = build_sites()
    s.to_csv(WORK / "sites_clean.csv", index=False)
    raw = s[["site_id", "site_name", "city", "country_code", "latitude", "longitude", "site_format",
             "opening_date", "has_ev_charging", "ev_since_date", "ev_charge_points"]].copy()
    raw["country"] = messy_country(raw.country_code, r, 0.05)
    raw = raw.drop(columns="country_code")
    i = np.flatnonzero(r.random(len(raw)) < 0.03)
    raw.loc[i, "city"] = "  " + raw.loc[i, "city"].str.upper() + " "
    raw["opening_date"] = fmt_dates(raw.opening_date, r, 0.03)
    ev = raw.ev_since_date.notna()
    raw["ev_since_date"] = ""
    raw.loc[ev, "ev_since_date"] = fmt_dates(s.ev_since_date[ev], r, 0.03)
    i = np.flatnonzero(r.random(len(raw)) < 0.05)
    raw.loc[i, "has_ev_charging"] = raw.loc[i, "has_ev_charging"].map(
        lambda v: r.choice(["yes", "TRUE", "1"]) if v == "Y" else r.choice(["no", "FALSE", "0"]))
    for col in ["latitude", "longitude"]:
        raw[col] = raw[col].astype(str)
        raw.loc[np.flatnonzero(r.random(len(raw)) < 0.01), col] = ""
    raw = pd.concat([raw, raw.sample(3, random_state=1)]).sample(frac=1, random_state=2)
    cols = ["site_id", "site_name", "city", "country", "latitude", "longitude", "site_format",
            "opening_date", "has_ev_charging", "ev_since_date", "ev_charge_points"]
    write(raw[cols], "master/sites.csv")

    # ---- assets (light dirt)
    a = pd.DataFrame(ASSETS, columns=ASSET_COLS)
    a.to_csv(WORK / "assets_clean.csv", index=False)
    araw = a[["asset_id", "asset_name", "asset_type", "country_code", "segment_id", "start_date",
              "capacity_value", "capacity_unit"]].copy()
    araw["country"] = messy_country(araw.country_code, r, 0.15)
    araw = araw.drop(columns="country_code")
    araw.loc[[3, 12], "asset_name"] = araw.loc[[3, 12], "asset_name"] + "  "
    araw.loc[[7], "asset_type"] = "oil field"
    araw = araw[["asset_id", "asset_name", "asset_type", "country", "segment_id", "start_date",
                 "capacity_value", "capacity_unit"]]
    write(araw, "master/assets.csv")


if __name__ == "__main__":
    main()
