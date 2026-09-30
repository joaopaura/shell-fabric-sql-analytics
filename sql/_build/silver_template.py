"""Builds the silver stored procedures from one template, so every table follows the
same pattern: type + validate -> log rejects -> deduplicate -> MERGE -> log run.
Run: python sql/_build/silver_template.py  (writes 09_silver_master_procs.sql and 10_silver_fact_procs.sql)"""
from pathlib import Path
from silver_specs import MASTER, FACTS

TEMPLATE = """/* -----------------------------------------------------------------------------
   silver.{target}  <-  bronze.{bronze}
   {doc}
----------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.usp_silver_{target}
    @pipeline_run_id NVARCHAR(100) = 'manual'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @run_id BIGINT, @rows_read BIGINT, @rows_rejected BIGINT, @rows_inserted BIGINT, @rows_updated BIGINT;
    EXEC etl.usp_log_start @pipeline_run_id, 'silver', '{target}', @run_id OUTPUT;

    BEGIN TRY
        /* 1. type and validate every bronze row */
        DROP TABLE IF EXISTS #typed;
{typed}
        SET @rows_read = @@ROWCOUNT;
        ALTER TABLE #typed ALTER COLUMN reject_reason NVARCHAR(200) NULL;  -- room for any reason text
        IF @rows_read = 0
            THROW 50002, 'bronze.{bronze} is empty: silver left unchanged (protects against deleting everything).', 1;
{post}
        /* 2. keep rejected rows (original values as JSON) */
        INSERT INTO etl.rejected_rows (run_id, table_name, reject_reason, source_row)
        SELECT @run_id, '{target}', t.reject_reason, (SELECT b.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM #typed t
        JOIN bronze.{bronze} b ON b.bronze_id = t.bronze_id
        WHERE t.reject_reason IS NOT NULL;
        SET @rows_rejected = @@ROWCOUNT;

        /* 3. one row per business key: {dedup_doc} */
        DROP TABLE IF EXISTS #src;
        SELECT {cols}
        INTO #src
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY {key} ORDER BY {order}) AS rn
            FROM #typed
            WHERE reject_reason IS NULL
        ) x
        WHERE rn = 1;

        /* 4. synchronise silver (insert new, update changed, delete vanished) */
        DROP TABLE IF EXISTS #actions;
        CREATE TABLE #actions (action NVARCHAR(10));
        BEGIN TRANSACTION;
        MERGE silver.{target} AS tgt
        USING #src AS src
           ON {on}
        WHEN MATCHED AND EXISTS (SELECT {src_cmp} EXCEPT SELECT {tgt_cmp})
            THEN UPDATE SET {set}
        WHEN NOT MATCHED BY TARGET
            THEN INSERT ({cols}) VALUES ({src_cols})
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
"""


def indent(sql, n=8):
    return "\n".join((" " * n + l) if l.strip() else "" for l in sql.strip("\n").split("\n"))


def build(spec):
    cols, key = spec["cols"], spec["key"]
    non_key = [c for c in cols if c not in key]
    return TEMPLATE.format(
        target=spec["target"], bronze=spec["bronze"], doc=spec["doc"], dedup_doc=spec["dedup_doc"],
        typed=indent(spec["typed"]), post=("\n" + indent(spec["post"]) + "\n") if spec.get("post") else "",
        cols=", ".join(cols), key=", ".join(key), order=spec["order"],
        on=" AND ".join(f"tgt.{k} = src.{k}" for k in key),
        src_cmp=", ".join(f"src.{c}" for c in non_key), tgt_cmp=", ".join(f"tgt.{c}" for c in non_key),
        set=", ".join(f"tgt.{c} = src.{c}" for c in non_key),
        src_cols=", ".join(f"src.{c}" for c in cols))


HEADER = """/* =============================================================================
   Shell | Fabric SQL Database | {n} - Silver procedures ({what})
   Generated from sql/_build/silver_template.py (same pattern for every table):
     1. type + validate (CROSS APPLY parsing functions, value_map lookups)
     2. rejected rows -> etl.rejected_rows as JSON with the reason
     3. deduplicate with ROW_NUMBER() on the business key
     4. MERGE into silver (idempotent: re-running changes nothing)
     5. counts + status -> etl.run_log, TRY/CATCH with rollback
============================================================================= */

"""

ORCHESTRATOR = "\n/* -----------------------------------------------------------------------------\n   Orchestrator: master data first (facts validate against it), then facts.\n   Called by the Fabric pipeline with its run id.\n----------------------------------------------------------------------------- */\nCREATE OR ALTER PROCEDURE etl.usp_silver_all\n    @pipeline_run_id NVARCHAR(100) = 'manual'\nAS\nBEGIN\n    SET NOCOUNT ON;\n    EXEC etl.usp_silver_country             @pipeline_run_id;\n    EXEC etl.usp_silver_segment             @pipeline_run_id;\n    EXEC etl.usp_silver_product             @pipeline_run_id;\n    EXEC etl.usp_silver_site                @pipeline_run_id;\n    EXEC etl.usp_silver_asset               @pipeline_run_id;\n    EXEC etl.usp_silver_retail_sales        @pipeline_run_id;\n    EXEC etl.usp_silver_ev_charging         @pipeline_run_id;\n    EXEC etl.usp_silver_production_monthly  @pipeline_run_id;\n    EXEC etl.usp_silver_asset_downtime      @pipeline_run_id;\n    EXEC etl.usp_silver_lng_sales           @pipeline_run_id;\n    EXEC etl.usp_silver_financials          @pipeline_run_id;\n    EXEC etl.usp_silver_emissions           @pipeline_run_id;\n    EXEC etl.usp_silver_targets             @pipeline_run_id;\nEND;\nGO\n"

here = Path(__file__).parent
(here.parent / "09_silver_master_procs.sql").write_text(
    HEADER.format(n="09", what="master data") + "\n".join(build(s) for s in MASTER), encoding="utf-8")
(here.parent / "10_silver_fact_procs.sql").write_text(
    HEADER.format(n="10", what="facts") + "\n".join(build(s) for s in FACTS) + ORCHESTRATOR, encoding="utf-8")
print("ok")
