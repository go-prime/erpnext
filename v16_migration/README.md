# prime-erp → upstream ERPNext v16 migration

This folder isn't part of the `erpnext` Python package, so nothing in it runs on `bench migrate` while it lives in this repo.

```
v16_migration/
  goprime_erp/custom/*.json   Custom Fields + Property Setters → copy into goprime/goprime_erp/custom/ on v16
  scripts/
    export_fork_data.py       dump fork-only / orphan column data to JSON (never overwrites)
    fit_narrowed_columns.py   shorten exported values that won't fit upstream's narrower columns
    trim_fork_columns.py      drop exported orphan columns (dry run unless --execute)
    import_fork_data.py       write the data back on v16 (dry run unless --execute, idempotent)
```

Run every script from the bench's `sites` directory with the bench's Python:

```bash
cd ~/frappe-bench/sites
../env/bin/python /path/to/v16_migration/scripts/<script>.py --site SITE ...
```

They use only plain SQL and `frappe.get_meta`, so the same files work from v12 (Python 3.6+) through v16.

## Which data is at risk

| Column | Why |
|---|---|
| Purchase Order `purchase_order_id` | fork-only field |
| Quotation Item `free_stock`, `match_free_stock`, `special_instructions` | fork-only fields |
| Sales Order Item `free_stock` | fork-only field |
| Item Default `inventory_account` | fork-only field |
| Stock Reconciliation Item `reason` | fork-only field |
| Period Closing Voucher `branch`, Exchange Rate Revaluation `branch` | hard-coded in fork JSON; these two doctypes are **not** accounting-dimension doctypes, so the Branch dimension doesn't cover them |
| Journal Entry `remark`, `user_remark`, `total_amount_in_words` | fork widened the column types; upstream sync narrows them again and can truncate |
| anything else found by `--orphans` | old columns left by earlier fork versions, other apps, or core |

`branch` on GL Entry, Payment Entry, Journal Entry Account and the other dimension doctypes are real Custom Fields created by the Branch Accounting Dimension. They are kept through the upgrade and aren't touched here.

## Runbook

Rehearse the whole thing on a restored copy of production first.

### 0. Backup

```bash
bench --site SITE backup --with-files
```

Keep this backup, and keep the export directory from step 1. Both live outside the bench.

### 1. Export on the fork (v12, prime-erp code still installed)

```bash
../env/bin/python .../export_fork_data.py --site SITE --out ~/fork-export
```

This has to happen **before** the code switch. That is the only time the Journal Entry text columns are still at their full width.

### 1b. Shorten values that won't fit upstream's narrower columns

```bash
../env/bin/python .../fit_narrowed_columns.py --site SITE --in ~/fork-export            # review
../env/bin/python .../fit_narrowed_columns.py --site SITE --in ~/fork-export --execute
```

**Required.** Upstream stores `total_amount_in_words` as varchar(140). If any value is longer, `bench migrate` aborts with `Data too long for column 'total_amount_in_words'` (seen in testing). The script only shortens columns that have been exported, and the import restores the full text on v16.

### 2. Switch erpnext to upstream v12

```bash
cd ~/frappe-bench/apps/erpnext
git remote add upstream https://github.com/frappe/erpnext.git
git fetch upstream version-12
git checkout -B version-12 upstream/version-12
cd ~/frappe-bench && bench --site SITE migrate
```

The goprime app must still import and migrate cleanly here. If it calls fork-only functions (`get_branch_filter`, etc.), see "goprime during the upgrade" below.

### 3. Export everything that is now orphaned

```bash
cd sites
../env/bin/python .../export_fork_data.py --site SITE --out ~/fork-export --orphans-only
```

Columns already exported in step 1 are skipped, so their pre-upgrade copies are kept.

### 4. Trim

```bash
../env/bin/python .../trim_fork_columns.py --site SITE --in ~/fork-export            # review
../env/bin/python .../trim_fork_columns.py --site SITE --in ~/fork-export --execute
```

A column is only dropped if it was exported, is no longer in the meta, and its row count still matches the export. Fields still in the meta, such as the Journal Entry columns, are left alone.

### 5. Upgrade one major version at a time

For each of `version-13`, `version-14`, `version-15`, `version-16`:

```bash
bench switch-to-branch version-NN frappe erpnext --upgrade
bench setup requirements
bench --site SITE migrate
bench build
```

These upstream steps run each version's own patches; nothing custom is needed. Before each step, check the release notes for the Python, Node and MariaDB versions it requires, and recreate the env when Python changes (`bench setup env --python pythonX.Y`). Version-specific points:

- **v14**: HR and Payroll moved to the separate `hrms` app, and the payment gateways moved to `payments`. Run `bench get-app hrms --branch version-14` and `bench --site SITE install-app hrms` **before** migrating, if HR or payroll data is used.
- **After each step**: run `bench --site SITE trim-tables --dry-run` (on any version where the command exists) to confirm nothing new is orphaned. If something is, export it with `--orphans-only` before trimming.
- **v16**: migrate first, then continue with step 6.

### 6. Install the customisations on v16

Copy `goprime_erp/custom/*.json` into `goprime/goprime_erp/custom/` on goprime's v16 branch, then:

```bash
bench --site SITE migrate
```

This creates the Custom Fields as new, empty columns and applies the Property Setters.

- **goprime must be installed** first. Property Setters are inserted with link validation, so their `module` ("Goprime Erp") must exist as a Module Def.
- **`pos_closing_voucher_details.json` is skipped** with a printed message, because that doctype was replaced by POS Closing Entry after v12. It's harmless, and the file can be deleted.
- **Property Setters change the field type in the meta, but not the column.** Only Custom Fields make Frappe update the schema, and migrate doesn't touch it either. `import_fork_data.py --execute` runs `frappe.db.updatedb` on each target doctype before writing, which widens `total_amount_in_words` back to longtext.

### 7. Import

```bash
cd sites
../env/bin/python .../import_fork_data.py --site SITE --in ~/fork-export            # review counts
../env/bin/python .../import_fork_data.py --site SITE --in ~/fork-export --execute
../env/bin/python .../import_fork_data.py --site SITE --in ~/fork-export            # should show 0 to write
```

Writes are direct `UPDATE`s: no `modified` bump, no hooks, no re-validation. Rows whose document was deleted or renamed during the upgrade show up as "missing docs". Exports with no v16 field, such as old core columns, are reported and skipped.

## goprime during the upgrade

goprime stays in the site's installed apps the whole time, so at every step its code must be importable and `bench migrate` must pass. Choose one:

- keep a minimal goprime branch per version (hooks plus doctypes only, logic stubbed), or
- temporarily remove it from `sites/apps.txt` and from the site's installed apps, then add it back at v16. Its tables stay, but test this on the rehearsal copy first.

## Purchase Order naming

The fork names POs from `purchase_order_id` (`autoname: field:purchase_order_id`). No special handling is needed:

- **Existing PO names are safe.** The export, trim and import never touch `name`; the import only writes `purchase_order_id` back onto rows matched by name.
- **Between v12 and v16, upstream naming applies.** Any PO created on the site then gets a `PUR-ORD-YYYY-#####` name, so don't use the site mid-upgrade.
- **On v16, the Property Setters restore fork behaviour,** which was verified on v15: new POs are named by PO number, a missing PO number is rejected ("PO Number is required"), a duplicate is rejected by the primary key, and amendments are named `<PO number>-1`.
- **A fork-era draft submitted under upstream code** gets `naming_series` filled with the default. Its name doesn't change.

## Behaviour notes

- **A required Select never blocks a save.** Frappe fills in the first option when none is given, so Stock Reconciliation rows saved without a reason get "Surplus/deficit on picking". The fork does the same.
- **Layout-only Custom Fields were removed from `quotation.json`.** `column_break_7` already exists in upstream Quotation, which makes the customisation sync fail. Worse, Frappe inserts the Custom Field before validating, so it leaves a duplicate field behind. The fork's column breaks only made sense in the v12 layout.
- **The restaurant and goprime apps hook Currency Exchange `after_insert`** (`create_reverse_exchange_rate`) and expect a `create_reverse_exchange` field. Inserting a Currency Exchange fails on any site that has the hook but not that field.

## Known leftovers

- **`period_name` unique index** (Accounting Period) and **`received_qty` index** (Purchase Order Item): these stay in the database. They do no harm, and the Property Setters expect them anyway.
- **`Stock Take Adjustments'` option**: the trailing apostrophe is kept on purpose, because existing rows store it. To fix it, change the option and run `update ... set reason = 'Stock Take Adjustments' where reason = 'Stock Take Adjustments'''` together.
