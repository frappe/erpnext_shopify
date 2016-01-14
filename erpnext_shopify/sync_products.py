import re
import frappe
import base64
import datetime
from frappe import _
import requests.exceptions
from .exceptions import ShopifyError
from frappe.utils import cstr, flt, nowdate, cint, get_files_path
from .utils import disable_shopify_sync_for_item, disable_shopify_sync_on_exception
from .shopify_requests import (get_request, post_request, get_shopify_items, put_request, 
	get_shopify_item_image)

shopify_variants_attr_list = ["option1", "option2", "option3"]

def sync_products(price_list, warehouse):
	sync_shopify_items(warehouse)
	sync_erp_items(price_list, warehouse)

def sync_shopify_items(warehouse):
	for item in get_shopify_items():
		make_item(warehouse, item)

def make_item(warehouse, item):
	add_item_weight(item)
	if has_variants(item):
		attributes = create_attribute(item)
		create_item(item, warehouse, 1, attributes)
		create_item_variants(item, warehouse, attributes, shopify_variants_attr_list)
	else:
		item["variant_id"] = item['variants'][0]["id"]
		create_item(item, warehouse)
		
def add_item_weight(item):
	item["weight"] = item['variants'][0]["weight"]
	item["weight_unit"] = item['variants'][0]["weight_unit"]
	
def has_variants(item):
	if len(item.get("options")) >= 1 and "Default Title" not in item.get("options")[0]["values"]:
		return True
	return False

def create_attribute(item):
	attribute = []
	# shopify item dict
	for attr in item.get('options'):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			frappe.get_doc({
				"doctype": "Item Attribute",
				"attribute_name": attr.get("name"),
				"item_attribute_values": [
					{
						"attribute_value": attr_value, 
						"abbr": get_attribute_abbr(attr_value)
					} 
					for attr_value in attr.get("values")
				]
			}).insert()
			attribute.append({"attribute": attr.get("name")})

		else:
			"check for attribute values"
			item_attr = frappe.get_doc("Item Attribute", attr.get("name"))
			if not item_attr.numeric_values:
				set_new_attribute_values(item_attr, attr.get("values"))
				item_attr.save()
				attribute.append({"attribute": attr.get("name")})
			else:
				attribute.append({
					"attribute": attr.get("name"), 
					"from_range": item_attr.get("from_range"),
					"to_range": item_attr.get("to_range"),
					"increment": item_attr.get("increment"),
					"numeric_values": item_attr.get("numeric_values")
				})
		
	return attribute

def set_new_attribute_values(item_attr, values):
	for attr_value in values:
		if not any((d.abbr == attr_value or d.attribute_value == attr_value) for d in item_attr.item_attribute_values):
			item_attr.append("item_attribute_values", {
				"attribute_value": attr_value,
				"abbr": get_attribute_abbr(attr_value)
			})
			
def get_attribute_abbr(attribute_value):
	attribute_value = cstr(attribute_value)
	if re.findall("[\d]+", attribute_value, flags=re.UNICODE):
		# if attribute value has a number in it, pass value as abbrivation
		return attribute_value 
	else:
		return attribute_value[:3]

def create_item(item, warehouse, has_variant=0, attributes=None,variant_of=None):
	item_dict = {
		"doctype": "Item",
		"shopify_id": item.get("id"),
		"shopify_variant_id": item.get("variant_id"),
		"variant_of": variant_of,
		"sync_with_shopify": 1,
		"item_code": cstr(item.get("item_code")) or cstr(item.get("id")),
		"item_name": item.get("title"),
		"description": item.get("body_html") or item.get("title"),
		"item_group": get_item_group(item.get("product_type")),
		"has_variants": has_variant,
		"attributes":attributes or [],
		"stock_uom": item.get("uom") or _("Nos"),
		"stock_keeping_unit": item.get("sku") or get_sku(item),
		"default_warehouse": warehouse,
		"image": get_item_image(item),
		"weight_uom": item.get("weight_unit"),
		"net_weight": item.get("weight")
	}
	
	name, item_details = get_item_details(item)
	if not name:
		new_item = frappe.get_doc(item_dict)
		new_item.insert()
		name = new_item.name

	else:
		update_item(item_details, item_dict)

	if not has_variant:
		add_to_price_list(item, name)

def create_item_variants(item, warehouse, attributes, shopify_variants_attr_list):
	template_item = frappe.db.get_value("Item",
		filters={"shopify_id": item.get("id")},
		fieldname=["name", "stock_uom"],
		as_dict=True)

	for variant in item.get("variants"):
		variant_item = {
			"id" : variant.get("id"),
			"item_code": variant.get("id"),
			"title": item.get("title"),
			"product_type": item.get("product_type"),
			"sku": variant.get("sku"),
			"uom": template_item.stock_uom or _("Nos"),
			"item_price": variant.get("price"),
			"variant_id": variant.get("id"),
			"weight_unit": variant.get("weight_unit"),
			"weight": variant.get("weight")
		}

		for i, variant_attr in enumerate(shopify_variants_attr_list):
			if variant.get(variant_attr):
				attributes[i].update({"attribute_value": get_attribute_value(variant.get(variant_attr), attributes[i])})

		create_item(variant_item, warehouse, 0, attributes, template_item.name)

def get_attribute_value(variant_attr_val, attribute):
	attribute_value = frappe.db.sql("""select attribute_value from `tabItem Attribute Value`
		where parent = %s and (abbr = %s or attribute_value = %s)""", (attribute["attribute"], variant_attr_val,
		variant_attr_val), as_list=1)
	
	return attribute_value[0][0] if len(attribute_value)>0 else cint(variant_attr_val)

def get_item_group(product_type=None):
	if product_type:
		if not frappe.db.get_value("Item Group", product_type, "name"):
			return frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": product_type,
				"parent_item_group": _("All Item Groups"),
				"is_group": "No"
			}).insert().name
		else:
			return product_type
	else:
		return _("All Item Groups")

def get_sku(item):
	if item.get("variants"):
		return item.get("variants")[0].get("sku")
	return ""

def add_to_price_list(item, name):
	item_price_name = frappe.db.get_value("Item Price", {"item_code": name}, "name")
	if not item_price_name:
		frappe.get_doc({
			"doctype": "Item Price",
			"price_list": frappe.get_doc("Shopify Settings", "Shopify Settings").price_list,
			"item_code": name,
			"price_list_rate": item.get("item_price") or item.get("variants")[0].get("price")
		}).insert()
	else:
		item_rate = frappe.get_doc("Item Price", item_price_name)
		item_rate.price_list_rate = item.get("item_price") or item.get("variants")[0].get("price")
		item_rate.save()

def get_item_image(item):
	if item.get("image"):
		return item.get("image").get("src")
	return None

def get_item_details(item):
	name, item_details = None, {}

	item_details = frappe.db.get_value("Item", {"shopify_id": item.get("id")},
		["name", "stock_uom", "item_name"], as_dict=1)

	if item_details:
		name = item_details.name
	else:
		item_details = frappe.db.get_value("Item", {"shopify_variant_id": item.get("id")},
			["name", "stock_uom", "item_name"], as_dict=1)
		if item_details:
			name = item_details.name

	return name, item_details

def update_item(item_details, item_dict):
	update_item = frappe.get_doc("Item", item_details.name)
	item_dict["stock_uom"] = item_details.stock_uom
	item_dict["description"] = item_dict["description"] or update_item.description
	
	del item_dict['item_code']
	del item_dict["variant_of"]

	update_item.update(item_dict)
	update_item.save()

def sync_erp_items(price_list, warehouse):
	for item in frappe.db.sql("""select item_code, item_name, item_group,
		description, has_variants, stock_uom, image, shopify_id, shopify_variant_id, 
		sync_qty_with_shopify, net_weight, weight_uom from tabItem 
		where sync_with_shopify=1 and (variant_of is null or variant_of = '') 
		and (disabled is null or disabled = 0)""", as_dict=1):
		sync_item_with_shopify(item, price_list, warehouse)

def sync_item_with_shopify(item, price_list, warehouse):
	variant_item_code_list = []

	item_data = { "product":
		{
			"title": item.get("item_name"),
			"body_html": item.get("description"),
			"product_type": item.get("item_group"),
			"published_scope": "global",
			"published_status": "published",
			"published_at": datetime.datetime.now().isoformat()
		}
	}

	if item.get("has_variants"):
		variant_list, options, variant_item_code = get_variant_attributes(item, price_list, warehouse)

		item_data["product"]["variants"] = variant_list
		item_data["product"]["options"] = options

		variant_item_code_list.extend(variant_item_code)

	else:
		item_data["product"]["variants"] = [get_price_and_stock_details(item, warehouse, price_list)]

	erp_item = frappe.get_doc("Item", item.get("item_code"))

	# check if the item really exists on shopify
	if item.get("shopify_id"):
		try:
			get_request("/admin/products/{}.json".format(item.get("shopify_id")))
		except requests.exceptions.HTTPError, e:
			if e.args[0] and e.args[0].startswith("404"):
				disable_shopify_sync_for_item(erp_item)
				return
			else:
				disable_shopify_sync_for_item(erp_item)
				raise
			
	if not item.get("shopify_id"):
		new_item = post_request("/admin/products.json", item_data)
		erp_item.shopify_id = new_item['product'].get("id")

		if not item.get("has_variants"):
			erp_item.shopify_variant_id = new_item['product']["variants"][0].get("id")

		erp_item.save()

		update_variant_item(new_item, variant_item_code_list)

	else:
		item_data["product"]["id"] = item.get("shopify_id")
		put_request("/admin/products/{}.json".format(item.get("shopify_id")), item_data)
				
	sync_item_image(erp_item)

def sync_item_image(item):
	image_info = {
        "image": {}
	}

	if item.image:
		img_details = frappe.db.get_value("File", {"file_url": item.image}, ["file_name", "content_hash"])
		if img_details and img_details[0] and img_details[1]:
			is_private = item.image.startswith("/private/files/")
			with open(get_files_path(img_details[0].strip("/"), is_private=is_private), "rb") as image_file:
			    image_info["image"]["attachment"] = base64.b64encode(image_file.read())
			image_info["image"]["filename"] = img_details[0]

		elif item.image.startswith("http") or item.image.startswith("ftp"):
			image_info["image"]["src"] = item.image

		if image_info["image"]:
			try:
				if not exist_item_image(item.shopify_id, image_info):
					try:
						post_request("/admin/products/{0}/images.json".format(item.shopify_id), image_info)
					except requests.exceptions.HTTPError, e:
						if e.args[0] and e.args[0].startswith("422"):
							disable_shopify_sync_for_item(item)
						else:
							disable_shopify_sync_for_item(erp_item)
							raise
						
			except ShopifyError:
				raise ShopifyError
				
def exist_item_image(shopify_id, image_info):
	"""check same image exist or not"""
	
	for image in get_shopify_item_image(shopify_id):
		if image_info.get("image").get("filename"):
			if image.get("src").split("/")[-1:][0].split("?")[0] == image_info.get("image").get("filename"):
				return True
		elif image_info.get("image").get("src"):
			if image.get("src") == image_info.get("image").get("src"):
				return True
		else:
			return False
		
def update_variant_item(new_item, item_code_list):
	for i, item_code in enumerate(item_code_list):
		erp_item = frappe.get_doc("Item", item_code)
		erp_item.shopify_id = new_item['product']["variants"][i].get("id")
		erp_item.shopify_variant_id = new_item['product']["variants"][i].get("id")
		erp_item.save()

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list, variant_item_code = [], [], []
	attr_dict = {}

	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("item_code")},
		fields=['name'])):

		item_variant = frappe.get_doc("Item", variant.get("name"))
		variant_list.append(get_price_and_stock_details(item_variant, warehouse, price_list))

		for attr in item_variant.get('attributes'):
			if not attr_dict.get(attr.attribute):
				attr_dict.setdefault(attr.attribute, [])

			attr_dict[attr.attribute].append(attr.attribute_value)

			if attr.idx <= 3:
				variant_list[i]["option"+cstr(attr.idx)] = attr.attribute_value

		variant_item_code.append(item_variant.item_code)

	for i, attr in enumerate(attr_dict):
		options.append({
            "name": attr,
            "position": i+1,
            "values": list(set(attr_dict[attr]))
        })

	return variant_list, options, variant_item_code

def get_price_and_stock_details(item, warehouse, price_list):
	qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse}, "actual_qty")
	price = frappe.db.get_value("Item Price", \
			{"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate")

	item_price_and_quantity = {
		"price": flt(price)
	}
	
	if item.net_weight:
		if item.weight_uom and item.weight_uom.lower() in ["kg", "g", "oz", "lb"]:
			item_price_and_quantity.update({
				"weight_unit": item.weight_uom.lower(),
				"weight": item.net_weight,
				"grams": get_weight_in_grams(item.net_weight, item.weight_uom)
			})
		
	
	if item.get("sync_qty_with_shopify"):
		item_price_and_quantity.update({
			"inventory_quantity": cint(qty) if qty else 0,
			"inventory_management": "shopify"
		})
		
	if item.shopify_variant_id:
		item_price_and_quantity["id"] = item.shopify_variant_id
	
	return item_price_and_quantity
	
def get_weight_in_grams(weight, weight_uom):
	convert_to_gram = {
		"kg": 1000,
		"lb": 453.592,
		"oz": 28.3495,
		"g": 1
	}
	
	return weight * convert_to_gram[weight_uom.lower()]

def trigger_update_item_stock(doc, method):
	if doc.flags.via_stock_ledger_entry:
		shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
		if shopify_settings.shopify_url and shopify_settings.enable_shopify:
			update_item_stock(doc.item_code, shopify_settings, doc)

def update_item_stock_qty():
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	for item in frappe.get_all("Item", fields=['name', "item_code"], filters={"sync_with_shopify": 1, 
		"disabled": ("!=", 1)}):
		update_item_stock(item.item_code, shopify_settings)

def update_item_stock(item_code, shopify_settings, bin=None):
	item = frappe.get_doc("Item", item_code)
	if item.sync_qty_with_shopify:
		if not bin:
			if frappe.db.get_value("Bin", {"warehouse": shopify_settings.warehouse,
				"item_code": item_code}):
				bin = frappe.get_doc("Bin", {"warehouse": shopify_settings.warehouse,
					"item_code": item_code})
			else:
				bin = None

		if bin:
			if not item.shopify_id and not item.variant_of:
				sync_item_with_shopify(item, shopify_settings.price_list, shopify_settings.warehouse)

			if item.sync_with_shopify and item.shopify_id and shopify_settings.warehouse == bin.warehouse:
				if item.variant_of:
					item_data, resource = get_product_update_dict_and_resource(frappe.get_value("Item",
						item.variant_of, "shopify_id"), item.shopify_variant_id)

				else:
					item_data, resource = get_product_update_dict_and_resource(item.shopify_id, item.shopify_variant_id)

				item_data["product"]["variants"][0].update({
					"inventory_quantity": cint(bin.actual_qty),
					"inventory_management": "shopify"
				})

				put_request(resource, item_data)

def get_product_update_dict_and_resource(shopify_id, shopify_variant_id):
	"""
	JSON required to update product

	item_data =	{
		    "product": {
		        "id": 3649706435 (shopify_id),
		        "variants": [
		            {
		                "id": 10577917379 (shopify_variant_id),
		                "inventory_management": "shopify",
		                "inventory_quantity": 10
		            }
		        ]
		    }
		}
	"""

	item_data = {
		"product": {
			"variants": []
		}
	}

	item_data["product"]["id"] = shopify_id
	item_data["product"]["variants"].append({
		"id": shopify_variant_id
	})

	resource = "admin/products/{}.json".format(shopify_id)

	return item_data, resource
