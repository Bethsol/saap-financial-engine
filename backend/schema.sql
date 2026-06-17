-- =====================================================================
-- Universal Financial Language (UFL) — Unified Schema
-- Target: PostgreSQL 14+ / SQLite 3.35+
-- Purpose: A schema-agnostic landing zone for SME financial data.
--          All source systems (SAGA, QuickBooks, Xero, DATEV) project
--          into this single shape after the Normalization Engine.
-- =====================================================================

CREATE TABLE IF NOT EXISTS client (
    client_id        TEXT PRIMARY KEY,
    legal_name       TEXT NOT NULL,
    country_iso2     CHAR(2) NOT NULL,
    base_currency    CHAR(3) NOT NULL DEFAULT 'EUR',
    industry         TEXT,
    fiscal_year_end  TEXT NOT NULL DEFAULT '12-31',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction (
    transaction_id     TEXT PRIMARY KEY,
    client_id          TEXT NOT NULL REFERENCES client(client_id),
    transaction_date   DATE NOT NULL,
    description        TEXT,
    source_amount      NUMERIC(18, 4) NOT NULL,
    source_currency    CHAR(3) NOT NULL,
    base_amount        NUMERIC(18, 4) NOT NULL, -- converted to client.base_currency
    fx_rate            NUMERIC(18, 8) NOT NULL,
    universal_category TEXT NOT NULL,           -- normalized via fiscal_mapping
    raw_category       TEXT,                    -- preserved for audit
    direction          CHAR(1) NOT NULL CHECK (direction IN ('I','E')), -- Income / Expense
    source_system      TEXT NOT NULL,           -- 'saga' | 'quickbooks' | 'datev' | ...
    ingested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transaction_client_date
    ON transaction (client_id, transaction_date);

CREATE TABLE IF NOT EXISTS fx_rate (
    rate_date     DATE NOT NULL,
    from_currency CHAR(3) NOT NULL,
    to_currency   CHAR(3) NOT NULL,
    rate          NUMERIC(18, 8) NOT NULL,
    PRIMARY KEY (rate_date, from_currency, to_currency)
);

-- The Universal Financial Language mapping table.
-- Each row maps a raw label (in any language) to a normalized category.
CREATE TABLE IF NOT EXISTS fiscal_mapping (
    raw_label          TEXT NOT NULL,
    language           CHAR(2) NOT NULL,
    universal_category TEXT NOT NULL,
    PRIMARY KEY (raw_label, language)
);

-- Pre-seeded UFL universe — extend over time, no schema changes required.
INSERT INTO fiscal_mapping VALUES
    ('Revenue',          'en', 'Revenue'),
    ('Sales',            'en', 'Revenue'),
    ('Venituri',         'ro', 'Revenue'),
    ('Vanzari',          'ro', 'Revenue'),
    ('Umsatz',           'de', 'Revenue'),
    ('Erlöse',           'de', 'Revenue'),
    ('Marketing',        'en', 'Marketing'),
    ('Advertising',      'en', 'Marketing'),
    ('Publicitate',      'ro', 'Marketing'),
    ('Werbung',          'de', 'Marketing'),
    ('Payroll',          'en', 'Payroll'),
    ('Salaries',         'en', 'Payroll'),
    ('Salarii',          'ro', 'Payroll'),
    ('Gehälter',         'de', 'Payroll'),
    ('Logistics',        'en', 'Logistics'),
    ('Courier',          'en', 'Logistics'),
    ('Fuel',             'en', 'Logistics'),
    ('Transport',        'ro', 'Logistics'),
    ('Combustibil',      'ro', 'Logistics'),
    ('Versand',          'de', 'Logistics'),
    ('Rent',             'en', 'Facilities'),
    ('Chirie',           'ro', 'Facilities'),
    ('Miete',            'de', 'Facilities'),
    ('Software',         'en', 'Technology'),
    ('Subscriptions',    'en', 'Technology'),
    ('Abonamente',       'ro', 'Technology'),
    ('Abonnements',      'de', 'Technology')
ON CONFLICT DO NOTHING;
