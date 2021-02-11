// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.require("assets/erpnext/js/financial_statements.js", function() {
	frappe.query_reports["Balance Sheet"] = $.extend({}, erpnext.financial_statements);

	frappe.query_reports["Balance Sheet"]["filters"].push({
		"fieldname": "accumulated_values",
		"label": __("Accumulated Values"),
		"fieldtype": "Check",
		"default": 1
	});

	frappe.query_reports["Balance Sheet"]["filters"].push({
		"fieldname": "include_default_book_entries",
		"label": __("Include Default Book Entries"),
		"fieldtype": "Check",
		"default": 1
	});

	frappe.query_reports["Balance Sheet"]["onload"] = function(report) {
		function hideChart() {
			if($('.chart-container').length == 0) {
				setTimeout(hideChart, 500)
				return
			}
			$('.chart-container').hide()
			
		}
		setTimeout(hideChart, 500)
		report.page.add_inner_button("Toggle Chart", function () {
			$('.chart-container').toggle()
		})
	}
});
