cur_frm.fields_dict["default_tax_account"].get_query = function(doc, dt, dn){
	return {
		"query": "erpnext.controllers.queries.tax_account_query",
		"filters": {
			"account_type": ["Tax", "Chargeable", "Expense Account"],
			"company": frappe.defaults.get_default("company")
		}
	}
}

frappe.ui.form.on("Shopify Settings", "sync_shopify", function(frm, dt, dn) { 
	frappe.call({
		method:"erpnext_shopify.erpnext_shopify.doctype.shopify_settings.shopify_settings.sync_shopify",
		freeze: true,
		callback:function(r){
			if(!r.exc){
				frappe.msgprint(__("Sync Completed!!"))
			}
		}
	})
});
