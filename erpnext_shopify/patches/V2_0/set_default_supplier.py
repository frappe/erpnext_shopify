# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.shopify_requests import get_shopify_items
from erpnext_shopify.sync_products import get_supplier
from erpnext_shopify.utils import is_shopify_enabled
from frappe.utils.fixtures import sync_fixtures

def execute():
	if not is_shopify_enabled():
		return

	sync_fixtures('erpnext_shopify')
	
	for index, shopify_item in enumerate(get_shopify_items(ignore_filter_conditions=True)):
		name = frappe.db.get_value("Item", {"shopify_product_id": shopify_item.get("id")}, "name")
		supplier = get_supplier(shopify_item)
	
		if name and supplier:
			frappe.db.set_value("Item", name, "default_supplier", supplier, update_modified=False)
					
		if (index+1) % 100 == 0:
			frappe.db.commit()
		
		