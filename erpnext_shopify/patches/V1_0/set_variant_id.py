# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.utils import get_request

def execute():
	for item in frappe.db.sql("""select name, item_code, shopify_id, has_variants, variant_of from tabItem 
		where sync_with_shopify=1 and shopify_id is not null""", as_dict=1):
			
		if item.get("varint_of"):
			frappe.db.sql(""" update tabItem set variant_id=shopify_id 
				where name = %s """, item.get("name"))
				
		elif not item.get("has_variants"):
			try:
				product = get_request('/admin/products/{}.json'.format(item.get("shopify_id")))['product']
			
				frappe.db.sql(""" update tabItem set variant_id=%s 
					where name = %s """, (product["variants"][0]["id"], item.get("name")))
			except:
				pass