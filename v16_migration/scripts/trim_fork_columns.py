"""Drop columns that have been exported and are no longer in the DocType meta.

A column is dropped only if ALL of these hold:
  * an export file for it exists in --in
  * the field is not in the current meta (core JSON or Custom Field)
  * the current non-NULL row count equals the exported count
    (use --allow-count-mismatch only if you understand why it differs)

Dry run by default; pass --execute to actually ALTER TABLE.
Take a database backup first: `bench --site SITE backup`.

Usage (from frappe-bench/sites, AFTER switching to upstream erpnext v12 + migrate):
  ../env/bin/python .../trim_fork_columns.py --site SITE --in ~/fork-export
  ../env/bin/python .../trim_fork_columns.py --site SITE --in ~/fork-export --execute
"""
from __future__ import print_function, unicode_literals

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as c  # noqa: E402


def main():
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--site", required=True)
	p.add_argument("--in", dest="in_dir", required=True)
	p.add_argument("--sites-path", default=".")
	p.add_argument("--execute", action="store_true")
	p.add_argument("--allow-count-mismatch", action="store_true")
	args = p.parse_args()

	in_dir = os.path.abspath(os.path.expanduser(args.in_dir))
	frappe = c.connect(args.site, args.sites_path)
	dropped, blocked = 0, 0
	try:
		print("{} on site {} (frappe {})".format(
			"EXECUTING" if args.execute else "DRY RUN", args.site, getattr(frappe, "__version__", "?")))
		for path, data in c.read_exports(in_dir):
			dt, fn = data["doctype"], data["fieldname"]
			label = "{}.{}".format(dt, fn)
			if not c.table_exists(frappe, dt) or fn not in c.table_columns(frappe, dt):
				print("  = {}: column already gone".format(label))
				continue
			if c.meta_has_field(frappe, dt, fn):
				print("  . {}: still a field in meta, kept".format(label))
				continue
			now = c.count_non_null(frappe, dt, fn)
			if now != data["count"] and not args.allow_count_mismatch:
				print("  ! {}: BLOCKED - {} non-null rows now vs {} exported; re-check the export".format(
					label, now, data["count"]))
				blocked += 1
				continue
			print("  - {}: drop column ({} rows exported)".format(label, data["count"]))
			if args.execute:
				frappe.db.commit()
				frappe.db.sql("alter table {} drop column {}".format(c.qi(c.table(dt)), c.qi(fn)))
				frappe.clear_cache(doctype=dt)
			dropped += 1
	finally:
		frappe.destroy()

	print("\n{} column(s) {}, {} blocked.".format(dropped, "dropped" if args.execute else "would be dropped", blocked))
	if blocked:
		sys.exit(1)


if __name__ == "__main__":
	main()
