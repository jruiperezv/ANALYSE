<%page args="video_distrib_json"/>

// Load the Visualization API and the chart package. Currently done on the HTML page.
//google.load("visualization", "1", {packages:["corechart"]});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(
  function() {
    drawChart2(${video_distrib_json});
}
);

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawChart2(json_data) {

  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.PieChart(document.getElementById('all_video_time'));
  
  if (json_data != null && json_data.length > 0) {
    
    // Create the data table.
    var data = new google.visualization.arrayToDataTable(json_data);
    
    var formatter = new google.visualization.NumberFormat(
  	      {suffix: ' min', pattern:'#,#', fractionDigits: '1'});
    formatter.format(data, 1);

    // Set chart options
    var options = {
      pieHole: 0.4,
      height: '350',
      chartArea: {width: '100%'}
    };
    
    chart.draw(data, options);
    
  } else {   

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('all_video_time').innerHTML = "";
    document.getElementById('all_video_time').appendChild(noData);
    
  }

}