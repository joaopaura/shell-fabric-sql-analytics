"""Shared config, master data and 'dirt' helpers for the Shell fictitious data generator.

All data is fictitious. Portfolio project, not affiliated with Shell plc.
"""
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
WORK = ROOT / "data" / "_work"
SEED = 2026
START, END = pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31")
YEARS = list(range(2020, 2026))

# --------------------------------------------------------------------------- countries
# code, name, region, mobility_sites, fuel_price_usd_per_l, shop_factor, ev_factor, ev_price_kwh
COUNTRIES = [
    ("GB", "United Kingdom", "Europe", 60, 1.75, 1.00, 1.30, 0.68),
    ("NL", "Netherlands", "Europe", 35, 2.05, 1.00, 1.50, 0.62),
    ("DE", "Germany", "Europe", 45, 1.95, 1.00, 1.20, 0.66),
    ("PL", "Poland", "Europe", 30, 1.45, 0.60, 0.80, 0.52),
    ("CH", "Switzerland", "Europe", 15, 1.90, 1.20, 1.10, 0.70),
    ("ES", "Spain", "Europe", 20, 1.65, 0.85, 0.90, 0.55),
    ("US", "United States", "Americas", 80, 0.85, 1.10, 0.90, 0.48),
    ("CA", "Canada", "Americas", 25, 1.10, 1.00, 0.80, 0.45),
    ("MX", "Mexico", "Americas", 20, 1.15, 0.50, 0.40, 0.35),
    ("IN", "India", "Asia-Pacific", 25, 1.20, 0.30, 0.35, 0.25),
    ("MY", "Malaysia", "Asia-Pacific", 25, 0.50, 0.40, 0.50, 0.30),
    ("SG", "Singapore", "Asia-Pacific", 20, 2.00, 1.10, 1.00, 0.60),
    # upstream / LNG / trading only
    ("BR", "Brazil", "Americas", 0, 0, 0, 0, 0),
    ("NG", "Nigeria", "Middle East & Africa", 0, 0, 0, 0, 0),
    ("OM", "Oman", "Middle East & Africa", 0, 0, 0, 0, 0),
    ("QA", "Qatar", "Middle East & Africa", 0, 0, 0, 0, 0),
    ("EG", "Egypt", "Middle East & Africa", 0, 0, 0, 0, 0),
    ("KZ", "Kazakhstan", "Asia-Pacific", 0, 0, 0, 0, 0),
    ("AU", "Australia", "Asia-Pacific", 0, 0, 0, 0, 0),
    ("JP", "Japan", "Asia-Pacific", 0, 0, 0, 0, 0),
    ("KR", "South Korea", "Asia-Pacific", 0, 0, 0, 0, 0),
    ("CN", "China", "Asia-Pacific", 0, 0, 0, 0, 0),
]
CTRY = pd.DataFrame(COUNTRIES, columns=["country_code", "country_name", "region", "sites",
                                        "fuel_price", "shop_factor", "ev_factor", "ev_price"])

# messy spellings used in raw files (silver maps them back through etl.country_alias)
COUNTRY_VARIANTS = {
    "GB": ["UK", "U.K.", "united kingdom", "Great Britain", "GB"],
    "NL": ["Holland", "the Netherlands", "NETHERLANDS", "NL"],
    "DE": ["Deutschland", "germany", "DE"],
    "PL": ["Polska", "POLAND", "PL"],
    "CH": ["Schweiz", "switzerland", "CH"],
    "ES": ["España", "spain", "ES"],
    "US": ["USA", "U.S.A.", "United States of America", "us"],
    "CA": ["canada", "CAN"],
    "MX": ["México", "mexico"],
    "IN": ["india", "IND"],
    "MY": ["malaysia", "MYS"],
    "SG": ["singapore", "SGP"],
    "BR": ["Brasil", "brazil"],
    "NG": ["nigeria", "NGA"],
    "OM": ["oman", "Sultanate of Oman"],
    "QA": ["qatar", "QAT"],
    "EG": ["egypt", "EGY"],
    "KZ": ["kazakhstan", "KAZ"],
    "AU": ["australia", "AUS"],
    "JP": ["japan", "JPN"],
    "KR": ["Korea", "Republic of Korea", "KOR"],
    "CN": ["china", "PRC", "CHN"],
}

CITIES = {
    "GB": [("London", 51.51, -0.13), ("Manchester", 53.48, -2.24), ("Birmingham", 52.49, -1.89), ("Glasgow", 55.86, -4.25), ("Leeds", 53.80, -1.55)],
    "NL": [("Amsterdam", 52.37, 4.90), ("Rotterdam", 51.92, 4.48), ("Utrecht", 52.09, 5.12), ("Eindhoven", 51.44, 5.47)],
    "DE": [("Berlin", 52.52, 13.40), ("Hamburg", 53.55, 9.99), ("Munich", 48.14, 11.58), ("Cologne", 50.94, 6.96), ("Frankfurt", 50.11, 8.68)],
    "PL": [("Warsaw", 52.23, 21.01), ("Krakow", 50.06, 19.94), ("Wroclaw", 51.11, 17.03), ("Gdansk", 54.35, 18.65), ("Poznan", 52.41, 16.93)],
    "CH": [("Zurich", 47.38, 8.54), ("Geneva", 46.20, 6.14), ("Basel", 47.56, 7.59)],
    "ES": [("Madrid", 40.42, -3.70), ("Barcelona", 41.39, 2.17), ("Valencia", 39.47, -0.38), ("Seville", 37.39, -5.98)],
    "US": [("Houston", 29.76, -95.37), ("Los Angeles", 34.05, -118.24), ("Chicago", 41.88, -87.63), ("New York", 40.71, -74.01), ("Atlanta", 33.75, -84.39), ("Denver", 39.74, -104.99)],
    "CA": [("Toronto", 43.65, -79.38), ("Calgary", 51.05, -114.07), ("Vancouver", 49.28, -123.12), ("Montreal", 45.50, -73.57)],
    "MX": [("Mexico City", 19.43, -99.13), ("Guadalajara", 20.67, -103.35), ("Monterrey", 25.69, -100.32)],
    "IN": [("Bengaluru", 12.97, 77.59), ("Mumbai", 19.08, 72.88), ("Chennai", 13.08, 80.27), ("Delhi", 28.70, 77.10)],
    "MY": [("Kuala Lumpur", 3.14, 101.69), ("Penang", 5.41, 100.33), ("Johor Bahru", 1.49, 103.74)],
    "SG": [("Singapore", 1.35, 103.82)],
}

SEGMENTS = [
    (1, "Upstream"), (2, "Integrated Gas"), (3, "Mobility"),
    (4, "Chemicals & Products"), (5, "Renewables & Energy Solutions"),
]

PRODUCTS = [
    ("P01", "Unleaded 95", "Fuel", 0.42, 1.00),
    ("P02", "Diesel", "Fuel", 0.40, 1.02),
    ("P03", "V-Power", "Fuel", 0.12, 1.12),
    ("P04", "LPG", "Fuel", 0.06, 0.55),
    ("P05", "Shop", "Non-fuel", 0, 0),
    ("P06", "Car Wash", "Non-fuel", 0, 0),
]
PRODUCT_VARIANTS = {
    "Unleaded 95": [" unleaded 95", "UNLEADED 95 ", "Unl 95", "Unleaded95"],
    "Diesel": ["diesel", " DIESEL", "Diesel ", "Gasoil"],
    "V-Power": ["V Power", "vpower", "V-POWER ", "VPower"],
    "LPG": ["lpg", " LPG ", "Autogas"],
    "Shop": ["shop", "SHOP ", "Convenience Shop"],
    "Car Wash": ["car wash", "Carwash", "CAR WASH "],
}

# approximate monthly Brent path (USD/bbl), annual anchors + intra-year shape
BRENT_YEAR = {2020: 42, 2021: 71, 2022: 99, 2023: 82, 2024: 80, 2025: 69}
BRENT_SHAPE = {2020: [64, 55, 32, 18, 29, 40, 43, 45, 41, 40, 43, 50],
               2021: [55, 62, 65, 65, 68, 73, 75, 71, 74, 84, 81, 74],
               2022: [86, 97, 117, 105, 113, 122, 111, 100, 90, 93, 91, 81],
               2023: [83, 83, 79, 84, 76, 75, 80, 86, 94, 91, 83, 78],
               2024: [80, 83, 85, 90, 82, 83, 85, 80, 74, 75, 74, 74],
               2025: [79, 75, 72, 67, 64, 70, 70, 67, 68, 64, 63, 62]}


def brent(year, month):
    return BRENT_SHAPE[year][month - 1]


def price_index(dates: pd.DatetimeIndex) -> np.ndarray:
    """Retail price index vs 2021 average (fuel pump prices lag and dampen crude)."""
    b = np.array([brent(d.year, d.month) for d in dates], dtype=float)
    return 0.72 + 0.28 * b / 71.0


def covid_factor(dates: pd.DatetimeIndex) -> np.ndarray:
    """Mobility demand shock in 2020 with gradual recovery through 2021."""
    f = np.ones(len(dates))
    ym = dates.year * 100 + dates.month
    shock = {202003: 0.78, 202004: 0.48, 202005: 0.62, 202006: 0.80, 202007: 0.88, 202008: 0.90,
             202009: 0.91, 202010: 0.89, 202011: 0.82, 202012: 0.84, 202101: 0.80, 202102: 0.84,
             202103: 0.90, 202104: 0.93, 202105: 0.95, 202106: 0.97}
    for k, v in shock.items():
        f[ym == k] = v
    return f


def rng(*keys) -> np.random.Generator:
    return np.random.default_rng([SEED, *keys])


# --------------------------------------------------------------------------- dirt helpers
def fmt_dates(d: pd.Series, r: np.random.Generator, rate=0.03, with_time=False) -> pd.Series:
    """ISO dates, with ~rate rows in dd/mm/yyyy or yyyymmdd."""
    iso = "%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d"
    idx0 = d.index
    d = pd.Series(pd.to_datetime(d.values))
    out = d.dt.strftime(iso)
    n = len(d)
    idx = np.flatnonzero(r.random(n) < rate)
    if len(idx):
        half = r.random(len(idx)) < 0.5
        a, b = idx[half], idx[~half]
        fa = "%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y"
        fb = "%Y%m%d %H%M%S" if with_time else "%Y%m%d"
        out.iloc[a] = pd.Series(d.iloc[a].values).dt.strftime(fa).values
        out.iloc[b] = pd.Series(d.iloc[b].values).dt.strftime(fb).values
    out.index = idx0
    return out


def fmt_num(x: pd.Series, r: np.random.Generator, rate=0.02, decimals=2) -> pd.Series:
    """Numbers as text; ~rate rows with comma decimal ('1234,56') or currency prefix ('$1234.56')."""
    vals = x.round(decimals)
    out = vals.map(lambda v: "" if pd.isna(v) else f"{v:.{decimals}f}")
    idx = np.flatnonzero((r.random(len(x)) < rate) & vals.notna().values)
    if len(idx):
        half = r.random(len(idx)) < 0.5
        a, b = idx[half], idx[~half]
        out.iloc[a] = out.iloc[a].str.replace(".", ",", regex=False).values
        out.iloc[b] = ("$" + out.iloc[b]).values
    return out


def blank(s: pd.Series, r: np.random.Generator, rate=0.01) -> pd.Series:
    s = s.copy()
    s.iloc[np.flatnonzero(r.random(len(s)) < rate)] = ""
    return s


def messy_country(codes: pd.Series, r: np.random.Generator, rate=0.05, clean="name") -> pd.Series:
    names = dict(zip(CTRY.country_code, CTRY.country_name))
    out = codes.map(names) if clean == "name" else codes.copy()
    idx = np.flatnonzero(r.random(len(codes)) < rate)
    for i in idx:
        v = COUNTRY_VARIANTS[codes.iloc[i]]
        out.iloc[i] = v[r.integers(len(v))]
    return out


def add_duplicates(df: pd.DataFrame, r: np.random.Generator, rate=0.015) -> pd.DataFrame:
    dup = df.iloc[np.flatnonzero(r.random(len(df)) < rate)]
    return pd.concat([df, dup], ignore_index=True).sample(frac=1, random_state=int(r.integers(1e9))).reset_index(drop=True)


def write(df: pd.DataFrame, rel: str):
    p = RAW / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding="utf-8")
    print(f"  wrote {rel:55s} {len(df):>10,} rows  {p.stat().st_size/1e6:7.1f} MB")
