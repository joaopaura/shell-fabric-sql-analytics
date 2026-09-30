/* =============================================================================
   Shell | Fabric SQL Database | 05 - Date dimension (generated, no source file)
   Covers 2020-01-01 to 2030-12-31 so 2030 targets can be plotted.
   GENERATE_SERIES builds one row per day without loops or recursive CTEs.
============================================================================= */
DROP TABLE IF EXISTS gold.dim_date;
CREATE TABLE gold.dim_date (
    date_key          INT          NOT NULL CONSTRAINT pk_dim_date PRIMARY KEY,   -- yyyymmdd
    [date]            DATE         NOT NULL,
    [year]            SMALLINT     NOT NULL,
    quarter_number    TINYINT      NOT NULL,
    quarter_label     CHAR(7)      NOT NULL,   -- 2024 Q1
    month_number      TINYINT      NOT NULL,
    month_name        NVARCHAR(10) NOT NULL,
    month_short       CHAR(3)      NOT NULL,
    month_start       DATE         NOT NULL,
    year_month        INT          NOT NULL,   -- 202401, sort key
    year_month_label  CHAR(8)      NOT NULL,   -- Jan 2024
    iso_week          TINYINT      NOT NULL,
    day_of_week       TINYINT      NOT NULL,   -- 1 = Monday
    day_name          NVARCHAR(10) NOT NULL,
    is_weekend        BIT          NOT NULL
);

DECLARE @start DATE = '2020-01-01', @end DATE = '2030-12-31';

WITH d AS (
    SELECT DATEADD(DAY, value, @start) AS dt
    FROM GENERATE_SERIES(0, DATEDIFF(DAY, @start, @end))
)
INSERT INTO gold.dim_date
SELECT
    CONVERT(INT, FORMAT(dt, 'yyyyMMdd')),
    dt,
    YEAR(dt),
    DATEPART(QUARTER, dt),
    CONCAT(YEAR(dt), ' Q', DATEPART(QUARTER, dt)),
    MONTH(dt),
    DATENAME(MONTH, dt),
    LEFT(DATENAME(MONTH, dt), 3),
    DATEFROMPARTS(YEAR(dt), MONTH(dt), 1),
    YEAR(dt) * 100 + MONTH(dt),
    CONCAT(LEFT(DATENAME(MONTH, dt), 3), ' ', YEAR(dt)),
    DATEPART(ISO_WEEK, dt),
    (DATEPART(WEEKDAY, dt) + @@DATEFIRST - 2) % 7 + 1,
    DATENAME(WEEKDAY, dt),
    CASE WHEN (DATEPART(WEEKDAY, dt) + @@DATEFIRST - 2) % 7 + 1 IN (6, 7) THEN 1 ELSE 0 END
FROM d;

SELECT MIN([date]) AS first_day, MAX([date]) AS last_day, COUNT(*) AS days FROM gold.dim_date;
