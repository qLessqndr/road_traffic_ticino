import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import xml.etree.ElementTree as ET

API_KEYS = [
    'UVsn6VzZWgF7g6WyJsHIK0PB7AxIViMR',
    '9rOohoq8cY5OfzXX6eEWyJ3OKTc4Evwy',
    'svPxr72ecAxZZbNeHVBrSUkgzdTeucBH',
    'CGP7Hg94SLpGGto15LrxMfUHIFVgL3qb',
    '5QD1LbzXsN3WePtgSPoOjcNwIEAa7qWb',
    'LwAGCFlGMgalWGjLjEINzWRRqwJaEkSH',
    'GE4eKKsC6jYwVoOUeEwzlIz0F3TPwR6G',
    'EazXTUVqwB0B1eMGLQGhLyaibbQEDSqA',
    'QTnBvR9MfVp1mHPxAUt6UAtV2x7FlmM1',
    'aU3PsvoqBrTaGbsEpElPfOGlqBQkKATn',
    'x3BpUkaSkTYodhypDqGCGsbTfoomq8UO',
    'sTyD4IYjQKDrnrLHkn8aU1J94AeAXQIH',
    'zdWSqW9cjjWGtJl123A7XchUpKzNbXzA',
    'RvipU5Qh8Krk3sBwxj0yUSf4z6yRabPt',
    'DrVVLSAzOum8Y0ZOBP7u3SIB0BdGeKbu',
    'gwwe1M1huk6lBwGRAXTosLaed9BiMZ8E',
    'xfXAt5ECrGNCecMjF9H70epAQVGvOJ9s',
    'mz9PilygMZkR426FmtmzmebTmjkr2m28',
    'Z3CbTUWGiSyMGc8etFoF8Q6VxFJsAPNa',
    'gSCGsC6JXQNTOWBf8K6nPNHvaiytB1Xs',
    'ga0nsqAYkh9x32EG9ZZALrdzh24am8dY'
]

def get_traffic_data(coords):
    for key in API_KEYS:
            try:
                api_url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/xml?key={key}&point={coords}"
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
                    print(f"Error with API key {key}: {response.status_code}")
                    print(f"Response Text: {response.text}")

            except requests.exceptions.RequestException as e:
                print(f"An error occurred with API key {key}: {e}")
        
    print("All API keys failed to retrieve data.")
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