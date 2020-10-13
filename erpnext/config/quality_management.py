from __future__ import unicode_literals
from frappe import _
import frappe 
def get_data():
	tiles = frappe.get_list("Module Tile", filters={'module': 'Quality Management'})
	if tiles:
		return [frappe.get_doc("Module Tile", tile['name']).as_module_dict() for tile in tiles]
    
	return [
		{
			"label": _("Goal and Procedure"),
			"items": [
				{
					"type": "doctype",
					"name": "Quality Goal",
					"description":_("Quality Goal."),
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Quality Procedure",
					"description":_("Quality Procedure."),
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Quality Procedure",
					"icon": "fa fa-sitemap",
					"label": _("Tree of Procedures"),
					"route": "#Tree/Quality Procedure",
					"description": _("Tree of Quality Procedures."),
				},
			]
		},
		{
			"label": _("Review and Action"),
			"items": [
				{
					"type": "doctype",
					"name": "Quality Review",
					"description":_("Quality Review"),
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Quality Action",
					"description":_("Quality Action"),
				}
			]
		},
		{
			"label": _("Meeting"),
			"items": [
				{
					"type": "doctype",
					"name": "Quality Meeting",
					"description":_("Quality Meeting"),
				}
			]
		},
		{
			"label": _("Feedback"),
			"items": [
				{
					"type": "doctype",
					"name": "Quality Feedback",
					"description":_("Quality Feedback"),
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Quality Feedback Template",
					"description":_("Quality Feedback Template"),
				}
			]
		},
	]