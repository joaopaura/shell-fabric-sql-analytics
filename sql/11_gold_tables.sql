/* =============================================================================
   Shell | Fabric SQL Database | 11 - Gold star schema (consumed by Power BI)
   Conformed dimensions + one fact per business process. Natural keys are kept
   (site_id, asset_id, ...) because they are stable and readable; dates use
   date_key (yyyymmdd) to join gold.dim_date (script 05).
============================================================================= */
DROP TABLE IF EXISTS gold.fact_retail_sales, gold.fact_ev_charging, gold.fact_production, gold.fact_asset_downtime,
                     gold.fact_lng_sales, gold.fact_financials, gold.fact_emissions, gold.fact_targets,
                     gold.dim_site, gold.dim_asset, gold.dim_product, gold.dim_segment, gold.dim_country;

-- ---------------------------------------------------------------- dimensions
CREATE TABLE gold.dim_country (
    country_code   CHAR(2)       NOT NULL CONSTRAINT pk_g_dim_country PRIMARY KEY,
    country_name   NVARCHAR(100) NOT NULL,
    region         NVARCHAR(50)  NOT NULL,
    has_mobility   BIT           NOT NULL,   -- country with Shell retail sites
    has_upstream   BIT           NOT NULL    -- country with upstream / LNG assets
);

CREATE TABLE gold.dim_segment (
    segment_id     TINYINT      NOT NULL CONSTRAINT pk_g_dim_segment PRIMARY KEY,
    segment_name   NVARCHAR(50) NOT NULL,
    is_low_carbon  BIT          NOT NULL,
    sort_order     TINYINT      NOT NULL
);

CREATE TABLE gold.dim_product (
    product_id     CHAR(3)      NOT NULL CONSTRAINT pk_g_dim_product PRIMARY KEY,
    product_name   NVARCHAR(50) NOT NULL,
    product_group  NVARCHAR(20) NOT NULL
);

CREATE TABLE gold.dim_site (
    site_id           VARCHAR(10)   NOT NULL CONSTRAINT pk_g_dim_site PRIMARY KEY,
    site_name         NVARCHAR(200) NOT NULL,
    city              NVARCHAR(100) NOT NULL,
    country_code      CHAR(2)       NOT NULL,
    latitude          DECIMAL(9, 5) NULL,
    longitude         DECIMAL(9, 5) NULL,
    site_format       NVARCHAR(20)  NOT NULL,
    opening_date      DATE          NOT NULL,
    opening_year      SMALLINT      NOT NULL,
    has_ev_charging   BIT           NOT NULL,
    ev_status         NVARCHAR(20)  NOT NULL,   -- 'EV hub' / 'Fuel only'
    ev_since_date     DATE          NULL,
    ev_charge_points  SMALLINT      NOT NULL
);

CREATE TABLE gold.dim_asset (
    asset_id        VARCHAR(10)    NOT NULL CONSTRAINT pk_g_dim_asset PRIMARY KEY,
    asset_name      NVARCHAR(200)  NOT NULL,
    asset_type      NVARCHAR(20)   NOT NULL,
    country_code    CHAR(2)        NOT NULL,
    segment_id      TINYINT        NOT NULL,
    start_date      DATE           NOT NULL,
    capacity_value  DECIMAL(12, 2) NOT NULL,
    capacity_unit   NVARCHAR(10)   NOT NULL,
    capacity_label  NVARCHAR(40)   NOT NULL
);

-- ---------------------------------------------------------------- facts
CREATE TABLE gold.fact_retail_sales (
    date_key           INT            NOT NULL,
    site_id            VARCHAR(10)    NOT NULL,
    product_id         CHAR(3)        NOT NULL,
    volume_litres      DECIMAL(12, 1) NULL,
    revenue_usd        DECIMAL(14, 2) NOT NULL,
    cost_usd           DECIMAL(14, 2) NOT NULL,
    gross_margin_usd   DECIMAL(14, 2) NOT NULL,
    transactions       INT            NOT NULL,
    is_volume_imputed  BIT            NOT NULL,
    CONSTRAINT pk_g_fact_retail PRIMARY KEY (date_key, site_id, product_id)
);

CREATE TABLE gold.fact_ev_charging (
    date_key             INT            NOT NULL,
    site_id              VARCHAR(10)    NOT NULL,
    sessions             INT            NOT NULL,
    energy_mwh           DECIMAL(10, 3) NOT NULL,
    revenue_usd          DECIMAL(12, 2) NOT NULL,
    avg_session_minutes  DECIMAL(6, 1)  NOT NULL,
    CONSTRAINT pk_g_fact_ev PRIMARY KEY (date_key, site_id)
);

CREATE TABLE gold.fact_production (
    date_key          INT            NOT NULL,   -- first day of the month
    asset_id          VARCHAR(10)    NOT NULL,
    oil_bbl           BIGINT         NOT NULL,
    gas_boe           BIGINT         NOT NULL,
    total_boe         BIGINT         NOT NULL,
    planned_boe       BIGINT         NOT NULL,
    opex_usd          DECIMAL(16, 2) NOT NULL,
    days_in_month     TINYINT        NOT NULL,
    downtime_hours    DECIMAL(8, 1)  NOT NULL,
    CONSTRAINT pk_g_fact_production PRIMARY KEY (date_key, asset_id)
);

CREATE TABLE gold.fact_asset_downtime (
    event_id        VARCHAR(10)   NOT NULL CONSTRAINT pk_g_fact_downtime PRIMARY KEY,
    date_key        INT           NOT NULL,   -- start date
    asset_id        VARCHAR(10)   NOT NULL,
    start_ts        DATETIME2(0)  NOT NULL,
    end_ts          DATETIME2(0)  NOT NULL,
    downtime_hours  DECIMAL(8, 1) NOT NULL,
    cause           NVARCHAR(30)  NOT NULL,
    is_planned      BIT           NOT NULL
);

CREATE TABLE gold.fact_lng_sales (
    date_key                  INT            NOT NULL,
    plant_asset_id            VARCHAR(10)    NOT NULL,
    destination_country_code  CHAR(2)        NOT NULL,
    contract_type             NVARCHAR(20)   NOT NULL,
    volume_mt                 DECIMAL(12, 4) NOT NULL,
    revenue_usd               DECIMAL(16, 2) NOT NULL,
    CONSTRAINT pk_g_fact_lng PRIMARY KEY (date_key, plant_asset_id, destination_country_code, contract_type)
);

CREATE TABLE gold.fact_financials (
    date_key            INT            NOT NULL,
    segment_id          TINYINT        NOT NULL,
    country_code        CHAR(2)        NOT NULL,
    revenue_usd         DECIMAL(16, 2) NOT NULL,
    operating_cost_usd  DECIMAL(16, 2) NOT NULL,
    ebitda_usd          DECIMAL(16, 2) NOT NULL,
    capex_usd           DECIMAL(16, 2) NOT NULL,
    is_ebitda_mismatch  BIT            NOT NULL,
    CONSTRAINT pk_g_fact_financials PRIMARY KEY (date_key, segment_id, country_code)
);

CREATE TABLE gold.fact_emissions (
    date_key      INT            NOT NULL,
    segment_id    TINYINT        NOT NULL,
    country_code  CHAR(2)        NOT NULL,
    scope         TINYINT        NOT NULL,
    scope_label   NVARCHAR(10)   NOT NULL,
    tco2e         DECIMAL(14, 1) NOT NULL,
    CONSTRAINT pk_g_fact_emissions PRIMARY KEY (date_key, segment_id, country_code, scope)
);

CREATE TABLE gold.fact_targets (
    target_year   SMALLINT       NOT NULL,
    metric        NVARCHAR(50)   NOT NULL,
    unit          NVARCHAR(20)   NOT NULL,
    target_value  DECIMAL(14, 2) NOT NULL,
    CONSTRAINT pk_g_fact_targets PRIMARY KEY (target_year, metric)
);

SELECT name AS gold_table FROM sys.tables WHERE SCHEMA_NAME(schema_id) = 'gold' ORDER BY name;
