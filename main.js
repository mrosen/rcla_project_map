function initMap() {
    //console.log("Loaded initMap!");
    fetch('RCLA_Projects.csv')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.text();
        })
        .then(csvText => {
            Papa.parse(csvText, {
                header: true,  // Indicates that the first row of the CSV is the header
                skipEmptyLines: true,  // Skips empty lines in the input
                dynamicTyping: true,  // Automatically convert numeric strings to numbers
                complete: function(results) {
                    const pointsOfInterest = results.data;

                    //console.log(results.data);
                    const map = new google.maps.Map(document.getElementById("map"), {
                        zoom: 10,
                        center: { lat: 14.703454, lng: -91.191623 },
                    });

            pointsOfInterest.forEach(point => {
                let infoWindowContent;
                // Handle detailed object descriptions
                console.log("Setting up infoWindow for ", point);

                infoWindowContent = `
                    <div id="content">
                        <h1 id="firstHeading" class="firstHeading">${point.title}</h1>
                        <h2>${point.description}</h2>
                        <p>RI ${point.title} Grant Amount - ${point.description_grantAmount}</p>
                        <p>${point.description_short}</p>
                        <p><strong>International Club:</strong> ${point.internationalClub_name}, District ${point.internationalClub_district}</p>
                        <p><strong>Host Club:</strong> ${point.description_hostClub}</p>
                        <p><a href="${point.url}" target="_blank">Learn More</a></p>
                        </div>
                `;
                        const infoWindow = new google.maps.InfoWindow({
                            content: infoWindowContent
                        });


                        // Choose a different marker color based on the status
                        let markerColor = getMarkerColor(point.status);
                        
                        //console.log("Adding point", point, markerColor);
                        // Construct the position object from the parsed latitude and longitude
                        const position = {
                            lat: point.position_lat,
                            lng: point.position_lng
                        };   
                        marker = new google.maps.Marker({
                            position: position,
                            map: map,
                            title: point.title,
                            icon: `http://maps.google.com/mapfiles/ms/icons/${markerColor}-dot.png`  // Use the chosen color for the marker
                        });

                        marker.addListener('click', function () {
                            infoWindow.open(map, marker);
                        });
                    });
                }
            });
        })            
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error.message);
        });
}
function getMarkerColor(status) {
    switch (status) {
        case 'draft': return 'purple';
        case 'submitted': return 'blue';
        case 'approved': return 'green';
        case 'approved/delinquent': return 'yellow';
        case 'closed': return 'orange';
        default: return 'red';
    }
}
window.onload = initMap;

