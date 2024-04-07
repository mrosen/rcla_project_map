function initMap() {
    fetchProjectsData()
        .then(createMapWithPoints)
        .catch(handleDataError);
}

function fetchProjectsData() {
    return fetch('RCLA_Projects.csv')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.text();
        })
        .then(parseCSVData);
}

function parseCSVData(csvText) {
    return new Promise((resolve, reject) => {
        Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            dynamicTyping: true,
            complete: results => resolve(results.data),
            error: err => reject(err)
        });
    });
}

function createMapWithPoints(pointsOfInterest) {
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 10,
        center: { lat: 14.703454, lng: -91.191623 },
    });

    pointsOfInterest.forEach(point => {
        const infoWindowContent = createInfoWindowContent(point);
        const infoWindow = new google.maps.InfoWindow({ content: infoWindowContent });
        const position = { lat: point.position_lat, lng: point.position_lng };
        const marker = createMarkerForPoint(point, position, map);

        marker.addListener('click', () => infoWindow.open(map, marker));
    });
}

function createInfoWindowContent(point) {
    const urlHTML = point.url ? `<p><a href="${point.url}" target="_blank">Learn More</a></p>` : '';
    const formattedGrantAmount = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(point.grantAmount);
    
    return `
        <div id="content">
            <h1 id="firstHeading" class="firstHeading">${point.title + ' (' + point.id + ', ' + point.status + ': ' + point.period + ')'}</h1>
            <p>${point.description}</p>
            <p><strong>Local Shepard:</strong> ${point.shepard}</p>
            <p><strong>Grant Amount:</strong> ${formattedGrantAmount}</p>
            <p><strong>International Club:</strong> ${point.internationalClub_name} (D ${point.internationalClub_district})</p>
            <p><strong>Key Partner(s):</strong> ${point.partner}</p>
            ${urlHTML}
        </div>
    `;
}

function createMarkerForPoint(point, position, map) {
    return new google.maps.Marker({
        position: position,
        map: map,
        title: point.title + ' (' + point.id + ', ' + point.status + ': ' + point.period + ')',
        icon: `http://maps.google.com/mapfiles/ms/icons/${getMarkerColor(point.status)}-dot.png`
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
