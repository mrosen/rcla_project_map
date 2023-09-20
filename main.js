function initMap() {
    console.log("Loaded initMap!");
    fetch('pointsOfInterest.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(pointsOfInterest => {
            // Now, `pointsOfInterest` contains the data from your JSON file

            const map = new google.maps.Map(document.getElementById("map"), {
                zoom: 10,
                center: { lat: 14.703454, lng: -91.191623 },
            });

            pointsOfInterest.forEach(point => {
                let infoWindowContent;

                if (typeof point.description === "string") {
                    // Handle simple string descriptions
                    infoWindowContent = `
            <div id="content">
                <h1 id="firstHeading" class="firstHeading">${point.title}</h1>
                <div id="bodyContent">
                    <p>${point.description}. <a href="${point.url}">Learn More</a></p>
                </div>
            </div>
        `;
                } else {
                    // Handle detailed object descriptions
                    infoWindowContent = `
            <div id="content">
                <h1 id="firstHeading" class="firstHeading">${point.title}</h1>
                <h2>${point.description.short}</h2>
                <p>RI ${point.title} Grant Amount - ${point.description.grantAmount}</p>
                <p>${point.description.details}</p>
                <p><strong>International Club:</strong> ${point.description.internationalClub.name}, District ${point.description.internationalClub.district}</p>
                <p><strong>Host Club:</strong> ${point.description.hostClub}</p>
                <p><a href="${point.url}">Learn More</a></p>
            </div>
        `;
                }
                const infoWindow = new google.maps.InfoWindow({
                    content: infoWindowContent
                });


                // Choose a different marker color based on the status
                let markerColor;
                switch (point.status) {
                    case 'draft':
                        markerColor = 'purple';
                        break;
                    case 'submitted':
                        markerColor = 'blue';
                        break;
                    case 'approved':
                        markerColor = 'green';
                        break;
                    case 'approved/delinquent':
                        markerColor = 'yellow';
                        break;
                    case 'closed':
                        markerColor = 'orange';
                        break;
                    default:
                        markerColor = 'red';  // Default color, used if the status doesn't match any of the above
                }
                console.log(point.status, markerColor);

                const marker = new google.maps.Marker({
                    position: point.position,
                    map: map,
                    title: point.title,
                    icon: `http://maps.google.com/mapfiles/ms/icons/${markerColor}-dot.png`  // Use the chosen color for the marker
                });

                marker.addListener('click', function () {
                    infoWindow.open(map, marker);
                });
            });
        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error.message);
        });
}

window.onload = initMap;

