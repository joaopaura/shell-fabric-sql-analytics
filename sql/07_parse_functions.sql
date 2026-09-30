/* =============================================================================
   Shell | Fabric SQL Database | 07 - Parsing functions
   Inline table-valued functions (used with CROSS APPLY) instead of scalar UDFs:
   the optimizer expands them into the calling query, so they stay fast on
   millions of rows.
============================================================================= */

/* Dates arrive as 2024-03-01, 01/03/2024 (dd/mm/yyyy) or 20240301 */
CREATE OR ALTER FUNCTION etl.tvf_parse_date (@s NVARCHAR(100))
RETURNS TABLE
AS RETURN
SELECT CASE
         WHEN v LIKE '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]%' THEN TRY_CONVERT(DATE, LEFT(v, 10), 23)
         WHEN v LIKE '[0-3][0-9]/[01][0-9]/[12][0-9][0-9][0-9]%' THEN TRY_CONVERT(DATE, LEFT(v, 10), 103)
         WHEN v LIKE '[12][0-9][0-9][0-9][01][0-9][0-3][0-9]%'   THEN TRY_CONVERT(DATE, LEFT(v, 8), 112)
       END AS value
FROM (SELECT TRIM(@s) AS v) x;
GO

/* Timestamps arrive as 2024-03-01 14:30:00, 01/03/2024 14:30 or 20240301 143000 */
CREATE OR ALTER FUNCTION etl.tvf_parse_datetime (@s NVARCHAR(100))
RETURNS TABLE
AS RETURN
SELECT CASE
         WHEN v LIKE '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9] [0-2][0-9]:[0-5][0-9]:[0-5][0-9]'
              THEN TRY_CONVERT(DATETIME2(0), v, 120)
         WHEN v LIKE '[0-3][0-9]/[01][0-9]/[12][0-9][0-9][0-9] [0-2][0-9]:[0-5][0-9]'
              THEN TRY_CONVERT(DATETIME2(0), CONCAT(SUBSTRING(v, 7, 4), '-', SUBSTRING(v, 4, 2), '-', LEFT(v, 2), ' ', SUBSTRING(v, 12, 5), ':00'), 120)
         WHEN v LIKE '[12][0-9][0-9][0-9][01][0-9][0-3][0-9] [0-2][0-9][0-5][0-9][0-5][0-9]'
              THEN TRY_CONVERT(DATETIME2(0), CONCAT(LEFT(v, 4), '-', SUBSTRING(v, 5, 2), '-', SUBSTRING(v, 7, 2), ' ',
                                                   SUBSTRING(v, 10, 2), ':', SUBSTRING(v, 12, 2), ':', SUBSTRING(v, 14, 2)), 120)
       END AS value
FROM (SELECT TRIM(@s) AS v) x;
GO

/* Numbers arrive as 1234.56, 1234,56 (comma decimal) or $1234.56 */
CREATE OR ALTER FUNCTION etl.tvf_parse_number (@s NVARCHAR(100))
RETURNS TABLE
AS RETURN
SELECT TRY_CAST(
         CASE WHEN v LIKE '%,%' AND v NOT LIKE '%.%' THEN REPLACE(v, ',', '.') ELSE REPLACE(v, ',', '') END
         AS DECIMAL(19, 4)) AS value
FROM (SELECT NULLIF(REPLACE(REPLACE(TRIM(@s), '$', ''), ' ', ''), '') AS v) x;
GO

-- quick tests
SELECT d1.value AS iso, d2.value AS ddmmyyyy, d3.value AS yyyymmdd,
       t1.value AS ts_iso, t2.value AS ts_ddmm, t3.value AS ts_compact,
       n1.value AS num_dot, n2.value AS num_comma, n3.value AS num_dollar, n4.value AS num_blank
FROM etl.tvf_parse_date('2024-03-01') d1
CROSS APPLY etl.tvf_parse_date('01/03/2024') d2
CROSS APPLY etl.tvf_parse_date('20240301') d3
CROSS APPLY etl.tvf_parse_datetime('2024-03-01 14:30:00') t1
CROSS APPLY etl.tvf_parse_datetime('01/03/2024 14:30') t2
CROSS APPLY etl.tvf_parse_datetime('20240301 143000') t3
CROSS APPLY etl.tvf_parse_number('1234.56') n1
CROSS APPLY etl.tvf_parse_number('1234,56') n2
CROSS APPLY etl.tvf_parse_number('$1234.56') n3
CROSS APPLY etl.tvf_parse_number('') n4;
