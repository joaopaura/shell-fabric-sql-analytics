/* =============================================================================
   Shell | Fabric SQL Database | 06 - Logging and helper procedures
   Every silver / gold / DQ procedure calls usp_log_start + usp_log_end.
   The pipeline calls usp_prepare_bronze before each Copy and usp_log_copy after it.
============================================================================= */

CREATE OR ALTER PROCEDURE etl.usp_log_start
    @pipeline_run_id NVARCHAR(100),
    @step            NVARCHAR(20),
    @object_name     NVARCHAR(100),
    @run_id          BIGINT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO etl.run_log (pipeline_run_id, step, object_name)
    VALUES (@pipeline_run_id, @step, @object_name);
    SET @run_id = SCOPE_IDENTITY();
END;
GO

CREATE OR ALTER PROCEDURE etl.usp_log_end
    @run_id         BIGINT,
    @status         NVARCHAR(20),
    @rows_read      BIGINT = NULL,
    @rows_inserted  BIGINT = NULL,
    @rows_updated   BIGINT = NULL,
    @rows_rejected  BIGINT = NULL,
    @error_message  NVARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE etl.run_log
       SET ended_at      = SYSUTCDATETIME(),
           status        = @status,
           rows_read     = @rows_read,
           rows_inserted = @rows_inserted,
           rows_updated  = @rows_updated,
           rows_rejected = @rows_rejected,
           error_message = @error_message
     WHERE run_id = @run_id;
END;
GO

/* Empties one bronze table before the Copy activity reloads it.
   The name is validated against etl.source_config, so the dynamic SQL
   can only ever touch a known bronze table. */
CREATE OR ALTER PROCEDURE etl.usp_prepare_bronze
    @bronze_table NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM etl.source_config WHERE bronze_table = @bronze_table)
        THROW 50001, 'Unknown bronze table. Check etl.source_config.', 1;

    DECLARE @sql NVARCHAR(400) = N'TRUNCATE TABLE bronze.' + QUOTENAME(@bronze_table) + N';';
    EXEC sp_executesql @sql;
END;
GO

/* Logs the result of one Copy activity (rows copied comes from the activity output). */
CREATE OR ALTER PROCEDURE etl.usp_log_copy
    @pipeline_run_id NVARCHAR(100),
    @bronze_table    NVARCHAR(100),
    @rows_copied     BIGINT,
    @status          NVARCHAR(20)   = 'Succeeded',
    @error_message   NVARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO etl.run_log (pipeline_run_id, step, object_name, ended_at, status,
                             rows_read, rows_inserted, error_message)
    VALUES (@pipeline_run_id, 'bronze', @bronze_table, SYSUTCDATETIME(), @status,
            @rows_copied, @rows_copied, @error_message);
END;
GO

-- quick test: writes one fake entry and shows it
DECLARE @id BIGINT;
EXEC etl.usp_log_start @pipeline_run_id = 'manual-test', @step = 'test', @object_name = 'logging', @run_id = @id OUTPUT;
EXEC etl.usp_log_end   @run_id = @id, @status = 'Succeeded', @rows_read = 0;
SELECT * FROM etl.run_log WHERE pipeline_run_id = 'manual-test';
DELETE FROM etl.run_log WHERE pipeline_run_id = 'manual-test';
