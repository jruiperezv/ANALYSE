// Load the Visualization API and the areachart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_vid_prob_prog = (function(){
	var CHART_ID = 4;
	
	var ALL_STUDENTS = -1;
   	var PROF_GROUP = -2;
    var PASS_GROUP = -3;
    var FAIL_GROUP = -4;
	
	var PROBLEM_COLOR = "#dc3912";
	var VIDEO_COLOR = "#3366cc";
	var DEFAULT_TITLE = 'Problem-Video Progress';
	var DEFAULT_LEGEND = ['Videos percent', 'Problems grades'];
	var EMPTY_TEXT = 'No data';

	var data = null;
	var options = null;
	var prog_json = null;
	
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){

			// Default data
			prog_json = VID_PROB_PROG_DUMP[getSelectedUser()];
			if (prog_json == null){
				updateChart();
				return;
			}
			var prog_array = [['Date','Video Percent', 'Problems grades'],];
			for(var i = 0; i < prog_json.length; i++){
				prog_array.push([prog_json[i]['time'],prog_json[i]['videos']/100,prog_json[i]['problems']/100]);
			}
			data = google.visualization.arrayToDataTable(prog_array);
			// Format data as xxx%
			var formatter = new google.visualization.NumberFormat({pattern:'#,###%'});
			formatter.format(data,1);
			formatter.format(data,2);
			
			options = {
				colors: [VIDEO_COLOR, PROBLEM_COLOR],
				legend: {position: 'none'},
				isStacked: false,
				vAxis: {format: '#,###%',
						viewWindow: {max: 1.0001,
								 	 min: 0},}
			};
			document.getElementById('vid_prob_prog_legend_title').innerHTML = DEFAULT_TITLE;
	
			// Fill legend
			fillLegend(DEFAULT_LEGEND, [VIDEO_COLOR, PROBLEM_COLOR]);
			
			// Select callbacks
			setSelectCallback();
			
			if (prog_json.length == 0){
				document.getElementById('chart_vid_prob_prog').innerHTML = EMPTY_TEXT;
				return;
			}
		}
		
		var chart = new google.visualization.AreaChart(document.getElementById('chart_vid_prob_prog'));
		chart.draw(data, options);
		
		
		function fillLegend(names, colors){
			var ul = document.getElementById("vid_prob_prog_legend_list");
			// Empty list
			ul.innerHTML = "";
			for(var i = 0; i< names.length; i++){
				var li = document.createElement("li");
				li.innerHTML = "<span style='background:"+colors[i]+";'></span>"+names[i];
				ul.appendChild(li);
			}
		}
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
				VID_PROB_PROG_DUMP = json;
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
		var selectOptions = document.getElementById('vid_prob_prog_options');
		var selectStudent = document.getElementById('vid_prob_prog_student');
		var selectGroup = document.getElementById('vid_prob_prog_group');
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
		var selectOptions = document.getElementById('vid_prob_prog_options');
		var selectStudent = document.getElementById('vid_prob_prog_student');
		var selectGroup = document.getElementById('vid_prob_prog_group');
			
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
		prog_json = null;
		var ul = document.getElementById("vid_prob_prog_legend_list");
		// Empty list
		ul.innerHTML = "";
		LA_vid_prob_prog.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_vid_prob_prog.drawChart);