from flask import Flask, render_template_string, request, jsonify
import folium
import traffic
import get_speedbox
import route_calculator
import geopy.distance
import pandas as pd
from datetime import datetime, timedelta
import os
import ast
from geopy.distance import geodesic
import webbrowser
import requests
import io
import base64
import json
import threading

app = Flask(__name__)

traffic_data_list = []

with open("frontend.html", "r", encoding="utf-8") as f:
    html_template = f.read()

size = 1

@app.route('/')
def index():
    return render_template_string(html_template)


def get_traffic_data(lat, lon):
    geojson_data = get_speedbox.get_speed_limits(lat, lon, size)
    traffic_data_points = []
    for feature in geojson_data['features']:
        if feature['geometry']['type'] == 'LineString':
            coordinates = feature['geometry']['coordinates']
            speed_limit = feature['properties'].get('maxspeed', None)
            speed_limit = int(speed_limit) if speed_limit and speed_limit.isdigit() else 50
            center_index = len(coordinates) // 2
            center_point = (coordinates[center_index][1], coordinates[center_index][0])
            traffic_info = traffic.get_data(center_point)
            current_speed = float(traffic_info['current_speed']) if traffic_info and 'current_speed' in traffic_info else None
            traffic_data_points.append({
                'coordinates': coordinates,
                'speed_limit': speed_limit,
                'current_speed': current_speed,
                'color': get_color_by_congestion(50, speed_limit)
            })

    return traffic_data_points


def get_color_by_congestion(current_speed, speed_limit):
    if current_speed is None:
        return 'gray'
    congestion_level = current_speed / speed_limit if speed_limit else 0
    if congestion_level >= 0.8:
        return 'green'
    elif congestion_level >= 0.5:
        return 'orange'
    else:
        return 'red'


@app.route('/get_point_traffic')
def get_point_traffic():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    traffic_data = get_traffic_data(lat, lon)
    for t in traffic_data:
        traffic_data_list.append({
            'coordinates': t['coordinates'], 
            'color': t['color'],
            'speed_limit': t['speed_limit'],
            'current_speed': t['current_speed']
        })
    return jsonify({'features': [{'geometry': {'coordinates': t['coordinates']}, 'properties': {'speed_limit': t['speed_limit'], 'current_speed': t['current_speed'], 'color': t['color']}} for t in traffic_data]})



@app.route('/get_files_for_date')
def get_files_for_date():
    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({'files': []})
    formatted_date = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d_%m_%Y')
    date_files = []
    url = f'https://api.github.com/repos/{REPO}/contents/his_data'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        files = response.json()
        for file in files:
            if formatted_date in file['name'] and file['name'].endswith('.csv'):
                date_files.append(file['name'])
    else:
        return jsonify({'success': False, 'message': 'Could not fetch files from GitHub.'})

    return jsonify({'files': date_files})



traffic_cache = []
def find_nearby_traffic(coords, radius_km=1):
    for cached_data in traffic_cache:
        cc = cached_data['coordinates'][0]
        cached_coords = (cc[1], cc[0])
        distance = geodesic(coords, cached_coords).km
        if distance <= radius_km:
            return cached_data
    return None


GITHUB_TOKEN = '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'
REPO = 'qLessqndr/road_traffic_ticino'

def save_to_github(filename, content):
    url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # First, check if the file exists to get its SHA
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        file_info = response.json()
        sha = file_info['sha']
    
    data = {
        "message": "Add/update traffic data",
        "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
        "branch": "main"
    }
    
    # Include SHA if the file exists
    if sha:
        data['sha'] = sha

    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code not in [200, 201]:
        print("Failed to save to GitHub:", response.status_code, response.json())
    return response.status_code in [201, 200]



@app.route('/save_traffic_data', methods=['POST'])
def save_traffic_data():
    if len(traffic_data_list) == 0:
        return jsonify({'success': False, 'message': 'No traffic data to save.'})
    timestamp = datetime.now().strftime("%d_%m_%Y_%H-%M")
    filename = f"his_data/t_data_{timestamp}.csv"   

    content = 'coordinates;color;speed_limit;current_speed\n'
    for data in traffic_data_list:
        content += f"{data['coordinates']};{data['color']};{data['speed_limit']};{data['current_speed']}\n"
    
    success = save_to_github(filename, content)

    if success:
        traffic_data_list.clear()
        return jsonify({'success': True, 'filename': filename})
    else:
        return jsonify({'success': False, 'message': 'Failed to save to GitHub.'})


@app.route('/load_traffic_data', methods=['GET'])
def load_traffic_data():
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'features': []})

    url = f"https://api.github.com/repos/{REPO}/contents/his_data/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw"
    }
    
    response = requests.get(url, headers=headers)
    print(response)
    if response.status_code == 200:
        content = response.text
        df = pd.read_csv(io.StringIO(content), delimiter=";")
        traffic_data = []
        
        for index, row in df.iterrows():
            traffic_data.append({
                'coordinates': ast.literal_eval(row["coordinates"]),          
                'speed_limit': row['speed_limit'],
                'current_speed': row['current_speed'],
                'color': row['color']            
            })        
        return jsonify({'features': [{'geometry': {'coordinates': t['coordinates']}, 'properties': {'speed_limit': t['speed_limit'], 'current_speed': t['current_speed'], 'color': t['color']}} for t in traffic_data]})
    else:
        return jsonify({'features': [], 'message': 'File not found on GitHub.'})


@app.route('/update_traffic_data', methods=['POST'])
def update_traffic_data():
    file_name = 'default_routes.csv'
    file_path = os.path.join('his_data', file_name)
    
    url = f"https://api.github.com/repos/{REPO}/contents/his_data/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return jsonify({'success': False, 'message': 'Failed to retrieve default routes.'})

    df = pd.read_csv(io.StringIO(response.text), delimiter=";")
    traffic_data = []
    traffic_data_list = []

    for index, row in df.iterrows():
        coords = ast.literal_eval(row["coordinates"])
        fp = coords[0]
        first_point = (fp[1], fp[0])
        cached_data = find_nearby_traffic(first_point)
        
        if cached_data:
            cur_speed = cached_data['current_speed']
            color = get_color_by_congestion(cur_speed, int(row["speed_limit"]))
        else:
            td = traffic.get_data(first_point)
            print(td)
            if td is not None:
                cur_speed = int(td['current_speed'])
                color = get_color_by_congestion(cur_speed, int(row["speed_limit"]))
            else:
                cur_speed = 50
                color = 'grey'
            
            traffic_cache.append({
                'coordinates': coords,
                'speed_limit': row['speed_limit'],
                'current_speed': cur_speed,
                'color': color
            })
        
        traffic_data.append({
            'coordinates': coords,
            'speed_limit': row['speed_limit'],
            'current_speed': cur_speed,
            'color': color
        })

    timestamp = datetime.now().strftime("%d_%m_%Y_%H-%M")
    filename = f"his_data/t_data_{timestamp}.csv"
    content = 'coordinates;color;speed_limit;current_speed\n'
    for data in traffic_data:
        content += f"{data['coordinates']};{data['color']};{data['speed_limit']};{data['current_speed']}\n"

    success = save_to_github(filename, content)
    
    if success:
        traffic_data_list.clear()
        return jsonify({'success': True, 'filename': filename})
    else:
        return jsonify({'success': False, 'message': 'Failed to save to GitHub.'})

def schedule_task():
    now = datetime.now()    
    scheduled_times = [
        (8, 0),
        (9, 0),
        (10, 0),
        (12, 0),
        (14, 0),
        (15, 0),
        (16, 0),
        (18, 0),
        (20, 0),
        (22, 0),
        (0, 0)
    ]    
    for hour, minute in scheduled_times:
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)        
        delay = (scheduled_time - now).total_seconds()
        threading.Timer(delay, update_traffic_data).start()



if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000/")
    #schedule_task()
    app.run(host='0.0.0.0', port=5000, debug=True)
