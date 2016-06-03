# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from .exceptions import ShopifySetupError

def disable_shopify_sync_for_item(item, rollback=False):
	"""Disable Item if not exist on shopify"""
	if rollback:
		frappe.db.rollback()
		
	item.sync_with_shopify = 0
	item.sync_qty_with_shopify = 0
	item.save(ignore_permissions=True)
	frappe.db.commit()

def disable_shopify_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("Shopify Settings", None, "enable_shopify", 0)
	frappe.db.commit()

def is_shopify_enabled():
	shopify_settings = frappe.get_doc("Shopify Settings")
	if not shopify_settings.enable_shopify:
		return False
	try:
		shopify_settings.validate()
	except ShopifySetupError:
		return False
	
	return True
	
def make_shopify_log(title="Sync Log", status="Queued", method="sync_shopify", message=None, exception=False, 
name=None, request_data={}):
	if not name:
		name = frappe.db.get_value("Shopify Log", {"status": "Queued"})
		
		if name:
			""" if name not provided by log calling method then fetch existing queued state log"""
			log = frappe.get_doc("Shopify Log", name)
		
		else:
			""" if queued job is not found create a new one."""
			log = frappe.get_doc({"doctype":"Shopify Log"}).insert(ignore_permissions=True)
		
		if exception:
			frappe.db.rollback()
			log = frappe.get_doc({"doctype":"Shopify Log"}).insert(ignore_permissions=True)
			
		log.message = message if message else frappe.get_traceback()
		log.title = title[0:140]
		log.method = method
		log.status = status
		log.request_data= json.dumps(request_data)
		
		log.save(ignore_permissions=True)
		frappe.db.commit()