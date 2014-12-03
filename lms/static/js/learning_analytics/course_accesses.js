// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_course_accesses = (function(){
	var CHART_ID = 3;
	
	var ALL_STUDENTS = -1;
   	var PROF_GROUP = -2;
    var PASS_GROUP = -3;
    var FAIL_GROUP = -4;
    var EXPAND_CHAPT = 0;
    var EXPAND_SEQ = 1;
    var EXPAND_VERT = 2;
    
    var DEFAULT_COLORS = ["#3366cc","#dc3912","#ff9900","#109618","#990099",
					  "#0099c6","#dd4477","#66aa00","#b82e2e","#316395",
					  "#994499","#22aa99","#aaaa11","#6633cc","#e67300",
					  "#8b0707","#651067","#329262","#5574a6","#3b3eac",
					  "#b77322","#16d620","#b91383","#f4359e","#9c5935",
					  "#a9c413","#2a778d","#668d1c","#bea413","#0c5922",
					  "#743411"];
	var DEFAULT_TITLE = 'Chapters accesses';
    
	var ca_json = null;
	var def_names = [];
	var def_data = null;
	var cur_chapt = null;
	var cur_seq = null;
	var cur_names = [];
	var options = null;
	var data = null;
	var expand_level = EXPAND_CHAPT;
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){

			// Default data
			ca_json = ACCESS_DUMP[getSelectedUser()];
			if (ca_json == null){
				updateChart();
				return;
			}
			var access_array = [['Chapter','Accesses', { role: 'style' }],];
			for(var i = 0; i < ca_json.length; i++){
				access_array.push([ca_json[i]['name'],
					ca_json[i]['accesses'], DEFAULT_COLORS[i%DEFAULT_COLORS.length]]);
				def_names.push(ca_json[i]['name']);
			}
			def_data = google.visualization.arrayToDataTable(access_array);
			data = def_data;
			options = {
				colors: DEFAULT_COLORS,
				legend: {position: 'none'},
				vAxis: {baseline: 0,},
			};
			document.getElementById('course_accesses_legend_title').innerHTML = DEFAULT_TITLE;
	
			// Fill legend
			fillLegend(def_names, DEFAULT_COLORS);
			
			// Select callbacks
			setSelectCallback();
		}
				
		var chart = new google.visualization.ColumnChart(document.getElementById('chart_course_accesses'));
		chart.draw(data, options);
		
		// Event handlers
		google.visualization.events.addListener(chart, 'select', selectHandler);
		
		function fillLegend(names, colors){
			var ul = document.getElementById("course_accesses_legend_list");
			// Empty list
			ul.innerHTML = "";
			for(var i = 0; i< names.length; i++){
				var li = document.createElement("li");
				li.innerHTML = "<span style='background:"+colors[i]+";'></span>"+names[i];
				ul.appendChild(li);
			}
		}
		
		function selectHandler() {
			switch (expand_level){
				case EXPAND_CHAPT:
					var selection = chart.getSelection();
					if (selection != null  && selection.length > 0){
						var row = selection[0].row;
						cur_chapt = row;
						expandChapter(row);
						fillLegend(cur_names, DEFAULT_COLORS);
					}
					break;
				case EXPAND_SEQ:
					var selection = chart.getSelection();
					if (selection != null  && selection.length > 0){
						var row = selection[0].row;
						cur_seq = row;
						expandSequential(row);
						fillLegend(cur_names, DEFAULT_COLORS);
					}
					break;
				case EXPAND_VERT:
					expandChapter(cur_chapt);
					fillLegend(cur_names, DEFAULT_COLORS);
					break;
			}	
		}
		
	};

	var expandChapter = function(row){
		var access_array = [['Sequential','Accesses', { role: 'style' }],];
		var total = 0;
		cur_names = [];
		for(var i = 0; i < ca_json[row]['sequentials'].length; i++){
			access_array.push([ca_json[row]['sequentials'][i]['name'],
							   ca_json[row]['sequentials'][i]['accesses'],
							   DEFAULT_COLORS[i%DEFAULT_COLORS.length]]);
			total += ca_json[row]['sequentials'][i]['accesses'];
			cur_names.push(ca_json[row]['sequentials'][i]['name']);
		}
		access_array.push(['Total', total,DEFAULT_COLORS[i%DEFAULT_COLORS.length]]);
		cur_names.push('Total');
		data =  google.visualization.arrayToDataTable(access_array);
		document.getElementById('course_accesses_legend_title').innerHTML = 'Sequential';
		expand_level = EXPAND_SEQ;
		drawChart();
	};
	
	var expandSequential = function(row){
		var num_seqs = ca_json[cur_chapt]['sequentials'].length;
		if (row >= num_seqs){
			data = def_data;
			cur_names = def_names;
			document.getElementById('course_accesses_legend_title').innerHTML = DEFAULT_TITLE;
			expand_level = EXPAND_CHAPT;
			
			drawChart();
		}else{
			var access_array = [['Vertical','Accesses', { role: 'style' }],];
			var total = 0;
			cur_names = [];
			for(var i = 0; i < ca_json[cur_chapt]['sequentials'][row]['verticals'].length; i++){
				access_array.push([ca_json[cur_chapt]['sequentials'][row]['verticals'][i]['name'],
								   ca_json[cur_chapt]['sequentials'][row]['verticals'][i]['accesses'],
								   DEFAULT_COLORS[i%DEFAULT_COLORS.length]]);
				total += ca_json[cur_chapt]['sequentials'][row]['verticals'][i]['accesses'];
				cur_names.push(ca_json[cur_chapt]['sequentials'][row]['verticals'][i]['name']);
			}
			access_array.push(['Total', total, DEFAULT_COLORS[i%DEFAULT_COLORS.length]]);
			cur_names.push('Total');
			data =  google.visualization.arrayToDataTable(access_array);
			
			document.getElementById('course_accesses_legend_title').innerHTML = 'Vertical';
			expand_level = EXPAND_VERT;
			
			drawChart();
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
				ACCESS_DUMP = json;
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
		var selectOptions = document.getElementById('course_accesses_options');
		var selectStudent = document.getElementById('course_accesses_student');
		var selectGroup = document.getElementById('course_accesses_group');
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
		var selectOptions = document.getElementById('course_accesses_options');
		var selectStudent = document.getElementById('course_accesses_student');
		var selectGroup = document.getElementById('course_accesses_group');
			
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
		ca_json = null;
		expand_level = EXPAND_CHAPT;
		var ul = document.getElementById("course_accesses_legend_list");
		// Empty list
		ul.innerHTML = "";
		data = null;
		LA_course_accesses.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_course_accesses.drawChart);