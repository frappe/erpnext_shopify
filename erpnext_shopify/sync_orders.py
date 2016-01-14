import frappe
from frappe import _
from .exceptions import ShopifyError
from .utils import create_log_entry
from .sync_products import make_item
from .sync_customers import create_customer
from frappe.utils import cstr, flt, nowdate
from .shopify_requests import get_request, get_shopify_orders
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice

def sync_orders():
	sync_shopify_orders()

def sync_shopify_orders():
	for order in get_shopify_orders():
		if valid_customer_and_product(order):
			create_order(order)

def valid_customer_and_product(order):
	customer_id = order.get("customer", {}).get("id")
	if customer_id:
		if not frappe.db.get_value("Customer", {"shopify_id": customer_id}, "name"):
			create_customer(order.get("customer"))
	else:
		create_log_entry(order, _("Customer is mandatory to create order"))
		frappe.msgprint(_("Customer is mandatory to create order"))
		return False
	
	warehouse = frappe.get_doc("Shopify Settings", "Shopify Settings").warehouse
	for item in order.get("line_items"):
		if not frappe.db.get_value("Item", {"shopify_id": item.get("product_id")}, "name"):
			item = get_request("/admin/products/{}.json".format(item.get("product_id")))["product"]
			make_item(warehouse, item)
	
	return True

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
	if not frappe.db.get_value("Sales Invoice", {"shopify_id": order.get("id")}, "name") and so.docstatus==1 \
		and not so.per_billed:
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
