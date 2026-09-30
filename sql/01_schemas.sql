/* =============================================================================
   Shell | Fabric SQL Database | 01 - Schemas
   Medallion layers inside one database:
     bronze : raw CSV landing, every column NVARCHAR, loaded by the Fabric pipeline
     silver : typed, cleaned, deduplicated data
     gold   : star schema + reporting views consumed by Power BI
     etl    : metadata, run log, rejected rows, data quality results
   Portfolio project. Not affiliated with Shell plc. All data is fictitious.
============================================================================= */
IF SCHEMA_ID('bronze') IS NULL EXEC('CREATE SCHEMA bronze');
IF SCHEMA_ID('silver') IS NULL EXEC('CREATE SCHEMA silver');
IF SCHEMA_ID('gold')   IS NULL EXEC('CREATE SCHEMA gold');
IF SCHEMA_ID('etl')    IS NULL EXEC('CREATE SCHEMA etl');

SELECT name AS schema_name FROM sys.schemas WHERE name IN ('bronze', 'silver', 'gold', 'etl');
