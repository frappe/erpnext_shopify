import frappe
import json
from frappe.utils import cstr

def get_address_type(i):
	return ["Billing", "Shipping", "Office", "Personal", "Plant", "Postal", "Shop", "Subsidiary", 
	"Warehouse", "Other"][i]

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