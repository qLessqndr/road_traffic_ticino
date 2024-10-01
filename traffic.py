import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import xml.etree.ElementTree as ET

#API_KEY = 'LwAGCFlGMgalWGjLjEINzWRRqwJaEkSH'
API_KEY = '9rOohoq8cY5OfzXX6eEWyJ3OKTc4Evwy'
#API_KEY = 'svPxr72ecAxZZbNeHVBrSUkgzdTeucBH'

def get_traffic_data(coords):
    api_url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/xml?key={API_KEY}&point={coords}"
    try:
        response = requests.get(api_url, timeout=0.5)

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type')
            if 'application/json' in content_type:
                return response.json()
            elif 'application/xml' in content_type or 'text/xml' in content_type:
                return parse_xml(response.text)
            else:
                print(f"Unsupported content type: {content_type}")
                return None
        else:
            print(f"Error: {response.status_code}")
            print(f"Response Text: {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def parse_xml(xml_data):
    root = ET.fromstring(xml_data)
    current_speed = root.find('currentSpeed').text
    free_flow_speed = root.find('freeFlowSpeed').text
    current_travel_time = root.find('currentTravelTime').text
    free_flow_travel_time = root.find('freeFlowTravelTime').text
    confidence = root.find('confidence').text
    road_closure = root.find('roadClosure').text

    return {
        "current_speed": current_speed,
        "free_flow_speed": free_flow_speed,
        "current_travel_time": current_travel_time,
        "free_flow_travel_time": free_flow_travel_time,
        "confidence": confidence,
        "road_closure": road_closure
    }


def get_data(point):
    lat = point[0]
    lon = point[1]
    return get_traffic_data(f"{lat},{lon}")