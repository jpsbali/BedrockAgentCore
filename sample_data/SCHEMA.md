# Sample Data Schema

Synthetic KYC data loaded into SQLite with FTS5 trigram indexes for fuzzy text matching.

## Building the Database

```bash
python3 sample_data/sources/build_db.py
```

This reads the JSONL source files from `sample_data/sources/` and creates `kyc_data.db` in the same directory. Re-run after modifying the JSONL files.

## Row Counts

| Table | Rows |
|---|---|
| credit_reports | 1000 |
| income_verification | 1000 |
| property_records | 722 |
| lien_records | 125 |

## Tables

### credit_reports

| Column | Type | Description |
|---|---|---|
| government_id | TEXT PK | SSN (e.g. `655-15-0410`) |
| full_legal_name | TEXT | Full name |
| date_of_birth | INTEGER | Epoch milliseconds |
| primary_address | TEXT | Street, city, state, zip |
| credit_score | INTEGER | 450-850 |
| account_tradelines | TEXT | JSON array of credit accounts |

### income_verification

| Column | Type | Description |
|---|---|---|
| government_id | TEXT PK | Links to credit_reports |
| employee_name | TEXT | May be a perturbed variant of the legal name |
| employer_name | TEXT | Company name |
| verified_annual_salary | REAL | Annual salary |

### property_records

| Column | Type | Description |
|---|---|---|
| property_id | TEXT PK | UUID |
| owner_name_on_deed | TEXT | May be a perturbed variant of the legal name |
| property_address | TEXT | May be a perturbed variant of the credit address |
| assessed_value | REAL | Property value |

### lien_records

| Column | Type | Description |
|---|---|---|
| lien_id | TEXT PK | UUID |
| property_id | TEXT | Links to property_records |
| debtor_name | TEXT | May be a perturbed variant of the legal name |
| debtor_address | TEXT | May be a perturbed variant of the credit address |
| lien_holder | TEXT | IRS, State Tax Board, or County Clerk |
| lien_amount | REAL | Lien dollar amount |
| lien_status | TEXT | Always "Active" |

## FTS5 Indexes

Each table has a corresponding `*_fts` virtual table using the `trigram` tokenizer. Trigram tokenization splits text into 3-character overlapping tokens, enabling substring and fuzzy matching similar to character bigram BM25.

| FTS Table | Base Table | Indexed Fields |
|---|---|---|
| credit_reports_fts | credit_reports | full_legal_name, primary_address |
| income_verification_fts | income_verification | employee_name |
| property_records_fts | property_records | owner_name_on_deed, property_address |
| lien_records_fts | lien_records | debtor_name, debtor_address |

The content-sync mode is used (`content=<table>`), so the FTS index is rebuilt from the base table data.

## Querying

### Fuzzy Text Search

Use `MATCH` with a double-quoted phrase for substring matching. The trigram tokenizer finds rows containing the query string as a substring:

```sql
-- Find credit reports with a name containing "anielle"
SELECT cr.*
FROM credit_reports cr
JOIN credit_reports_fts fts ON cr.rowid = fts.rowid
WHERE credit_reports_fts MATCH '"anielle"'
ORDER BY bm25(credit_reports_fts)
LIMIT 5;
```

The double quotes around the search term are required for phrase matching with trigram. Without them, each token is matched independently.

### Multi-Column Search

Search across multiple indexed fields in one query (all indexed columns are searched):

```sql
-- Search both owner_name_on_deed AND property_address
SELECT pr.*
FROM property_records pr
JOIN property_records_fts fts ON pr.rowid = fts.rowid
WHERE property_records_fts MATCH '"Jeffery Park"'
ORDER BY bm25(property_records_fts)
LIMIT 5;
```

### Exact ID Lookup

```sql
SELECT * FROM credit_reports WHERE government_id = '655-15-0410';
SELECT * FROM property_records WHERE property_id = 'a1378823-...';
```

### Ranking

Use `bm25()` to rank results by relevance:

```sql
SELECT cr.full_legal_name, bm25(credit_reports_fts) AS score
FROM credit_reports cr
JOIN credit_reports_fts fts ON cr.rowid = fts.rowid
WHERE credit_reports_fts MATCH '"William"'
ORDER BY score
LIMIT 10;
```

Lower `bm25()` scores are better matches.

### Cross-Table Joins

Link records across tables using shared identifiers:

```sql
-- Find all data for a person starting from a credit report
SELECT
    cr.full_legal_name,
    cr.credit_score,
    iv.employee_name,
    iv.employer_name,
    pr.property_address,
    pr.assessed_value
FROM credit_reports cr
LEFT JOIN income_verification iv ON cr.government_id = iv.government_id
LEFT JOIN property_records pr ON pr.property_id IN (
    SELECT p2.property_id FROM property_records p2
    JOIN property_records_fts fts ON p2.rowid = fts.rowid
    WHERE property_records_fts MATCH SUBSTR(cr.full_legal_name, 1, 5)
)
WHERE cr.government_id = '655-15-0410';
```

Note: names and addresses are intentionally perturbed across datasets to simulate real-world fuzzy matching scenarios. The `employee_name` in income_verification may differ from `full_legal_name` in credit_reports (middle initials, typos, nicknames, etc.).

## Data Relationships

```
credit_reports.government_id ──┬── income_verification.government_id
                                │
                                ├── property_records (fuzzy link via name/address)
                                │       └── lien_records.property_id
                                │
                                └── lien_records (fuzzy link via name/address)
```

The synthetic data is generated by `agent_code/helpers/generate_workshop_data.py` which creates 1000 people with intentionally perturbed names and addresses across datasets to test fuzzy matching.
