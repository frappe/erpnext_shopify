# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt, nowdate, nowtime, cint
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice
from erpnext_shopify.utils import (get_request, get_shopify_customers, get_address_type, post_request,
	get_shopify_items, get_shopify_orders)
import requests.exceptions

shopify_variants_attr_list = ["option1", "option2", "option3"]

class ShopifyError(Exception):pass

class ShopifySettings(Document):
	def validate(self):
		if self.enable_shopify == 1:
			self.validate_access_credentials()
			self.validate_access()

	def validate_access_credentials(self):
		if self.app_type == "Private":
			if not (self.password and self.api_key and self.shopify_url):
				frappe.msgprint(_("Missing value for Passowrd, API Key or Shopify URL"), raise_exception=1)

		else:
			if not (self.access_token and self.shopify_url):
				frappe.msgprint(_("Access token or Shopify URL missing"), raise_exception=1)

	def validate_access(self):
		try:
			get_request('/admin/products.json', {"api_key": self.api_key,
				"password": self.password, "shopify_url": self.shopify_url,
				"access_token": self.access_token, "app_type": self.app_type})

		except requests.exceptions.HTTPError:
			self.set("enable_shopify", 0)
			frappe.throw(_("""Invalid Shopify app credentails or access token"""))


@frappe.whitelist()
def get_series():
		return {
			"sales_order_series" : frappe.get_meta("Sales Order").get_options("naming_series") or "SO-Shopify-",
			"sales_invoice_series" : frappe.get_meta("Sales Invoice").get_options("naming_series")  or "SI-Shopify-",
			"delivery_note_series" : frappe.get_meta("Delivery Note").get_options("naming_series")  or "DN-Shopify-"
		}

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

		except ShopifyError:
			shopify_settings.erpnext_shopify = 0
			shopify_settings.save()

	elif frappe.local.form_dict.cmd == "erpnext_shopify.erpnext_shopify.doctype.shopify_settings.shopify_settings.sync_shopify":
		frappe.throw(_("""Shopify connector is not enabled.
			Click on 'Connect to Shopify' to connect ERPNext and your Shopify store."""))

def sync_products(price_list, warehouse):
	sync_shopify_items(warehouse)
	sync_erp_items(price_list, warehouse)

def sync_shopify_items(warehouse):
	for item in get_shopify_items():
		if not frappe.db.get_value("Item", {"shopify_id": item.get("id")}, "name"):
			make_item(warehouse, item)

def make_item(warehouse, item):
	if has_variants(item):
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
			set_new_attribute_values(item_attr, attr.get("values"))
			item_attr.save()

		attribute.append({"attribute": attr.get("name")})
	return attribute

def set_new_attribute_values(item_attr, values):
	for attr_value in values:
		if not any((d.abbr == attr_value or d.attribute_value == attr_value) for d in item_attr.item_attribute_values):
			item_attr.append("item_attribute_values", {
				"attribute_value": attr_value,
				"abbr": cstr(attr_value)[:3]
			})

def create_item(item, warehouse, has_variant=0, attributes=[],variant_of=None):
	item_name = frappe.get_doc({
		"doctype": "Item",
		"shopify_id": item.get("id"),
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
			"id" : variant.get("id"),
			"item_code": variant.get("id"),
			"title": item.get("title"),
			"product_type": item.get("product_type"),
			"uom": get_stock_uom(item),
			"item_price": variant.get("price")
		}

		for i, variant_attr in enumerate(shopify_variants_attr_list):
			if variant.get(variant_attr):
				attributes[i].update({"attribute_value": get_attribute_value(variant.get(variant_attr), attributes[i])})

		create_item(variant_item, warehouse, 0, attributes, cstr(item.get("id")))

def get_attribute_value(variant_attr_val, attribute):
	return frappe.db.sql("""select attribute_value from `tabItem Attribute Value`
		where parent = '{0}' and (abbr = '{1}' or attribute_value = '{2}')""".format(attribute["attribute"], variant_attr_val,
		variant_attr_val))[0][0]

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
		where sync_with_shopify=1 and variant_of is null and shopify_id is null""", as_dict=1):
		variant_item_code_list = []

		item_data = {
					"product": {
						"title": item.get("item_code"),
						"body_html": item.get("description"),
						"product_type": item.get("item_group")
					}
				}

		if item.get("has_variants"):
			variant_list, options, variant_item_code = get_variant_attributes(item, price_list, warehouse)

			item_data["product"]["variants"] = variant_list
			item_data["product"]["options"] = options

			variant_item_code_list.extend(variant_item_code)

		else:
			item_data["product"]["variants"] = [get_price_and_stock_details(item, item.get("stock_uom"), warehouse, price_list)]
		new_item = post_request("/admin/products.json", item_data)
		erp_item = frappe.get_doc("Item", item.get("item_code"))
		erp_item.shopify_id = new_item['product'].get("id")
		erp_item.save()

		update_variant_item(new_item, variant_item_code_list)

def update_variant_item(new_item, item_code_list):
	for i, item_code in enumerate(item_code_list):
		erp_item = frappe.get_doc("Item", item_code)
		erp_item.shopify_id = new_item['product']["variants"][i].get("id")
		erp_item.save()

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list, variant_item_code = [], [], []
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

		variant_item_code.append(item_variant.item_code)

	for i, attr in enumerate(attr_dict):
		options.append({
            "name": attr,
            "position": i+1,
            "values": list(set(attr_dict[attr]))
        })

	return variant_list, options, variant_item_code

def get_price_and_stock_details(item, uom, warehouse, price_list):
	qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse}, "actual_qty")
	price = frappe.db.get_value("Item Price", \
			{"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate")

	item_price_and_quantity = {
		"price": flt(price),
		"sku": uom,
		"inventory_quantity": cint(qty) if qty else 0,
		"inventory_management": "shopify"
	}

	return item_price_and_quantity

def sync_customers():
	sync_shopify_customers()
	sync_erp_customers()

def sync_shopify_customers():
	for customer in get_shopify_customers():
		if not frappe.db.get_value("Customer", {"shopify_id": customer.get('id')}, "name"):
			create_customer(customer)

def create_customer(customer):
	erp_cust = None
	cust_name = (customer.get("first_name") + " " + (customer.get("last_name") and  customer.get("last_name") or ""))\
		if customer.get("first_name") else customer.get("email")

	try:
		erp_cust = frappe.get_doc({
			"doctype": "Customer",
			"name": customer.get("id"),
			"customer_name" : cust_name,
			"shopify_id": customer.get("id"),
			"customer_group": "Commercial",
			"territory": "All Territories",
			"customer_type": "Company"
		}).insert()
	except:
		pass

	if erp_cust:
		create_customer_address(erp_cust, customer)

def create_customer_address(erp_cust, customer):
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
	for customer in frappe.db.sql("""select name, customer_name from tabCustomer where ifnull(shopify_id, '') = ''
		and sync_with_shopify = 1 """, as_dict=1):
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
		customer.shopify_id = cust['customer'].get("id")
		customer.save()

def sync_orders():
	sync_shopify_orders()

def sync_shopify_orders():
	for order in get_shopify_orders():
		validate_customer_and_product(order)
		create_order(order)

def validate_customer_and_product(order):
	if not frappe.db.get_value("Customer", {"shopify_id": order.get("customer").get("id")}, "name"):
		create_customer(order.get("customer"))

	warehouse = frappe.get_doc("Shopify Settings", "Shopify Settings").warehouse
	for item in order.get("line_items"):
		if not frappe.db.get_value("Item", {"shopify_id": item.get("product_id")}, "name"):
			item = get_request("/admin/products/{}.json".format(item.get("product_id")))["product"]
			make_item(warehouse, item)

def get_shopify_id(item):pass

def create_order(order):
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	so = create_salse_order(order, shopify_settings)
	if order.get("financial_status") == "paid":
		create_sales_invoice(order, shopify_settings, so)

	if order.get("fulfillments"):
		create_delivery_note(order, shopify_settings, so)

def create_salse_order(order, shopify_settings):
	so = frappe.db.get_value("Sales Order", {"shopify_id": order.get("id")}, "name")
	if not so:
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"naming_series": shopify_settings.sales_order_series or "SO-Shopify-",
			"shopify_id": order.get("id"),
			"customer": frappe.db.get_value("Customer", {"shopify_id": order.get("customer").get("id")}, "name"),
			"delivery_date": nowdate(),
			"selling_price_list": shopify_settings.price_list,
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"discount_amount": get_discounted_amount(order),
			"items": get_item_line(order.get("line_items"), shopify_settings),
			"taxes": get_tax_line(order, order.get("shipping_lines"), shopify_settings)
		}).insert()

		so.submit()

	else:
		so = frappe.get_doc("Sales Order", so)

	return so

def create_sales_invoice(order, shopify_settings, so):
	sales_invoice = frappe.db.get_value("Sales Order", {"shopify_id": order.get("id")},\
		 ["ifnull(per_billed, '') as per_billed"], as_dict=1)

	if not frappe.db.get_value("Sales Invoice", {"shopify_id": order.get("id")}, "name") and so.docstatus==1 \
		and not sales_invoice["per_billed"]:
		si = make_sales_invoice(so.name)
		si.shopify_id = order.get("id")
		si.naming_series = shopify_settings.sales_invoice_series or "SI-Shopify-"
		si.is_pos = 1
		si.cash_bank_account = shopify_settings.cash_bank_account
		si.submit()

def create_delivery_note(order, shopify_settings, so):
	for fulfillment in order.get("fulfillments"):
		if not frappe.db.get_value("Delivery Note", {"shopify_id": fulfillment.get("id")}, "name") and so.docstatus==1:
			dn = make_delivery_note(so.name)
			dn.shopify_id = fulfillment.get("id")
			dn.naming_series = shopify_settings.delivery_note_series or "DN-Shopify-"
			dn.items = update_items_qty(dn.items, fulfillment.get("line_items"), shopify_settings)
			dn.save()

def update_items_qty(dn_items, fulfillment_items, shopify_settings):
	return [dn_item.update({"qty": item.get("quantity")}) for item in fulfillment_items for dn_item in dn_items\
		 if get_item_code(item) == dn_item.item_code]

def get_discounted_amount(order):
	discounted_amount = 0.0
	for discount in order.get("discount_codes"):
		discounted_amount += flt(discount.get("amount"))
	return discounted_amount

def get_item_line(order_items, shopify_settings):
	items = []
	for item in order_items:
		item_code = get_item_code(item)
		items.append({
			"item_code": item_code,
			"item_name": item.get("name"),
			"rate": item.get("price"),
			"qty": item.get("quantity"),
			"stock_uom": item.get("sku"),
			"warehouse": shopify_settings.warehouse
		})
	return items

def get_item_code(item):
	item_code = frappe.db.get_value("Item", {"shopify_id": item.get("variant_id")}, "item_code")
	if not item_code:
		item_code = frappe.db.get_value("Item", {"shopify_id": item.get("product_id")}, "item_code")

	return item_code

def get_tax_line(order, shipping_lines, shopify_settings):
	taxes = []
	for tax in order.get("tax_lines"):
		taxes.append({
			"charge_type": _("On Net Total"),
			"account_head": get_tax_account_head(tax),
			"description": tax.get("title") + "-" + cstr(tax.get("rate") * 100.00),
			"rate": tax.get("rate") * 100.00,
			"included_in_print_rate": set_included_in_print_rate(order)
		})

	taxes = update_taxes_with_shipping_rule(taxes, shipping_lines)

	return taxes

def set_included_in_print_rate(order):
	if order.get("total_tax"):
		if (flt(order.get("total_price")) - flt(order.get("total_line_items_price"))) == 0.0:
			return 1
	return 0

def update_taxes_with_shipping_rule(taxes, shipping_lines):
	for shipping_charge in shipping_lines:
		taxes.append({
			"charge_type": _("Actual"),
			"account_head": get_tax_account_head(shipping_charge),
			"description": shipping_charge["title"],
			"tax_amount": shipping_charge["price"]
		})

	return taxes

def get_tax_account_head(tax):
	tax_account =  frappe.db.get_value("Shopify Tax Account", \
		{"parent": "Shopify Settings", "shopify_tax": tax.get("title")}, "tax_account")

	if not tax_account:
		frappe.throw("Tax Account not specified for Shopify Tax {}".format(tax.get("title")))

	return tax_account
