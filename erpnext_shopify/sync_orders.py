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
	for shopify_order in get_shopify_orders():
		if valid_customer_and_product(shopify_order):
			create_order(shopify_order)

def valid_customer_and_product(shopify_order):
	customer_id = shopify_order.get("customer", {}).get("id")
	if customer_id:
		if not frappe.db.get_value("Customer", {"shopify_customer_id": customer_id}, "name"):
			create_customer(shopify_order.get("customer"))
	else:
		create_log_entry(shopify_order, _("Customer is mandatory to create order"))
		frappe.msgprint(_("Customer is mandatory to create order"))
		return False
	
	warehouse = frappe.get_doc("Shopify Settings", "Shopify Settings").warehouse
	for item in shopify_order.get("line_items"):
		if not frappe.db.get_value("Item", {"shopify_product_id": item.get("product_id")}, "name"):
			item = get_request("/admin/products/{}.json".format(item.get("product_id")))["product"]
			make_item(warehouse, item)
	
	return True

def create_order(shopify_order, company=None):
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	so = create_sales_order(shopify_order, shopify_settings, company)
	if shopify_order.get("financial_status") == "paid":
		create_sales_invoice(shopify_order, shopify_settings, so)

	if shopify_order.get("fulfillments"):
		create_delivery_note(shopify_order, shopify_settings, so)

def create_sales_order(shopify_order, shopify_settings, company=None):
	so = frappe.db.get_value("Sales Order", {"shopify_order_id": shopify_order.get("id")}, "name")
	if not so:
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"naming_series": shopify_settings.sales_order_series or "SO-Shopify-",
			"shopify_order_id": shopify_order.get("id"),
			"customer": frappe.db.get_value("Customer", {"shopify_customer_id": shopify_order.get("customer").get("id")}, "name"),
			"delivery_date": nowdate(),
			"selling_price_list": shopify_settings.price_list,
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"discount_amount": get_discounted_amount(shopify_order),
			"items": get_order_items(shopify_order.get("line_items"), shopify_settings),
			"taxes": get_order_taxes(shopify_order, shopify_settings)
		})
		
		if company:
			so.update({
				"company": company,
				"status": "Draft"
			})

		so.save(ignore_permissions=True)
		so.submit()

	else:
		so = frappe.get_doc("Sales Order", so)

	return so

def create_sales_invoice(shopify_order, shopify_settings, so):
	if not frappe.db.get_value("Sales Invoice", {"shopify_order_id": shopify_order.get("id")}, "name") and so.docstatus==1 \
		and not so.per_billed:
		si = make_sales_invoice(so.name)
		si.shopify_order_id = shopify_order.get("id")
		si.naming_series = shopify_settings.sales_invoice_series or "SI-Shopify-"
		si.is_pos = 1
		si.cash_bank_account = shopify_settings.cash_bank_account
		si.submit()

def create_delivery_note(shopify_order, shopify_settings, so):
	for fulfillment in shopify_order.get("fulfillments"):
		if not frappe.db.get_value("Delivery Note", {"shopify_order_id": fulfillment.get("id")}, "name") and so.docstatus==1:
			dn = make_delivery_note(so.name)
			dn.shopify_order_id = fulfillment.get("order_id")
			dn.shopify_fulfillment_id = fulfillment.get("id")
			dn.naming_series = shopify_settings.delivery_note_series or "DN-Shopify-"
			dn.items = get_fulfillment_items(dn.items, fulfillment.get("line_items"), shopify_settings)
			dn.save()

def get_fulfillment_items(dn_items, fulfillment_items, shopify_settings):
	return [dn_item.update({"qty": item.get("quantity")}) for item in fulfillment_items for dn_item in dn_items\
			 if get_item_code(item) == dn_item.item_code]
			 
	# items = []
# 	for shopify_item in fulfillment_items:
# 		for item in dn_items:
# 			if get_item_code(shopify_item) == item.item_code:
# 				items.append(item.update({"qty": item.get("quantity")}))
# 	return items
	
def get_discounted_amount(order):
	discounted_amount = 0.0
	for discount in order.get("discount_codes"):
		discounted_amount += flt(discount.get("amount"))
	return discounted_amount

def get_order_items(order_items, shopify_settings):
	items = []
	for shopify_item in order_items:
		item_code = get_item_code(shopify_item)
		items.append({
			"item_code": item_code,
			"item_name": shopify_item.get("name"),
			"rate": shopify_item.get("price"),
			"qty": shopify_item.get("quantity"),
			"stock_uom": shopify_item.get("sku"),
			"warehouse": shopify_settings.warehouse
		})
	return items

def get_item_code(shopify_item):
	item_code = frappe.db.get_value("Item", {"shopify_variant_id": shopify_item.get("variant_id")}, "item_code")
	if not item_code:
		item_code = frappe.db.get_value("Item", {"shopify_product_id": shopify_item.get("product_id")}, "item_code")

	return item_code

def get_order_taxes(shopify_order, shopify_settings):
	taxes = []
	for tax in shopify_order.get("tax_lines"):
		taxes.append({
			"charge_type": _("On Net Total"),
			"account_head": get_tax_account_head(tax),
			"description": "{0} - {1}%".format(tax.get("title"), tax.get("rate") * 100.0),
			"rate": tax.get("rate") * 100.00,
			"included_in_print_rate": set_included_in_print_rate(shopify_order)
		})

	taxes = update_taxes_with_shipping_lines(taxes, shopify_order.get("shipping_lines"))

	return taxes

def set_included_in_print_rate(shopify_order):
	if shopify_order.get("total_tax"):
		if (flt(shopify_order.get("total_price")) - flt(shopify_order.get("total_line_items_price"))) == 0.0:
			return 1
	return 0

def update_taxes_with_shipping_lines(taxes, shipping_lines):
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
