"""Restore exported fork data into the v16 Custom Fields / widened columns.

Run on the upgraded v16 site AFTER the goprime app (with goprime_erp/custom/*.json)
has been migrated, so the Custom Fields and Property Setters exist.

For each export file whose field exists in the v16 meta:
  * rows whose document no longer exists are counted as "missing"
  * rows whose current value already equals the exported value are left alone
  * everything else is written with a direct UPDATE (no `modified` change,
    no controller hooks), so it is idempotent and safe to re-run.
Export files for fields with no v16 target are reported and skipped; the data
stays in the export file.

Dry run by default; pass --execute to write.

Usage (from frappe-bench/sites):
  ../env/bin/python .../import_fork_data.py --site SITE --in ~/fork-export
  ../env/bin/python .../import_fork_data.py --site SITE --in ~/fork-export --execute
"""
from __future__ import print_function, unicode_literals

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as c  # noqa: E402

BATCH = 1000


def same(a, b):
	if a is None or b is None:
		return a is b
	if str(a) == str(b):
		return True
	try:  # numeric columns: "1.000000" vs 1.0
		return float(a) == float(b)
	except (TypeError, ValueError):
		return False


def main():
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--site", required=True)
	p.add_argument("--in", dest="in_dir", required=True)
	p.add_argument("--sites-path", default=".")
	p.add_argument("--execute", action="store_true")
	p.add_argument("--only", action="append", default=[],
		help="restrict to 'Doctype.fieldname' (repeatable)")
	args = p.parse_args()

	in_dir = os.path.abspath(os.path.expanduser(args.in_dir))
	frappe = c.connect(args.site, args.sites_path)
	problems = 0
	schema_synced = set()
	try:
		print("{} on site {} (frappe {})".format(
			"EXECUTING" if args.execute else "DRY RUN", args.site, getattr(frappe, "__version__", "?")))
		for path, data in c.read_exports(in_dir):
			dt, fn = data["doctype"], data["fieldname"]
			label = "{}.{}".format(dt, fn)
			if args.only and label not in args.only:
				continue
			if not c.table_exists(frappe, dt):
				print("  ? {}: doctype table not on this site, skipped".format(label))
				problems += 1
				continue
			if not c.meta_has_field(frappe, dt, fn) or fn not in c.table_columns(frappe, dt):
				print("  ? {}: no field/column on this site, skipped ({} rows stay in {})".format(
					label, data["count"], os.path.basename(path)))
				continue

			current = dict(frappe.db.sql("select name, {} from {}".format(c.qi(fn), c.qi(c.table(dt)))))
			to_write, unchanged, missing = [], 0, 0
			for name, value in data["rows"]:
				if name not in current:
					missing += 1
				elif same(current[name], value):
					unchanged += 1
				else:
					to_write.append((value, name))

			print("  {} {}: {} to write, {} unchanged, {} missing docs (of {})".format(
				"+" if to_write else "=", label, len(to_write), unchanged, missing, data["count"]))
			if missing:
				problems += 1

			if to_write and dt not in schema_synced:
				# Property Setters synced from an app's custom/ folder change the meta but
				# NOT the column (only Custom Fields trigger a schema update), so e.g.
				# total_amount_in_words stays varchar(140). Align the table with the meta
				# (what Customize Form does on save) before restoring long values.
				before = c.table_columns(frappe, dt).get(fn)
				if args.execute:
					frappe.db.updatedb(dt)
					frappe.clear_cache(doctype=dt)
					after = c.table_columns(frappe, dt).get(fn)
					if after != before:
						print("    schema synced: {} {} -> {}".format(fn, before, after))
				else:
					print("    (will sync {} schema to meta first; {} is {})".format(dt, fn, before))
				schema_synced.add(dt)

			if args.execute and to_write:
				sql = "update {} set {} = %s where name = %s".format(c.qi(c.table(dt)), c.qi(fn))
				for i, (value, name) in enumerate(to_write, 1):
					frappe.db.sql(sql, (value, name))
					if i % BATCH == 0:
						frappe.db.commit()
				frappe.db.commit()
				frappe.clear_cache(doctype=dt)
	finally:
		frappe.destroy()

	if problems:
		print("\n{} file(s) need attention (missing docs or tables) - see above.".format(problems))


if __name__ == "__main__":
	main()
