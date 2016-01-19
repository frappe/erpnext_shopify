# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests.exceptions
from .exceptions import ShopifyError

from .sync_orders import sync_orders
from .sync_customers import sync_customers
from frappe.utils.user import get_system_managers
from .sync_products import sync_products, update_item_stock_qty
from .utils import create_log_entry, disable_shopify_sync_on_exception

@frappe.whitelist()
def sync_shopify():
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	if shopify_settings.enable_shopify:
		
		if not frappe.session.user:
			frappe.set_user("Administrator")
			
		try :
			sync_products(shopify_settings.price_list, shopify_settings.warehouse)
			sync_customers()
			sync_orders()
			update_item_stock_qty()
			frappe.db.set_value("Shopify Settings", None, "last_sync_datetime", frappe.utils.now())
			
		except ShopifyError:
			disable_shopify_sync_on_exception()
			
		except requests.exceptions.HTTPError, e:
			#HTTPError: 402 Client Error: Payment Required 
			if e.args[0] and e.args[0].startswith("402"):
				disable_shopify_sync_on_exception()
				content = _("""Shopify has suspended your account till you complete the payment. We have disabled ERPNext Shopify Sync. Please enable it once your complete the payment at Shopify.""")
				frappe.sendmail(get_system_managers(), subject=_("Shopify Sync has been disabled"), content=content)
					
	elif frappe.local.form_dict.cmd == "erpnext_shopify.erpnext_shopify.doctype.shopify_settings.shopify_settings.sync_shopify":
		frappe.throw(_("""Shopify connector is not enabled. Click on 'Connect to Shopify' to connect ERPNext and your Shopify store."""))