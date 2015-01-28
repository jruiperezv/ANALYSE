<%page args="video_prog_json"/>

// Graph for video percentage as well as total video time seen.

// Load the Visualization API and the chart package. Currently done on the HTML page.
//google.load('visualization', '1.0', {'packages':['corechart']});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(
  function() {
    drawChart1(${video_prog_json});
}
);

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawChart1(json_data) {

  var PROGRESS_NON_OVERLAPPED = "#003366";
  var PROGRESS_OVERLAPPED = "#0080FF";
  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.ColumnChart(document.getElementById('video_prog_chart'));
  
  if (json_data != null && json_data.length > 0) {
    
    // Create the data table.
    var data = new google.visualization.arrayToDataTable(json_data);

    // Set chart options
    var options = {legend: {position: 'bottom'},
    		       colors: [PROGRESS_NON_OVERLAPPED, PROGRESS_OVERLAPPED],
    		       legend: {position: 'none'},
    
    };
    
    chart.draw(data, options);
    
  } else {   

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('video_prog_chart').innerHTML = "";
    document.getElementById('video_prog_chart').appendChild(noData);
    
  }    

}