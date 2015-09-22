from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Settings"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Shopify Settings",
					"description": _("Settings for shopify webhooks.")
				}
			]
		}
	]