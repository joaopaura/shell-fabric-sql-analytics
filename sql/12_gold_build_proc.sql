/* =============================================================================
   Shell | Fabric SQL Database | 12 - Gold build
   Full rebuild of the star schema from silver inside ONE transaction, so the
   report never reads a half-built gold layer. Each table is logged in etl.run_log.
============================================================================= */
CREATE OR ALTER PROCEDURE etl.usp_build_gold
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @n BIGINT;

    BEGIN TRY
        BEGIN TRANSACTION;

        /* ---------- dim_country ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'dim_country', @run_id OUTPUT;
        TRUNCATE TABLE gold.dim_country;
        INSERT INTO gold.dim_country (country_code, country_name, region, has_mobility, has_upstream)
        SELECT c.country_code, c.country_name, c.region,
               CASE WHEN EXISTS (SELECT 1 FROM silver.site  s WHERE s.country_code = c.country_code) THEN 1 ELSE 0 END,
               CASE WHEN EXISTS (SELECT 1 FROM silver.asset a WHERE a.country_code = c.country_code) THEN 1 ELSE 0 END
        FROM silver.country c;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- dim_segment ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'dim_segment', @run_id OUTPUT;
        TRUNCATE TABLE gold.dim_segment;
        INSERT INTO gold.dim_segment (segment_id, segment_name, is_low_carbon, sort_order)
        SELECT segment_id, segment_name,
               CASE WHEN segment_name = 'Renewables & Energy Solutions' THEN 1 ELSE 0 END,
               segment_id
        FROM silver.segment;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- dim_product ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'dim_product', @run_id OUTPUT;
        TRUNCATE TABLE gold.dim_product;
        INSERT INTO gold.dim_product (product_id, product_name, product_group)
        SELECT product_id, product_name, product_group FROM silver.product;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- dim_site ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'dim_site', @run_id OUTPUT;
        TRUNCATE TABLE gold.dim_site;
        INSERT INTO gold.dim_site (site_id, site_name, city, country_code, latitude, longitude, site_format,
                                   opening_date, opening_year, has_ev_charging, ev_status, ev_since_date, ev_charge_points)
        SELECT site_id, site_name, city, country_code, latitude, longitude, site_format,
               opening_date, YEAR(opening_date), has_ev_charging,
               CASE WHEN has_ev_charging = 1 THEN 'EV hub' ELSE 'Fuel only' END,
               ev_since_date, ev_charge_points
        FROM silver.site;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- dim_asset ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'dim_asset', @run_id OUTPUT;
        TRUNCATE TABLE gold.dim_asset;
        INSERT INTO gold.dim_asset (asset_id, asset_name, asset_type, country_code, segment_id, start_date,
                                    capacity_value, capacity_unit, capacity_label)
        SELECT asset_id, asset_name, asset_type, country_code, segment_id, start_date, capacity_value, capacity_unit,
               CASE WHEN capacity_unit = 'Mtpa' THEN CONCAT(FORMAT(capacity_value, 'N1'), ' Mtpa')
                    ELSE CONCAT(FORMAT(capacity_value, 'N0'), ' boe/d') END
        FROM silver.asset;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_retail_sales ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_retail_sales', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_retail_sales;
        INSERT INTO gold.fact_retail_sales (date_key, site_id, product_id, volume_litres, revenue_usd, cost_usd,
                                            gross_margin_usd, transactions, is_volume_imputed)
        SELECT YEAR(transaction_date) * 10000 + MONTH(transaction_date) * 100 + DAY(transaction_date),
               site_id, product_id, volume_litres, revenue_usd, cost_usd,
               revenue_usd - cost_usd, transactions, is_volume_imputed
        FROM silver.retail_sales;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_ev_charging ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_ev_charging', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_ev_charging;
        INSERT INTO gold.fact_ev_charging (date_key, site_id, sessions, energy_mwh, revenue_usd, avg_session_minutes)
        SELECT YEAR(charge_date) * 10000 + MONTH(charge_date) * 100 + DAY(charge_date),
               site_id, sessions, energy_mwh, revenue_usd, avg_session_minutes
        FROM silver.ev_charging;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_production (+ monthly downtime hours) ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_production', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_production;
        WITH downtime AS (
            SELECT asset_id, DATEFROMPARTS(YEAR(start_ts), MONTH(start_ts), 1) AS month_start,
                   SUM(downtime_hours) AS downtime_hours
            FROM silver.asset_downtime
            GROUP BY asset_id, DATEFROMPARTS(YEAR(start_ts), MONTH(start_ts), 1)
        )
        INSERT INTO gold.fact_production (date_key, asset_id, oil_bbl, gas_boe, total_boe, planned_boe, opex_usd,
                                          days_in_month, downtime_hours)
        SELECT YEAR(p.production_month) * 10000 + MONTH(p.production_month) * 100 + 1,
               p.asset_id, p.oil_bbl, p.gas_boe, p.total_boe, p.planned_boe, p.opex_usd,
               DAY(EOMONTH(p.production_month)),
               -- downtime cannot exceed the hours in the month
               CASE WHEN ISNULL(d.downtime_hours, 0) > 24 * DAY(EOMONTH(p.production_month))
                    THEN 24 * DAY(EOMONTH(p.production_month)) ELSE ISNULL(d.downtime_hours, 0) END
        FROM silver.production_monthly p
        LEFT JOIN downtime d ON d.asset_id = p.asset_id AND d.month_start = p.production_month;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_asset_downtime ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_asset_downtime', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_asset_downtime;
        INSERT INTO gold.fact_asset_downtime (event_id, date_key, asset_id, start_ts, end_ts, downtime_hours, cause, is_planned)
        SELECT event_id, YEAR(start_ts) * 10000 + MONTH(start_ts) * 100 + DAY(start_ts),
               asset_id, start_ts, end_ts, downtime_hours, cause,
               CASE WHEN cause = 'Planned maintenance' THEN 1 ELSE 0 END
        FROM silver.asset_downtime
        WHERE start_ts >= '2020-01-01' AND start_ts < '2031-01-01';
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_lng_sales ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_lng_sales', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_lng_sales;
        INSERT INTO gold.fact_lng_sales (date_key, plant_asset_id, destination_country_code, contract_type, volume_mt, revenue_usd)
        SELECT YEAR(sale_month) * 10000 + MONTH(sale_month) * 100 + 1,
               plant_asset_id, destination_code, contract_type, volume_mt, revenue_usd
        FROM silver.lng_sales;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_financials ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_financials', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_financials;
        INSERT INTO gold.fact_financials (date_key, segment_id, country_code, revenue_usd, operating_cost_usd,
                                          ebitda_usd, capex_usd, is_ebitda_mismatch)
        SELECT YEAR(financial_month) * 10000 + MONTH(financial_month) * 100 + 1,
               segment_id, country_code, revenue_usd, operating_cost_usd, ebitda_usd, capex_usd, is_ebitda_mismatch
        FROM silver.financials;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_emissions ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_emissions', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_emissions;
        INSERT INTO gold.fact_emissions (date_key, segment_id, country_code, scope, scope_label, tco2e)
        SELECT YEAR(emission_month) * 10000 + MONTH(emission_month) * 100 + 1,
               segment_id, country_code, scope, CONCAT('Scope ', scope), tco2e
        FROM silver.emissions;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        /* ---------- fact_targets ---------- */
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'fact_targets', @run_id OUTPUT;
        TRUNCATE TABLE gold.fact_targets;
        INSERT INTO gold.fact_targets (target_year, metric, unit, target_value)
        SELECT target_year, metric, unit, target_value FROM silver.targets;
        SET @n = @@ROWCOUNT;
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;   -- also undoes the log rows written inside the transaction
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @fail_id BIGINT;
        EXEC etl.usp_log_start @pipeline_run_id, 'gold', 'usp_build_gold', @fail_id OUTPUT;
        EXEC etl.usp_log_end @fail_id, 'Failed', NULL, NULL, NULL, NULL, @err;
        THROW;
    END CATCH
END;
GO
