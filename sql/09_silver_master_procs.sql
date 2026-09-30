/* =============================================================================
   Shell | Fabric SQL Database | 09 - Silver procedures (master data)
   Generated from sql/_build/silver_template.py (same pattern for every table):
     1. type + validate (CROSS APPLY parsing functions, value_map lookups)
     2. rejected rows -> etl.rejected_rows as JSON with the reason
     3. deduplicate with ROW_NUMBER() on the business key
     4. MERGE into silver (idempotent: re-running changes nothing)
     5. counts + status -> etl.run_log, TRY/CATCH with rollback
============================================================================= */

/* -----------------------------------------------------------------------------
   silver.country  <-  bronze.countries
   Reference list of countries and regions.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_country
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'country', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
        SELECT b.bronze_id,
               CAST(UPPER(TRIM(b.country_code)) AS CHAR(2)) AS country_code,
               TRIM(b.country_name)                         AS country_name,
               TRIM(b.region)                               AS region,
               CASE WHEN LEN(TRIM(b.country_code)) <> 2         THEN 'Invalid country_code'
                    WHEN NULLIF(TRIM(b.country_name), '') IS NULL THEN 'Missing country_name'
                    WHEN NULLIF(TRIM(b.region), '') IS NULL       THEN 'Missing region'
               END AS reject_reason
        INTO #typed
        FROM bronze.countries b;
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.countries is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'country', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.countries b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: last loaded row wins */
        DROP TABLE IF EXISTS #src;
        SELECT country_code, country_name, region
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.country AS tgt
        USING #src AS src
           ON tgt.country_code = src.country_code
        WHEN MATCHED AND EXISTS (SELECT src.country_name, src.region EXCEPT SELECT tgt.country_name, tgt.region)
            THEN UPDATE SET tgt.country_name = src.country_name, tgt.region = src.region
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (country_code, country_name, region) VALUES (src.country_code, src.country_name, src.region)
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
   silver.segment  <-  bronze.segments
   Shell business segments.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_segment
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'segment', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
        SELECT b.bronze_id,
               TRY_CAST(TRIM(b.segment_id) AS TINYINT) AS segment_id,
               TRIM(b.segment_name)                    AS segment_name,
               CASE WHEN TRY_CAST(TRIM(b.segment_id) AS TINYINT) IS NULL THEN 'Invalid segment_id'
                    WHEN NULLIF(TRIM(b.segment_name), '') IS NULL        THEN 'Missing segment_name'
               END AS reject_reason
        INTO #typed
        FROM bronze.segments b;
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.segments is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'segment', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.segments b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: last loaded row wins */
        DROP TABLE IF EXISTS #src;
        SELECT segment_id, segment_name
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY segment_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.segment AS tgt
        USING #src AS src
           ON tgt.segment_id = src.segment_id
        WHEN MATCHED AND EXISTS (SELECT src.segment_name EXCEPT SELECT tgt.segment_name)
            THEN UPDATE SET tgt.segment_name = src.segment_name
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (segment_id, segment_name) VALUES (src.segment_id, src.segment_name)
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
   silver.product  <-  bronze.products
   Retail products (fuel and non-fuel).
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_product
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'product', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
        SELECT b.bronze_id,
               CAST(UPPER(TRIM(b.product_id)) AS CHAR(3)) AS product_id,
               TRIM(b.product_name)                       AS product_name,
               TRIM(b.product_group)                      AS product_group,
               CASE WHEN LEN(TRIM(b.product_id)) <> 3              THEN 'Invalid product_id'
                    WHEN TRIM(b.product_group) NOT IN ('Fuel', 'Non-fuel') THEN 'Invalid product_group'
               END AS reject_reason
        INTO #typed
        FROM bronze.products b;
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.products is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'product', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.products b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: last loaded row wins */
        DROP TABLE IF EXISTS #src;
        SELECT product_id, product_name, product_group
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.product AS tgt
        USING #src AS src
           ON tgt.product_id = src.product_id
        WHEN MATCHED AND EXISTS (SELECT src.product_name, src.product_group EXCEPT SELECT tgt.product_name, tgt.product_group)
            THEN UPDATE SET tgt.product_name = src.product_name, tgt.product_group = src.product_group
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (product_id, product_name, product_group) VALUES (src.product_id, src.product_name, src.product_group)
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
   silver.site  <-  bronze.sites
   Retail stations. Fixes: country spellings, city case/spaces, EV flag variants, missing coordinates.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_site
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'site', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN etl.value_map fl ON fl.domain = 'flag'    AND fl.raw_value = TRIM(b.has_ev_charging);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.sites is empty: silver left unchanged (protects against deleting everything).', 1;

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
        WHERE t.latitude IS NULL OR t.longitude IS NULL;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'site', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.sites b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: duplicated site rows, last loaded wins */
        DROP TABLE IF EXISTS #src;
        SELECT site_id, site_name, city, country_code, latitude, longitude, is_geo_imputed, site_format, opening_date, has_ev_charging, ev_since_date, ev_charge_points
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.site AS tgt
        USING #src AS src
           ON tgt.site_id = src.site_id
        WHEN MATCHED AND EXISTS (SELECT src.site_name, src.city, src.country_code, src.latitude, src.longitude, src.is_geo_imputed, src.site_format, src.opening_date, src.has_ev_charging, src.ev_since_date, src.ev_charge_points EXCEPT SELECT tgt.site_name, tgt.city, tgt.country_code, tgt.latitude, tgt.longitude, tgt.is_geo_imputed, tgt.site_format, tgt.opening_date, tgt.has_ev_charging, tgt.ev_since_date, tgt.ev_charge_points)
            THEN UPDATE SET tgt.site_name = src.site_name, tgt.city = src.city, tgt.country_code = src.country_code, tgt.latitude = src.latitude, tgt.longitude = src.longitude, tgt.is_geo_imputed = src.is_geo_imputed, tgt.site_format = src.site_format, tgt.opening_date = src.opening_date, tgt.has_ev_charging = src.has_ev_charging, tgt.ev_since_date = src.ev_since_date, tgt.ev_charge_points = src.ev_charge_points
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (site_id, site_name, city, country_code, latitude, longitude, is_geo_imputed, site_format, opening_date, has_ev_charging, ev_since_date, ev_charge_points) VALUES (src.site_id, src.site_name, src.city, src.country_code, src.latitude, src.longitude, src.is_geo_imputed, src.site_format, src.opening_date, src.has_ev_charging, src.ev_since_date, src.ev_charge_points)
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
   silver.asset  <-  bronze.assets
   Upstream fields and LNG plants. Fixes: country spellings, name spaces, asset_type case.
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_asset
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', 'asset', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
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
        LEFT JOIN silver.segment sg ON sg.segment_id = TRY_CAST(TRIM(b.segment_id) AS TINYINT);
        SET @rows_read = @@ROWCOUNT;
        IF @rows_read = 0
            THROW 50002, 'bronze.assets is empty: silver left unchanged (protects against deleting everything).', 1;

        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, 'asset', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.assets b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: last loaded row wins */
        DROP TABLE IF EXISTS #src;
        SELECT asset_id, asset_name, asset_type, country_code, segment_id, start_date, capacity_value, capacity_unit
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY bronze_id DESC) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.asset AS tgt
        USING #src AS src
           ON tgt.asset_id = src.asset_id
        WHEN MATCHED AND EXISTS (SELECT src.asset_name, src.asset_type, src.country_code, src.segment_id, src.start_date, src.capacity_value, src.capacity_unit EXCEPT SELECT tgt.asset_name, tgt.asset_type, tgt.country_code, tgt.segment_id, tgt.start_date, tgt.capacity_value, tgt.capacity_unit)
            THEN UPDATE SET tgt.asset_name = src.asset_name, tgt.asset_type = src.asset_type, tgt.country_code = src.country_code, tgt.segment_id = src.segment_id, tgt.start_date = src.start_date, tgt.capacity_value = src.capacity_value, tgt.capacity_unit = src.capacity_unit
        WHEN NOT MATCHED BY TARGET
            THEN INSERT (asset_id, asset_name, asset_type, country_code, segment_id, start_date, capacity_value, capacity_unit) VALUES (src.asset_id, src.asset_name, src.asset_type, src.country_code, src.segment_id, src.start_date, src.capacity_value, src.capacity_unit)
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
