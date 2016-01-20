import frappe
from frappe import _
from .utils import get_address_type
from .exceptions import ShopifyError
from .shopify_requests import get_shopify_customers, post_request

def sync_customers():
	sync_shopify_customers()
	sync_erpnext_customers()

def sync_shopify_customers():
	for shopify_customer in get_shopify_customers():
		if not frappe.db.get_value("Customer", {"shopify_customer_id": customer.get('id')}, "name"):
			create_customer(shopify_customer)

def create_customer(shopify_customer):
	erp_cust = None
	cust_name = (shopify_customer.get("first_name") + " " + (shopify_customer.get("last_name") \
		and  shopify_customer.get("last_name") or "")) if shopify_customer.get("first_name")\
		 else shopify_customer.get("email")

	try:
		customer = frappe.get_doc({
			"doctype": "Customer",
			"name": shopify_customer.get("id"),
			"customer_name" : cust_name,
			"shopify_customer_id": shopify_customer.get("id"),
			"customer_group": "Commercial",
			"territory": "All Territories",
			"customer_type": "Company"
		}).insert()
	except:
		pass

	if customer:
		create_customer_address(customer, shopify_customer)

def create_customer_address(customer, shopify_customer):
	for i, address in enumerate(shopify_customer.get("addresses")):
		frappe.get_doc({
			"doctype": "Address",
			"shopify_address_id": address.get("id"),
			"address_title": customer.customer_name,
			"address_type": get_address_type(i),
			"address_line1": address.get("address1") or "Address 1",
			"address_line2": address.get("address2"),
			"city": address.get("city") or "City",
			"state": address.get("province"),
			"pincode": address.get("zip"),
			"country": address.get("country"),
			"phone": address.get("phone"),
			"email_id": shopify_customer.get("email"),
			"customer": customer.name,
			"customer_name":  customer.customer_name
		}).insert()

def sync_erpnext_customers():
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	
	last_sync_condition = ""
	if shopify_settings.last_sync_datetime:
		last_sync_condition = "and modified >= '{0}' ".format(shopify_settings.last_sync_datetime)
	
	customer_query = """select name, customer_name from tabCustomer 
		where ifnull(shopify_customer_id, '') = '' and sync_with_shopify = 1 %s""" % last_sync_condition
	
	for customer in frappe.db.sql(customer_query, as_dict=1):
		shopify_customer = {
			"first_name": customer['customer_name']
		}

		addresses = frappe.db.sql("""select addr.address_line1 as address1, addr.address_line2 as address2,
			addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip 
			from tabAddress addr where addr.customer ='%s' """%(customer['customer_name']), as_dict=1)

		if addresses:
			shopify_customer["addresses"] = addresses

		shopify_customer = post_request("/admin/customers.json", { "customer": shopify_customer})

		customer = frappe.get_doc("Customer", customer['name'])
		customer.shopify_customer_id = shopify_customer['customer'].get("id")
		customer.save()
