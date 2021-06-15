import frappe


def get_tiles(module_name, default):
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
