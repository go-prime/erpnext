from __future__ import unicode_literals
from frappe import _
import frappe

def get_data():
    tiles = frappe.get_list("Module Tile", ignore_permissions=True, filters={'module': 'Retail'})
    if tiles:
        return [frappe.get_doc("Module Tile", tile['name']).as_module_dict() for tile in tiles]
        
    return [
		{
            "label": _("Retail Operations"),
            "items": [
                {
                    "type": "doctype",
                    "name": "POS Profile",
                    "label": _("Point-of-Sale Profile"),
                    "description": _("Setup default values for POS Invoices"),
					"onboard": 1,
                },
                {
                    "type": "page",
                    "name": "pos",
                    "label": _("POS"),
                    "description": _("Point of Sale"),
					"onboard": 1,
					"dependencies": ["POS Profile"]
                },
                {
                    "type": "doctype",
                    "name": "Cashier Closing",
                    "description": _("Cashier Closing"),
                },
                {
                    "type": "doctype",
                    "name": "POS Settings",
                    "description": _("Setup mode of POS (Online / Offline)")
                },
                {
                    "type": "doctype",
                    "name": "Loyalty Program",
                    "label": _("Loyalty Program"),
                    "description": _("To make Customer based incentive schemes.")
                },
                {
                    "type": "doctype",
                    "name": "Loyalty Point Entry",
                    "label": _("Loyalty Point Entry"),
                    "description": _("To view logs of Loyalty Points assigned to a Customer.")
                }
            ]
        }
	]