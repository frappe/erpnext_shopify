from __future__ import unicode_literals
import frappe

class ShopifyError(frappe.ValidationError): pass
class ShopifySetupError(frappe.ValidationError): pass