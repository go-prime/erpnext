# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate, cstr
from frappe import _
from erpnext.accounts.utils import (
    get_fiscal_year,
    FiscalYearError,
    get_allow_cost_center_in_entry_of_bs_account
)


def execute(filters=None):
    from goprime.config.utils import get_features

    if not filters: filters = {}

    columns = get_columns()

    if not filters.get("account"): return columns, []

    account_currency = frappe.db.get_value("Account", filters.account, "account_currency")

    data = get_entries(filters)

    from erpnext.accounts.utils import get_balance_on
    # issue #1: getting account balance instead of filtering transactions by branch.
    balance_as_per_system = 0
    if get_features().get('JMann_simple_ui'):
        balance_as_per_system = get_balance_by_branch(filters["account"], filters["report_date"], filters['branch'])
    else:
        balance_as_per_system = get_balance_on(filters["account"], filters["report_date"])

    total_debit, total_credit = 0, 0
    for d in data:
        total_debit += flt(d.debit)
        total_credit += flt(d.credit)

    # issue #2: this function does not filter by branch - done
    amounts_not_reflected_in_system = get_amounts_not_reflected_in_system(filters)

    bank_bal = flt(balance_as_per_system) - flt(total_debit) + flt(total_credit) \
        + amounts_not_reflected_in_system

    data += [
        get_balance_row(_("Bank Statement balance as per General Ledger"), balance_as_per_system, account_currency),
        {},
        {
            "payment_entry": _("Outstanding Cheques and Deposits to clear"),
            "debit": total_debit,
            "credit": total_credit,
            "account_currency": account_currency
        },
        get_balance_row(
            _("Cheques and Deposits incorrectly cleared"),
            amounts_not_reflected_in_system,
            account_currency
        ),
        {},
        get_balance_row(
            _("Calculated Bank Statement balance"),
            bank_bal,
            account_currency
        )
    ]

    return columns, data


def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 90
        },
        {
            "fieldname": "payment_document",
            "label": _("Payment Document Type"),
            "fieldtype": "Data",
            "width": 220
        },
        {
            "fieldname": "payment_entry",
            "label": _("Payment Document"),
            "fieldtype": "Dynamic Link",
            "options": "payment_document",
            "width": 220
        },
        {
            "fieldname": "debit",
            "label": _("Debit"),
            "fieldtype": "Currency",
            "options": "account_currency",
            "width": 120
        },
        {
            "fieldname": "credit",
            "label": _("Credit"),
            "fieldtype": "Currency",
            "options": "account_currency",
            "width": 120
        },
        {
            "fieldname": "against_account",
            "label": _("Against Account"),
            "fieldtype": "Link",
            "options": "Account",
            "width": 200
        },
        {
            "fieldname": "reference_no",
            "label": _("Reference"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "ref_date",
            "label": _("Ref Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "clearance_date",
            "label": _("Clearance Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "account_currency",
            "label": _("Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "width": 100
        }
    ]


def get_entries(filters):
    from goprime.config.utils import get_features

    branch_filter = ""
    if get_features().get('JMann_simple_ui'):
        branch_filter = ' and branch = "{}"'.format(filters.get("branch"))

    journal_entries = frappe.db.sql("""
        select "Journal Entry" as payment_document, jv.posting_date,
            jv.name as payment_entry, jvd.debit_in_account_currency as debit,
            jvd.credit_in_account_currency as credit, jvd.against_account,
            jv.cheque_no as reference_no, jv.cheque_date as ref_date, jv.clearance_date, jvd.account_currency
        from
            `tabJournal Entry Account` jvd, `tabJournal Entry` jv
        where jvd.parent = jv.name and jv.docstatus=1
            and jvd.account = %(account)s and jv.posting_date <= %(report_date)s
            and ifnull(jv.clearance_date, '4000-01-01') > %(report_date)s
            and ifnull(jv.is_opening, 'No') = 'No' {}""".format(branch_filter), filters, as_dict=1)

    payment_entries = frappe.db.sql("""
        select
            "Payment Entry" as payment_document, name as payment_entry,
            reference_no, reference_date as ref_date,
            if(paid_to=%(account)s, received_amount, 0) as debit,
            if(paid_from=%(account)s, paid_amount, 0) as credit,
            posting_date, ifnull(party,if(paid_from=%(account)s,paid_to,paid_from)) as against_account, clearance_date,
            if(paid_to=%(account)s, paid_to_account_currency, paid_from_account_currency) as account_currency
        from `tabPayment Entry`
        where
            (paid_from=%(account)s or paid_to=%(account)s) and docstatus=1
            and posting_date <= %(report_date)s
            and ifnull(clearance_date, '4000-01-01') > %(report_date)s
            {}
    """.format(branch_filter), filters, as_dict=1)

    pos_entries = []
    if filters.include_pos_transactions:
        pos_entries = frappe.db.sql("""
            select
                "Sales Invoice Payment" as payment_document, sip.name as payment_entry, sip.amount as debit,
                si.posting_date, si.debit_to as against_account, sip.clearance_date,
                account.account_currency, 0 as credit
            from `tabSales Invoice Payment` sip, `tabSales Invoice` si, `tabAccount` account
            where
                sip.account=%(account)s and si.docstatus=1 and sip.parent = si.name
                and account.name = sip.account and si.posting_date <= %(report_date)s and
                ifnull(sip.clearance_date, '4000-01-01') > %(report_date)s
            order by
                si.posting_date ASC, si.name DESC
        """, filters, as_dict=1)

    return sorted(
        list(payment_entries)
        + list(journal_entries+list(pos_entries)),
        key=lambda k: k['posting_date'] or getdate(nowdate())
    )


def get_amounts_not_reflected_in_system(filters):
    from goprime.config.utils import get_features

    branch_filter = ""
    pe_branch_filter = ""
    if get_features().get('JMann_simple_ui'):
        branch_filter = ' and jvd.branch = "{}"'.format(filters.get("branch"))
        pe_branch_filter = ' and branch = "{}"'.format(filters.get("branch"))

    je_amount = frappe.db.sql("""
        select sum(jvd.debit_in_account_currency - jvd.credit_in_account_currency)
        from `tabJournal Entry Account` jvd, `tabJournal Entry` jv
        where jvd.parent = jv.name and jv.docstatus=1 and jvd.account=%(account)s
        and jv.posting_date > %(report_date)s and jv.clearance_date <= %(report_date)s
        and ifnull(jv.is_opening, 'No') = 'No' 
        {}""".format(branch_filter), filters)

    je_amount = flt(je_amount[0][0]) if je_amount else 0.0

    pe_amount = frappe.db.sql("""
        select sum(if(paid_from=%(account)s, paid_amount, received_amount))
        from `tabPayment Entry`
        where (paid_from=%(account)s or paid_to=%(account)s) and docstatus=1
        and posting_date > %(report_date)s and clearance_date <= %(report_date)s
        {}""".format(pe_branch_filter), filters)

    pe_amount = flt(pe_amount[0][0]) if pe_amount else 0.0

    return je_amount + pe_amount


def get_balance_row(label, amount, account_currency):
    if amount > 0:
        return {
            "payment_entry": label,
            "debit": amount,
            "credit": 0,
            "account_currency": account_currency
        }
    else:
        return {
            "payment_entry": label,
            "debit": 0,
            "credit": abs(amount),
            "account_currency": account_currency
        }


def get_balance_by_branch(account, date, branch):
    cond = []
    in_account_currency = True

    if branch:
        cond.append("branch = '%s'" % branch)

    if date:
        cond.append("posting_date <= %s" % frappe.db.escape(cstr(date)))
    else:
        # get balance of all entries that exist
        date = nowdate()
    acc = frappe.get_doc("Account", account)

    try:
        year_start_date = get_fiscal_year(date, verbose=0)[1]
    except FiscalYearError:
        if getdate(date) > getdate(nowdate()):
            # if fiscal year not found and the date is greater than today
            # get fiscal year for today's date and its corresponding year start date
            year_start_date = get_fiscal_year(nowdate(), verbose=1)[1]
        else:
            # this indicates that it is a date older than any existing fiscal year.
            # hence, assuming balance as 0.0
            return 0.0

    report_type = acc.report_type

    if not (frappe.flags.ignore_account_permission or False):
        acc.check_permission("read")

    if report_type == 'Profit and Loss':
        # for pl accounts, get balance within a fiscal year
        cond.append("posting_date >= '%s' and voucher_type != 'Period Closing Voucher'" \
            % year_start_date)
    # different filter for group and ledger - improved performance
    if acc.is_group:
        cond.append("""exists (
            select name from `tabAccount` ac where ac.name = gle.account
            and ac.lft >= %s and ac.rgt <= %s
        )""" % (acc.lft, acc.rgt))

        # If group and currency same as company,
        # always return balance based on debit and credit in company currency
        if acc.account_currency == frappe.get_cached_value('Company',  acc.company,  "default_currency"):
            in_account_currency = False
    else:
        cond.append("""gle.account = %s """ % (frappe.db.escape(account, percent=False), ))

    if account:
        if in_account_currency:
            select_field = "sum(debit_in_account_currency) - sum(credit_in_account_currency)"
        else:
            select_field = "sum(debit) - sum(credit)"
        bal = frappe.db.sql("""
            SELECT {0}
            FROM `tabGL Entry` gle
            WHERE {1}""".format(select_field, " and ".join(cond)))[0][0]

        # if bal is None, return 0
        return flt(bal)
