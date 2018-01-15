import frappe
from .shopify_requests import post_request
from frappe.limits import get_usage_info
from frappe.utils import getdate, markdown
from frappe.email import get_system_managers

def send_payment_notification_to_user():
	if not frappe.db.get_single_value('Shopify Settings', 'enable_shopify'):
		return 

	if frappe.db.get_single_value('Shopify Settings', 'app_type') == 'Private':
		return

	if frappe.db.get_single_value("Global Defaults", "default_currency") == 'INR':
		return

	confirmation_url = create_shopify_application_charges()
	if confirmation_url:
		send_billing_reminder(confirmation_url)

def create_shopify_application_charges():
	"""
		response :
			{
				"application_charge": {
					"api_client_id": 1203780,
					"charge_type": None,
					"confirmation_url": "https://testerps.myshopify.com/admin/charges/46006316/confirm_application_charge?signature=BAhpBCwAvgI%3D--24633d18d865a2e3f62e19a9d1cd88f14e00d038",
					"created_at": "2018-01-11T15:47:04+05:30",
					"decorated_return_url": "https://apps.shopify.com/erpnext?charge_id=46006316",
					"id": 46006316,
					"name": "test plan",
					"price": "0.50",
					"return_url": "https://apps.shopify.com/erpnext",
					"status": "pending",
					"test": True,
					"updated_at": "2018-01-11T15:47:04+05:30"
				}
			}
	"""
	billing_url = 'admin/application_charges.json'
	data = prepare_data()

	if not data:
		return

	try:
		res = post_request(billing_url, data)
		return res["application_charge"]["confirmation_url"]
	except Exception:
		pass

def prepare_data():
	usage_info = get_usage_info()

	if not usage_info:
		return

	site_creation_date = frappe.get_doc('User', 'Administrator').creation.date()
	site_creation_days =  (getdate(site_creation_date) - getdate()).days

	if usage_info.days_to_expiry == 1 and site_creation_days <= 30:
		plan = "P-{0}".format(usage_info.limits.users)

		return {
			"application_charge": {
				"name": "ERPNext Subscription: P-{0}".format(usage_info.limits.users),
				"price": get_plan_wise_prices(plan),
				"return_url": usage_info.upgrade_url
			}
		}

def get_plan_wise_prices(plan):
	return {
		"P-5": 299,
		"P-10": 449,
		"P-15": 599,
		"P-25": 899,
		"P-50": 1499,
		"P-100": 1999,
		"P-200": 2599,
		"P-1000": 3999,
	}[plan]

def send_billing_reminder(confirmation_url):
	system_manager = get_system_managers()[0]
	usage_info = get_usage_info()
	data = {
		'site': frappe.local.site,
		'full_name': frappe.db.get_value('User', system_manager, 'concat(ifnull(first_name, ""), ifnull(last_name, ""))'),
		'support_email': 'support@erpnext.com',
		'confirmation_url': confirmation_url,
		'expires_on': usage_info.expires_on
	}

	stats = frappe.render_template('erpnext_shopify/templates/emails/billing.md', data, is_path=True)
	frappe.sendmail(recipients=[system_manager], subject='Your Shopify-ERPNext subscription is about to expire', message=markdown(stats))
