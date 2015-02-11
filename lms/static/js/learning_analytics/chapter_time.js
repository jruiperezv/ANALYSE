// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_chapter_time = (function(){
	var CHART_ID = 9;
	
	var ALL_STUDENTS = -1;
   	var PROF_GROUP = -2;
    var PASS_GROUP = -3;
    var FAIL_GROUP = -4;
	var EXPANDED_NAMES = ['Graded time', 'Ungraded time', 'Chapter time'];
	var EXPANDED_COLORS = ["#297ACC","#008F00","#B20000"];
	var DEFAULT_COLORS = ["#3366cc","#dc3912","#ff9900","#109618","#990099",
					  "#0099c6","#dd4477","#66aa00","#b82e2e","#316395",
					  "#994499","#22aa99","#aaaa11","#6633cc","#e67300",
					  "#8b0707","#651067","#329262","#5574a6","#3b3eac",
					  "#b77322","#16d620","#b91383","#f4359e","#9c5935",
					  "#a9c413","#2a778d","#668d1c","#bea413","#0c5922",
					  "#743411"];
	var UNSELECT_COLOR = "#B8B8B8";
	var DEFAULT_TITLE = 'Chapters spent time';
	var EMPTY_TEXT = 'No data';

	var data = null;
	var options = null;
	var def_data = null;
	var def_names = [];
	var time_json = null;
	var expanded = false;
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){

			// Default data
			time_json = TIME_DUMP[getSelectedUser()];
			if (time_json == null){
				updateChart();
				return;
			}
			var time_array = [['Chapter','Time spent'],];
			var empty = true;
			for(var i = 0; i < time_json.length; i++){
				time_array.push([time_json[i]['name'],
					time_json[i]['total_time']]);
				def_names.push(time_json[i]['name']);
				if(time_json[i]['total_time'] > 0){
					empty = false;
				}
			}
			def_data = google.visualization.arrayToDataTable(time_array);
			data = def_data;
			options = {
				colors: DEFAULT_COLORS,
				legend: {position: 'none'},
				chartArea: { height: '75%',
					         width: '75%',},
				
			};
			document.getElementById('chapter_time_legend_title').innerHTML = DEFAULT_TITLE;
	
			// Fill legend
			fillLegend(def_names, DEFAULT_COLORS);
			
			// Select callbacks
			setSelectCallback();
			
			if (empty){
				document.getElementById('chart_chapter_time').innerHTML = EMPTY_TEXT;
				return;
			}
		}
		
		var chart = new google.visualization.PieChart(document.getElementById('chart_chapter_time'));
		
	    var formatter = new google.visualization.NumberFormat(
	    	      {suffix: ' min', pattern:'#,#', fractionDigits: '2'});
	    formatter.format(data, 1);
		chart.draw(data, options);
		
		// Event handlers
		google.visualization.events.addListener(chart, 'select', selectHandler);
		
		function fillLegend(names, colors){
			var ul = document.getElementById("chapter_time_legend_list");
			// Empty list
			ul.innerHTML = "";
			for(var i = 0; i< names.length; i++){
				var li = document.createElement("li");
				li.innerHTML = "<span style='background:"+colors[i]+";'></span>"+names[i];
				ul.appendChild(li);
			}
		}
		
		function selectHandler() {
			if (expanded){
				data = def_data;
				options = {
					colors: DEFAULT_COLORS,
					legend: {position: 'none'},
					chartArea: { height: '75%',
					             width: '75%',},
				};
				document.getElementById('chapter_time_legend_title').innerHTML = DEFAULT_TITLE;
				drawChart();
				fillLegend(def_names, DEFAULT_COLORS);
				expanded = false;
			}else {
				var selection = chart.getSelection();
				if (selection != null  && selection.length > 0){
					var row = selection[0].row;
					expandTime(row);
					fillLegend(EXPANDED_NAMES, EXPANDED_COLORS);
					expanded = true;
				}
			}
			
		}
	};

	var expandTime = function(row){
	
	    selectData = def_data.clone();
	    selectData.removeRow(row);
	    var graded = time_json[row]['graded_time'];
	    var ungraded = time_json[row]['ungraded_time'];
	    var chapt = time_json[row]['total_time'] - graded - ungraded;
	    selectData.insertRows(row,[['Graded time',graded],
	    						  ['Ungraded time', ungraded],
	    						  ['Chapter time', chapt]]);
	    
	    var selColors = DEFAULT_COLORS.slice(0);
	    for (var i = 0; i < selColors.length; i++){
	    	if (i < row || i > row + 2){
	    		selColors[i] = UNSELECT_COLOR;
	    	}else{
	    		selColors[i] = EXPANDED_COLORS[i-row];
	    	}
	    }
	 	
	 	data = selectData;
	 	options={
	 		colors: selColors,
			legend: {position: 'none'},
			chartArea: { height: '75%',
					     width: '75%',},
		};
		document.getElementById('chapter_time_legend_title').innerHTML = def_data.getFormattedValue(row,0);
		options.slices = [];
	    options.slices[row] = { offset: 0.1 };
	    options.slices[row+1] = { offset: 0.1 };
	    options.slices[row+2] = { offset: 0.1 };
		
		drawChart();
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
				TIME_DUMP = json;
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
		var selectOptions = document.getElementById('chapter_time_options');
		var selectStudent = document.getElementById('chapter_time_student');
		var selectGroup = document.getElementById('chapter_time_group');
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
		var selectOptions = document.getElementById('chapter_time_options');
		var selectStudent = document.getElementById('chapter_time_student');
		var selectGroup = document.getElementById('chapter_time_group');
			
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
		def_data = null;
		def_names = [];
		time_json = null;
		expanded = false;
		var ul = document.getElementById("chapter_time_legend_list");
		// Empty list
		ul.innerHTML = "";
		data = null;
		LA_chapter_time.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_chapter_time.drawChart);