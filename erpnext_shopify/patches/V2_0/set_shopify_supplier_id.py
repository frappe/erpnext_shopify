# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.utils import is_shopify_enabled
from frappe.utils.fixtures import sync_fixtures

def execute():
	if not is_shopify_enabled():
		return
	
	sync_fixtures('erpnext_shopify')
	
	fieldnames = frappe.db.sql("select fieldname from `tabCustom Field`", as_dict=1)	
	
	if not any(field['fieldname'] == 'shopify_supplier_id' for field in fieldnames):
		return 
			
	frappe.db.sql("""update tabSupplier set shopify_supplier_id=supplier_name """)
	frappe.db.commit()
			