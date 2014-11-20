
// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_course_sort_students = (function(){
	//Colors
	var COLOR_NOT = "#B8B8B8";
	var COLOR_FAIL = "#B20000";
	var COLOR_OK = "#008F00";
	var COLOR_PROF = "#297ACC";
	var DEF_TITLE = "Course categories";
	var expanded = false;
	var all_sections = null;
	var wss = null;
	var gs = null;
	var wss_array = null;
	var options = null;
	var chart = null;
	var data = null;
	
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if (data == null){
			// Parse JSON
			all_sections = JSON.parse(SORT_STD_DUMP.replace(/&quot;/ig,'"'));
			wss = all_sections['weight_subsections'];
			gs = all_sections['graded_sections'];
			
			// Make data array
			wss_array = [['Category','Not Done','Fail','Pass','Proficiency'],];
			for(var i = 0; i < wss.length; i++){
				var total = wss[i]['NOT'] + wss[i]['FAIL'] + wss[i]['OK'] + wss[i]['PROFICIENCY'];
				wss_array.push([wss[i]['category'],
					wss[i]['NOT']/total,
					wss[i]['FAIL']/total,
					wss[i]['OK']/total,
					wss[i]['PROFICIENCY']/total]
				);
			}
		
			// Data
			data = wss_array;
			// Options
	    	options = {
				colors: [COLOR_NOT, COLOR_FAIL, COLOR_OK, COLOR_PROF],
				legend: {position: 'none'},
				vAxis: {
					format: '#,###%',
				},
				isStacked: true,
	    	};
	    	
	    	document.getElementById('legend_title').innerHTML = DEF_TITLE;
		}
		// Make DataTable
	    var dt = google.visualization.arrayToDataTable(data);

		// Format data as xxx%
		var formatter = new google.visualization.NumberFormat({pattern:'#,###%'});
		formatter.format(dt,1);
		formatter.format(dt,2);
		formatter.format(dt,3);
		formatter.format(dt,4);	
	
		// Draw chart
	    chart = new google.visualization.ColumnChart(window.document.getElementById('chart_course_sort_students'));
	    chart.draw(dt, options);
	  
	    // Event handlers
		google.visualization.events.addListener(chart, 'select', selectHandler);
		
		function selectHandler() {
			if (expanded){
				data = wss_array;
				drawChart();
				expanded = false;
				document.getElementById('legend_title').innerHTML = DEF_TITLE;
			}else {
				var selection = chart.getSelection();
				if (selection != null  && selection.length > 0){
					var row = selection[0].row;
					if (row != null){
						setRowData(row);
						drawChart();
						expanded = true;
					}
					
				}
			}
			
		}
	};

	var setRowData = function(row){
		var isTotal = row >= (wss.length - 1);
		if (isTotal){
			var category = 'All sections';
		}else{
			var category = wss[row]['category'];
		}
		cat_array = [[category,'Not Done','Fail','Pass','Proficiency'],];
		
		for(var i = 0; i < gs.length; i++){
			if (isTotal || gs[i]['category'] == category){
				var total = gs[i]['NOT'] + gs[i]['FAIL'] + gs[i]['OK'] + gs[i]['PROFICIENCY'];
				cat_array.push([gs[i]['label'],
					gs[i]['NOT']/total,
					gs[i]['FAIL']/total,
					gs[i]['OK']/total,
					gs[i]['PROFICIENCY']/total]
				);
			}
		}
		
		data = cat_array;
		document.getElementById('legend_title').innerHTML = category;
	};
	
	return{
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_course_sort_students.drawChart);