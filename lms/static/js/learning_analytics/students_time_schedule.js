// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_student_time_schedule = (function(){
	
	var CHART_ID = 11;
	var ALL_STUDENTS = -1;
	//Colors
	var DEFAULT_TITLE = "Time Schedule";

	var data = null;
	var options = null;
	var time_schedule = null;
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){
			time_schedule = STD_SCHEDULE_DUMP[getSelectedUser()];
			if(time_schedule == null){
				updateChart();
				return;
			}
			
			morningTime = time_schedule['morningTime']
			afternoonTime = time_schedule['afternoonTime']
			nightTime = time_schedule['nightTime']
			
			var schedule_array = [['Time Interval', 'Minutes'],
			                      ['Morning Time', morningTime],
								  ['Afternoon Time', afternoonTime],
								  ['Night Time', nightTime]]
			
			data = schedule_array;
			
			document.getElementById('students_schedule_legend_title').innerHTML = DEFAULT_TITLE;
			
			// Select callbacks
			setSelectCallback();
		}
		options = {
			legend: {position: 'none'},
			vAxis: {viewWindow: {max: 1.0001,
								 min: 0},},
			chartArea: { height: '75%',
						width: '75%',},
			colors: ['#C9C96C', '#7F7160', '50587C'],
		};
			
		var dt = google.visualization.arrayToDataTable(data);

	    var formatter = new google.visualization.NumberFormat(
	    	      {suffix: ' min', pattern:'#,#', fractionDigits: '1'});
	    formatter.format(dt, 1);
		var chart = new google.visualization.PieChart(document.getElementById('students_time_schedule_chart'));
		chart.draw(dt, options);
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
				STD_SCHEDULE_DUMP = json;
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
		var selectOptions = document.getElementById('students_schedule_options');
		var selectStudent = document.getElementById('students_schedule_student');
		var selection = selectOptions.options[selectOptions.selectedIndex].value;
			
		switch(selection){
			case "all":
				if(SU_ACCESS){
					selectStudent.style.display="none";
				}
				return ALL_STUDENTS;
			case "student":
				if(SU_ACCESS){
					selectStudent.style.display="";
				}
				return selectStudent.options[selectStudent.selectedIndex].value;
		}
		
		return USER_ID;
	};
	
	var setSelectCallback = function(){
		// Set selectors callbacks
		var selectOptions = document.getElementById('students_schedule_options');
		var selectStudent = document.getElementById('students_schedule_student');
			
		selectOptions.onchange = function(){
			var selection = selectOptions.options[selectOptions.selectedIndex].value;
			
			switch(selection){
				case "all":
					selectStudent.style.display="none";
					updateChart();
					break;
				case "student":
					selectStudent.style.display="";
					updateChart();
					break;
			}
			if(!SU_ACCESS){
				selectOptions.style.display="none";
				selectStudent.style.display="none";
			}
		};
		
		selectStudent.onchange = function(){
			updateChart();
		};
		
	};
	
	var change_data = function(){
		data = null;
		options = null;
		time_schedule = null;
		LA_student_time_schedule.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_student_time_schedule.drawChart);