# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from erpnext_shopify.erpnext_shopify.doctype.shopify_settings.shopify_settings import sync_erp_items, sync_erp_customers, ShopifyError
from erpnext_shopify.utils import get_request
from frappe.utils import cint

test_records = frappe.get_test_records('Shopify Settings')

class ShopifySettings(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.validate_shopify_settings()
	
	def validate_shopify_settings(self):
		self.enabled = False
		shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
		if shopify_settings.enable_shopify:
			self.enabled = True
			
	def test_product(self):
		if self.enabled:
			shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
			self.create_item(test_records[0])
			
			sync_erp_items(shopify_settings.price_list, shopify_settings.warehouse)
		
			item = frappe.get_doc("Item", "Test Shopify Item")
			try:
				synced_item = get_request('/admin/products/{}.json'.format(item.id))['product']
			except ShopifyError:
				raise ShopifyError
		
			self.assertEqual(cint(item.id), synced_item["id"])
			self.assertEqual(item.sync_with_shopify, 1)
			
	def create_item(self,item_details):
		if not frappe.db.get_value("Item", {"item_code": item_details["item_code"]}, "name"):
			frappe.get_doc(item_details).insert()
		
	def test_customer(self):
		if self.enabled:
			shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
			self.create_customer(test_records[1])
			
			sync_erp_customers()
			
			customer = frappe.get_doc("Customer", "_Test Shopify Customer")
	
			try:
				synced_customer = get_request('/admin/customers/{}.json'.format(customer.id))['customer']
			except ShopifyError:
				raise ShopifyError
	
			self.assertEqual(cint(customer.id), synced_customer["id"])
			self.assertEqual(customer.sync_with_shopify, 1)
			
	def create_customer(self, customer_details):
		if not frappe.db.get_value("Customer", {"customer_name": customer_details["customer_name"]}, "name"):
			frappe.get_doc(customer_details).insert()
		
test_dependencies = ["Customer Group", "Company", "Item Group", "Warehouse", "UOM"]