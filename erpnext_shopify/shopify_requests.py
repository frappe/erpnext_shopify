import frappe
from frappe import _
import json, math, time
from .exceptions import ShopifyError
from frappe.utils import get_request_session

def check_api_call_limit(response):
	"""
		This article will show you how to tell your program to take small pauses 
		to keep your app a few API calls shy of the API call limit and 
		to guard you against a 429 - Too Many Requests error.
		
		ref : https://docs.shopify.com/api/introduction/api-call-limit	
	"""
	if response.headers.get("HTTP_X_SHOPIFY_SHOP_API_CALL_LIMIT") == 39:
		time.sleep(10)    # pause 10 seconds

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
	check_api_call_limit(r)
	r.raise_for_status()
	return r.json()

def post_request(path, data):
	settings = get_shopify_settings()
	s = get_request_session()
	url = get_shopify_url(path, settings)
	r = s.post(url, data=json.dumps(data), headers=get_header(settings))
	check_api_call_limit(r)
	r.raise_for_status()
	return r.json()

def put_request(path, data):
	settings = get_shopify_settings()
	s = get_request_session()
	url = get_shopify_url(path, settings)
	r = s.put(url, data=json.dumps(data), headers=get_header(settings))
	check_api_call_limit(r)
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

def get_filtering_condition():
	shopify_settings = get_shopify_settings()
	if shopify_settings.last_sync_datetime:
		return 'updated_at_min="{}"'.format(shopify_settings.last_sync_datetime)
	return ''

def get_total_pages(resource):
	filter_condition = get_filtering_condition()
	
	return int(math.ceil(get_request('/admin/{0}/count.json?{1}'.format(resource, filter_condition)).get('count', 0) / 250))
 
def get_country():
	return get_request('/admin/countries.json')['countries']

def get_shopify_items():
	shopify_products = []
	filter_condition = get_filtering_condition()
	
	for page_idx in xrange(0, get_total_pages("products") or 1):
		shopify_products.extend(get_request('/admin/products.json?limit=250&page={0}&{1}'.format(page_idx+1, 
			filter_condition))['products'])
	return shopify_products

def get_shopify_item_image(shopify_id):
	return get_request("/admin/products/{0}/images.json".format(shopify_id))["images"]
	
def get_shopify_orders():
	shopify_orders = []
	filter_condition = get_filtering_condition()
	
	for page_idx in xrange(0, get_total_pages("orders") or 1):
		shopify_orders.extend(get_request('/admin/orders.json?limit=250&page={0}&{1}'.format(page_idx+1, 
			filter_condition))['orders'])
	return shopify_orders

def get_shopify_customers():
	shopify_customers = []
	filter_condition = get_filtering_condition()
	
	for page_idx in xrange(0, get_total_pages("customers") or 1):
		shopify_customers.extend(get_request('/admin/customers.json?limit=250&page={0}&{1}'.format(page_idx+1, 
			filter_condition))['customers'])
	return shopify_customers