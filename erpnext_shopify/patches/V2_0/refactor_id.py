# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
from frappe.utils.fixtures import sync_fixtures
from six import iteritems

def execute():
	sync_fixtures("erpnext_shopify")
	frappe.reload_doctype("Item")
	frappe.reload_doctype("Customer")
	frappe.reload_doctype("Sales Order")
	frappe.reload_doctype("Delivery Note")
	frappe.reload_doctype("Sales Invoice")
	
	for doctype, column in iteritems({"Customer": "shopify_customer_id", 
		"Item": "shopify_product_id", 
		"Sales Order": "shopify_order_id", 
		"Delivery Note": "shopify_order_id", 
		"Sales Invoice": "shopify_order_id"}):
		
		if "shopify_id" in frappe.db.get_table_columns(doctype):
			frappe.db.sql("update `tab%s` set %s=shopify_id" % (doctype, column))	