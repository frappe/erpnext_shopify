# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext_shopify.utils import create_webhook, delete_request, get_request, get_shopify_customers, get_address_type, post_request
from frappe.model.document import Document

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
		# sync_customers()
		sync_products()
		frappe.msgprint("Customers Sync")
		

def sync_products():
	push_items_to_shopify()
	
def push_items_to_shopify():
	"""
	{
	    "product": {
	        "title": "Pack123",
	        "body_html": "<strong>Good snowboard!111</strong>",
	        "product_type": "Snowboard",
	        "variants": [
	            {
	                "option1": "M",
	                "option2": "Pink",
	                "option3": "cotton",
	                "price": "10.00",
	                "sku": 123
	            },
	            {
	                "option1": "L",
	                "option2": "Blue",
	                "option3": "silk",
	                "price": "20.00",
	                "sku": "123"
	            }
	        ],
	        "options": [
	            {
	                "name": "Size",
	                "position": 1,
	                "values": [
	                    "M",
	                    "L"
	                ]
	            },
	            {
	                "name": "Color",
	                "position": 2,
	                "values": [
	                    "Pink",
	                    "Blue"
	                ]
	            },
	            {
	                "name": "Material",
	                "position": 3,
	                "values": [
	                    "cotton",
	                    "silk"
	                ]
	            }
	        ]
	    }
	}
	"""
	import json
	for item in frappe.db.sql("""select item_code, item_name, description, item_group, has_variants from tabItem 
		where sync_with_shopify=1 and variant_of is null""", as_dict=1):
		
		item_data = {
					"product": {
						"title": item.get("item_code"),
						"body_html": item.get("description"),
						"product_type": item.get("item_group")
					}
				}
		
		if item.get("has_variants"):
			item_data["product"]["variants"] = get_variant_details(item)
			item_data["product"]["options"] = get_variant_attributes(item)
			
		
		item = post_request("/admin/products.json", item_data)

		erp_item = frappe.get_doc("Item", item.get("item_code"))
		erp_item.id = cust['product'].get("id")
		erp_item.save()
			

def get_variant_attributes(item):
	options = []
	for i, option in enumerate(frappe.db.sql("""select distinct group_concat(attribute_value) as value, attribute from `tabItem Variant Attribute` 
			where parent in (select name from tabItem 
				where variant_of="%s") group by attribute"""%(item.get("item_code")),as_dict=1)):
				
		values = option["value"].split(',')		
		
        options.append({
            "name": option["attribute"],
            "position": i,
            "values": values
        })
				
	return options

def get_variant_details(item):
	tem_val = ["", "", ""]
	variant_list = []
	
	for variant in frappe.db.sql("""select group_concat(attribute_value) as value, stock_uom,  
				coalesce((select coalesce(price_list_rate,0) from `tabItem Price` ip 
					where ip.item_code = iva.parent), 0.0) as price_list_rate
			from `tabItem Variant Attribute` iva, `tabItem` 
			where iva.parent in 
				(select name from tabItem where variant_of="%s") 
			and tabItem.name = iva.parent group by iva.parent;"""%(item.get("item_code")), as_dict=1):
		
		value = variant["value"].split(',')
		value.extend(tem_val)
		
		variant_list.append({"option1": value[0], 
			"option2": value[1], 
			"option3": value[2], 
			"price": variant["price_list_rate"], 
			"sku": variant["stock_uom"]
		})
		
	return variant_list
	
	
def sync_customers():
	sync_shopify_customers()
	sync_erp_customers()

def sync_shopify_customers():
	for customer in get_shopify_customers():
		if not frappe.db.get_value("Customer", {"id": customer.get('id')}, "name"):
			print customer
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