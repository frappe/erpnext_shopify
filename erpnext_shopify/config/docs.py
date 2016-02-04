source_link = "https://github.com/frappe/erpnext_shopify"
docs_base_url = "https://frappe.github.io/erpnext_shopify"
headline = "ERPNext Shopify Connector"
sub_heading = "Sync transactions between Shopify and ERPNext"
long_description = """ERPNext Shopify Connector will sync data between your Shopify and ERPNext accounts.
<br>
<ol>
	<li> It will sync Products and Cutomers between Shopify and ERPNext</li>
	<li> It will push Orders from Shopify to ERPNext
		<ul>
			<li>
				If the Order has been paid for in Shopify, it will create a Sales Invoice in ERPNext and record the corresponding Payment Entry
			</li>
			<li>
				If the Order has been fulfilled in Shopify, it will create a draft Delivery Note in ERPNext
			</li>
		</ul>
	</li>
</ol>"""
docs_version = "1.0.0"

def get_context(context):
	context.title = "ERPNext Shopify Connector"
