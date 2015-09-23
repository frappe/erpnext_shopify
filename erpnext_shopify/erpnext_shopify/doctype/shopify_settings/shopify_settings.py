# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.utils import create_webhook, delete_request, get_request, get_shopify_customers,\
 get_address_type, post_request, get_shopify_items
from frappe.model.document import Document
from frappe.utils import cstr
from frappe import _
import json

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
	sync_erp_items(price_list, warehouse)

def sync_shopify_items(warehouse):
	shopify_variants_attr_list = ["option1", "option2", "option3"] 
	for item in get_shopify_items():
		if not frappe.db.get_value("Item", {"id": item.get("id")}, "name"):
			if has_variants(item):
				"""
					create variant attribute master
					create main item
					create variants
				"""
				attributes = create_attribute(item)
				create_item(item, warehouse, 1, attributes)
				create_item_variants(item, warehouse, attributes, shopify_variants_attr_list)
			else:
				create_item(item, warehouse)
				
def has_variants(item):
	if len(item.get("options")) > 1 and "Default Title" not in item.get("options")[0]["values"]:
		return True
	return False
	
def create_attribute(item):
	attribute = []
	for attr in item.get('options'):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			frappe.get_doc({
				"doctype": "Item Attribute",
				"attribute_name": attr.get("name"),
				"item_attribute_values": [{"attribute_value":attr_value, "abbr": cstr(attr_value)[:3]} for attr_value in attr.get("values")]
			}).insert()
		else:
			"check for attribute values"
			item_attr = frappe.get_doc("Item Attribute", attr.get("name"))
			new_attribute_values = get_new_attribute_values(item_attr.item_attribute_values, attr.get("values"))
			item_attr.item_attribute_values.extend(new_attribute_values)
			item_attr.save()
		
		attribute.append({"attribute": attr.get("name")})
	return attribute
	
def get_new_attribute_values(item_attribute_values, values):
	attr_values = []
	for attr_value in values:
		if not any(d.attribute_value == attr_value for d in item_attribute_values):
			attr_values.append({
				"attribute_value": attr_value,
				"abbr": cstr(attr_value)[:3]
			})
	return attr_values	
	
def create_item(item, warehouse, has_variant=0, attributes=[],variant_of=None):
	item_name = frappe.get_doc({
		"doctype": "Item",
		"id": item.get("id"),
		"variant_of": variant_of,
		"item_code": cstr(item.get("item_code")) or cstr(item.get("id")),
		"item_name": item.get("title"),
		"description": item.get("title"),
		"item_group": get_item_group(item.get("product_type")),
		"has_variants": has_variant,
		"attributes":attributes,
		"stock_uom": item.get("uom") or get_stock_uom(item), 
		"default_warehouse": warehouse
	}).insert()
	
	if not has_variant:
		add_to_price_list(item)

def create_item_variants(item, warehouse, attributes, shopify_variants_attr_list):
	for variant in item.get("variants"):
		variant_item = {
			"id" : variant.get("product_id"),
			"item_code": variant.get("id"),
			"title": item.get("title"),
			"product_type": item.get("product_type"),
			"uom": variant.get("sku"),
			"item_price": variant.get("price")
		}
		
		for i, variant_attr in enumerate(shopify_variants_attr_list):
			if variant.get(variant_attr):
				attributes[i].update({"attribute_value": variant.get(variant_attr)})
		
		create_item(variant_item, warehouse, 0, attributes, cstr(item.get("id")))

def get_item_group(product_type=None):
	if product_type:
		if not frappe.db.get_value("Item Group", product_type, "name"):
			return frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": product_type,
				"parent_item_group": _("All Item Groups"),
				"is_group": "No"
			}).insert().name
		else:
			return product_type
	else:
		return _("All Item Groups")

def get_stock_uom(item):
	sku = item.get("variants")[0].get("sku")
	if sku:
		if not frappe.db.get_value("UOM", sku, "name"):
			return frappe.get_doc({
				"doctype": "UOM",
				"uom_name": item.get("variants")[0].get("sku")
			}).insert().name
		else:
			return sku
	else:
		return _("Nos")

def add_to_price_list(item):
	frappe.get_doc({
		"doctype": "Item Price",
		"price_list": frappe.get_doc("Shopify Settings", "Shopify Settings").price_list,
		"item_code": cstr(item.get("item_code")) or cstr(item.get("id")),
		"price_list_rate": item.get("item_price") or item.get("variants")[0].get("price")
	}).insert()

def sync_erp_items(price_list, warehouse):
	for item in frappe.db.sql("""select item_code, item_name, item_group, description, has_variants, stock_uom from tabItem 
		where sync_with_shopify=1 and variant_of is null and id is null""", as_dict=1):
			
		item_data = {
					"product": {
						"title": item.get("item_code"),
						"body_html": item.get("description"),
						"product_type": item.get("item_group")
					}
				}
				
		if item.get("has_variants"):
			variant_list, options = get_variant_attributes(item, price_list, warehouse)
			
			item_data["product"]["variants"] = variant_list
			item_data["product"]["options"] = options
			
		else:
			item_data["product"]["variants"] = get_price_and_stock_details(item, item.get("stock_uom"), warehouse, price_list)
							
		new_item = post_request("/admin/products.json", item_data)

		erp_item = frappe.get_doc("Item", item.get("item_code"))
		erp_item.id = new_item['product'].get("id")
		erp_item.save()
			

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list = [], []
	attr_dict = {}
	
	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("item_code")}, fields=['name'])):
		
		item_variant = frappe.get_doc("Item", variant.get("name"))

		variant_list.append(get_price_and_stock_details(item, item_variant.stock_uom, warehouse, price_list))
		
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

def get_price_and_stock_details(item, uom, warehouse, price_list):
	qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse}, "actual_qty") 
	return {
		"price": frappe.db.get_value("Item Price", \
			{"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate"), 
		"sku": uom,
		"inventory_quantity": qty if qty else 0,
		"inventory_management": "shopify"
	}

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