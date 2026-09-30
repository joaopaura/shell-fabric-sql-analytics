"""Per-table rules for the silver procedures (typing, validation, extra fixes)."""

MASTER = [
dict(target="country", bronze="countries", doc="Reference list of countries and regions.",
     key=["country_code"], order="bronze_id DESC", dedup_doc="last loaded row wins",
     cols=["country_code", "country_name", "region"],
     typed="""
SELECT b.bronze_id,
       CAST(UPPER(TRIM(b.country_code)) AS CHAR(2)) AS country_code,
       TRIM(b.country_name)                         AS country_name,
       TRIM(b.region)                               AS region,
       CASE WHEN LEN(TRIM(b.country_code)) <> 2         THEN 'Invalid country_code'
            WHEN NULLIF(TRIM(b.country_name), '') IS NULL THEN 'Missing country_name'
            WHEN NULLIF(TRIM(b.region), '') IS NULL       THEN 'Missing region'
       END AS reject_reason
INTO #typed
FROM bronze.countries b;"""),

dict(target="segment", bronze="segments", doc="Shell business segments.",
     key=["segment_id"], order="bronze_id DESC", dedup_doc="last loaded row wins",
     cols=["segment_id", "segment_name"],
     typed="""
SELECT b.bronze_id,
       TRY_CAST(TRIM(b.segment_id) AS TINYINT) AS segment_id,
       TRIM(b.segment_name)                    AS segment_name,
       CASE WHEN TRY_CAST(TRIM(b.segment_id) AS TINYINT) IS NULL THEN 'Invalid segment_id'
            WHEN NULLIF(TRIM(b.segment_name), '') IS NULL        THEN 'Missing segment_name'
       END AS reject_reason
INTO #typed
FROM bronze.segments b;"""),

dict(target="product", bronze="products", doc="Retail products (fuel and non-fuel).",
     key=["product_id"], order="bronze_id DESC", dedup_doc="last loaded row wins",
     cols=["product_id", "product_name", "product_group"],
     typed="""
SELECT b.bronze_id,
       CAST(UPPER(TRIM(b.product_id)) AS CHAR(3)) AS product_id,
       TRIM(b.product_name)                       AS product_name,
       TRIM(b.product_group)                      AS product_group,
       CASE WHEN LEN(TRIM(b.product_id)) <> 3              THEN 'Invalid product_id'
            WHEN TRIM(b.product_group) NOT IN ('Fuel', 'Non-fuel') THEN 'Invalid product_group'
       END AS reject_reason
INTO #typed
FROM bronze.products b;"""),

dict(target="site", bronze="sites", doc="Retail stations. Fixes: country spellings, city case/spaces, EV flag variants, missing coordinates.",
     key=["site_id"], order="bronze_id DESC", dedup_doc="duplicated site rows, last loaded wins",
     cols=["site_id", "site_name", "city", "country_code", "latitude", "longitude", "is_geo_imputed", "site_format",
           "opening_date", "has_ev_charging", "ev_since_date", "ev_charge_points"],
     typed="""
SELECT b.bronze_id,
       CAST(TRIM(b.site_id) AS VARCHAR(10))                          AS site_id,
       TRIM(b.site_name)                                             AS site_name,
       TRIM(b.city)                                                  AS city,
       CAST(cm.clean_value AS CHAR(2))                               AS country_code,
       TRY_CAST(NULLIF(TRIM(b.latitude), '') AS DECIMAL(9, 5))       AS latitude,
       TRY_CAST(NULLIF(TRIM(b.longitude), '') AS DECIMAL(9, 5))      AS longitude,
       CAST(0 AS BIT)                                                AS is_geo_imputed,
       TRIM(b.site_format)                                           AS site_format,
       od.value                                                      AS opening_date,
       CAST(fl.clean_value AS BIT)                                   AS has_ev_charging,
       ed.value                                                      AS ev_since_date,
       ISNULL(TRY_CAST(TRIM(b.ev_charge_points) AS SMALLINT), 0)     AS ev_charge_points,
       CASE WHEN NULLIF(TRIM(b.site_id), '') IS NULL       THEN 'Missing site_id'
            WHEN cm.clean_value IS NULL                     THEN 'Unknown country'
            WHEN od.value IS NULL                           THEN 'Invalid opening_date'
            WHEN fl.clean_value IS NULL                     THEN 'Invalid EV flag'
            WHEN fl.clean_value = '1' AND ed.value IS NULL  THEN 'EV site without ev_since_date'
       END AS reject_reason
INTO #typed
FROM bronze.sites b
CROSS APPLY etl.tvf_parse_date(b.opening_date)  od
CROSS APPLY etl.tvf_parse_date(b.ev_since_date) ed
LEFT JOIN etl.value_map cm ON cm.domain = 'country' AND cm.raw_value = TRIM(b.country)
LEFT JOIN etl.value_map fl ON fl.domain = 'flag'    AND fl.raw_value = TRIM(b.has_ev_charging);""",
     post="""
/* city spelling: the most frequent case-sensitive spelling wins ('  MANCHESTER ' -> 'Manchester') */
WITH spellings AS (
    SELECT city COLLATE Latin1_General_CS_AS AS city_cs, COUNT(*) AS n
    FROM #typed
    GROUP BY city COLLATE Latin1_General_CS_AS
), ranked AS (
    SELECT city_cs, FIRST_VALUE(city_cs) OVER (PARTITION BY UPPER(city_cs) ORDER BY n DESC) AS best
    FROM spellings
)
UPDATE t SET city = r.best
FROM #typed t
JOIN ranked r ON t.city COLLATE Latin1_General_CS_AS = r.city_cs;

/* missing coordinates: average of the other sites in the same city */
UPDATE t
   SET latitude = COALESCE(t.latitude, c.lat), longitude = COALESCE(t.longitude, c.lon), is_geo_imputed = 1
FROM #typed t
JOIN (SELECT country_code, city, AVG(latitude) AS lat, AVG(longitude) AS lon
      FROM #typed GROUP BY country_code, city) c
  ON c.country_code = t.country_code AND c.city = t.city
WHERE t.latitude IS NULL OR t.longitude IS NULL;"""),

dict(target="asset", bronze="assets", doc="Upstream fields and LNG plants. Fixes: country spellings, name spaces, asset_type case.",
     key=["asset_id"], order="bronze_id DESC", dedup_doc="last loaded row wins",
     cols=["asset_id", "asset_name", "asset_type", "country_code", "segment_id", "start_date", "capacity_value", "capacity_unit"],
     typed="""
SELECT b.bronze_id,
       CAST(TRIM(b.asset_id) AS VARCHAR(10)) AS asset_id,
       TRIM(b.asset_name)                    AS asset_name,
       CASE TRIM(b.asset_type)               -- case-insensitive collation: 'oil field' = 'Oil field'
            WHEN 'Oil field' THEN 'Oil field' WHEN 'Gas field' THEN 'Gas field' WHEN 'LNG plant' THEN 'LNG plant'
       END                                   AS asset_type,
       CAST(cm.clean_value AS CHAR(2))       AS country_code,
       sg.segment_id,
       sd.value                              AS start_date,
       cap.value                             AS capacity_value,
       TRIM(b.capacity_unit)                 AS capacity_unit,
       CASE WHEN NULLIF(TRIM(b.asset_id), '') IS NULL THEN 'Missing asset_id'
            WHEN TRIM(b.asset_type) NOT IN ('Oil field', 'Gas field', 'LNG plant') THEN 'Unknown asset_type'
            WHEN cm.clean_value IS NULL   THEN 'Unknown country'
            WHEN sg.segment_id IS NULL    THEN 'Unknown segment_id'
            WHEN sd.value IS NULL         THEN 'Invalid start_date'
            WHEN cap.value IS NULL        THEN 'Missing capacity'
       END AS reject_reason
INTO #typed
FROM bronze.assets b
CROSS APPLY etl.tvf_parse_date(b.start_date)       sd
CROSS APPLY etl.tvf_parse_number(b.capacity_value) cap
LEFT JOIN etl.value_map cm ON cm.domain = 'country' AND cm.raw_value = TRIM(b.country)
LEFT JOIN silver.segment sg ON sg.segment_id = TRY_CAST(TRIM(b.segment_id) AS TINYINT);"""),
]

FACTS = [
dict(target="retail_sales", bronze="retail_sales",
     doc="Daily sales per site and product (~4.4M rows). Fixes: date formats, product spellings, number formats,\n   late corrections (latest record_updated_at wins), missing fuel volume imputed from the average price.",
     key=["transaction_date", "site_id", "product_id"], order="record_updated_at DESC, bronze_id DESC",
     dedup_doc="exact duplicates and late corrections, latest record_updated_at wins",
     cols=["transaction_date", "site_id", "product_id", "volume_litres", "revenue_usd", "cost_usd", "transactions",
           "is_volume_imputed", "record_updated_at"],
     typed="""
SELECT b.bronze_id,
       d.value                                           AS transaction_date,
       CAST(TRIM(b.site_id) AS VARCHAR(10))              AS site_id,
       CAST(pm.clean_value AS CHAR(3))                   AS product_id,
       p.product_group,
       v.value                                           AS volume_litres,
       r.value                                           AS revenue_usd,
       c.value                                           AS cost_usd,
       ISNULL(TRY_CAST(TRIM(b.transactions) AS INT), 0)  AS transactions,
       CAST(0 AS BIT)                                    AS is_volume_imputed,
       u.value                                           AS record_updated_at,
       CASE WHEN d.value IS NULL            THEN 'Invalid transaction_date'
            WHEN s.site_id IS NULL          THEN 'Unknown site_id'
            WHEN pm.clean_value IS NULL     THEN 'Unknown product'
            WHEN r.value IS NULL            THEN 'Missing revenue'
            WHEN c.value IS NULL            THEN 'Missing cost'
            WHEN v.value < 0                THEN 'Negative volume'
            WHEN v.value > 200000           THEN 'Volume outlier (> 200k litres/day)'
            WHEN d.value < s.opening_date   THEN 'Sale before site opening'
            WHEN u.value IS NULL            THEN 'Invalid record_updated_at'
       END AS reject_reason
INTO #typed
FROM bronze.retail_sales b
CROSS APPLY etl.tvf_parse_date(b.transaction_date)      d
CROSS APPLY etl.tvf_parse_number(b.volume_litres)       v
CROSS APPLY etl.tvf_parse_number(b.revenue_usd)         r
CROSS APPLY etl.tvf_parse_number(b.cost_usd)            c
CROSS APPLY etl.tvf_parse_datetime(b.record_updated_at) u
LEFT JOIN etl.value_map pm ON pm.domain = 'product' AND pm.raw_value = TRIM(b.product)
LEFT JOIN silver.product p ON p.product_id = pm.clean_value
LEFT JOIN silver.site    s ON s.site_id = TRIM(b.site_id);""",
     post="""
/* fuel rows without volume: impute from the average price per litre of the same site, product and month */
WITH price AS (
    SELECT site_id, product_id, EOMONTH(transaction_date) AS month_end,
           SUM(revenue_usd) / NULLIF(SUM(volume_litres), 0) AS usd_per_litre
    FROM #typed
    WHERE reject_reason IS NULL AND volume_litres > 0
    GROUP BY site_id, product_id, EOMONTH(transaction_date)
)
UPDATE t
   SET volume_litres = ROUND(t.revenue_usd / p.usd_per_litre, 1), is_volume_imputed = 1
FROM #typed t
JOIN price p ON p.site_id = t.site_id AND p.product_id = t.product_id AND p.month_end = EOMONTH(t.transaction_date)
WHERE t.reject_reason IS NULL AND t.product_group = 'Fuel' AND t.volume_litres IS NULL;

UPDATE #typed
   SET reject_reason = 'Missing volume (no price to impute)'
WHERE reject_reason IS NULL AND product_group = 'Fuel' AND volume_litres IS NULL;"""),

dict(target="ev_charging", bronze="ev_charging",
     doc="Daily EV charging per site. Rejects: future dates, dates outside the file year, charging before installation.",
     key=["charge_date", "site_id"], order="bronze_id DESC", dedup_doc="exact duplicates",
     cols=["charge_date", "site_id", "sessions", "energy_mwh", "revenue_usd", "avg_session_minutes"],
     typed="""
SELECT b.bronze_id,
       d.value                                                  AS charge_date,
       CAST(TRIM(b.site_id) AS VARCHAR(10))                     AS site_id,
       TRY_CAST(NULLIF(TRIM(b.sessions), '') AS INT)            AS sessions,
       e.value                                                  AS energy_mwh,
       r.value                                                  AS revenue_usd,
       m.value                                                  AS avg_session_minutes,
       CASE WHEN d.value IS NULL                                THEN 'Invalid charge_date'
            WHEN s.site_id IS NULL                              THEN 'Unknown site_id'
            WHEN d.value > CAST(SYSUTCDATETIME() AS DATE)       THEN 'Future date'
            WHEN YEAR(d.value) <> f.file_year                   THEN 'Date outside file period'
            WHEN d.value < s.ev_since_date OR s.ev_since_date IS NULL THEN 'Charging before EV installation'
            WHEN TRY_CAST(NULLIF(TRIM(b.sessions), '') AS INT) IS NULL THEN 'Missing sessions'
            WHEN e.value IS NULL OR r.value IS NULL             THEN 'Missing energy or revenue'
       END AS reject_reason
INTO #typed
FROM bronze.ev_charging b
CROSS APPLY etl.tvf_parse_date(b.charge_date)            d
CROSS APPLY etl.tvf_parse_number(b.energy_mwh)           e
CROSS APPLY etl.tvf_parse_number(b.revenue_usd)          r
CROSS APPLY etl.tvf_parse_number(b.avg_session_minutes)  m
CROSS APPLY (SELECT TRY_CAST(SUBSTRING(b.source_file, NULLIF(PATINDEX('%[12][0-9][0-9][0-9].csv', b.source_file), 0), 4) AS SMALLINT) AS file_year) f
LEFT JOIN silver.site s ON s.site_id = TRIM(b.site_id);"""),

dict(target="production_monthly", bronze="production_monthly",
     doc="Monthly production per asset. Fixes: late corrections; rejects negative or inconsistent totals.",
     key=["production_month", "asset_id"], order="record_updated_at DESC, bronze_id DESC",
     dedup_doc="duplicates and late corrections, latest record_updated_at wins",
     cols=["production_month", "asset_id", "oil_bbl", "gas_boe", "total_boe", "opex_usd", "planned_boe", "record_updated_at"],
     typed="""
SELECT b.bronze_id,
       DATEFROMPARTS(YEAR(d.value), MONTH(d.value), 1)  AS production_month,
       CAST(TRIM(b.asset_id) AS VARCHAR(10))            AS asset_id,
       o.value AS oil_bbl, g.value AS gas_boe, t.value AS total_boe, x.value AS opex_usd, p.value AS planned_boe,
       u.value                                          AS record_updated_at,
       CASE WHEN d.value IS NULL                          THEN 'Invalid production_month'
            WHEN a.asset_id IS NULL                       THEN 'Unknown asset_id'
            WHEN t.value < 0                              THEN 'Negative production'
            WHEN ABS(t.value - o.value - g.value) > 0.001 * ABS(t.value) + 2 THEN 'total_boe <> oil_bbl + gas_boe'
            WHEN x.value IS NULL OR p.value IS NULL       THEN 'Missing opex or plan'
            WHEN d.value < DATEFROMPARTS(YEAR(a.start_date), MONTH(a.start_date), 1) THEN 'Production before asset start'
            WHEN u.value IS NULL                          THEN 'Invalid record_updated_at'
       END AS reject_reason
INTO #typed
FROM bronze.production_monthly b
CROSS APPLY etl.tvf_parse_date(b.production_month)      d
CROSS APPLY etl.tvf_parse_number(b.oil_bbl)             o
CROSS APPLY etl.tvf_parse_number(b.gas_boe)             g
CROSS APPLY etl.tvf_parse_number(b.total_boe)           t
CROSS APPLY etl.tvf_parse_number(b.opex_usd)            x
CROSS APPLY etl.tvf_parse_number(b.planned_boe)         p
CROSS APPLY etl.tvf_parse_datetime(b.record_updated_at) u
LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.asset_id);"""),

dict(target="asset_downtime", bronze="asset_downtime_events",
     doc="Downtime events. Fixes: swapped start/end timestamps, missing hours recalculated, cause spellings.",
     key=["event_id"], order="bronze_id DESC", dedup_doc="exact duplicates",
     cols=["event_id", "asset_id", "start_ts", "end_ts", "downtime_hours", "cause", "was_ts_swapped", "was_hours_recalc"],
     typed="""
SELECT b.bronze_id,
       CAST(TRIM(b.event_id) AS VARCHAR(10))                              AS event_id,
       CAST(TRIM(b.asset_id) AS VARCHAR(10))                              AS asset_id,
       CASE WHEN sw.swapped = 1 THEN e.value ELSE s.value END             AS start_ts,
       CASE WHEN sw.swapped = 1 THEN s.value ELSE e.value END             AS end_ts,
       COALESCE(h.value, ABS(DATEDIFF(MINUTE, s.value, e.value)) / 60.0)  AS downtime_hours,
       cm.clean_value                                                     AS cause,
       CAST(sw.swapped AS BIT)                                            AS was_ts_swapped,
       CAST(CASE WHEN h.value IS NULL THEN 1 ELSE 0 END AS BIT)           AS was_hours_recalc,
       CASE WHEN NULLIF(TRIM(b.event_id), '') IS NULL   THEN 'Missing event_id'
            WHEN s.value IS NULL OR e.value IS NULL      THEN 'Invalid timestamp'
            WHEN a.asset_id IS NULL                      THEN 'Unknown asset_id'
            WHEN cm.clean_value IS NULL                  THEN 'Unknown cause'
       END AS reject_reason
INTO #typed
FROM bronze.asset_downtime_events b
CROSS APPLY etl.tvf_parse_datetime(b.start_ts)     s
CROSS APPLY etl.tvf_parse_datetime(b.end_ts)       e
CROSS APPLY etl.tvf_parse_number(b.downtime_hours) h
CROSS APPLY (SELECT CASE WHEN e.value < s.value THEN 1 ELSE 0 END AS swapped) sw
LEFT JOIN etl.value_map cm ON cm.domain = 'cause' AND cm.raw_value = TRIM(b.cause)
LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.asset_id);"""),

dict(target="lng_sales", bronze="lng_sales_monthly",
     doc="Monthly LNG sales per plant, destination and contract type.",
     key=["sale_month", "plant_asset_id", "destination_code", "contract_type"], order="bronze_id DESC",
     dedup_doc="exact duplicates",
     cols=["sale_month", "plant_asset_id", "destination_code", "contract_type", "volume_mt", "revenue_usd"],
     typed="""
SELECT b.bronze_id,
       DATEFROMPARTS(YEAR(d.value), MONTH(d.value), 1) AS sale_month,
       CAST(TRIM(b.plant_asset_id) AS VARCHAR(10))     AS plant_asset_id,
       CAST(cm.clean_value AS CHAR(2))                 AS destination_code,
       ct.clean_value                                  AS contract_type,
       v.value AS volume_mt, r.value AS revenue_usd,
       CASE WHEN d.value IS NULL                       THEN 'Invalid sale_month'
            WHEN a.asset_id IS NULL                    THEN 'Unknown LNG plant'
            WHEN cm.clean_value IS NULL                THEN 'Unknown destination country'
            WHEN ct.clean_value IS NULL                THEN 'Unknown contract_type'
            WHEN v.value IS NULL OR v.value < 0        THEN 'Invalid volume'
            WHEN r.value IS NULL                       THEN 'Missing revenue'
       END AS reject_reason
INTO #typed
FROM bronze.lng_sales_monthly b
CROSS APPLY etl.tvf_parse_date(b.sale_month)    d
CROSS APPLY etl.tvf_parse_number(b.volume_mt)   v
CROSS APPLY etl.tvf_parse_number(b.revenue_usd) r
LEFT JOIN etl.value_map cm ON cm.domain = 'country'       AND cm.raw_value = TRIM(b.destination_country)
LEFT JOIN etl.value_map ct ON ct.domain = 'contract_type' AND ct.raw_value = TRIM(b.contract_type)
LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.plant_asset_id) AND a.asset_type = 'LNG plant';"""),

dict(target="financials", bronze="financials_monthly",
     doc="Monthly P&L per segment and country. EBITDA is recalculated; mismatches with the reported value are flagged.",
     key=["financial_month", "segment_id", "country_code"], order="bronze_id DESC", dedup_doc="exact duplicates",
     cols=["financial_month", "segment_id", "country_code", "revenue_usd", "operating_cost_usd", "ebitda_usd",
           "ebitda_reported_usd", "is_ebitda_mismatch", "capex_usd"],
     typed="""
SELECT b.bronze_id,
       DATEFROMPARTS(YEAR(d.value), MONTH(d.value), 1)  AS financial_month,
       sg.segment_id,
       CAST(cm.clean_value AS CHAR(2))                  AS country_code,
       r.value AS revenue_usd, c.value AS operating_cost_usd,
       r.value - c.value                                AS ebitda_usd,
       e.value                                          AS ebitda_reported_usd,
       CAST(CASE WHEN ABS(e.value - (r.value - c.value)) > 1 THEN 1 ELSE 0 END AS BIT) AS is_ebitda_mismatch,
       ISNULL(x.value, 0)                               AS capex_usd,
       CASE WHEN d.value IS NULL                   THEN 'Invalid financial_month'
            WHEN sg.segment_id IS NULL             THEN 'Unknown segment'
            WHEN cm.clean_value IS NULL            THEN 'Unknown country'
            WHEN r.value IS NULL OR c.value IS NULL THEN 'Missing revenue or cost'
       END AS reject_reason
INTO #typed
FROM bronze.financials_monthly b
CROSS APPLY etl.tvf_parse_date(b.financial_month)      d
CROSS APPLY etl.tvf_parse_number(b.revenue_usd)        r
CROSS APPLY etl.tvf_parse_number(b.operating_cost_usd) c
CROSS APPLY etl.tvf_parse_number(b.ebitda_usd)         e
CROSS APPLY etl.tvf_parse_number(b.capex_usd)          x
LEFT JOIN silver.segment sg ON sg.segment_name = TRIM(b.segment)
LEFT JOIN etl.value_map  cm ON cm.domain = 'country' AND cm.raw_value = TRIM(b.country);"""),

dict(target="emissions", bronze="emissions_monthly",
     doc="Monthly GHG emissions per segment, country and scope. Fixes: scope and country spellings.",
     key=["emission_month", "segment_id", "country_code", "scope"], order="bronze_id DESC", dedup_doc="exact duplicates",
     cols=["emission_month", "segment_id", "country_code", "scope", "tco2e"],
     typed="""
SELECT b.bronze_id,
       DATEFROMPARTS(YEAR(d.value), MONTH(d.value), 1) AS emission_month,
       sg.segment_id,
       CAST(cm.clean_value AS CHAR(2))                 AS country_code,
       TRY_CAST(sc.clean_value AS TINYINT)             AS scope,
       t.value                                         AS tco2e,
       CASE WHEN d.value IS NULL              THEN 'Invalid emission_month'
            WHEN sg.segment_id IS NULL        THEN 'Unknown segment'
            WHEN cm.clean_value IS NULL       THEN 'Unknown country'
            WHEN sc.clean_value IS NULL       THEN 'Unknown scope'
            WHEN t.value IS NULL OR t.value < 0 THEN 'Invalid tco2e'
       END AS reject_reason
INTO #typed
FROM bronze.emissions_monthly b
CROSS APPLY etl.tvf_parse_date(b.emission_month) d
CROSS APPLY etl.tvf_parse_number(b.tco2e)        t
LEFT JOIN silver.segment sg ON sg.segment_name = TRIM(b.segment)
LEFT JOIN etl.value_map  cm ON cm.domain = 'country' AND cm.raw_value = TRIM(b.country)
LEFT JOIN etl.value_map  sc ON sc.domain = 'scope'   AND sc.raw_value = TRIM(b.scope);"""),

dict(target="targets", bronze="targets", doc="Business targets per year and metric.",
     key=["target_year", "metric"], order="bronze_id DESC", dedup_doc="last loaded row wins",
     cols=["target_year", "metric", "unit", "target_value"],
     typed="""
SELECT b.bronze_id,
       TRY_CAST(TRIM(b.target_year) AS SMALLINT) AS target_year,
       TRIM(b.metric)                            AS metric,
       TRIM(b.unit)                              AS unit,
       v.value                                   AS target_value,
       CASE WHEN TRY_CAST(TRIM(b.target_year) AS SMALLINT) IS NULL THEN 'Invalid target_year'
            WHEN NULLIF(TRIM(b.metric), '') IS NULL                 THEN 'Missing metric'
            WHEN v.value IS NULL                                    THEN 'Missing target_value'
       END AS reject_reason
INTO #typed
FROM bronze.targets b
CROSS APPLY etl.tvf_parse_number(b.target_value) v;"""),
]
