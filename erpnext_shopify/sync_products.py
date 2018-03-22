from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .exceptions import ShopifyError
from .utils import make_shopify_log, disable_shopify_sync_for_item
from erpnext.stock.utils import get_bin
from frappe.utils import cstr, flt, cint, get_files_path
from .shopify_requests import post_request, get_shopify_items, put_request, get_shopify_item_image
import base64, requests, datetime, os

shopify_variants_attr_list = ["option1", "option2", "option3"]

def sync_products(price_list, warehouse):
	shopify_item_list = []
	sync_shopify_items(warehouse, shopify_item_list)
	frappe.local.form_dict.count_dict["products"] = len(shopify_item_list)
	sync_erpnext_items(price_list, warehouse, shopify_item_list)

def sync_shopify_items(warehouse, shopify_item_list):
	for shopify_item in get_shopify_items():
		try:
			make_item(warehouse, shopify_item, shopify_item_list)

		except ShopifyError as e:
			make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
				request_data=shopify_item, exception=True)

		except Exception as e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
					request_data=shopify_item, exception=True)

def make_item(warehouse, shopify_item, shopify_item_list):
	add_item_weight(shopify_item)
	if has_variants(shopify_item):
		attributes = create_attribute(shopify_item)
		create_item(shopify_item, warehouse, 1, attributes, shopify_item_list=shopify_item_list)
		create_item_variants(shopify_item, warehouse, attributes, shopify_variants_attr_list, shopify_item_list=shopify_item_list)

	else:
		shopify_item["variant_id"] = shopify_item['variants'][0]["id"]
		create_item(shopify_item, warehouse, shopify_item_list=shopify_item_list)

def add_item_weight(shopify_item):
	shopify_item["weight"] = shopify_item['variants'][0]["weight"]
	shopify_item["weight_unit"] = shopify_item['variants'][0]["weight_unit"]

def has_variants(shopify_item):
	if len(shopify_item.get("options")) >= 1 and "Default Title" not in shopify_item.get("options")[0]["values"]:
		return True
	return False

def create_attribute(shopify_item):
	attribute = []
	# shopify item dict
	for attr in shopify_item.get('options'):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			frappe.get_doc({
				"doctype": "Item Attribute",
				"attribute_name": attr.get("name"),
				"item_attribute_values": [
					{
						"attribute_value": attr_value,
						"abbr":attr_value
					}
					for attr_value in attr.get("values")
				]
			}).insert()
			attribute.append({"attribute": attr.get("name")})

		else:
			# check for attribute values
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
		if not any((d.abbr.lower() == attr_value.lower() or d.attribute_value.lower() == attr_value.lower())\
		for d in item_attr.item_attribute_values):
			item_attr.append("item_attribute_values", {
				"attribute_value": attr_value,
				"abbr": attr_value
			})

def create_item(shopify_item, warehouse, has_variant=0, attributes=None,variant_of=None, shopify_item_list=[]):
	item_dict = {
		"doctype": "Item",
		"shopify_product_id": shopify_item.get("id"),
		"shopify_variant_id": shopify_item.get("variant_id"),
		"variant_of": variant_of,
		"sync_with_shopify": 1,
		"is_stock_item": 1,
		"item_code": cstr(shopify_item.get("item_code")) or cstr(shopify_item.get("id")),
		"item_name": shopify_item.get("title", '').strip(),
		"description": shopify_item.get("body_html") or shopify_item.get("title"),
		"shopify_description": shopify_item.get("body_html") or shopify_item.get("title"),
		"item_group": get_item_group(shopify_item.get("product_type")),
		"has_variants": has_variant,
		"attributes":attributes or [],
		"stock_uom": shopify_item.get("uom") or _("Nos"),
		"stock_keeping_unit": shopify_item.get("sku") or get_sku(shopify_item),
		"default_warehouse": warehouse,
		"image": get_item_image(shopify_item),
		"weight_uom": shopify_item.get("weight_unit"),
		"weight_per_unit": shopify_item.get("weight"),
		"default_supplier": get_supplier(shopify_item)
	}

	if not is_item_exists(item_dict, attributes, variant_of=variant_of, shopify_item_list=shopify_item_list):
		item_details = get_item_details(shopify_item)

		if not item_details:
			new_item = frappe.get_doc(item_dict)
			new_item.insert()
			name = new_item.name

		else:
			update_item(item_details, item_dict)
			name = item_details.name

		if not has_variant:
			add_to_price_list(shopify_item, name)

		frappe.db.commit()

def create_item_variants(shopify_item, warehouse, attributes, shopify_variants_attr_list, shopify_item_list):
	template_item = frappe.db.get_value("Item", filters={"shopify_product_id": shopify_item.get("id")},
		fieldname=["name", "stock_uom"], as_dict=True)

	if template_item:
		for variant in shopify_item.get("variants"):
			shopify_item_variant = {
				"id" : variant.get("id"),
				"item_code": variant.get("id"),
				"title": variant.get("title"),
				"product_type": shopify_item.get("product_type"),
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
			create_item(shopify_item_variant, warehouse, 0, attributes, template_item.name, shopify_item_list=shopify_item_list)

def get_attribute_value(variant_attr_val, attribute):
	attribute_value = frappe.db.sql("""select attribute_value from `tabItem Attribute Value`
		where parent = %s and (abbr = %s or attribute_value = %s)""", (attribute["attribute"], variant_attr_val,
		variant_attr_val), as_list=1)
	return attribute_value[0][0] if len(attribute_value)>0 else cint(variant_attr_val)

def get_item_group(product_type=None):
	import frappe.utils.nestedset
	parent_item_group = frappe.utils.nestedset.get_root_of("Item Group")

	if product_type:
		if not frappe.db.get_value("Item Group", product_type, "name"):
			item_group = frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": product_type,
				"parent_item_group": parent_item_group,
				"is_group": "No"
			}).insert()
			return item_group.name
		else:
			return product_type
	else:
		return parent_item_group


def get_sku(item):
	if item.get("variants"):
		return item.get("variants")[0].get("sku")
	return ""

def add_to_price_list(item, name):
	shopify_settings = frappe.db.get_value("Shopify Settings", None, ["price_list", "push_prices_to_shopify"], as_dict=1)
	if shopify_settings.push_prices_to_shopify:
		return

	item_price_name = frappe.db.get_value("Item Price",
		{"item_code": name, "price_list": shopify_settings.price_list}, "name")

	if not item_price_name:
		frappe.get_doc({
			"doctype": "Item Price",
			"price_list": shopify_settings.price_list,
			"item_code": name,
			"price_list_rate": item.get("item_price") or item.get("variants")[0].get("price")
		}).insert()
	else:
		item_rate = frappe.get_doc("Item Price", item_price_name)
		item_rate.price_list_rate = item.get("item_price") or item.get("variants")[0].get("price")
		item_rate.save()

def get_item_image(shopify_item):
	if shopify_item.get("image"):
		return shopify_item.get("image").get("src")
	return None

def get_supplier(shopify_item):
	if shopify_item.get("vendor"):
		supplier = frappe.db.sql("""select name from tabSupplier
			where name = %s or shopify_supplier_id = %s """, (shopify_item.get("vendor"),
			shopify_item.get("vendor").lower()), as_list=1)

		if not supplier:
			supplier = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": shopify_item.get("vendor"),
				"shopify_supplier_id": shopify_item.get("vendor").lower(),
				"supplier_type": get_supplier_type()
			}).insert()
			return supplier.name
		else:
			return shopify_item.get("vendor")
	else:
		return ""

def get_supplier_type():
	supplier_type = frappe.db.get_value("Supplier Type", _("Shopify Supplier"))
	if not supplier_type:
		supplier_type = frappe.get_doc({
			"doctype": "Supplier Type",
			"supplier_type": _("Shopify Supplier")
		}).insert()
		return supplier_type.name
	return supplier_type

def get_item_details(shopify_item):
	item_details = {}

	item_details = frappe.db.get_value("Item", {"shopify_product_id": shopify_item.get("id")},
		["name", "stock_uom", "item_name"], as_dict=1)

	if item_details:
		return item_details

	else:
		item_details = frappe.db.get_value("Item", {"shopify_variant_id": shopify_item.get("id")},
			["name", "stock_uom", "item_name"], as_dict=1)
		return item_details

def is_item_exists(shopify_item, attributes=None, variant_of=None, shopify_item_list=[]):
	if variant_of:
		name = variant_of
	else:
		name = frappe.db.get_value("Item", {"item_name": shopify_item.get("item_name")})

	shopify_item_list.append(cstr(shopify_item.get("shopify_product_id")))

	if name:
		item = frappe.get_doc("Item", name)
		item.flags.ignore_mandatory=True

		if not variant_of and not item.shopify_product_id:
			item.shopify_product_id = shopify_item.get("shopify_product_id")
			item.shopify_variant_id = shopify_item.get("shopify_variant_id")
			item.save()
			return True

		if item.shopify_product_id and attributes and attributes[0].get("attribute_value"):
			if not variant_of:
				variant_of = frappe.db.get_value("Item",
					{"shopify_product_id": item.shopify_product_id}, "variant_of")

			# create conditions for all item attributes,
			# as we are putting condition basis on OR it will fetch all items matching either of conditions
			# thus comparing matching conditions with len(attributes)
			# which will give exact matching variant item.

			conditions = ["(iv.attribute='{0}' and iv.attribute_value = '{1}')"\
				.format(attr.get("attribute"), attr.get("attribute_value")) for attr in attributes]

			conditions = "( {0} ) and iv.parent = it.name ) = {1}".format(" or ".join(conditions), len(attributes))

			parent = frappe.db.sql(""" select * from tabItem it where
				( select count(*) from `tabItem Variant Attribute` iv
					where {conditions} and it.variant_of = %s """.format(conditions=conditions) ,
				variant_of, as_list=1)

			if parent:
				variant = frappe.get_doc("Item", parent[0][0])
				variant.flags.ignore_mandatory = True

				variant.shopify_product_id = shopify_item.get("shopify_product_id")
				variant.shopify_variant_id = shopify_item.get("shopify_variant_id")
				variant.save()
			return False

		if item.shopify_product_id and item.shopify_product_id != shopify_item.get("shopify_product_id"):
			return False

		return True

	else:
		return False

def update_item(item_details, item_dict):
	item = frappe.get_doc("Item", item_details.name)
	item_dict["stock_uom"] = item_details.stock_uom

	if item_dict.get("default_warehouse"):
		del item_dict["default_warehouse"]

	del item_dict["description"]
	del item_dict["item_code"]
	del item_dict["variant_of"]
	del item_dict["item_name"]
	del item_dict["image"]

	item.update(item_dict)
	item.flags.ignore_mandatory = True
	item.save()

def sync_erpnext_items(price_list, warehouse, shopify_item_list):
	for item in get_erpnext_items(price_list):
		if item.shopify_product_id not in shopify_item_list:
			try:
				sync_item_with_shopify(item, price_list, warehouse)
				frappe.local.form_dict.count_dict["products"] += 1

			except ShopifyError as e:
				make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
					request_data=item, exception=True)
			except Exception as e:
				make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
					request_data=item, exception=True)

def get_erpnext_items(price_list):
	erpnext_items = []
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")

	last_sync_condition, item_price_condition = "", ""
	if shopify_settings.last_sync_datetime:
		last_sync_condition = "and modified >= '{0}' ".format(shopify_settings.last_sync_datetime)
		item_price_condition = "and ip.modified >= '{0}' ".format(shopify_settings.last_sync_datetime)

	item_from_master = """select name, item_code, item_name, item_group,
		description, shopify_description, has_variants, variant_of, stock_uom, image, shopify_product_id, 
		shopify_variant_id, sync_qty_with_shopify, weight_per_unit, weight_uom, default_supplier from tabItem
		where sync_with_shopify=1 and (variant_of is null or variant_of = '')
		and (disabled is null or disabled = 0)  %s """ % last_sync_condition

	erpnext_items.extend(frappe.db.sql(item_from_master, as_dict=1))

	template_items = [item.name for item in erpnext_items if item.has_variants]

	if len(template_items) > 0:
		item_price_condition += ' and i.variant_of not in (%s)'%(' ,'.join(["'%s'"]*len(template_items)))%tuple(template_items)

	item_from_item_price = """select i.name, i.item_code, i.item_name, i.item_group, i.description,
		i.shopify_description, i.has_variants, i.variant_of, i.stock_uom, i.image, i.shopify_product_id,
		i.shopify_variant_id, i.sync_qty_with_shopify, i.weight_per_unit, i.weight_uom,
		i.default_supplier from `tabItem` i, `tabItem Price` ip
		where price_list = '%s' and i.name = ip.item_code
			and sync_with_shopify=1 and (disabled is null or disabled = 0) %s""" %(price_list, item_price_condition)

	updated_price_item_list = frappe.db.sql(item_from_item_price, as_dict=1)

	# to avoid item duplication
	return [frappe._dict(tupleized) for tupleized in set(tuple(item.items())
		for item in erpnext_items + updated_price_item_list)]

def sync_item_with_shopify(item, price_list, warehouse):
	variant_item_name_list = []

	item_data = { "product":
		{
			"title": item.get("item_name"),
			"body_html": item.get("shopify_description") or item.get("web_long_description") or item.get("description"),
			"product_type": item.get("item_group"),
			"vendor": item.get("default_supplier"),
			"published_scope": "global",
			"published_status": "published",
			"published_at": datetime.datetime.now().isoformat()
		}
	}

	if item.get("has_variants") or item.get("variant_of"):

		if item.get("variant_of"):
			item = frappe.get_doc("Item", item.get("variant_of"))

		variant_list, options, variant_item_name = get_variant_attributes(item, price_list, warehouse)

		item_data["product"]["title"] = item.get("item_name")
		item_data["product"]["body_html"] = item.get("shopify_description") or item.get("web_long_description") or item.get("description")
		item_data["product"]["variants"] = variant_list
		item_data["product"]["options"] = options

		variant_item_name_list.extend(variant_item_name)

	else:
		item_data["product"]["variants"] = [get_price_and_stock_details(item, warehouse, price_list)]

	erp_item = frappe.get_doc("Item", item.get("name"))
	erp_item.flags.ignore_mandatory = True
	
	if not item.get("shopify_product_id"):
		create_new_item_to_shopify(item, item_data, erp_item, variant_item_name_list)
		sync_item_image(erp_item)

	else:
		item_data["product"]["id"] = item.get("shopify_product_id")
		try:
			put_request("/admin/products/{}.json".format(item.get("shopify_product_id")), item_data)

		except requests.exceptions.HTTPError as e:
			if e.args[0] and e.args[0].startswith("404"):
				if frappe.db.get_value("Shopify Settings", "Shopify Settings", "if_not_exists_create_item_to_shopify"):
					item_data["product"]["id"] = ''
					create_new_item_to_shopify(item, item_data, erp_item, variant_item_name_list)
				else:
					disable_shopify_sync_for_item(erp_item)
			else:
				raise e

	frappe.db.commit()

def create_new_item_to_shopify(item, item_data, erp_item, variant_item_name_list):
	new_item = post_request("/admin/products.json", item_data)
	erp_item.shopify_product_id = new_item['product'].get("id")

	if not item.get("has_variants"):
		erp_item.shopify_variant_id = new_item['product']["variants"][0].get("id")

	erp_item.save()
	update_variant_item(new_item, variant_item_name_list)

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

			#to avoid 422 : Unprocessable Entity
			if not image_info["image"]["attachment"] or not image_info["image"]["filename"]:
				return False

		elif item.image.startswith("http") or item.image.startswith("ftp"):
			if validate_image_url(item.image):
				#to avoid 422 : Unprocessable Entity
				image_info["image"]["src"] = item.image

		if image_info["image"]:
			if not item_image_exists(item.shopify_product_id, image_info):
				# to avoid image duplication
				post_request("/admin/products/{0}/images.json".format(item.shopify_product_id), image_info)


def validate_image_url(url):
	""" check on given url image exists or not"""
	res = requests.get(url)
	if res.headers.get("content-type") in ('image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/tiff'):
		return True
	return False

def item_image_exists(shopify_product_id, image_info):
	"""check same image exist or not"""
	for image in get_shopify_item_image(shopify_product_id):
		if image_info.get("image").get("filename"):
			if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("filename"))[0]:
				return True
		elif image_info.get("image").get("src"):
			if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("src"))[0].split("/")[-1]:
				return True
		else:
			return False

def update_variant_item(new_item, item_code_list):
	for i, name in enumerate(item_code_list):
		erp_item = frappe.get_doc("Item", name)
		erp_item.flags.ignore_mandatory = True
		erp_item.shopify_product_id = new_item['product']["variants"][i].get("id")
		erp_item.shopify_variant_id = new_item['product']["variants"][i].get("id")
		erp_item.save()

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list, variant_item_name, attr_sequence = [], [], [], []
	attr_dict = {}

	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("name")},
		fields=['name'])):

		item_variant = frappe.get_doc("Item", variant.get("name"))
		variant_list.append(get_price_and_stock_details(item_variant, warehouse, price_list))

		for attr in item_variant.get('attributes'):
			if attr.attribute not in attr_sequence:
				attr_sequence.append(attr.attribute)

			if not attr_dict.get(attr.attribute):
				attr_dict.setdefault(attr.attribute, [])

			attr_dict[attr.attribute].append(attr.attribute_value)

			if attr.idx <= 3:
				variant_list[i]["option"+cstr(attr.idx)] = attr.attribute_value

		variant_item_name.append(item_variant.name)

	for i, attr in enumerate(attr_sequence):
		options.append({
			"name": attr,
			"position": i+1,
			"values": list(set(attr_dict[attr]))
		})

	return variant_list, options, variant_item_name

def get_price_and_stock_details(item, warehouse, price_list):
	qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse}, "actual_qty")
	price = frappe.db.get_value("Item Price", \
			{"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate")

	item_price_and_quantity = {
		"price": flt(price)
	}

	if item.weight_per_unit:
		if item.weight_uom and item.weight_uom.lower() in ["kg", "g", "oz", "lb"]:
			item_price_and_quantity.update({
				"weight_unit": item.weight_uom.lower(),
				"weight": item.weight_per_unit,
				"grams": get_weight_in_grams(item.weight_per_unit, item.weight_uom)
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
	for item in frappe.get_all("Item", fields=['name', "item_code"],
		filters={"sync_with_shopify": 1, "disabled": ("!=", 1), 'shopify_variant_id': ('!=', '')}):
		try:
			update_item_stock(item.item_code, shopify_settings)
		except ShopifyError as e:
			make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
				request_data=item, exception=True)

		except Exception as e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
					request_data=item, exception=True)

def update_item_stock(item_code, shopify_settings, bin=None):
	item = frappe.get_doc("Item", item_code)
	if item.sync_qty_with_shopify:
		if not bin:
			bin = get_bin(item_code, shopify_settings.warehouse)

		if not item.shopify_product_id and not item.variant_of:
			sync_item_with_shopify(item, shopify_settings.price_list, shopify_settings.warehouse)

		if item.sync_with_shopify and item.shopify_product_id and shopify_settings.warehouse == bin.warehouse:
			if item.variant_of:
				item_data, resource = get_product_update_dict_and_resource(frappe.get_value("Item",
					item.variant_of, "shopify_product_id"), item.shopify_variant_id, is_variant=True,
					actual_qty=bin.actual_qty)
			else:
				item_data, resource = get_product_update_dict_and_resource(item.shopify_product_id,
					item.shopify_variant_id, actual_qty=bin.actual_qty)

			try:
				put_request(resource, item_data)
			except requests.exceptions.HTTPError as e:
				if e.args[0] and e.args[0].startswith("404"):
					make_shopify_log(title=e.message, status="Error", method="sync_shopify_items", message=frappe.get_traceback(),
						request_data=item_data, exception=True)
					disable_shopify_sync_for_item(item)
				else:
					raise e

def get_product_update_dict_and_resource(shopify_product_id, shopify_variant_id, is_variant=False, actual_qty=0):
	"""
	JSON required to update product

	item_data =	{
		"product": {
			"id": 3649706435 (shopify_product_id),
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

	varient_data = {
		"id": shopify_variant_id,
		"inventory_quantity": cint(actual_qty),
		"inventory_management": "shopify"
	}

	if is_variant:
		item_data = {
			"variant": varient_data
		}
		resource = "admin/variants/{}.json".format(shopify_variant_id)
	else:
		item_data["product"]["id"] = shopify_product_id
		item_data["product"]["variants"].append(varient_data)
		resource = "admin/products/{}.json".format(shopify_product_id)

	return item_data, resource
