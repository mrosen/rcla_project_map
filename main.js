function initMap() {
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 2,
        center: { lat: 46.619261, lng: -33.134766 },
    });

    const pointsOfInterest = [
        // Add your points of interest here
        { title: 'Point 1', position: { lat: 40.1, lng: -74.1 }, url: 'https://example.com/point1', description: 'Description 1' },
        { title: 'Point 2', position: { lat: 40.2, lng: -74.2 }, url: 'https://example.com/point2', description: 'Description 2' },
        // ...
        // Repeat for 10 points
    ];

    pointsOfInterest.forEach(point => {
        const infoWindowContent = `
            <div id="content">
                <h1 id="firstHeading" class="firstHeading">${point.title}</h1>
                <div id="bodyContent">
                    <p>${point.description}. Click <a href="${point.url}">here</a> for more info.</p>
                </div>
            </div>
        `;

        const infoWindow = new google.maps.InfoWindow({
            content: infoWindowContent
        });

        const marker = new google.maps.Marker({
            position: point.position,
            map: map,
            title: point.title
        });

        marker.addListener('click', function() {
            infoWindow.open(map, marker);
        });
    });
}

window.onload = initMap;

