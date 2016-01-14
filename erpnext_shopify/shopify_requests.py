import frappe
import json, math
from frappe import _
from .exceptions import ShopifyError
from frappe.utils import get_request_session

def get_shopify_settings():
	d = frappe.get_doc("Shopify Settings")
	if d.shopify_url:
		return d.as_dict()
	else:
		frappe.throw(_("Shopify store URL is not configured on Shopify Settings"), ShopifyError)

def get_request(path, settings=None):
	if not settings:
		settings = get_shopify_settings()

	s = get_request_session()
	url = get_shopify_url(path, settings)
	r = s.get(url, headers=get_header(settings))
	r.raise_for_status()
	return r.json()

def post_request(path, data):
	settings = get_shopify_settings()
	s = get_request_session()
	url = get_shopify_url(path, settings)
	r = s.post(url, data=json.dumps(data), headers=get_header(settings))
	r.raise_for_status()
	return r.json()

def put_request(path, data):
	settings = get_shopify_settings()
	s = get_request_session()
	url = get_shopify_url(path, settings)
	r = s.put(url, data=json.dumps(data), headers=get_header(settings))
	r.raise_for_status()
	return r.json()

def delete_request(path):
	s = get_request_session()
	url = get_shopify_url(path)
	r = s.delete(url)
	r.raise_for_status()

def get_shopify_url(path, settings):
	if settings['app_type'] == "Private":
		return 'https://{}:{}@{}/{}'.format(settings['api_key'], settings['password'], settings['shopify_url'], path)
	else:
		return 'https://{}/{}'.format(settings['shopify_url'], path)

def get_header(settings):
	header = {'Content-Type': 'application/json'}

	if settings['app_type'] == "Private":
		return header
	else:
		header["X-Shopify-Access-Token"] = settings['access_token']
		return header

def get_total_pages(resource):
	return int(math.ceil(get_request('/admin/{0}/count.json'.format(resource)).get('count', 0) / 250))
 
def get_country():
	return get_request('/admin/countries.json')['countries']

def get_shopify_items():
	# return get_request('/admin/products.json')['products']
	products = []
	for page_idx in xrange(0, get_total_pages("products") or 1):
		products.extend(get_request('/admin/products.json?limit=250&page={0}'.format(page_idx+1))['products'])
	return products

def get_shopify_item_image(shopify_id):
	return get_request("/admin/products/{0}/images.json".format(shopify_id))["images"]
	
def get_shopify_orders():
	orders = []
	for page_idx in xrange(0, get_total_pages("orders") or 1):
		orders.extend(get_request('/admin/orders.json?limit=250&page={0}'.format(page_idx+1))['orders'])
	return orders

def get_shopify_customers():
	customers = []
	for page_idx in xrange(0, get_total_pages("customers") or 1):
		customers.extend(get_request('/admin/customers.json?limit=250&page={0}'.format(page_idx+1))['customers'])
	return customers