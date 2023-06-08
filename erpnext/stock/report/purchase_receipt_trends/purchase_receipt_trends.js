// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.require("assets/erpnext/js/purchase_trends_filters.js", function() {
	frappe.query_reports["Purchase Receipt Trends"] = {
		filters: erpnext.get_purchase_trends_filters(),
		"formatter": function(value, row, column, data, default_formatter) {
			if (row){
				if((value == undefined && column.colIndex != row.length -1) || row[0].rowIndex == 2) {
					return "<i></i>"
				}
				if(column.colIndex == 3){
					return `<a target="_blank" href="/desk#Form/Supplier/${data.supplier_id}"><b>${value}</b></a>`;
				}
				if(value){
					return `<div style="text-align: center">${value}</div>`;
				}
			}else{
				if(value){
					return `<div style="text-align: center">${value}</div>`;
				} else{
					return "<i></i>"
				}
			}
		},
	}
});

