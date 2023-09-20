function initMap() {
    console.log('initMap().');
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 10,
        center: { lat: 14.703454, lng: -91.191623 },
    });

    const pointsOfInterest = [
        // Add your points of interest here
        { title: 'GG2344748', position: { lat: 14.765853, lng: -91.179493 }, url: 'https://example.com/point1', description: 'Vista Hermosa Water & Sanitation (Draft)' , status: 'draft'},
        { title: 'GG2352598', position: { lat: 14.7652, lng: -91.13217 }, url: 'https://example.com/point2', description: '*Patantic* & Sanika-ya (Approved)' , status: 'approved'},
        { title: 'GG2352598', position: { lat: 14.63454, lng: -91.15257 }, url: 'https://example.com/point2', description: 'Patantic & *Sanika-ya* (Approved)', status: 'approved' },
        { title: 'GG2346063', position: { lat: 14.74219, lng: -91.2044 }, url: 'https://example.com/point2', description: 'Amigos de Santa Cruz (Approved)', status: 'approved' },
        { title: 'GG2091778', position: { lat: 14.7708, lng: -91.26555 }, url: 'https://example.com/point2', description: 'Water & Sanitation in *Santa Lucia Utatlan* and San Andreas (Approved)', status: 'approved' },
        { title: 'GG2091778', position: { lat: 14.74625, lng: -91.13336 }, url: 'https://example.com/point2', description: 'Water & Sanitation in Santa Lucia Utatlan and *San Andreas* (Approved)', status: 'approved' },
        { title: 'GG2125241', position: { lat: 14.72823, lng: -91.07540 }, url: 'https://example.com/point2', description: 'WASH El Potrero (Approved)', status: 'approved' },
        { title: 'GG1873788', position: { lat: 14.63551, lng: -91.14264 }, url: 'https://example.com/point2', description: 'Stoves in San Lucas (Approved)', status: 'approved' },
        { title: 'GG1985748', position: { lat: 14.62098, lng: -91.23814 }, url: 'https://example.com/point2', description: 'Simple School in Tzanchaj (Closed, 2020)', status: 'closed' },
        { title: 'GG1985748', position: { lat: 14.63707, lng: -91.14876 }, url: 'https://example.com/point2', description: 'X-ray Fluoroscopy, Hosp Schafer, San Lucas (Closed, 2018)', status: 'closed' },
        { title: 'GG1870757', position: { lat: 14.7544, lng: -90.98983 }, url: 'https://example.com/point2', description: 'Maternal Health, Tecpan Chimaltenango (Closed, 2015)', status: 'closed' },
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

        marker.addListener('click', function() {
            infoWindow.open(map, marker);
        });
    });
}

window.onload = initMap;

