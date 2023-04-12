import frappe
import json
import os


def get_tiles(module_name, default):
    config = None
    config_file = os.path.join(frappe.get_app_path('goprime'), 'config', 'optional_features.json')
    if not os.path.exists(config_file):
        return default

    with open(config_file, 'r') as f:
        config = json.load(f)
    if not config.get('JMann_new_modules'):
        return default

    try:
        frappe.get_list('Module Tile')
    except Exception:
        return default
    tiles = frappe.get_list("Module Tile",
                            ignore_permissions=True,
                            filters={'module': module_name},
                            order_by="tile_index asc")
    if tiles:
        return [frappe.get_doc("Module Tile", tile['name']).as_module_dict() for tile in tiles]

    return default
