function initMap() {
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 2,
        center: { lat: 46.619261, lng: -33.134766 },
    });

    const statueOfLibertyContent = '<div id="content">'+
        '<h1 id="firstHeading" class="firstHeading">Statue of Liberty</h1>'+
        '<div id="bodyContent">'+
        '<p>Click <a href="https://www.nps.gov/stli/index.htm">here</a> for more info.</p>'+
        '</div>'+
        '</div>';

    const eiffelTowerContent = '<div id="content">'+
        '<h1 id="firstHeading" class="firstHeading">Eiffel Tower</h1>'+
        '<div id="bodyContent">'+
        '<p>Click <a href="https://www.toureiffel.paris/en">here</a> for more info.</p>'+
        '</div>'+
        '</div>';

    const statueOfLibertyInfoWindow = new google.maps.InfoWindow({
        content: statueOfLibertyContent
    });

    const eiffelTowerInfoWindow = new google.maps.InfoWindow({
        content: eiffelTowerContent
    });

    const statueOfLibertyMarker = new google.maps.Marker({
        position: { lat: 40.6892, lng: -74.0445 },
        map: map,
        title: 'Statue of Liberty'
    });

    const eiffelTowerMarker = new google.maps.Marker({
        position: { lat: 48.8584, lng: 2.2945 },
        map: map,
        title: 'Eiffel Tower'
    });

    statueOfLibertyMarker.addListener('click', function() {
        statueOfLibertyInfoWindow.open(map, statueOfLibertyMarker);
    });

    eiffelTowerMarker.addListener('click', function() {
        eiffelTowerInfoWindow.open(map, eiffelTowerMarker);
    });
}

window.onload = initMap;

