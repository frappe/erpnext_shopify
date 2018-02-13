# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from .exceptions import ShopifyError
from .sync_orders import sync_orders
from .sync_customers import sync_customers
from .sync_products import sync_products, update_item_stock_qty
from .utils import disable_shopify_sync_on_exception, make_shopify_log
from frappe.utils.background_jobs import enqueue

@frappe.whitelist()
def sync_shopify():
	"Enqueue longjob for syncing shopify"
	enqueue("erpnext_shopify.api.sync_shopify_resources", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for syncing. It may take a few minutes to an hour if this is your first sync."))

@frappe.whitelist()
def sync_shopify_resources():
	shopify_settings = frappe.get_doc("Shopify Settings")

	make_shopify_log(title="Sync Job Queued", status="Queued", method=frappe.local.form_dict.cmd, message="Sync Job Queued")
	
	if shopify_settings.enable_shopify:
		try :
			now_time = frappe.utils.now()
			validate_shopify_settings(shopify_settings)
			frappe.local.form_dict.count_dict = {}
			sync_products(shopify_settings.price_list, shopify_settings.warehouse)
			sync_customers()
			sync_orders()
			update_item_stock_qty()
			frappe.db.set_value("Shopify Settings", None, "last_sync_datetime", now_time)
			
			make_shopify_log(title="Sync Completed", status="Success", method=frappe.local.form_dict.cmd, 
				message= "Updated {customers} customer(s), {products} item(s), {orders} order(s)".format(**frappe.local.form_dict.count_dict))

		except Exception as e:
			if e.args[0] and hasattr(e.args[0], "startswith") and e.args[0].startswith("402"):
				make_shopify_log(title="Shopify has suspended your account", status="Error",
					method="sync_shopify_resources", message=_("""Shopify has suspended your account till
					you complete the payment. We have disabled ERPNext Shopify Sync. Please enable it once
					your complete the payment at Shopify."""), exception=True)

				disable_shopify_sync_on_exception()
			
			else:
				make_shopify_log(title="sync has terminated", status="Error", method="sync_shopify_resources",
					message=frappe.get_traceback(), exception=True)
					
	elif frappe.local.form_dict.cmd == "erpnext_shopify.api.sync_shopify":
		make_shopify_log(
			title="Shopify connector is disabled",
			status="Error",
			method="sync_shopify_resources",
			message=_("""Shopify connector is not enabled. Click on 'Connect to Shopify' to connect ERPNext and your Shopify store."""),
			exception=True)

def validate_shopify_settings(shopify_settings):
	"""
		This will validate mandatory fields and access token or app credentials 
		by calling validate() of shopify settings.
	"""
	try:
		shopify_settings.save()
	except ShopifyError:
		disable_shopify_sync_on_exception()

@frappe.whitelist()
def get_log_status():
	log = frappe.db.sql("""select name, status from `tabShopify Log` 
		order by modified desc limit 1""", as_dict=1)
	if log:
		if log[0].status=="Queued":
			message = _("Last sync request is queued")
			alert_class = "alert-warning"
		elif log[0].status=="Error":
			message = _("Last sync request was failed, check <a href='../desk#Form/Shopify Log/{0}'> here</a>"
				.format(log[0].name))
			alert_class = "alert-danger"
		else:
			message = _("Last sync request was successful")
			alert_class = "alert-success"
			
		return {
			"text": message,
			"alert_class": alert_class
		}
		