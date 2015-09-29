import frappe
from werkzeug.wrappers import Response
import hashlib, base64, hmac
import requests
import json

@frappe.whitelist(allow_guest=True)
def authenticate_user():
	form_dict = frappe.local.form_dict
	
	api_key = "96d040e1b908d6b39a337300e7fff77c"
	scopes = "read_products, write_products, read_customers, write_customers, read_orders, write_orders"
	redirect_uri = "https://myacc.localtunnel.me/api/method/erpnext_shopify.erpnext_shopify.generate_token"

	install_url = "https://{}/admin/oauth/authorize?client_id={}&scope={}&redirect_uri={}\
		".format(form_dict["shop"], api_key, scopes, redirect_uri)
	
	frappe.response["type"] = 'redirect'
	
	frappe.response["location"] = install_url

@frappe.whitelist(allow_guest=True)
def generate_token():
	form_dict = frappe.local.form_dict	
	
	frappe.set_user("Administrator")
	
	token_dict = {
		"client_id": "96d040e1b908d6b39a337300e7fff77c",
		"client_secret": "de1593719e236b571f0a8e251e366fd5",
		"code": form_dict["code"]
	}
	url = "https://{}/admin/oauth/access_token".format(form_dict["shop"])
	res = requests.post(url= url, data=json.dumps(token_dict), headers={'Content-type': 'application/json'})
	
	settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
		
	settings.update({
		"access_token": res.json()['access_token'],
		"shopify_url": form_dict["shop"]
	}).save()
	
	frappe.response["type"] = 'redirect'
	
	frappe.response["location"] = "https://{}/admin/apps".format(form_dict["shop"])
	