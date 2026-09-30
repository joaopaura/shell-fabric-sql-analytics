/* =============================================================================
   Shell | Fabric SQL Database | 13 - Data quality checks
   Runs after gold. Each check writes expected vs actual to etl.dq_results;
   the Data Pipeline & Quality page in Power BI reads them.
   A failed check does not stop the pipeline: it is reported, like in production.
============================================================================= */
CREATE OR ALTER PROCEDURE etl.usp_run_dq_checks
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id BIGINT, @n BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'dq', 'usp_run_dq_checks', @run_id OUTPUT;

    BEGIN TRY
        DECLARE @checks TABLE (check_name NVARCHAR(200), table_name NVARCHAR(100),
                               expected_value NVARCHAR(100), actual_value NVARCHAR(100), passed BIT);

        /* 1. completeness: silver and gold facts have the same row count */
        INSERT INTO @checks
        SELECT 'Row count silver = gold', t.name, CAST(t.silver_rows AS NVARCHAR(100)), CAST(t.gold_rows AS NVARCHAR(100)),
               CASE WHEN t.silver_rows = t.gold_rows THEN 1 ELSE 0 END
        FROM (VALUES
            ('fact_retail_sales', (SELECT COUNT_BIG(*) FROM silver.retail_sales),       (SELECT COUNT_BIG(*) FROM gold.fact_retail_sales)),
            ('fact_ev_charging',  (SELECT COUNT_BIG(*) FROM silver.ev_charging),        (SELECT COUNT_BIG(*) FROM gold.fact_ev_charging)),
            ('fact_production',   (SELECT COUNT_BIG(*) FROM silver.production_monthly), (SELECT COUNT_BIG(*) FROM gold.fact_production)),
            ('fact_lng_sales',    (SELECT COUNT_BIG(*) FROM silver.lng_sales),          (SELECT COUNT_BIG(*) FROM gold.fact_lng_sales)),
            ('fact_financials',   (SELECT COUNT_BIG(*) FROM silver.financials),         (SELECT COUNT_BIG(*) FROM gold.fact_financials)),
            ('fact_emissions',    (SELECT COUNT_BIG(*) FROM silver.emissions),          (SELECT COUNT_BIG(*) FROM gold.fact_emissions))
        ) t(name, silver_rows, gold_rows);

        /* 2. reconciliation: revenue is not lost or duplicated between layers */
        INSERT INTO @checks
        SELECT 'Revenue silver = gold (USD)', 'fact_retail_sales',
               FORMAT(s.v, 'N2'), FORMAT(g.v, 'N2'), CASE WHEN s.v = g.v THEN 1 ELSE 0 END
        FROM (SELECT SUM(revenue_usd) v FROM silver.retail_sales) s
        CROSS JOIN (SELECT SUM(revenue_usd) v FROM gold.fact_retail_sales) g;

        /* 3. referential integrity: every fact key exists in its dimension */
        INSERT INTO @checks
        SELECT 'Orphan keys (fact without dimension)', t.name, '0', CAST(t.orphans AS NVARCHAR(100)),
               CASE WHEN t.orphans = 0 THEN 1 ELSE 0 END
        FROM (VALUES
            ('fact_retail_sales -> dim_site',    (SELECT COUNT_BIG(*) FROM gold.fact_retail_sales f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_site d WHERE d.site_id = f.site_id))),
            ('fact_retail_sales -> dim_product', (SELECT COUNT_BIG(*) FROM gold.fact_retail_sales f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_product d WHERE d.product_id = f.product_id))),
            ('fact_retail_sales -> dim_date',    (SELECT COUNT_BIG(*) FROM gold.fact_retail_sales f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_date d WHERE d.date_key = f.date_key))),
            ('fact_ev_charging -> dim_site',     (SELECT COUNT_BIG(*) FROM gold.fact_ev_charging f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_site d WHERE d.site_id = f.site_id))),
            ('fact_production -> dim_asset',     (SELECT COUNT_BIG(*) FROM gold.fact_production f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_asset d WHERE d.asset_id = f.asset_id))),
            ('fact_lng_sales -> dim_country',    (SELECT COUNT_BIG(*) FROM gold.fact_lng_sales f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_country d WHERE d.country_code = f.destination_country_code))),
            ('fact_financials -> dim_country',   (SELECT COUNT_BIG(*) FROM gold.fact_financials f WHERE NOT EXISTS (SELECT 1 FROM gold.dim_country d WHERE d.country_code = f.country_code)))
        ) t(name, orphans);

        /* 4. business rules */
        INSERT INTO @checks
        SELECT 'Production total = oil + gas', 'fact_production', '0',
               CAST(COUNT_BIG(*) AS NVARCHAR(100)), CASE WHEN COUNT_BIG(*) = 0 THEN 1 ELSE 0 END
        FROM gold.fact_production WHERE ABS(total_boe - oil_bbl - gas_boe) > 0.001 * total_boe + 2;

        INSERT INTO @checks
        SELECT 'No negative or extreme fuel volumes', 'fact_retail_sales', '0',
               CAST(COUNT_BIG(*) AS NVARCHAR(100)), CASE WHEN COUNT_BIG(*) = 0 THEN 1 ELSE 0 END
        FROM gold.fact_retail_sales WHERE volume_litres < 0 OR volume_litres > 200000;

        INSERT INTO @checks
        SELECT 'Reported EBITDA = revenue - cost', 'fact_financials', '0',
               CAST(SUM(CAST(is_ebitda_mismatch AS INT)) AS NVARCHAR(100)),
               CASE WHEN SUM(CAST(is_ebitda_mismatch AS INT)) = 0 THEN 1 ELSE 0 END
        FROM gold.fact_financials;

        INSERT INTO @checks
        SELECT 'Imputed fuel volume share < 1%', 'fact_retail_sales', '< 1.00%',
               FORMAT(AVG(CAST(is_volume_imputed AS FLOAT)), 'P2'),
               CASE WHEN AVG(CAST(is_volume_imputed AS FLOAT)) < 0.01 THEN 1 ELSE 0 END
        FROM gold.fact_retail_sales WHERE volume_litres IS NOT NULL;

        /* 5. freshness: data reaches the expected period end */
        INSERT INTO @checks
        SELECT 'Latest sales date', 'fact_retail_sales', '20251231', CAST(MAX(date_key) AS NVARCHAR(100)),
               CASE WHEN MAX(date_key) >= 20251231 THEN 1 ELSE 0 END
        FROM gold.fact_retail_sales;

        /* 6. rejection rate per silver table in this run stays under 2% */
        INSERT INTO @checks
        SELECT 'Reject rate < 2%', l.object_name, '< 2.00%',
               FORMAT(1.0 * l.rows_rejected / NULLIF(l.rows_read, 0), 'P2'),
               CASE WHEN 1.0 * l.rows_rejected / NULLIF(l.rows_read, 0) < 0.02 THEN 1 ELSE 0 END
        FROM etl.run_log l
        WHERE l.pipeline_run_id = @pipeline_run_id AND l.step = 'silver' AND l.status = 'Succeeded';

        INSERT INTO etl.dq_results (pipeline_run_id, check_name, table_name, expected_value, actual_value, passed)
        SELECT @pipeline_run_id, check_name, table_name, expected_value, actual_value, passed FROM @checks;
        SET @n = @@ROWCOUNT;

        DECLARE @failed BIGINT = (SELECT COUNT(*) FROM @checks WHERE passed = 0);
        EXEC etl.usp_log_end @run_id, 'Succeeded', @n, @n, NULL, @failed;   -- rows_rejected = failed checks

        SELECT check_name, table_name, expected_value, actual_value,
               CASE passed WHEN 1 THEN 'PASS' ELSE 'FAIL' END AS result
        FROM @checks ORDER BY passed, check_name, table_name;
    END TRY
    BEGIN CATCH
        DECLARE @err NVARCHAR(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log_end @run_id, 'Failed', NULL, NULL, NULL, NULL, @err;
        THROW;
    END CATCH
END;
GO
