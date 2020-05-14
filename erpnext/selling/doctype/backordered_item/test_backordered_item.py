import frappe
import unittest
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

def create_data():

    frappe.set_user("Administrator")
    #Create company
    # company = frappe.new_doc("Company")
    # company.company_name = "bentsch"
    # company.abbr = "bch"
    # company.default_currency = "USD"
    # company.create_chart_of_accounts_based_on = "Standard Template"
    # company.chart_of_accounts = "Standard Template"
    # company.save()

    #Create warehouse
    whs = frappe.get_list('Warehouse')
    
    #Create Item
    item = make_item('PROD001', properties={'warehouse': whs[0]['name'], 'opening_stock': 5})

    #Create Sales Order w sales order item
    doc = make_sales_order(item='PRODOO1')
    # Should automatically submit in which case the item 
    # quantity is less than available so we should have a backorder

print('testing')

class TestBackorderedItem(unittest.TestCase):
    def setUp(self):
        create_data()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_has_backordered_item(self):
        frappe.set_user("Administrator")
        docs = frappe.get_list(doctype="Backordered Item")
        self.assertEqual(len(docs), 1)

    def test_has_backordered_item_quantity(self):
        frappe.set_user("Administrator")
        docs = frappe.get_list(doctype="Backordered Item")
        doc = frappe.get_doc('Backordered Item', docs[0]['name'])
        self.assertEqual(doc.quantity, 5)
