import frappe
from frappe import _
from .utils import get_address_type
from .exceptions import ShopifyError
from .shopify_requests import get_shopify_customers, post_request

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
		frappe.get_doc({
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
	for customer in frappe.db.sql("""select name, customer_name from tabCustomer 
		where ifnull(shopify_id, '') = '' and sync_with_shopify = 1 """, as_dict=1):
		
		cust = {
			"first_name": customer['customer_name']
		}

		addresses = frappe.db.sql("""select addr.address_line1 as address1, addr.address_line2 as address2,
			addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip 
			from tabAddress addr where addr.customer ='%s' """%(customer['customer_name']), as_dict=1)

		if addresses:
			cust["addresses"] = addresses

		cust = post_request("/admin/customers.json", { "customer": cust})

		customer = frappe.get_doc("Customer", customer['name'])
		customer.shopify_id = cust['customer'].get("id")
		customer.save()
