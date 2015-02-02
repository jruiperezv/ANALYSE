// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_student_grades = (function(){
	var CHART_ID = 8;
	
	var ALL_STUDENTS = -1;
   	var PROF_GROUP = -2;
    var PASS_GROUP = -3;
    var FAIL_GROUP = -4;
	//Colors
	var COLOR_NOT = "#B8B8B8";
	var COLOR_FAIL = "#B20000";
	var COLOR_OK = "#E5C80B";
	var COLOR_PROF = "#4c9900";
	var DEFAULT_TITLE = "Grade categories";

	var data = null;
	var options = null;
	var all_sections = null;
	var wss = null;
	var gs = null;
	var wss_array = null;
	var expanded = false;
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){
			all_sections = STD_GRADES_DUMP[getSelectedUser()];

			if(all_sections == null){
				updateChart();
				return;
			}
			wss = all_sections['weight_subsections'];
			gs = all_sections['graded_sections'];
			
			var wss_array = [['Chapter','Grade', { role: 'style' }],];
			for(var i = 0; i < wss.length; i++){
				var percent = 0;
				var color = null;
				if (wss[i]['score'] != null){
					percent = wss[i]['score']/wss[i]['total'];
					if (percent >= PROF_LIMIT){
						color = COLOR_PROF;
					} else if(percent >= PASS_LIMIT){
						color = COLOR_OK;
					} else{
						color = COLOR_FAIL;
					}
				} else{
					color = COLOR_NOT;
				}
				wss_array.push([wss[i]['category'], percent, color]);
			}
			
			data = wss_array;
			
			document.getElementById('students_grades_legend_title').innerHTML = DEFAULT_TITLE;
			
			// Select callbacks
			setSelectCallback();
		}
		options = {
			legend: {position: 'none'},
			vAxis: {format: '#,###%',
					viewWindow: {max: 1.0001,
								 min: 0},},
		};
			
		var dt = google.visualization.arrayToDataTable(data);
		// Format data as xxx%
		var formatter = new google.visualization.NumberFormat({pattern:'#,###%'});
		formatter.format(dt,1);
		
		var chart = new google.visualization.ColumnChart(document.getElementById('students_grades_chart'));
		chart.draw(dt, options);
		
		// Event handlers
		google.visualization.events.addListener(chart, 'select', selectHandler);
		
		function selectHandler() {
			if (expanded){
				data = wss_array;
				drawChart();
				expanded = false;
				document.getElementById('students_grades_legend_title').innerHTML = DEFAULT_TITLE;
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
			var cat_array = [[category,'Grade',{ role: 'style' }],];
		}else{
			var category = wss[row]['category'];
			var cat_array = [[category,'Grade',{ role: 'style' }],];
		}
		
		for(var i = 0; i < gs.length; i++){
			if (isTotal || gs[i]['category'] == category){
				var percent = 0;
				var color = null;
				if (gs[i]['score'] != null){
					percent = gs[i]['score']/gs[i]['total'];
					if (percent >= PROF_LIMIT){
						color = COLOR_PROF;
					} else if(percent >= PASS_LIMIT){
						color = COLOR_OK;
					} else{
						color = COLOR_FAIL;
					}
				} else{
					color = COLOR_NOT;
				}
				cat_array.push([gs[i]['label'], percent, color]);
			}
		}
		
		data = cat_array;
		document.getElementById('students_grades_legend_title').innerHTML = category;
	};
	
	var updateChart = function(event) {
		var sel_user = getSelectedUser();
		
		$.ajax({
			// the URL for the request
			url: "/courses/learning_analytics/chart_update",
			
			// the data to send (will be converted to a query string)
			data: {
				user_id   : sel_user,
				course_id : COURSE_ID,
				chart : CHART_ID
			},
			
			// whether to convert data to a query string or not
			// for non convertible data should be set to false to avoid errors
			processData: true,
			
			// whether this is a POST or GET request
			type: "GET",
			
			// the type of data we expect back
			dataType : "json",
			
			// code to run if the request succeeds;
			// the response is passed to the function
			success: function( json ) {
				STD_GRADES_DUMP = json;
				change_data();
			},
		
			// code to run if the request fails; the raw request and
			// status codes are passed to the function
			error: function( xhr, status, errorThrown ) {
				// TODO dejar selectores como estaban
				console.log( "Error: " + errorThrown );
				console.log( "Status: " + status );
				console.dir( xhr );
			},
		
			// code to run regardless of success or failure
			complete: function( xhr, status ) {
			}      
		});
	};
	
	var getSelectedUser = function(){
		var selectOptions = document.getElementById('students_grades_options');
		var selectStudent = document.getElementById('students_grades_student');
		var selectGroup = document.getElementById('students_grades_group');
		var selection = selectOptions.options[selectOptions.selectedIndex].value;
			
		switch(selection){
			case "all":
				if(SU_ACCESS){
					selectStudent.style.display="none";
					selectGroup.style.display="none";
				}
				return ALL_STUDENTS;
			case "student":
				if(SU_ACCESS){
					selectStudent.style.display="";
					selectGroup.style.display="none";
				}
				return selectStudent.options[selectStudent.selectedIndex].value;
			case "group":
				if(SU_ACCESS){
					selectStudent.style.display="none";
					selectGroup.style.display="";
				}
				switch(selectGroup.options[selectGroup.selectedIndex].value){
					case "prof":
						return PROF_GROUP;
					case "pass":
						return PASS_GROUP;
					case "fail":
						return FAIL_GROUP;
				}
		}
	};
	
	var setSelectCallback = function(){
		// Set selectors callbacks
		var selectOptions = document.getElementById('students_grades_options');
		var selectStudent = document.getElementById('students_grades_student');
		var selectGroup = document.getElementById('students_grades_group');
			
		selectOptions.onchange = function(){
			var selection = selectOptions.options[selectOptions.selectedIndex].value;
			
			switch(selection){
				case "all":
					selectStudent.style.display="none";
					selectGroup.style.display="none";
					updateChart();
					break;
				case "student":
					selectStudent.style.display="";
					selectGroup.style.display="none";
					updateChart();
					break;
				case "group":
					selectStudent.style.display="none";
					selectGroup.style.display="";
					updateChart();
					break;
			}
			if(!SU_ACCESS){
				selectOptions.style.display="none";
				selectStudent.style.display="none";
				selectGroup.style.display="none";
			}
		};
		
		selectStudent.onchange = function(){
			updateChart();
		};
		
		selectGroup.onchange = function(){
			updateChart();
		};
	};
	
	var change_data = function(){
		data = null;
		options = null;
		all_sections = null;
		wss = null;
		gs = null;
		wss_array = null;
		expanded = false;
		LA_student_grades.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_student_grades.drawChart);