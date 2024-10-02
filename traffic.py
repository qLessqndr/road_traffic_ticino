import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import xml.etree.ElementTree as ET

API_KEY1 = 'LwAGCFlGMgalWGjLjEINzWRRqwJaEkSH'
API_KEY2 = '9rOohoq8cY5OfzXX6eEWyJ3OKTc4Evwy'
API_KEY3 = 'svPxr72ecAxZZbNeHVBrSUkgzdTeucBH'
API_KEY4 = 'CGP7Hg94SLpGGto15LrxMfUHIFVgL3qb'
API_KEY5 = '5QD1LbzXsN3WePtgSPoOjcNwIEAa7qWb'
API_KEY6 = ''
API_KEY7 = ''
API_KEY8 = ''
API_KEY9 = ''
API_KEY10 = ''

API_KEYS = [API_KEY1, API_KEY2, API_KEY3, API_KEY4, API_KEY5]

def get_traffic_data(coords, key=API_KEY1, index=0):
    api_url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/xml?key={key}&point={coords}"
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
            if(index+1 < len(API_KEYS)):
                return get_traffic_data(coords, API_KEYS[index+1], index+1)
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