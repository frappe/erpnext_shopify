import frappe
from erpnext_shopify.shopify_requests import get_request
from erpnext_shopify.sync_orders import set_included_in_print_rate
from frappe.utils import cint

def execute():
	for so in frappe.db.sql("""select name, shopify_order_id, discount_amount from `tabSales Order` where shopify_order_id is not null and
		docstatus=1 """, as_dict=1):
		
		shopify_order = get_request("/admin/orders/{0}.json".format(so.shopify_order_id))
		
		if set_included_in_print_rate(shopify_order) and cint(so.discount_amount):
			try:
				so = frappe.get_doc("Sales Order", so.name)
				si = recalculate_totals_for_sales_invoice(so)
			
				so.docstatus=2
				so.on_cancel()
				setup_inclusive_taxes(so)
			
				so.validate()
				so.docstatus=1
				so.on_submit()
			
				if si:
					si.on_submit()
			
				frappe.db.commit()
			except:
				frappe.db.rollback()

def recalculate_totals_for_sales_invoice(so):
	si = frappe.get_doc("Sales Invoice", {"shopify_order_id": so.shopify_order_id, "docstatus": 1})
	if si:
		si.docstatus=2
		si.on_cancel()
		setup_inclusive_taxes(si)
		si.validate()
		si.docstatus=1
		return si

def setup_inclusive_taxes(doc):
	for tax in doc.taxes:
		tax.included_in_print_rate = 1
		