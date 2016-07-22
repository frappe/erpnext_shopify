// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext_shopify.shopify_settings");

frappe.ui.form.on("Shopify Settings", "onload", function(frm, dt, dn){
	frappe.call({
		method:"erpnext_shopify.erpnext_shopify.doctype.shopify_settings.shopify_settings.get_series",
		callback:function(r){
			$.each(r.message, function(key, value){
				set_field_options(key, value)
			})
		}
	})
	erpnext_shopify.shopify_settings.setup_queries(frm);
})

frappe.ui.form.on("Shopify Settings", "app_type", function(frm, dt, dn) {
	frm.toggle_reqd("api_key", (frm.doc.app_type == "Private"));
	frm.toggle_reqd("password", (frm.doc.app_type == "Private"));
})

frappe.ui.form.on("Shopify Settings", "refresh", function(frm){
	if(!frm.doc.__islocal && frm.doc.enable_shopify === 1){
		frm.toggle_reqd("price_list", true);
		frm.toggle_reqd("warehouse", true);
		frm.toggle_reqd("taxes", true);
		frm.toggle_reqd("cash_bank_account", true);
		frm.toggle_reqd("sales_order_series", true);
		frm.toggle_reqd("sales_invoice_series", true);
		frm.toggle_reqd("delivery_note_series", true);
		frm.toggle_reqd("customer_group", true);

		cur_frm.add_custom_button(__('Sync Shopify'),
			function() {
				frappe.call({
					method:"erpnext_shopify.api.sync_shopify",
				})
			}, 'icon-sitemap')
	}

	if(!frm.doc.access_token && !frm.doc.api_key) {
		cur_frm.add_custom_button(__("Connect to Shopify"),
			function(){
				window.open("https://apps.shopify.com/erpnext");
			}).addClass("btn-primary")
	}

	cur_frm.add_custom_button(__("Shopify Log"), function(){
		frappe.set_route("List", "Shopify Log");
	})


	frappe.call({
		method: "erpnext_shopify.api.get_log_status",
		callback: function(r) {
			if(r.message){
				frm.dashboard.set_headline_alert(r.message.text, r.message.alert_class)
			}
		}
	})

})


$.extend(erpnext_shopify.shopify_settings, {
	setup_queries: function(frm) {
		frm.fields_dict["warehouse"].get_query = function(doc) {
			return {
				filters:{
					"company": doc.company,
					"is_group": "No"
				}
			}
		}
		
		frm.fields_dict["taxes"].grid.get_field("tax_account").get_query = function(doc, dt, dn){
			return {
				"query": "erpnext.controllers.queries.tax_account_query",
				"filters": {
					"account_type": ["Tax", "Chargeable", "Expense Account"],
					"company": frappe.defaults.get_default("Company")
				}
			}
		}
		
		frm.fields_dict["cash_bank_account"].get_query = function(doc) {
			return {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			}
		}
	}
})
