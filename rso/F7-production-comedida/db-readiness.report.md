# F7 DB Readiness Report - competitor_intel

**Mode:** Codex PMO read-only verification.  
**No live apply:** no database was created; only server dry-run/read-only checks.

## RHO Checklist

### Acceptance Criteria
- [x] Infra branch containing `competitor-intel` CR exists and is pushed. Evidence: `/home/dibanez/k8s/_worktrees/k8s-infra-competitor-crawler-F3` on `codex/competitor-crawler-F3-history...origin/codex/competitor-crawler-F3-history`, HEAD `a6e64e9 Add competitor intel database CR`.
- [x] CR shape is correct for CNPG shared cluster. Evidence: `databases/postgres-shared/app-databases.yaml` has `kind: Database`, `metadata.name: competitor-intel`, `spec.name: competitor_intel`, `owner: skirmshop`, `cluster.name: postgres-shared`.
- [x] Server dry-run accepts the infra kustomization. Evidence: `kubectl apply --dry-run=server -k databases/postgres-shared` returned `database.postgresql.cnpg.io/competitor-intel created (server dry run)`.
- [blocked] Live DB is not created. Evidence: `kubectl -n databases get database competitor-intel -o yaml` returned no object.
- [blocked] SQL migration `db/migrations/001_f3_history.sql` is not live-applied to `competitor_intel`. Evidence: no live DB exists yet.

## Next Gate
F7 needs an explicit apply/migration gate:
1. Merge/apply infra branch containing `competitor-intel`.
2. Wait for CNPG `Database` ready.
3. Run/apply `db/migrations/001_f3_history.sql` with approved credentials.
4. Verify `competitor_intel.price_stock_observation`, ledger table, monthly partition, and `estimated_sales_daily`.
