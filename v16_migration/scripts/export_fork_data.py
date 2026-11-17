"""Export fork-only column data to JSON before tables are trimmed.

One file per (doctype, column): {"doctype", "fieldname", "column_type", "count", "rows": [[name, value], ...]}.
Only non-NULL values are exported. Existing export files are NEVER overwritten,
so the first (pre-upgrade) export of a column is always the one that is kept.

Usage (from frappe-bench/sites):

  # 1. On the fork, BEFORE switching code: known fork columns + type-changed columns
  ../env/bin/python .../export_fork_data.py --site SITE --out ~/fork-export

  # 2. After switching to upstream erpnext v12 and migrating: everything orphaned
  ../env/bin/python .../export_fork_data.py --site SITE --out ~/fork-export --orphans
"""
from __future__ import print_function, unicode_literals

import argparse
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as c  # noqa: E402


def export_column(frappe, out_dir, doctype, fieldname, reason):
	path = os.path.join(out_dir, c.export_filename(doctype, fieldname))
	if os.path.exists(path):
		print("  = {}.{}: already exported, kept existing file".format(doctype, fieldname))
		return
	if not c.table_exists(frappe, doctype):
		print("  - {}.{}: table missing, skipped".format(doctype, fieldname))
		return
	cols = c.table_columns(frappe, doctype)
	if fieldname not in cols:
		print("  - {}.{}: column missing, skipped".format(doctype, fieldname))
		return

	rows = frappe.db.sql(
		"select name, {col} from {tab} where {col} is not null order by name".format(
			col=c.qi(fieldname), tab=c.qi(c.table(doctype))
		)
	)
	payload = {
		"doctype": doctype,
		"fieldname": fieldname,
		"column_type": cols[fieldname],
		"reason": reason,
		"frappe_version": getattr(frappe, "__version__", "?"),
		"exported_at": datetime.datetime.now().isoformat(),
		"count": len(rows),
		"rows": [[r[0], c.to_json_value(r[1])] for r in rows],
	}
	with io.open(path, "w", encoding="utf-8") as f:
		f.write(json.dumps(payload, indent=1, ensure_ascii=False))
	print("  + {}.{}: {} rows -> {}".format(doctype, fieldname, len(rows), os.path.basename(path)))


def main():
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--site", required=True)
	p.add_argument("--out", required=True, help="export directory (created if missing)")
	p.add_argument("--sites-path", default=".")
	p.add_argument("--orphans", action="store_true",
		help="also export every column not in the current DocType meta (run after switching to upstream code)")
	p.add_argument("--orphans-only", action="store_true", help="skip the built-in column list")
	args = p.parse_args()

	out_dir = os.path.abspath(os.path.expanduser(args.out))
	if not os.path.isdir(out_dir):
		os.makedirs(out_dir)

	frappe = c.connect(args.site, args.sites_path)
	try:
		print("Site {} (frappe {})".format(args.site, getattr(frappe, "__version__", "?")))
		if not args.orphans_only:
			print("Known fork columns:")
			for dt, fn in c.FORK_COLUMNS:
				export_column(frappe, out_dir, dt, fn, "fork-only column")
			print("Type-changed columns:")
			for dt, fn in c.TYPE_CHANGED_COLUMNS:
				export_column(frappe, out_dir, dt, fn, "type changed by fork")
		if args.orphans or args.orphans_only:
			print("Orphan columns (not in current meta):")
			orphans = c.find_orphan_columns(frappe)
			if not orphans:
				print("  none")
			for dt, fn in orphans:
				export_column(frappe, out_dir, dt, fn, "orphan column")
	finally:
		frappe.destroy()


if __name__ == "__main__":
	main()
