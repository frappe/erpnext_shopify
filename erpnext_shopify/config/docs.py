
source_link = "https://github.com/frappe/erpnext_shopify"
docs_base_url = "https://frappe.github.io/erpnext_shopify"
headline = "ERPNext-Shopify Connector"
sub_heading = "Provides syncing between configured Shopify Account and ERPNext Account"
long_description = """ERPNext Shopify Connector will sync data between Shopify account to ERPNext account.
<br>
<ol>
	<li> It will sync Products and Cutomers from Shopify to ERPnext and Vice Versa.</li>
	<li> It will sync Orders from Shopify to ERPNext.
		<ul>
			<li>If payment is marked on Shopify against Order then it will create Sales Invoice is ERPNext marked as paid.</li>
			<li>If fulfillment has been marked against Order in Shopify then in ERPNext it will create Delivery Note in Draft state.</li>
		</ul>
	</li>
</ol>"""

def get_context(context):
	context.title = "ERPNext Shopify Connector"