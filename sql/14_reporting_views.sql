/* =============================================================================
   Shell | Fabric SQL Database | 14 - Reporting and analysis views
   pipeline views feed page 5 of the report; analysis views show SQL-side
   analytics (window functions) and are handy for ad-hoc checks.
============================================================================= */

/* ---------- Page 5: pipeline runs (one row per step execution) ---------- */
CREATE OR ALTER VIEW gold.vw_pipeline_runs AS
SELECT l.run_id, l.pipeline_run_id, l.step, l.object_name, l.status,
       l.started_at, l.ended_at, l.duration_seconds,
       CAST(l.started_at AS DATE) AS run_date,
       l.rows_read, l.rows_inserted, l.rows_updated, l.rows_rejected, l.error_message,
       CASE l.step WHEN 'bronze' THEN 1 WHEN 'silver' THEN 2 WHEN 'gold' THEN 3 WHEN 'dq' THEN 4 ELSE 9 END AS step_order
FROM etl.run_log l
WHERE l.pipeline_run_id NOT LIKE 'manual-test%';
GO

/* ---------- Page 5: rejected rows by reason ---------- */
CREATE OR ALTER VIEW gold.vw_rejections AS
SELECT l.pipeline_run_id, r.table_name, r.reject_reason, COUNT_BIG(*) AS rejected_rows
FROM etl.rejected_rows r
JOIN etl.run_log l ON l.run_id = r.run_id
GROUP BY l.pipeline_run_id, r.table_name, r.reject_reason;
GO

/* ---------- Page 5: data quality checks ---------- */
CREATE OR ALTER VIEW gold.vw_dq_results AS
SELECT pipeline_run_id, check_name, table_name, expected_value, actual_value, passed,
       CASE passed WHEN 1 THEN 'Pass' ELSE 'Fail' END AS result, checked_at
FROM etl.dq_results;
GO

/* ---------- Analysis: monthly fuel volume by country with YoY (LAG) ---------- */
CREATE OR ALTER VIEW gold.vw_mobility_monthly_yoy AS
WITH m AS (
    SELECT d.month_start, s.country_code,
           SUM(f.volume_litres) / 1e6 AS fuel_ml,
           SUM(f.revenue_usd)         AS revenue_usd
    FROM gold.fact_retail_sales f
    JOIN gold.dim_date    d ON d.date_key = f.date_key
    JOIN gold.dim_site    s ON s.site_id = f.site_id
    JOIN gold.dim_product p ON p.product_id = f.product_id
    WHERE p.product_group = 'Fuel'
    GROUP BY d.month_start, s.country_code
)
SELECT month_start, country_code, fuel_ml, revenue_usd,
       LAG(fuel_ml, 12) OVER (PARTITION BY country_code ORDER BY month_start) AS fuel_ml_ly,
       fuel_ml / NULLIF(LAG(fuel_ml, 12) OVER (PARTITION BY country_code ORDER BY month_start), 0) - 1 AS fuel_yoy_pct,
       SUM(fuel_ml) OVER (PARTITION BY country_code, YEAR(month_start) ORDER BY month_start
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS fuel_ml_ytd
FROM m;
GO

/* ---------- Analysis: site ranking inside each country (RANK / NTILE) ---------- */
CREATE OR ALTER VIEW gold.vw_site_ranking AS
WITH s AS (
    SELECT f.site_id, d.[year],
           SUM(f.gross_margin_usd) AS gross_margin_usd,
           SUM(f.volume_litres)    AS fuel_litres
    FROM gold.fact_retail_sales f
    JOIN gold.dim_date d ON d.date_key = f.date_key
    GROUP BY f.site_id, d.[year]
)
SELECT s.[year], s.site_id, ds.site_name, ds.country_code, ds.site_format, s.gross_margin_usd, s.fuel_litres,
       RANK()   OVER (PARTITION BY s.[year], ds.country_code ORDER BY s.gross_margin_usd DESC) AS margin_rank_in_country,
       NTILE(4) OVER (PARTITION BY s.[year] ORDER BY s.gross_margin_usd DESC)                  AS margin_quartile
FROM s
JOIN gold.dim_site ds ON ds.site_id = s.site_id;
GO

/* ---------- Analysis: asset uptime and production vs plan ---------- */
CREATE OR ALTER VIEW gold.vw_asset_performance AS
SELECT d.[year], a.asset_id, a.asset_name, a.asset_type, a.country_code,
       SUM(p.total_boe)   AS total_boe,
       SUM(p.planned_boe) AS planned_boe,
       1.0 * SUM(p.total_boe) / NULLIF(SUM(p.planned_boe), 0) - 1 AS vs_plan_pct,
       1 - SUM(p.downtime_hours) / NULLIF(SUM(24.0 * p.days_in_month), 0) AS uptime_pct,
       SUM(p.opex_usd) / NULLIF(SUM(p.total_boe), 0) AS opex_per_boe
FROM gold.fact_production p
JOIN gold.dim_date  d ON d.date_key = p.date_key
JOIN gold.dim_asset a ON a.asset_id = p.asset_id
GROUP BY d.[year], a.asset_id, a.asset_name, a.asset_type, a.country_code;
GO
