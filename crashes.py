import traffic
import requests

API_KEYS = traffic.API_KEYS
BOUNDS = "8.872202,46.008146,9.396801,46.348579" #TICINO
#BOUNDS = "-118.6204,33.7041,-118.1553,34.3373" #LOS ANGELES (TEST)
MODEL_ID = "1727965880"

def get_crash_data(index=0):
    KEY = API_KEYS[index]    

    base_url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?key={KEY}&bbox={BOUNDS}" + \
                f"&fields={{incidents{{type,geometry{{type,coordinates}},properties{{events{{description}},startTime,endTime}}}}}}" + \
                f"&language=en-GB&t={MODEL_ID}&categoryFilter=Accident&timeValidityFilter=present"
    try:
        response = requests.get(base_url, timeout=0.5)
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
                return get_crash_data(index+1)
            print(f"Error: {response.status_code}")
            print(f"Response Text: {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    print(get_crash_data())