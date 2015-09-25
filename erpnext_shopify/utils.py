import frappe
from frappe.utils import get_request_session
from frappe.exceptions import AuthenticationError, ValidationError
from functools import wraps

import hashlib, base64, hmac, json

def get_shopify_items():
	return get_request('/admin/products.json')['products']

def get_shopify_orders():
	return get_request('/admin/orders.json')['orders']

def get_country():
	return get_request('/admin/countries.json')['countries']
	
def get_shopify_customers():
	return get_request('/admin/customers.json')['customers']

def get_address_type(i):
	return ["Billing", "Shipping", "Office", "Personal", "Plant", "Postal", "Shop", "Subsidiary", "Warehouse", "Other"][i]

def create_webhook(topic, address):
	post_request('admin/webhooks.json', json.dumps({
		"webhook": {
			"topic": topic,
			"address": address,
			"format": "json"
		}
	}))

def shopify_webhook(f):
	"""
	A decorator thats checks and validates a Shopify Webhook request.
	"""
 
	def _hmac_is_valid(body, secret, hmac_to_verify):
		# secret = "62ec6a7130f5d1fff0fb56bc9b322bab"
		secret = str(secret)
		hash = hmac.new(secret, body, hashlib.sha256)
		hmac_calculated = base64.b64encode(hash.digest())
		return hmac_calculated == hmac_to_verify
 
	@wraps(f)
	def wrapper(*args, **kwargs):
		# Try to get required headers and decode the body of the request.
		try:
			webhook_topic = frappe.local.request.headers.get('X-Shopify-Topic')
			webhook_hmac	= frappe.local.request.headers.get('X-Shopify-Hmac-Sha256')
			webhook_data	= frappe._dict(json.loads(frappe.local.request.get_data()))
		except:
			raise ValidationError()

		# Verify the HMAC.
		if not _hmac_is_valid(frappe.local.request.get_data(), get_shopify_settings().password, webhook_hmac):
			raise AuthenticationError()

			# Otherwise, set properties on the request object and return.
		frappe.local.request.webhook_topic = webhook_topic
		frappe.local.request.webhook_data  = webhook_data
		kwargs.pop('cmd')
		
		return f(*args, **kwargs)
	return wrapper
	
@frappe.whitelist(allow_guest=True)
@shopify_webhook
def webhook_handler():
	from webhooks import handler_map
	topic = frappe.local.request.webhook_topic
	data = frappe.local.request.webhook_data
	handler = handler_map.get(topic)
	if handler:
		handler(data)

def get_shopify_settings():
	d = frappe.get_doc("Shopify Settings")
	return d.as_dict()
	
def get_request(path):
	settings = get_shopify_settings()
	s = get_request_session()
	url = 'https://{}:{}@{}/{}'.format(settings['api_key'], settings['password'], settings['shopify_url'], path)
	r = s.get(url)
	r.raise_for_status()
	return r.json()
	
def post_request(path, data):
	settings = get_shopify_settings()
	s = get_request_session()
	url = 'https://{}:{}@{}/{}'.format(settings['api_key'], settings['password'], settings['shopify_url'], path)
	r = s.post(url, data=json.dumps(data), headers={'Content-type': 'application/json'})
	r.raise_for_status()
	return r.json()

def delete_request(path):
	settings = get_shopify_settings()
	s = get_request_session()
	url = 'https://{}:{}@{}/{}'.format(settings['api_key'], settings['password'], settings['shopify_url'], path)
	r = s.delete(url)
	r.raise_for_status()
	
def delete_webhooks():
	webhooks = get_webhooks()
	for webhook in webhooks:
		delete_request("/admin/webhooks/{}.json".format(webhook['id']))

def get_webhooks():
	webhooks = get_request("/admin/webhooks.json")
	return webhooks["webhooks"]
	
def create_webhooks():
	settings = get_shopify_settings()
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
					
		create_webhook(event, settings.webhook_address)