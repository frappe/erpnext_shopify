# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.shopify_requests import get_shopify_items
from frappe.utils import cint
from frappe import _
from erpnext_shopify.exceptions import ShopifyError
import requests.exceptions
from frappe.utils.fixtures import sync_fixtures

def execute():
	sync_fixtures("erpnext_shopify")
	frappe.reload_doctype("Item")

	shopify_settings = frappe.get_doc("Shopify Settings")
	if not shopify_settings.enable_shopify or not shopify_settings.password:
		return

	try:
		shopify_items = get_item_list()
	except ShopifyError:
		print("Could not run shopify patch 'set_variant_id' for site: {0}".format(frappe.local.site))
		return

	if shopify_settings.shopify_url and shopify_items:
		for item in frappe.db.sql("""select name, item_code, shopify_id, has_variants, variant_of from tabItem
			where sync_with_shopify=1 and shopify_id is not null""", as_dict=1):

			if item.get("variant_of"):
				frappe.db.sql(""" update tabItem set shopify_variant_id=shopify_id
					where name = %s """, item.get("name"))

			elif not item.get("has_variants"):
				product = filter(lambda shopify_item: shopify_item['id'] == cint(item.get("shopify_id")), shopify_items)

				if product:
					frappe.db.sql(""" update tabItem set shopify_variant_id=%s
						where name = %s """, (product[0]["variants"][0]["id"], item.get("name")))

def get_item_list():
	try:
		return get_shopify_items()
	except (requests.exceptions.HTTPError, ShopifyError) as e:
		frappe.throw(_("Something went wrong: {0}").format(frappe.get_traceback()), ShopifyError)

