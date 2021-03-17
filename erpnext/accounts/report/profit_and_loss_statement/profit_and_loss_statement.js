// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


frappe.require("assets/erpnext/js/financial_statements.js", function() {
	frappe.query_reports["Profit and Loss Statement"] = $.extend({},
		erpnext.financial_statements);

	frappe.query_reports["Profit and Loss Statement"]["filters"].push(
		// {
		// 	"fieldname": "project",
		// 	"label": __("Project"),
		// 	"fieldtype": "MultiSelectList",
		// 	get_data: function(txt) {
		// 		return frappe.db.get_link_options('Project', txt);
		// 	}
		// },
		{
			"fieldname": "accumulated_values",
			"label": __("Accumulated Values"),
			"fieldtype": "Check"
		},
		{
			"fieldname": "include_default_book_entries",
			"label": __("Include Default Book Entries"),
			"fieldtype": "Check",
			"default": 1
		}
	);

	frappe.query_reports["Profit and Loss Statement"]["onload"] = function(report) {
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
