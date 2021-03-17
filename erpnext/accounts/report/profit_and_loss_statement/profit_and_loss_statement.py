# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.report.financial_statements import (get_period_list, get_columns, get_data)

def jmann_execute(filters=None):
	period_list = get_period_list(filters.from_fiscal_year, filters.to_fiscal_year,
		filters.periodicity, filters.accumulated_values, filters.company)

	abbr = frappe.db.get_value('Company', filters.get('company'), 'abbr')
	income = get_data(filters.company, "Income", "Credit", period_list, filters = filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)
	
	def get_children(data_list, name):
		return [child for child in data_list \
			if child.get('parent_account') == name]

	direct_income_parent = frappe.db.sql('''
		select name from `tabAccount` where name like "%direct income%"
		and name not like "%indirect%" and company = "{}"'''.format(filters.get('company')))[0][0]
	indirect_income_parent = frappe.db.sql('''
		select name from `tabAccount` where name like "%indirect income%"
		 and company = "{}"'''.format(filters.get('company')))[0][0]
	direct_income = []
	indirect_income = []
	
	direct_income_account = None
	indirect_income_account = None
	for i in income:
		if i.get('account') == direct_income_parent:
			direct_income_account = i
		if i.get('account') == indirect_income_parent:
			indirect_income_account = i
		if i.get('parent_account') == direct_income_parent:
			direct_income.append(i)
			direct_income.extend(get_children(income, i.get('account')))
		if i.get('parent_account') == indirect_income_parent:
			indirect_income.append(i)
			indirect_income.extend(get_children(income, i.get('account')))
			
	if direct_income_account:
		direct_income.insert(0, direct_income_account)
	if indirect_income_account:
		# del indirect_income_account['parent_account']
		indirect_income.insert(0, indirect_income_account)
	
	expense = get_data(filters.company, "Expense", "Debit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)
	
	direct_expenses_parent = frappe.db.sql('''
		select name from `tabAccount` where name like "%direct expenses%"
		and name not like "%indirect%" and company = "{}"'''.format(filters.get('company')))[0][0]
	indirect_expenses_parent = frappe.db.sql('''
		select name from `tabAccount` where name like "%indirect expenses%"
		and company = "{}"'''.format(filters.get('company')))[0][0]
	direct_expenses = []
	indirect_expenses = []
	
	direct_expenses_account = None
	indirect_expenses_account = None

	for i in expense:
		if i.get('account') == direct_expenses_parent:
			direct_expenses_account = i
		if i.get('account') == indirect_expenses_parent:
			indirect_expenses_account = i
		if i.get('parent_account') == direct_expenses_parent:
			direct_expenses.append(i)
			direct_expenses.extend(get_children(expense, i.get('account')))
		if i.get('parent_account') == indirect_expenses_parent:
			indirect_expenses.append(i)
			indirect_expenses.extend(get_children(expense, i.get('account')))

	
	period_keys = [i.get('key') for i in period_list]
	gross_profit = {
		'account': 'Gross Profit',
		'account_name': 'Gross Profit',
		'currency': frappe.db.get_value('Company', filters.get('company'), 'default_currency'),
	}
	gross_profit_total = 0
	if direct_income_account and direct_expenses_account:
		for key in period_keys:
			gross = direct_income_account[key] - direct_expenses_account[key]
			gross_profit[key] = gross
			gross_profit_total += gross

		gross_profit['total'] = gross_profit_total

	if direct_expenses_account:
		direct_expenses.insert(0, direct_expenses_account)
	if indirect_expenses_account:
		indirect_expenses.insert(0, indirect_expenses_account)
	
	net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, filters.presentation_currency)

	data = []
	data.extend(direct_income or [])
	data.extend(direct_expenses or [])
	data.append(gross_profit)
	data.append({})
	data.extend(indirect_income or [])
	data.extend(indirect_expenses or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	for i in data:
		if i.get('indent'):
			i['indent'] = i['indent'] - 1 if i['indent'] > 0 else 0 

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	#GoPrime 2020
	columns = [
		columns[0],
		{
			'fieldtype': 'Data',
			'fieldname': 'account_number',
			'label': 'Account Number',
			'width': 140
		},
		*columns[1:]
	]

	def add_account_no(row):
		if row.get('account'):
			row['account_number'] = frappe.db.get_value('Account', row['account'], 'account_number')
		else:
			row['account_number'] = ''
		return row

	data = [add_account_no(i) for i in data]

	chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	return columns, data, None, chart

def execute(filters=None):
	from goprime.config.utils import get_features
	config = get_features()
	jmann = config.get("JMann_item_fields", False)
	if jmann:
		return jmann_execute(filters)

	period_list = get_period_list(filters.from_fiscal_year, filters.to_fiscal_year,
		filters.periodicity, filters.accumulated_values, filters.company)

	income = get_data(filters.company, "Income", "Credit", period_list, filters = filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	expense = get_data(filters.company, "Expense", "Debit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, filters.presentation_currency)

	data = []
	data.extend(income or [])
	data.extend(expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)	
	chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	return columns, data, None, chart

def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False):
	total = 0
	net_profit_loss = {
		"account_name": "'" + _("Net Profit for the year") + "'",
		"account": "'" + _("Profit for the year") + "'",
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value('Company',  company,  "default_currency")
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key
		total_income = flt(income[-2][key], 3) if income else 0
		total_expense = flt(expense[-2][key], 3) if expense else 0
		net_profit_loss[key] = total_income - total_expense

		if net_profit_loss[key]:
			has_value=True

		total += flt(net_profit_loss[key])
		net_profit_loss["total"] = total

	if has_value:
		return net_profit_loss

def get_chart_data(filters, columns, income, expense, net_profit_loss):
	labels = [d.get("label") for d in columns[2:]]

	income_data, expense_data, net_profit = [], [], []

	for p in columns[2:]:
		if income:
			income_data.append(income[-2].get(p.get("fieldname")))
		if expense:
			expense_data.append(expense[-2].get(p.get("fieldname")))
		if net_profit_loss:
			net_profit.append(net_profit_loss.get(p.get("fieldname")))

	datasets = []
	if income_data:
		datasets.append({'name': _('Income'), 'values': income_data})
	if expense_data:
		datasets.append({'name': _('Expense'), 'values': expense_data})
	if net_profit:
		datasets.append({'name': _('Net Profit/Loss'), 'values': net_profit})

	chart = {
		"data": {
			'labels': labels,
			'datasets': datasets
		}
	}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"

	return chart