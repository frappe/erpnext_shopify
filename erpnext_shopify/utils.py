# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils import cstr
from .exceptions import ShopifySetupError

def disable_shopify_sync_for_item(item):
	"""Disable Item if not exist on shopify"""
	frappe.db.rollback()
	item.sync_with_shopify = 0
	item.save()
	frappe.db.commit()

def disable_shopify_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("Shopify Settings", None, "enable_shopify", 0)
	frappe.db.commit()

def create_log_entry(data_json, exception):
	error_log = frappe.new_doc("Shopify Error Log")
	error_log.log_datetime = frappe.utils.now()
	error_log.request_data = json.dumps(data_json)
	error_log.traceback = cstr(exception)
	error_log.save(ignore_permissions=True)
	
def is_shopify_enabled():
	shopify_settings = frappe.get_doc("Shopify Settings")
	if not shopify_settings.enable_shopify:
		return False
	
	try:
		shopify_settings.validate()
	except ShopifySetupError:
		return False
	
	return True
		
	