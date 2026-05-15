-- Real Riga: dbo.transactions
-- Target: Azure SQL, database inudat
-- Source: S3 realrigafingoodhealth/real_riga/Transactions.xlsx (Lambda output)
-- Created: 2026-05-12

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = 'transactions' AND schema_id = SCHEMA_ID('dbo')
)
BEGIN
    CREATE TABLE dbo.transactions (
        id                      INT IDENTITY(1,1) PRIMARY KEY,

        -- Core sale data
        transaction_date        DATE            NOT NULL,
        price                   DECIMAL(12, 2)  NOT NULL,
        area_apt                DECIMAL(8, 2)   NOT NULL,   -- m², apartment area
        rooms                   TINYINT         NOT NULL,   -- 1–5

        -- Address & cadastre
        room_address            NVARCHAR(400)   NOT NULL,
        building_cadastre_nr    NVARCHAR(50)    NULL,
        apt_cadastre_nr         NVARCHAR(50)    NULL,
        property_cadastre_nr    NVARCHAR(50)    NULL,

        -- Building metadata
        min_floor               TINYINT         NULL,       -- apartment floor
        max_floor               TINYINT         NULL,       -- total building floors
        building_material       NVARCHAR(100)   NULL,
        building_depreciation   DECIMAL(5, 2)   NULL,       -- %
        area_land               DECIMAL(10, 2)  NULL,       -- m², land area

        -- Geocoding (populated at load time via address lookup)
        lat                     DECIMAL(9, 6)   NULL,
        lng                     DECIMAL(9, 6)   NULL,
        district                NVARCHAR(100)   NULL,

        -- Derived / computed
        price_per_sqm           AS CAST(price / NULLIF(area_apt, 0) AS DECIMAL(10, 2)) PERSISTED,

        -- Load metadata
        loaded_at               DATETIME2       DEFAULT GETUTCDATE()
    );

    CREATE INDEX IX_transactions_date     ON dbo.transactions (transaction_date);
    CREATE INDEX IX_transactions_rooms    ON dbo.transactions (rooms);
    CREATE INDEX IX_transactions_district ON dbo.transactions (district);
    CREATE INDEX IX_transactions_cadastre ON dbo.transactions (property_cadastre_nr);

    PRINT 'dbo.transactions created.';
END
ELSE
BEGIN
    PRINT 'dbo.transactions already exists — skipping.';
END
