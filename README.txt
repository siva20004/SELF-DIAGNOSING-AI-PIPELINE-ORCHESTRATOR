SELF-DIAGNOSING PIPELINE ORCHESTRATOR - TEST DATA
====================================================

Files:
1. sales_transactions_1M_valid.csv
   - 1,000,000 records
   - All records are designed to satisfy sales_contract_v1.yaml.
   - Suitable for a large upload/load test.

2. sales_transactions_invalid_test.csv
   - 10 deliberately invalid records.
   - Contains examples of:
     * wrong datatype
     * missing required value
     * negative value
     * invalid enum
     * invalid date
     * arithmetic/quality-rule violation
     * quantity range violation
     * invalid ID pattern
     * duplicate transaction ID

3. sales_contract_v1.yaml
   - Versioned data contract defining schema and quality rules.

Recommended test sequence:
A. Upload the YAML contract.
B. Upload sales_transactions_1M_valid.csv.
C. Run validation: expected PASS.
D. Upload sales_transactions_invalid_test.csv.
E. Run validation: expected FAIL with specific rule violations.
F. Store each validation result in PostgreSQL.
G. Feed failure events into diagnosis/backfill/scheduling modules.

Important:
- This is synthetic but realistic project test data.
- It contains no real people's private information.
- The valid file intentionally contains repeated customer IDs because one customer can make multiple transactions.
- transaction_id is unique in the valid file.
