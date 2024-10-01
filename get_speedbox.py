import requests
import json

def calculate_bounding_box(lat, lon, size_km):
    earth_radius_km = 6371
    delta_lat = 0.01 * size_km
    delta_lon = 0.01 * size_km

    lat_min = lat - delta_lat
    lat_max = lat + delta_lat
    lon_min = lon - delta_lon
    lon_max = lon + delta_lon
    return lat_min, lon_min, lat_max, lon_max

def fetch_speed_limits(lat_min, lon_min, lat_max, lon_max):
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
        way["highway"]["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|track|path|footway|cycleway|pedestrian"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out body;
    """
    
    response = requests.get(overpass_url, params={'data': overpass_query})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def fetch_node_coordinates(node_ids):
    """Fetch coordinates for the given node IDs."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    node_query = f"""
    [out:json];
    (
      node(id:{','.join(map(str, node_ids))});
    );
    out body;
    """
    
    response = requests.post(overpass_url, data=node_query)
    if response.status_code == 200:
        data = response.json()
        coordinates = {}
        
        for element in data['elements']:
            if element['type'] == 'node':
                coordinates[element['id']] = (element['lon'], element['lat'])
        
        return coordinates
    else:
        print(f"Error fetching node coordinates ({node_ids}): {response.status_code} - {response.text}")
        return {}

def convert_node_to_coords(way, node_coordinates):
    """Convert nodes in a way to coordinates."""
    coordinates = []
    for node_id in way['nodes']:
        if node_id in node_coordinates:
            coordinates.append(node_coordinates[node_id])
    return coordinates

def get_speed_limits(lat, lon, size):
    lamin, lomin, lamax, lomax = calculate_bounding_box(lat, lon, size)
    ways = fetch_speed_limits(lamin, lomin, lamax, lomax)

    if ways:
        feature_collection = {
            "type": "FeatureCollection",
            "features": []
        }
        
        node_ids = []
        for way in ways['elements']:
            if way['type'] == 'way':
                node_ids.extend(way['nodes'])
        
        if len(node_ids) != 0:
            node_coordinates = fetch_node_coordinates(set(node_ids))

        for way in ways['elements']:
            wayType = way['tags']['highway']
            if way['type'] == 'way' and (wayType == "primary" or wayType == "trunk" or wayType == "motorway" or wayType == "secondary"):
                coordinates = convert_node_to_coords(way, node_coordinates)
                feature = {
                    "type": "Feature",
                    "id": f"way/{way['id']}",
                    "properties": {
                        "@id": f"way/{way['id']}",
                        **way['tags'],
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates
                    }
                }
                feature_collection["features"].append(feature)
        
        return feature_collection
    return None


def get_speed_limit_at_point(lon, lat):
    """Fetch speed limit for a specific point given by latitude and longitude."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
        way["highway"]["maxspeed"]({lat - 0.00001},{lon - 0.00001},{lat + 0.00001},{lon + 0.00001});
    );
    out body;
    """
    
    response = requests.get(overpass_url, params={'data': overpass_query})
    if response.status_code == 200:
        data = response.json()
        print(data, lon, lat)
        if 'elements' in data and len(data['elements']) > 0:
            way = data['elements'][0]
            maxspeed = way['tags'].get('maxspeed', None)
            return int(maxspeed) if maxspeed and maxspeed.isdigit() else None
        else:
            print("No speed limit found at this point.")
            return None
    else:
        print(f"Error fetching speed limit at point: {response.status_code} - {response.text}")
        return None


'''import requests

def calculate_bounding_box(lat, lon, size_km):
    earth_radius_km = 6371
    delta_lat = size_km / earth_radius_km * (180 / 3.141592653589793)
    delta_lon = size_km / (earth_radius_km * (3.141592653589793 / 180) * abs(lat))

    lat_min = lat - delta_lat
    lat_max = lat + delta_lat
    lon_min = lon - delta_lon
    lon_max = lon + delta_lon
    return lat_min, lon_min, lat_max, lon_max


def fetch_speed_limits(lat_min, lon_min, lat_max, lon_max):
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
    way["highway"]["maxspeed"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out body;
    """

    response = requests.get(overpass_url, params={'data': overpass_query})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def convert_node_to_coords(node):
    ...

    
def get_speed_limits(lat, lon, size):
    lamin, lomin, lamax, lomax = calculate_bounding_box(lat, lon, size)
    return fetch_speed_limits(lamin, lomin, lamax, lomax)'''