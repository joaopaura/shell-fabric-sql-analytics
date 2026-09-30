/* =============================================================================
   Shell | Fabric SQL Database | 02 - ETL metadata, logging and audit tables
============================================================================= */

-- Sources the pipeline loads (drives the Lookup + ForEach in the Fabric pipeline)
DROP TABLE IF EXISTS etl.source_config;
CREATE TABLE etl.source_config (
    source_id      INT           NOT NULL CONSTRAINT pk_source_config PRIMARY KEY,
    source_name    NVARCHAR(50)  NOT NULL,
    folder_path    NVARCHAR(200) NOT NULL,   -- inside Lakehouse Files
    file_pattern   NVARCHAR(100) NOT NULL,   -- wildcard used by the Copy activity
    bronze_table   NVARCHAR(100) NOT NULL,
    load_order     INT           NOT NULL,
    is_active      BIT           NOT NULL CONSTRAINT df_source_config_active DEFAULT (1)
);

INSERT INTO etl.source_config (source_id, source_name, folder_path, file_pattern, bronze_table, load_order) VALUES
 ( 1, 'countries',              'raw/master',       'countries.csv',                 'countries',              1),
 ( 2, 'segments',               'raw/master',       'segments.csv',                  'segments',               1),
 ( 3, 'products',               'raw/master',       'products.csv',                  'products',               1),
 ( 4, 'sites',                  'raw/master',       'sites.csv',                     'sites',                  1),
 ( 5, 'assets',                 'raw/master',       'assets.csv',                    'assets',                 1),
 ( 6, 'retail_sales',           'raw/retail_sales', 'retail_sales_*.csv',            'retail_sales',           2),
 ( 7, 'ev_charging',            'raw/ev_charging',  'ev_charging_*.csv',             'ev_charging',            2),
 ( 8, 'production_monthly',     'raw/upstream',     'production_monthly.csv',        'production_monthly',     2),
 ( 9, 'asset_downtime_events',  'raw/upstream',     'asset_downtime_events.csv',     'asset_downtime_events',  2),
 (10, 'lng_sales_monthly',      'raw/upstream',     'lng_sales_monthly.csv',         'lng_sales_monthly',      2),
 (11, 'financials_monthly',     'raw/group',        'financials_monthly.csv',        'financials_monthly',     2),
 (12, 'emissions_monthly',      'raw/group',        'emissions_monthly.csv',         'emissions_monthly',      2),
 (13, 'targets',                'raw/group',        'targets.csv',                   'targets',                2);

-- One row per step execution (bronze copy, silver proc, gold build, DQ checks)
DROP TABLE IF EXISTS etl.run_log;
CREATE TABLE etl.run_log (
    run_id            BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_run_log PRIMARY KEY,
    pipeline_run_id   NVARCHAR(100)  NOT NULL,
    step              NVARCHAR(20)   NOT NULL,          -- bronze | silver | gold | dq
    object_name       NVARCHAR(100)  NOT NULL,
    started_at        DATETIME2(0)   NOT NULL CONSTRAINT df_run_log_start DEFAULT (SYSUTCDATETIME()),
    ended_at          DATETIME2(0)   NULL,
    status            NVARCHAR(20)   NOT NULL CONSTRAINT df_run_log_status DEFAULT ('Running'),
    rows_read         BIGINT         NULL,
    rows_inserted     BIGINT         NULL,
    rows_updated      BIGINT         NULL,
    rows_rejected     BIGINT         NULL,
    error_message     NVARCHAR(4000) NULL,
    duration_seconds  AS DATEDIFF(SECOND, started_at, ended_at),
    CONSTRAINT ck_run_log_status CHECK (status IN ('Running', 'Succeeded', 'Failed'))
);

-- Rows that failed validation in silver, kept as JSON for investigation
DROP TABLE IF EXISTS etl.rejected_rows;
CREATE TABLE etl.rejected_rows (
    reject_id      BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_rejected_rows PRIMARY KEY,
    run_id         BIGINT        NOT NULL,
    table_name     NVARCHAR(100) NOT NULL,
    reject_reason  NVARCHAR(200) NOT NULL,
    source_row     NVARCHAR(MAX) NULL,
    rejected_at    DATETIME2(0)  NOT NULL CONSTRAINT df_rejected_at DEFAULT (SYSUTCDATETIME())
);

-- Data quality checks executed after gold is built
DROP TABLE IF EXISTS etl.dq_results;
CREATE TABLE etl.dq_results (
    dq_id            BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_dq_results PRIMARY KEY,
    pipeline_run_id  NVARCHAR(100)  NOT NULL,
    check_name       NVARCHAR(200)  NOT NULL,
    table_name       NVARCHAR(100)  NOT NULL,
    expected_value   NVARCHAR(100)  NULL,
    actual_value     NVARCHAR(100)  NULL,
    passed           BIT            NOT NULL,
    checked_at       DATETIME2(0)   NOT NULL CONSTRAINT df_dq_checked DEFAULT (SYSUTCDATETIME())
);
