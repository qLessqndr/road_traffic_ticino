import requests
import plotly.graph_objects as go
import geopandas as gpd
from shapely.geometry import Point, LineString
import pandas as pd
from geopy.distance import geodesic
import traffic

get_traffic = traffic.get_data

API_KEY = 'LwAGCFlGMgalWGjLjEINzWRRqwJaEkSH'
#API_KEY = '9rOohoq8cY5OfzXX6eEWyJ3OKTc4Evwy'
#API_KEY = 'svPxr72ecAxZZbNeHVBrSUkgzdTeucBH'

OSM_URL = "http://overpass-api.de/api/interpreter"

DEFAULT_SPEED_LIMIT = 50  # Default speed limit (Europe)

def get_osm_speed_limit(lat, lon):
    """Query OSM for speed limits around a given latitude and longitude."""
    overpass_query = f"""
    <osm-script output="json">
      <query type="way">
        <around lat="{lat}" lon="{lon}" radius="10"/>
        <has-kv k="maxspeed"/>
      </query>
      <print/>
    </osm-script>
    """
    try:
        response = requests.post(OSM_URL, data={'data': overpass_query}, timeout=1)
        if response.status_code == 200:
            data = response.json()
            for element in data['elements']:
                if 'tags' in element and 'maxspeed' in element['tags']:
                    try:
                        return int(element['tags']['maxspeed'])
                    except ValueError:
                        return None  # If maxspeed is not an integer
        return None
    except requests.exceptions.Timeout:
        print(f"OSM request timed out for point ({lat}, {lon})")
        return None
    except Exception as e:
        print(f"Error fetching OSM data: {e}")
        return None

def calculate_route(origin, destination):
    """Fetch the route from TomTom API."""
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin}:{destination}/json?key={API_KEY}&traffic=true"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")

def plot_route_with_traffic(route_data, interval=800):
    """Plot the route with traffic data, dynamically fetching speed limits from OSM."""
    route_geometry = route_data['routes'][0]['legs'][0]['points']
    latitudes = [point['latitude'] for point in route_geometry]
    longitudes = [point['longitude'] for point in route_geometry]
    segments = []
    traffic_speeds = []
    speeds = []
    colors = []
    total_distance = 0
    last_request_location = None
    last_traffic_data = None

    for i in range(len(latitudes) - 1):
        color = 'grey'
        start_point = Point(longitudes[i], latitudes[i])
        end_point = Point(longitudes[i + 1], latitudes[i + 1])
        line_segment = LineString([start_point, end_point])

        # Calculate distance between current point and the last traffic request point
        current_distance = geodesic((latitudes[i], longitudes[i]), (latitudes[i + 1], longitudes[i + 1])).meters
        total_distance += current_distance

        if last_request_location is None or total_distance >= interval:
            midpoint = line_segment.interpolate(0.5, normalized=True)

            # Fetch traffic data at the midpoint
            traffic_data = get_traffic((midpoint.y, midpoint.x))

            # Fetch speed limit from OSM at the midpoint, default to 50 if none found
            speed_limit = get_osm_speed_limit(midpoint.y, midpoint.x)
            if speed_limit is None:
                speed_limit = DEFAULT_SPEED_LIMIT  # Default if no speed limit is found

            if traffic_data is not None:
                traffic_speed = int(traffic_data['current_speed'])
                if traffic_speed >= speed_limit:
                    color = 'green'
                elif traffic_speed >= 0.75 * speed_limit:
                    color = 'yellow'
                elif traffic_speed >= 0.5 * speed_limit:
                    color = 'orange'
                else:
                    color = 'red'
                last_request_location = midpoint
                total_distance = 0

                speeds.append(speed_limit)
                traffic_speeds.append(traffic_speed)
                colors.append(color)
                segments.append(line_segment)
            else:
                print(f"No traffic data for segment at {midpoint}")
                # Use default speed limit and grey color when no traffic data is found
                speeds.append(speed_limit)
                traffic_speeds.append(DEFAULT_SPEED_LIMIT)
                colors.append('grey')
                segments.append(line_segment)
        else:
            # Use the last fetched traffic data if still within the interval
            traffic_speed = int(last_traffic_data['current_speed']) if last_traffic_data else DEFAULT_SPEED_LIMIT
            speed_limit = get_osm_speed_limit(line_segment.centroid.y, line_segment.centroid.x)
            if speed_limit is None:
                speed_limit = DEFAULT_SPEED_LIMIT  # Default if no speed limit is found

            if traffic_speed >= speed_limit:
                color = 'green'
            elif traffic_speed >= 0.75 * speed_limit:
                color = 'yellow'
            elif traffic_speed >= 0.5 * speed_limit:
                color = 'orange'
            else:
                color = 'red'

            speeds.append(speed_limit)
            traffic_speeds.append(traffic_speed)
            colors.append(color)
            segments.append(line_segment)

    fig = go.Figure()

    for i, segment in enumerate(segments):
        x, y = segment.xy
        current_speed = traffic_speeds[i]
        speed_limit = speeds[i]
        t = f'Traffic Speed: {float(current_speed):.2f} km/h<br>Speed Limit: {speed_limit} km/h'

        fig.add_trace(go.Scattermapbox(
            mode='lines',
            lon=x.tolist(),
            lat=y.tolist(),
            line=dict(width=4, color=colors[i]),
            hoverinfo='text',
            text=t
        ))

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center=dict(lon=(longitudes[0] + longitudes[-1]) / 2, lat=(latitudes[0] + latitudes[-1]) / 2),
            zoom=13
        ),
        title='Calculated Route Colored by Traffic Conditions',
    )

    fig.show()