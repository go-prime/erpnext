"""Shorten values that won't fit the upstream (narrower) column type.

Without this, `bench migrate` on upstream code aborts with
`(1406, "Data too long for column 'total_amount_in_words'")`.

Only columns listed in _common.NARROWED_LIMITS are touched, and only when an
export file for the column exists in --in and its row count matches the table,
so the full values can be restored on v16 by import_fork_data.py.

Dry run by default; pass --execute to write.

Usage (from frappe-bench/sites), after export_fork_data.py and BEFORE migrating upstream code:
  ../env/bin/python .../fit_narrowed_columns.py --site SITE --in ~/fork-export
  ../env/bin/python .../fit_narrowed_columns.py --site SITE --in ~/fork-export --execute
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
	args = p.parse_args()

	in_dir = os.path.abspath(os.path.expanduser(args.in_dir))
	exports = {(d["doctype"], d["fieldname"]): d for _, d in c.read_exports(in_dir)}
	frappe = c.connect(args.site, args.sites_path)
	blocked = 0
	try:
		print("{} on site {} (frappe {})".format(
			"EXECUTING" if args.execute else "DRY RUN", args.site, getattr(frappe, "__version__", "?")))
		for (dt, fn), limit in sorted(c.NARROWED_LIMITS.items()):
			label = "{}.{}".format(dt, fn)
			if not c.table_exists(frappe, dt) or fn not in c.table_columns(frappe, dt):
				print("  = {}: column not on this site".format(label))
				continue
			tab, col = c.qi(c.table(dt)), c.qi(fn)
			too_long = frappe.db.sql(
				"select count(*) from {} where char_length({}) > %s".format(tab, col), (limit,))[0][0]
			if not too_long:
				print("  = {}: all values fit in {} chars".format(label, limit))
				continue
			data = exports.get((dt, fn))
			if not data:
				print("  ! {}: BLOCKED - {} value(s) > {} chars but no export file; run export first".format(
					label, too_long, limit))
				blocked += 1
				continue
			now = c.count_non_null(frappe, dt, fn)
			if now != data["count"]:
				print("  ! {}: BLOCKED - {} non-null rows now vs {} exported; re-export first".format(
					label, now, data["count"]))
				blocked += 1
				continue
			print("  ~ {}: shorten {} value(s) to {} chars (full values are in the export)".format(
				label, too_long, limit))
			if args.execute:
				frappe.db.sql("update {tab} set {col} = left({col}, %s) where char_length({col}) > %s".format(
					tab=tab, col=col), (limit, limit))
				frappe.db.commit()
	finally:
		frappe.destroy()
	if blocked:
		sys.exit(1)


if __name__ == "__main__":
	main()
