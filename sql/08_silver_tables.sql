/* =============================================================================
   Shell | Fabric SQL Database | 08 - Silver tables (typed, clean, one row per key)
============================================================================= */
DROP TABLE IF EXISTS silver.retail_sales, silver.ev_charging, silver.production_monthly, silver.asset_downtime,
                     silver.lng_sales, silver.financials, silver.emissions, silver.targets,
                     silver.site, silver.asset, silver.product, silver.segment, silver.country;

CREATE TABLE silver.country (
    country_code  CHAR(2)       NOT NULL CONSTRAINT pk_s_country PRIMARY KEY,
    country_name  NVARCHAR(100) NOT NULL,
    region        NVARCHAR(50)  NOT NULL
);

CREATE TABLE silver.segment (
    segment_id    TINYINT       NOT NULL CONSTRAINT pk_s_segment PRIMARY KEY,
    segment_name  NVARCHAR(50)  NOT NULL
);

CREATE TABLE silver.product (
    product_id     CHAR(3)      NOT NULL CONSTRAINT pk_s_product PRIMARY KEY,
    product_name   NVARCHAR(50) NOT NULL,
    product_group  NVARCHAR(20) NOT NULL
);

CREATE TABLE silver.site (
    site_id            VARCHAR(10)   NOT NULL CONSTRAINT pk_s_site PRIMARY KEY,
    site_name          NVARCHAR(200) NOT NULL,
    city               NVARCHAR(100) NOT NULL,
    country_code       CHAR(2)       NOT NULL CONSTRAINT fk_s_site_country REFERENCES silver.country (country_code),
    latitude           DECIMAL(9, 5) NULL,
    longitude          DECIMAL(9, 5) NULL,
    is_geo_imputed     BIT           NOT NULL,
    site_format        NVARCHAR(20)  NOT NULL,
    opening_date       DATE          NOT NULL,
    has_ev_charging    BIT           NOT NULL,
    ev_since_date      DATE          NULL,
    ev_charge_points   SMALLINT      NOT NULL
);

CREATE TABLE silver.asset (
    asset_id        VARCHAR(10)    NOT NULL CONSTRAINT pk_s_asset PRIMARY KEY,
    asset_name      NVARCHAR(200)  NOT NULL,
    asset_type      NVARCHAR(20)   NOT NULL,
    country_code    CHAR(2)        NOT NULL CONSTRAINT fk_s_asset_country REFERENCES silver.country (country_code),
    segment_id      TINYINT        NOT NULL CONSTRAINT fk_s_asset_segment REFERENCES silver.segment (segment_id),
    start_date      DATE           NOT NULL,
    capacity_value  DECIMAL(12, 2) NOT NULL,
    capacity_unit   NVARCHAR(10)   NOT NULL
);

CREATE TABLE silver.retail_sales (
    transaction_date   DATE           NOT NULL,
    site_id            VARCHAR(10)    NOT NULL,
    product_id         CHAR(3)        NOT NULL,
    volume_litres      DECIMAL(12, 1) NULL,          -- NULL for non-fuel products
    revenue_usd        DECIMAL(14, 2) NOT NULL,
    cost_usd           DECIMAL(14, 2) NOT NULL,
    transactions       INT            NOT NULL,
    is_volume_imputed  BIT            NOT NULL,
    record_updated_at  DATETIME2(0)   NOT NULL,
    CONSTRAINT pk_s_retail_sales PRIMARY KEY (transaction_date, site_id, product_id)
);

CREATE TABLE silver.ev_charging (
    charge_date          DATE           NOT NULL,
    site_id              VARCHAR(10)    NOT NULL,
    sessions             INT            NOT NULL,
    energy_mwh           DECIMAL(10, 3) NOT NULL,
    revenue_usd          DECIMAL(12, 2) NOT NULL,
    avg_session_minutes  DECIMAL(6, 1)  NOT NULL,
    CONSTRAINT pk_s_ev_charging PRIMARY KEY (charge_date, site_id)
);

CREATE TABLE silver.production_monthly (
    production_month   DATE           NOT NULL,
    asset_id           VARCHAR(10)    NOT NULL,
    oil_bbl            BIGINT         NOT NULL,
    gas_boe            BIGINT         NOT NULL,
    total_boe          BIGINT         NOT NULL,
    opex_usd           DECIMAL(16, 2) NOT NULL,
    planned_boe        BIGINT         NOT NULL,
    record_updated_at  DATETIME2(0)   NOT NULL,
    CONSTRAINT pk_s_production PRIMARY KEY (production_month, asset_id)
);

CREATE TABLE silver.asset_downtime (
    event_id         VARCHAR(10)   NOT NULL CONSTRAINT pk_s_downtime PRIMARY KEY,
    asset_id         VARCHAR(10)   NOT NULL,
    start_ts         DATETIME2(0)  NOT NULL,
    end_ts           DATETIME2(0)  NOT NULL,
    downtime_hours   DECIMAL(8, 1) NOT NULL,
    cause            NVARCHAR(30)  NOT NULL,
    was_ts_swapped   BIT           NOT NULL,
    was_hours_recalc BIT           NOT NULL
);

CREATE TABLE silver.lng_sales (
    sale_month        DATE           NOT NULL,
    plant_asset_id    VARCHAR(10)    NOT NULL,
    destination_code  CHAR(2)        NOT NULL,
    contract_type     NVARCHAR(20)   NOT NULL,
    volume_mt         DECIMAL(12, 4) NOT NULL,
    revenue_usd       DECIMAL(16, 2) NOT NULL,
    CONSTRAINT pk_s_lng PRIMARY KEY (sale_month, plant_asset_id, destination_code, contract_type)
);

CREATE TABLE silver.financials (
    financial_month      DATE           NOT NULL,
    segment_id           TINYINT        NOT NULL,
    country_code         CHAR(2)        NOT NULL,
    revenue_usd          DECIMAL(16, 2) NOT NULL,
    operating_cost_usd   DECIMAL(16, 2) NOT NULL,
    ebitda_usd           DECIMAL(16, 2) NOT NULL,   -- recalculated: revenue - operating cost
    ebitda_reported_usd  DECIMAL(16, 2) NULL,       -- as received
    is_ebitda_mismatch   BIT            NOT NULL,
    capex_usd            DECIMAL(16, 2) NOT NULL,
    CONSTRAINT pk_s_financials PRIMARY KEY (financial_month, segment_id, country_code)
);

CREATE TABLE silver.emissions (
    emission_month  DATE           NOT NULL,
    segment_id      TINYINT        NOT NULL,
    country_code    CHAR(2)        NOT NULL,
    scope           TINYINT        NOT NULL CONSTRAINT ck_s_emissions_scope CHECK (scope IN (1, 2, 3)),
    tco2e           DECIMAL(14, 1) NOT NULL,
    CONSTRAINT pk_s_emissions PRIMARY KEY (emission_month, segment_id, country_code, scope)
);

CREATE TABLE silver.targets (
    target_year   SMALLINT       NOT NULL,
    metric        NVARCHAR(50)   NOT NULL,
    unit          NVARCHAR(20)   NOT NULL,
    target_value  DECIMAL(14, 2) NOT NULL,
    CONSTRAINT pk_s_targets PRIMARY KEY (target_year, metric)
);

SELECT name AS silver_table FROM sys.tables WHERE SCHEMA_NAME(schema_id) = 'silver' ORDER BY name;
