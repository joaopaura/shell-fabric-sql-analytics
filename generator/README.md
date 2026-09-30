# Fictitious data generator

Generates the raw, intentionally dirty CSV files that feed the Fabric SQL Database (bronze layer).
All data is fictitious. Portfolio project, not affiliated with Shell plc.

```
pip install pandas numpy
python generator/run_all.py      # ~1 minute, output in data/raw (git-ignored)
```

| Folder | File(s) | Grain |
|---|---|---|
| master | countries, segments, products, sites, assets | reference data |
| retail_sales | retail_sales_YYYY.csv | day x site x product |
| ev_charging | ev_charging_YYYY.csv | day x EV site |
| upstream | production_monthly, asset_downtime_events, lng_sales_monthly | month x asset / event / month x plant x destination x contract |
| group | financials_monthly, emissions_monthly, targets | month x segment x country (x scope) / year x metric |

Dirt injected on purpose: exact duplicates, late corrected records (`record_updated_at`), mixed date formats
(ISO, dd/mm/yyyy, yyyymmdd), inconsistent country / product / cause / scope spellings, numbers with comma
decimals or `$` prefix, blanks, negative and x1000 values, orphan keys, future dates, swapped start/end
timestamps and EBITDA that does not equal revenue minus cost.
