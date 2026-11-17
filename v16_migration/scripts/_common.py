"""Shared helpers for the fork-data export / trim / import scripts.

Written to run unchanged on every Frappe version from v12 (Python 3.6) to v16,
so only plain SQL against information_schema is used for schema checks.

Run every script from the bench's `sites` directory with the bench's Python:

    cd ~/frappe-bench/sites
    ../env/bin/python /path/to/v16_migration/scripts/<script>.py --site <site> ...
"""
from __future__ import print_function, unicode_literals

import datetime
import decimal
import json
import os
import re

# Columns that exist only because of the prime-erp fork's DocType JSON and
# would be orphaned (and later trimmed) once upstream ERPNext replaces the fork.
# `branch` on the accounting-dimension doctypes is NOT listed: those columns are
# real Custom Fields created by the "Branch" Accounting Dimension and survive.
FORK_COLUMNS = [
	("Purchase Order", "purchase_order_id"),
	("Quotation Item", "free_stock"),
	("Quotation Item", "match_free_stock"),
	("Quotation Item", "special_instructions"),
	("Sales Order Item", "free_stock"),
	("Item Default", "inventory_account"),
	("Stock Reconciliation Item", "reason"),
	# Not accounting-dimension doctypes: `branch` is hard-coded in the fork JSON.
	("Period Closing Voucher", "branch"),
	("Exchange Rate Revaluation", "branch"),
]

# Columns that stay in upstream, but whose type the fork widened. Upstream's
# schema sync narrows them again (longtext -> text / varchar(140)) before the
# v16 Property Setters widen them back, which can truncate long values.
# Exported so the import can restore anything that was cut short.
TYPE_CHANGED_COLUMNS = [
	("Journal Entry", "remark"),
	("Journal Entry", "user_remark"),
	("Journal Entry", "total_amount_in_words"),
]

# Max length (characters) the upstream column type can hold, for type-changed
# columns that upstream narrows. MariaDB refuses the ALTER (`Data too long`,
# migrate aborts) if any value is longer, so fit_narrowed_columns.py shortens
# those values (after export) and import_fork_data.py restores them on v16.
# Small Text and Text are both `text` on v12-v15, so remark/user_remark are not narrowed.
NARROWED_LIMITS = {
	("Journal Entry", "total_amount_in_words"): 140,  # Text Editor (longtext) -> Data (varchar(140))
}

# Standard columns that never correspond to a DocField.
BASE_COLUMNS = {
	"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
	"parent", "parentfield", "parenttype", "doctype",
}

EXPORT_SUFFIX = ".json"


def connect(site, sites_path="."):
	import frappe

	frappe.init(site=site, sites_path=sites_path)
	frappe.connect()
	return frappe


def table(doctype):
	return "tab" + doctype


def qi(identifier):
	"""Quote a MariaDB identifier."""
	return "`" + identifier.replace("`", "``") + "`"


def table_columns(frappe, doctype):
	"""{column_name: column_type} straight from information_schema."""
	rows = frappe.db.sql(
		"""select column_name, column_type from information_schema.columns
		where table_schema = database() and table_name = %s""",
		(table(doctype),),
	)
	return {r[0]: r[1] for r in rows}


def table_exists(frappe, doctype):
	return bool(frappe.db.sql(
		"""select 1 from information_schema.tables
		where table_schema = database() and table_name = %s""",
		(table(doctype),),
	))


def meta_has_field(frappe, doctype, fieldname):
	meta = frappe.get_meta(doctype, cached=False)
	return bool(meta.get_field(fieldname))


def meta_fieldnames_with_value(frappe, doctype):
	meta = frappe.get_meta(doctype, cached=False)
	return set(meta.get_fieldnames_with_value())


def find_orphan_columns(frappe):
	"""Columns present in a table but absent from the current DocType meta
	(core JSON + Custom Fields). Mirrors frappe.model.meta.trim_table()."""
	orphans = []
	for dt in frappe.get_all("DocType", filters={"issingle": 0}, fields=["name"]):
		doctype = dt.name if hasattr(dt, "name") else dt["name"]
		if not table_exists(frappe, doctype):
			continue
		try:
			meta = frappe.get_meta(doctype, cached=False)
			if getattr(meta, "is_virtual", 0):
				continue
			fields = set(meta.get_fieldnames_with_value())
		except Exception as e:  # broken meta on a half-upgraded site
			print("  ! skipping {}: {}".format(doctype, e))
			continue
		for col in table_columns(frappe, doctype):
			if col in BASE_COLUMNS or col.startswith("_") or col in fields:
				continue
			orphans.append((doctype, col))
	return orphans


def export_filename(doctype, fieldname):
	safe = re.sub(r"[^A-Za-z0-9_]+", "_", doctype).strip("_").lower()
	return "{}--{}{}".format(safe, fieldname, EXPORT_SUFFIX)


def to_json_value(value):
	if isinstance(value, decimal.Decimal):
		return str(value)
	if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
		return value.isoformat()
	if isinstance(value, datetime.timedelta):
		return str(value)
	if isinstance(value, bytes):
		return value.decode("utf-8", "replace")
	return value


def read_exports(directory):
	for fn in sorted(os.listdir(directory)):
		if fn.endswith(EXPORT_SUFFIX) and "--" in fn:
			path = os.path.join(directory, fn)
			with open(path) as f:
				yield path, json.load(f)


def count_non_null(frappe, doctype, fieldname):
	return frappe.db.sql(
		"select count(*) from {} where {} is not null".format(qi(table(doctype)), qi(fieldname))
	)[0][0]
