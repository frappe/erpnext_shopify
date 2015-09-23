# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.utils import create_webhook, delete_request, get_request, get_shopify_customers,\
 get_address_type, post_request, get_shopify_items
from frappe.model.document import Document
from frappe.utils import cstr

class ShopifySettings(Document):
	def on_update(self):
		pass
	
	def sync_shopify(self):
		""" 
			1. sync product
			2. sync customer : address, cutomergroup
			3. sync order
			4. 
		"""
		sync_products(self.price_list, self.warehouse)
		# sync_customers()
		frappe.msgprint("Customers Sync")
		

def sync_products(price_list, warehouse):
	sync_shopify_items(warehouse)
	# sync_erp_items(price_list)

def sync_shopify_items(warehouse):
	for item in get_shopify_items():
		if not frappe.db.get_value("Item", {"id": item.get("id")}, "name"):
			if has_variants(item):
				frappe.errprint(item["title"])
			else:
				create_item(item, warehouse)
				
def has_variants(item):
	if len(item.get("options")) > 1 and "Default Title" not in item.get("options")[0]["values"]:
		return True
	return False

def create_item(item, warehouse, has_variant=0):
	frappe.get_doc({
		"doctype": "Item",
		"id": item.get("id"),
		"item_code": cstr(item.get("id")),
		"item_name": item.get("title"),
		"description": item.get("body_html"),
		"item_group": get_item_group(item.get("product_type")),
		"has_variants": has_variant,
		"default_warehouse": warehouse
	}).insert()

def get_item_group(product_type=None):
	if product_type:
		return frappe.get_doc({
			"doctype": "Item Group",
			"name_field": product_type,
			"is_group": "No"
		}).save().name
		
	return "All Item Groups"
	
			
def sync_erp_items(price_list):
	for item in frappe.get_list("Item", filters={"sync_with_shopify": 1, "variant_of": None, "id": None}, 
			fields=["item_code", "item_name", "item_group", "description", "has_variants"]):
			
		item_data = {
					"product": {
						"title": item.get("item_code"),
						"body_html": item.get("description"),
						"product_type": item.get("item_group")
					}
				}
		
		if item.get("has_variants"):
			variant_list, options = get_variant_attributes(item, price_list)
			
			item_data["product"]["variants"] = variant_list
			item_data["product"]["options"] = options
			
		new_item = post_request("/admin/products.json", item_data)

		erp_item = frappe.get_doc("Item", item.get("item_code"))
		erp_item.id = new_item['product'].get("id")
		erp_item.save()
			

def get_variant_attributes(item, price_list):
	options, variant_list = [], []
	attr_dict = {}
	
	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("item_code")}, fields=['name'])):
		
		item_variant = frappe.get_doc("Item", variant.get("name"))
		
		variant_list.append({
			"price": frappe.db.get_value("Item Price", {"price_list": price_list}, "price_list_rate"), 
			"sku": item_variant.stock_uom
		})
		
		for attr in item_variant.get('attributes'):
			if not attr_dict.get(attr.attribute):
				attr_dict.setdefault(attr.attribute, [])
			
			attr_dict[attr.attribute].append(attr.attribute_value)
			
			if attr.idx <= 3:
				variant_list[i]["option"+cstr(attr.idx)] = attr.attribute_value
	
	for i, attr in enumerate(attr_dict):
		options.append({
            "name": attr,
            "position": i+1,
            "values": list(set(attr_dict[attr]))
        })
	
	return variant_list, options
	
def sync_customers():
	sync_shopify_customers()
	sync_erp_customers()

def sync_shopify_customers():
	for customer in get_shopify_customers():
		if not frappe.db.get_value("Customer", {"id": customer.get('id')}, "name"):
			cust_name = (customer.get("first_name") + " " + (customer.get("last_name") and  customer.get("last_name") or ""))\
				if customer.get("first_name") else customer.get("email")
			erp_cust = frappe.get_doc({
				"doctype": "Customer",
				"customer_name" : cust_name,
				"id": customer.get("id"),
				"customer_group": "Commercial",
				"territory": "All Territories",
				"customer_type": "Company"
			}).insert()
		
			for i, address in enumerate(customer.get("addresses")):
				addr = frappe.get_doc({
					"doctype": "Address",
					"address_title": erp_cust.customer_name,
					"address_type": get_address_type(i),
					"address_line1": address.get("address1") or "Address 1",
					"address_line2": address.get("address2"),
					"city": address.get("city") or "City",
					"state": address.get("province"),
					"pincode": address.get("zip"),
					"country": address.get("country"),
					"phone": address.get("phone"),
					"email_id": customer.get("email"),
					"customer": erp_cust.name,
					"customer_name":  erp_cust.customer_name
				}).insert()

def sync_erp_customers():
	for customer in frappe.db.sql("""select name, customer_name from tabCustomer where ifnull(id, '') = '' """, as_dict=1):
		cust = {
			"first_name": customer['customer_name']
		}
		
		addresses = frappe.db.sql("""select addr.address_line1 as address1, addr.address_line2 as address2, 
						addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip from 
						tabAddress addr where addr.customer ='%s' """%(customer['customer_name']), as_dict=1)
		
		if addresses:
			cust["addresses"] = addresses
						
		cust = post_request("/admin/customers.json", { "customer": cust})

		customer = frappe.get_doc("Customer", customer['name'])
		customer.id = cust['customer'].get("id")
		customer.save()

def sync_orders():
	pass

def delete_webhooks():
	webhooks = get_webhooks()
	for webhook in webhooks:
		delete_request("/admin/webhooks/{}.json".format(webhook['id']))

def get_webhooks():
	webhooks = get_request("/admin/webhooks.json")
	return webhooks["webhooks"]
	
def create_webhooks():
	for event in ["orders/create", "orders/delete", "orders/updated", "orders/paid", "orders/cancelled", "orders/fulfilled", 
					"orders/partially_fulfilled", "order_transactions/create", "carts/create", "carts/update", 
					"checkouts/create", "checkouts/update", "checkouts/delete", "refunds/create", "products/create", 
					"products/update", "products/delete", "collections/create", "collections/update", "collections/delete", 
					"customer_groups/create", "customer_groups/update", "customer_groups/delete", "customers/create", 
					"customers/enable", "customers/disable", "customers/update", "customers/delete", "fulfillments/create", 
					"fulfillments/update", "shop/update", "disputes/create", "disputes/update", "app/uninstalled", 
					"channels/delete", "product_publications/create", "product_publications/update", 
					"product_publications/delete", "collection_publications/create", "collection_publications/update", 
					"collection_publications/delete", "variants/in_stock", "variants/out_of_stock"]:
					
		create_webhook(event, "http://demo.healthsnapp.com/")