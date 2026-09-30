/* =============================================================================
   Shell | Fabric SQL Database | 04 - Bronze tables
   Landing tables loaded 1:1 from the CSV files by the pipeline Copy activity.
   Every business column is NVARCHAR on purpose: bronze never rejects a row,
   typing and validation happen in silver where failures are logged.
   bronze_id   : surrogate key (also required for OneLake mirroring)
   source_file : filled by the Copy activity (additional column $$FILEPATH)
   loaded_at   : load timestamp
============================================================================= */

DROP TABLE IF EXISTS bronze.countries;
CREATE TABLE bronze.countries (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_countries PRIMARY KEY,
    country_code           NVARCHAR(100) NULL,
    country_name           NVARCHAR(100) NULL,
    region                 NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_countries_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.segments;
CREATE TABLE bronze.segments (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_segments PRIMARY KEY,
    segment_id             NVARCHAR(100) NULL,
    segment_name           NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_segments_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.products;
CREATE TABLE bronze.products (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_products PRIMARY KEY,
    product_id             NVARCHAR(100) NULL,
    product_name           NVARCHAR(100) NULL,
    product_group          NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_products_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.sites;
CREATE TABLE bronze.sites (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_sites PRIMARY KEY,
    site_id                NVARCHAR(100) NULL,
    site_name              NVARCHAR(200) NULL,
    city                   NVARCHAR(100) NULL,
    country                NVARCHAR(100) NULL,
    latitude               NVARCHAR(100) NULL,
    longitude              NVARCHAR(100) NULL,
    site_format            NVARCHAR(100) NULL,
    opening_date           NVARCHAR(100) NULL,
    has_ev_charging        NVARCHAR(100) NULL,
    ev_since_date          NVARCHAR(100) NULL,
    ev_charge_points       NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_sites_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.assets;
CREATE TABLE bronze.assets (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_assets PRIMARY KEY,
    asset_id               NVARCHAR(100) NULL,
    asset_name             NVARCHAR(200) NULL,
    asset_type             NVARCHAR(100) NULL,
    country                NVARCHAR(100) NULL,
    segment_id             NVARCHAR(100) NULL,
    start_date             NVARCHAR(100) NULL,
    capacity_value         NVARCHAR(100) NULL,
    capacity_unit          NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_assets_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.retail_sales;
CREATE TABLE bronze.retail_sales (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_retail_sales PRIMARY KEY,
    transaction_date       NVARCHAR(100) NULL,
    site_id                NVARCHAR(100) NULL,
    product                NVARCHAR(100) NULL,
    volume_litres          NVARCHAR(100) NULL,
    revenue_usd            NVARCHAR(100) NULL,
    cost_usd               NVARCHAR(100) NULL,
    transactions           NVARCHAR(100) NULL,
    record_updated_at      NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_retail_sales_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.ev_charging;
CREATE TABLE bronze.ev_charging (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_ev_charging PRIMARY KEY,
    charge_date            NVARCHAR(100) NULL,
    site_id                NVARCHAR(100) NULL,
    sessions               NVARCHAR(100) NULL,
    energy_mwh             NVARCHAR(100) NULL,
    revenue_usd            NVARCHAR(100) NULL,
    avg_session_minutes    NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_ev_charging_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.production_monthly;
CREATE TABLE bronze.production_monthly (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_production_monthly PRIMARY KEY,
    production_month       NVARCHAR(100) NULL,
    asset_id               NVARCHAR(100) NULL,
    oil_bbl                NVARCHAR(100) NULL,
    gas_boe                NVARCHAR(100) NULL,
    total_boe              NVARCHAR(100) NULL,
    opex_usd               NVARCHAR(100) NULL,
    planned_boe            NVARCHAR(100) NULL,
    record_updated_at      NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_production_monthly_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.asset_downtime_events;
CREATE TABLE bronze.asset_downtime_events (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_asset_downtime_events PRIMARY KEY,
    event_id               NVARCHAR(100) NULL,
    asset_id               NVARCHAR(100) NULL,
    start_ts               NVARCHAR(100) NULL,
    end_ts                 NVARCHAR(100) NULL,
    downtime_hours         NVARCHAR(100) NULL,
    cause                  NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_asset_downtime_events_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.lng_sales_monthly;
CREATE TABLE bronze.lng_sales_monthly (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_lng_sales_monthly PRIMARY KEY,
    sale_month             NVARCHAR(100) NULL,
    plant_asset_id         NVARCHAR(100) NULL,
    destination_country    NVARCHAR(100) NULL,
    contract_type          NVARCHAR(100) NULL,
    volume_mt              NVARCHAR(100) NULL,
    revenue_usd            NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_lng_sales_monthly_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.financials_monthly;
CREATE TABLE bronze.financials_monthly (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_financials_monthly PRIMARY KEY,
    financial_month        NVARCHAR(100) NULL,
    segment                NVARCHAR(100) NULL,
    country                NVARCHAR(100) NULL,
    revenue_usd            NVARCHAR(100) NULL,
    operating_cost_usd     NVARCHAR(100) NULL,
    ebitda_usd             NVARCHAR(100) NULL,
    capex_usd              NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_financials_monthly_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.emissions_monthly;
CREATE TABLE bronze.emissions_monthly (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_emissions_monthly PRIMARY KEY,
    emission_month         NVARCHAR(100) NULL,
    segment                NVARCHAR(100) NULL,
    country                NVARCHAR(100) NULL,
    scope                  NVARCHAR(100) NULL,
    tco2e                  NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_emissions_monthly_loaded DEFAULT (SYSUTCDATETIME())
);

DROP TABLE IF EXISTS bronze.targets;
CREATE TABLE bronze.targets (
    bronze_id    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_bronze_targets PRIMARY KEY,
    target_year            NVARCHAR(100) NULL,
    metric                 NVARCHAR(100) NULL,
    unit                   NVARCHAR(100) NULL,
    target_value           NVARCHAR(100) NULL,
    source_file            NVARCHAR(400) NULL,
    loaded_at              DATETIME2(0) NOT NULL CONSTRAINT df_bronze_targets_loaded DEFAULT (SYSUTCDATETIME())
);

SELECT t.name AS bronze_table, COUNT(c.column_id) AS columns
FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id
WHERE SCHEMA_NAME(t.schema_id) = 'bronze'
GROUP BY t.name ORDER BY t.name;
