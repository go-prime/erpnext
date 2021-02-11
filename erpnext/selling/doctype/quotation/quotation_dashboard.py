from __future__ import unicode_literals
from frappe import _

def get_data():
	from goprime.config.utils import get_features
	simple_ui = get_features().get("JMann_simple_ui", False)
	transactions = [
			{
				'label': _('Sales Order'),
				'items': ['Sales Order']
			}
		]
	if not simple_ui:
		transactions.append({
				'label': _('Subscription'),
				'items': ['Auto Repeat']
			})
	
	return {
		'fieldname': 'prevdoc_docname',
		'non_standard_fieldnames': {
			'Auto Repeat': 'reference_document',
		},
		'transactions': transactions
	}