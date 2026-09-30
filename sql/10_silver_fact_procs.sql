/* =============================================================================
   Shell | Fabric SQL Database | 10 - Silver procedures (facts)
   Generated from sql/_build/silver_template.py (same pattern for every table):
     1. type + validate (CROSS APPLY parsing functions, value_map lookups)
     2. rejected rows -> etl.rejected_rows as JSON with the reason
     3. deduplicate with ROW_NUMBER() on the business key
     4. MERGE into silver (idempotent: re-running changes nothing)
     5. counts + status -> etl.run_log, TRY/CATCH with rollback
============================================================================= */

/* -----------------------------------------------------------------------------
   silver.retail_sales  <-  bronze.retail_sales
   Daily sales per site and product (~4.4M rows). Fixes: date formats, product spellings, number formats,
   late corrections (latest record_updated_at wins), missing fuel volume imputed from the average price.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_retail_sales
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'retail_sales', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.site    s ON s.site_id = TRIM(b.site_id);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.retail_sales is empty: silver left unchanged (protects against deleting everything).', 1;

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
        WHERE reject_reason IS NULL AND product_group = 'Fuel' AND volume_litres IS NULL;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'retail_sales', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.retail_sales b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates and late corrections, latest record_updated_at wins */
        DROP TABLE IF EXISTS #src;
        SELECT transaction_date, site_id, product_id, volume_litres, revenue_usd, cost_usd, transactions, is_volume_imputed, record_updated_at
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY transaction_date, site_id, product_id ORDER BY record_updated_at DESC, bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.retail_sales AS tgt
        USING #src AS src
           ON tgt.transaction_date = src.transaction_date AND tgt.site_id = src.site_id AND tgt.product_id = src.product_id
        WHEN MATCHED AND EXISTS (SELECT src.volume_litres, src.revenue_usd, src.cost_usd, src.transactions, src.is_volume_imputed, src.record_updated_at EXCEPT SELECT tgt.volume_litres, tgt.revenue_usd, tgt.cost_usd, tgt.transactions, tgt.is_volume_imputed, tgt.record_updated_at)
            THEN UPDATE SET tgt.volume_litres = src.volume_litres, tgt.revenue_usd = src.revenue_usd, tgt.cost_usd = src.cost_usd, tgt.transactions = src.transactions, tgt.is_volume_imputed = src.is_volume_imputed, tgt.record_updated_at = src.record_updated_at
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (transaction_date, site_id, product_id, volume_litres, revenue_usd, cost_usd, transactions, is_volume_imputed, record_updated_at) VALUES (src.transaction_date, src.site_id, src.product_id, src.volume_litres, src.revenue_usd, src.cost_usd, src.transactions, src.is_volume_imputed, src.record_updated_at)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.ev_charging  <-  bronze.ev_charging
   Daily EV charging per site. Rejects: future dates, dates outside the file year, charging before installation.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_ev_charging
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'ev_charging', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.site s ON s.site_id = TRIM(b.site_id);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.ev_charging is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'ev_charging', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.ev_charging b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates */
        DROP TABLE IF EXISTS #src;
        SELECT charge_date, site_id, sessions, energy_mwh, revenue_usd, avg_session_minutes
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY charge_date, site_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.ev_charging AS tgt
        USING #src AS src
           ON tgt.charge_date = src.charge_date AND tgt.site_id = src.site_id
        WHEN MATCHED AND EXISTS (SELECT src.sessions, src.energy_mwh, src.revenue_usd, src.avg_session_minutes EXCEPT SELECT tgt.sessions, tgt.energy_mwh, tgt.revenue_usd, tgt.avg_session_minutes)
            THEN UPDATE SET tgt.sessions = src.sessions, tgt.energy_mwh = src.energy_mwh, tgt.revenue_usd = src.revenue_usd, tgt.avg_session_minutes = src.avg_session_minutes
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (charge_date, site_id, sessions, energy_mwh, revenue_usd, avg_session_minutes) VALUES (src.charge_date, src.site_id, src.sessions, src.energy_mwh, src.revenue_usd, src.avg_session_minutes)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.production_monthly  <-  bronze.production_monthly
   Monthly production per asset. Fixes: late corrections; rejects negative or inconsistent totals.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_production_monthly
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'production_monthly', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.asset_id);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.production_monthly is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'production_monthly', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.production_monthly b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: duplicates and late corrections, latest record_updated_at wins */
        DROP TABLE IF EXISTS #src;
        SELECT production_month, asset_id, oil_bbl, gas_boe, total_boe, opex_usd, planned_boe, record_updated_at
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY production_month, asset_id ORDER BY record_updated_at DESC, bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.production_monthly AS tgt
        USING #src AS src
           ON tgt.production_month = src.production_month AND tgt.asset_id = src.asset_id
        WHEN MATCHED AND EXISTS (SELECT src.oil_bbl, src.gas_boe, src.total_boe, src.opex_usd, src.planned_boe, src.record_updated_at EXCEPT SELECT tgt.oil_bbl, tgt.gas_boe, tgt.total_boe, tgt.opex_usd, tgt.planned_boe, tgt.record_updated_at)
            THEN UPDATE SET tgt.oil_bbl = src.oil_bbl, tgt.gas_boe = src.gas_boe, tgt.total_boe = src.total_boe, tgt.opex_usd = src.opex_usd, tgt.planned_boe = src.planned_boe, tgt.record_updated_at = src.record_updated_at
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (production_month, asset_id, oil_bbl, gas_boe, total_boe, opex_usd, planned_boe, record_updated_at) VALUES (src.production_month, src.asset_id, src.oil_bbl, src.gas_boe, src.total_boe, src.opex_usd, src.planned_boe, src.record_updated_at)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.asset_downtime  <-  bronze.asset_downtime_events
   Downtime events. Fixes: swapped start/end timestamps, missing hours recalculated, cause spellings.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_asset_downtime
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'asset_downtime', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.asset_id);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.asset_downtime_events is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'asset_downtime', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.asset_downtime_events b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates */
        DROP TABLE IF EXISTS #src;
        SELECT event_id, asset_id, start_ts, end_ts, downtime_hours, cause, was_ts_swapped, was_hours_recalc
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.asset_downtime AS tgt
        USING #src AS src
           ON tgt.event_id = src.event_id
        WHEN MATCHED AND EXISTS (SELECT src.asset_id, src.start_ts, src.end_ts, src.downtime_hours, src.cause, src.was_ts_swapped, src.was_hours_recalc EXCEPT SELECT tgt.asset_id, tgt.start_ts, tgt.end_ts, tgt.downtime_hours, tgt.cause, tgt.was_ts_swapped, tgt.was_hours_recalc)
            THEN UPDATE SET tgt.asset_id = src.asset_id, tgt.start_ts = src.start_ts, tgt.end_ts = src.end_ts, tgt.downtime_hours = src.downtime_hours, tgt.cause = src.cause, tgt.was_ts_swapped = src.was_ts_swapped, tgt.was_hours_recalc = src.was_hours_recalc
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (event_id, asset_id, start_ts, end_ts, downtime_hours, cause, was_ts_swapped, was_hours_recalc) VALUES (src.event_id, src.asset_id, src.start_ts, src.end_ts, src.downtime_hours, src.cause, src.was_ts_swapped, src.was_hours_recalc)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.lng_sales  <-  bronze.lng_sales_monthly
   Monthly LNG sales per plant, destination and contract type.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_lng_sales
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'lng_sales', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.asset a ON a.asset_id = TRIM(b.plant_asset_id) AND a.asset_type = 'LNG plant';
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.lng_sales_monthly is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'lng_sales', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.lng_sales_monthly b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates */
        DROP TABLE IF EXISTS #src;
        SELECT sale_month, plant_asset_id, destination_code, contract_type, volume_mt, revenue_usd
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY sale_month, plant_asset_id, destination_code, contract_type ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.lng_sales AS tgt
        USING #src AS src
           ON tgt.sale_month = src.sale_month AND tgt.plant_asset_id = src.plant_asset_id AND tgt.destination_code = src.destination_code AND tgt.contract_type = src.contract_type
        WHEN MATCHED AND EXISTS (SELECT src.volume_mt, src.revenue_usd EXCEPT SELECT tgt.volume_mt, tgt.revenue_usd)
            THEN UPDATE SET tgt.volume_mt = src.volume_mt, tgt.revenue_usd = src.revenue_usd
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (sale_month, plant_asset_id, destination_code, contract_type, volume_mt, revenue_usd) VALUES (src.sale_month, src.plant_asset_id, src.destination_code, src.contract_type, src.volume_mt, src.revenue_usd)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.financials  <-  bronze.financials_monthly
   Monthly P&L per segment and country. EBITDA is recalculated; mismatches with the reported value are flagged.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_financials
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'financials', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN etl.value_map  cm ON cm.domain = 'country' AND cm.raw_value = TRIM(b.country);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.financials_monthly is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'financials', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.financials_monthly b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates */
        DROP TABLE IF EXISTS #src;
        SELECT financial_month, segment_id, country_code, revenue_usd, operating_cost_usd, ebitda_usd, ebitda_reported_usd, is_ebitda_mismatch, capex_usd
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY financial_month, segment_id, country_code ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.financials AS tgt
        USING #src AS src
           ON tgt.financial_month = src.financial_month AND tgt.segment_id = src.segment_id AND tgt.country_code = src.country_code
        WHEN MATCHED AND EXISTS (SELECT src.revenue_usd, src.operating_cost_usd, src.ebitda_usd, src.ebitda_reported_usd, src.is_ebitda_mismatch, src.capex_usd EXCEPT SELECT tgt.revenue_usd, tgt.operating_cost_usd, tgt.ebitda_usd, tgt.ebitda_reported_usd, tgt.is_ebitda_mismatch, tgt.capex_usd)
            THEN UPDATE SET tgt.revenue_usd = src.revenue_usd, tgt.operating_cost_usd = src.operating_cost_usd, tgt.ebitda_usd = src.ebitda_usd, tgt.ebitda_reported_usd = src.ebitda_reported_usd, tgt.is_ebitda_mismatch = src.is_ebitda_mismatch, tgt.capex_usd = src.capex_usd
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (financial_month, segment_id, country_code, revenue_usd, operating_cost_usd, ebitda_usd, ebitda_reported_usd, is_ebitda_mismatch, capex_usd) VALUES (src.financial_month, src.segment_id, src.country_code, src.revenue_usd, src.operating_cost_usd, src.ebitda_usd, src.ebitda_reported_usd, src.is_ebitda_mismatch, src.capex_usd)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.emissions  <-  bronze.emissions_monthly
   Monthly GHG emissions per segment, country and scope. Fixes: scope and country spellings.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_emissions
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'emissions', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN etl.value_map  sc ON sc.domain = 'scope'   AND sc.raw_value = TRIM(b.scope);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.emissions_monthly is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'emissions', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.emissions_monthly b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: exact duplicates */
        DROP TABLE IF EXISTS #src;
        SELECT emission_month, segment_id, country_code, scope, tco2e
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY emission_month, segment_id, country_code, scope ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.emissions AS tgt
        USING #src AS src
           ON tgt.emission_month = src.emission_month AND tgt.segment_id = src.segment_id AND tgt.country_code = src.country_code AND tgt.scope = src.scope
        WHEN MATCHED AND EXISTS (SELECT src.tco2e EXCEPT SELECT tgt.tco2e)
            THEN UPDATE SET tgt.tco2e = src.tco2e
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (emission_month, segment_id, country_code, scope, tco2e) VALUES (src.emission_month, src.segment_id, src.country_code, src.scope, src.tco2e)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO

/* -----------------------------------------------------------------------------
   silver.targets  <-  bronze.targets
   Business targets per year and metric.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_targets
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'targets', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        CROSS APPLY etl.tvf_parse_number(b.target_value) v;
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.targets is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'targets', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.targets b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: last loaded row wins */
        DROP TABLE IF EXISTS #src;
        SELECT target_year, metric, unit, target_value
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY target_year, metric ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.targets AS tgt
        USING #src AS src
           ON tgt.target_year = src.target_year AND tgt.metric = src.metric
        WHEN MATCHED AND EXISTS (SELECT src.unit, src.target_value EXCEPT SELECT tgt.unit, tgt.target_value)
            THEN UPDATE SET tgt.unit = src.unit, tgt.target_value = src.target_value
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (target_year, metric, unit, target_value) VALUES (src.target_year, src.metric, src.unit, src.target_value)
        WHEN NOT MATCHED BY SOURCE
            THEN DELETE
        OUTPUT $action INTO #actions;
        COMMIT TRANSACTION;

        SELECT @rows_inserted = COUNT(CASE WHEN action = 'INSERT' THEN 1 END),
               @rows_updated  = COUNT(CASE WHEN action = 'UPDATE' THEN 1 END)
        FROM #actions;

        EXEC etl.usp_log_end @run_id, 'Succeeded', @rows_read, @rows_inserted, @rows_updated, @rows_rejected;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', @rows_read, NULL, NULL, @rows_rejected, @err;
        THROW;
    END CATCH
END;
GO
