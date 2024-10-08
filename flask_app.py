from flask import Flask, render_template_string, request, jsonify, render_template
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
import time, threading, json, base64, io, requests
import crashes
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


app = Flask(__name__)

traffic_data_list = []

size = 1


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
    current_speed = int(current_speed)
    speed_limit = int(speed_limit)
    if speed_limit is None:
        speed_limit = 50
    if current_speed is None or current_speed == 0:
        return 'gray'
    
    congestion_level = current_speed / speed_limit

    if congestion_level >= 0.8:
        return 'rgb(44,173,35'
    elif congestion_level >= 0.6:
        return 'rgb(255,245,0)'
    elif congestion_level >= 0.4:
        return 'rgb(224,122,38)'
    elif congestion_level >= 0.2:
        return 'rgb(184,28,28)'
    else:
        return 'rgb(255,0,0)'


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
        return jsonify({'exists': False, 'message': 'No date provided.'})
    
    formatted_date = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d_%m_%Y')
    
    expected_file_name = f"t_data_{formatted_date}.csv"
    
    url = f'https://api.github.com/repos/{REPO}/contents/his_data'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        files = response.json()
        for file in files:
            if file['name'] == expected_file_name:
                return jsonify({'exists': True, 'file': expected_file_name})
        
        return jsonify({'exists': False, 'message': 'File does not exist.'})
    else:
        return jsonify({'success': False, 'message': 'Could not fetch files from GitHub.'})



def find_nearby_traffic(traffic_cache, coords, radius_km=0.7):
    for cached_data in traffic_cache:
        cc = cached_data['coordinates'][0]
        cached_coords = (cc[1], cc[0])
        distance = geodesic(coords, cached_coords).km
        if distance <= radius_km:
            return cached_data
    return None


GITHUB_TOKEN1 = 'ghp_FWbnVrSli6jpSBFkEn'
GITHUB_TOKEN2 = 'utbwZT211G7X1pKl0G'
GITHUB_TOKEN = GITHUB_TOKEN1 + GITHUB_TOKEN2
REPO = 'qLessqndr/road_traffic_ticino'

def save_to_github(filename, content):
    url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        file_info = response.json()
        sha = file_info['sha']
    
    data = {
        "message": "Backend-Gathered Data",
        "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
        "branch": "main"
    }
    
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
    timestamp = (datetime.now() + timedelta(hours=2)).strftime("%d_%m_%Y_%H-%M")
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



def find_closest_time_column(df, target_time):
    closest_col = None
    closest_diff = None
    target_dt = datetime.strptime(target_time, '%H:%M')
    for col in df.columns:
        try:
            col_time = datetime.strptime(col, '%H_%M')
            diff = abs((col_time - target_dt).total_seconds())
            
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest_col = col
        except ValueError:
            continue

    return closest_col


list_of_df = {}
@app.route('/load_traffic_data', methods=['GET'])
def load_traffic_data():
    date = request.args.get('date')
    date_obj = datetime.strptime(date, '%Y-%m-%d')    
    date_str = date_obj.strftime('%d_%m_%Y')
    file_name = f"t_data_{date_str}.csv"
 

    traffic_data = []
    
    if not file_name:
        return jsonify({'features': []})

    if file_name in list_of_df:
        df = list_of_df[file_name]
    else:
        url = f"https://api.github.com/repos/{REPO}/contents/his_data/{file_name}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.raw"
        }        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.text
            df = pd.read_csv(io.StringIO(content), delimiter=";")
            list_of_df[file_name] = df
        else:
            return jsonify({'features': [], 'message': 'File not found on GitHub.'})

    time_columns = [col for col in df.columns if col not in ['coordinates', 'speed_limit']]

    df['coordinates'] = df['coordinates'].apply(lambda x: str(x) if isinstance(x, list) else x)
    

    time_columns = [col for col in df.columns if col not in ['coordinates', 'speed_limit']]

    df_long = pd.melt(df, id_vars=['coordinates', 'speed_limit'], value_vars=time_columns, 
                    var_name='time', value_name='current_speed')

    df_long['color'] = df_long.apply(lambda row: get_color_by_congestion(row['current_speed'], row['speed_limit']), axis=1)

    df_long = df_long.astype({
        'speed_limit': 'float',
        'current_speed': 'float',
        'color': 'str',
    })

    traffic_data = df_long.groupby(['coordinates', 'speed_limit']).apply(
        lambda x: {
            'geometry': {'coordinates': ast.literal_eval(x['coordinates'].iloc[0])},
            'properties': {
                'speed_limit': x['speed_limit'].iloc[0],
                'times': {row['time']: {'current_speed': row['current_speed'], 'color': row['color']} for _, row in x.iterrows()}
            }
        }
    ).tolist()

    return jsonify({'features': traffic_data})


def retrieve_routes(file_name='default_routes.csv'):
    file_path = f"his_data/{file_name}"    
    url = f"https://api.github.com/repos/{REPO}/contents/his_data/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw"
    }
    response = requests.get(url, headers=headers)    
    if response.status_code != 200:
        return None
    df = pd.read_csv(io.StringIO(response.text), delimiter=";")
    return df


@app.route('/update_traffic_data', methods=['POST'])
def update_traffic_data():    
    timestamp = (datetime.now() + timedelta(hours=2)).strftime("%d_%m_%Y")
    time_of = (datetime.now() + timedelta(hours=2)).strftime("%H_%M")
    total = 0

    save_crash_data(crashes.get_crash_data())
    
    df = retrieve_routes(f't_data_{timestamp}.csv')
    if df is None:
        df = retrieve_routes()

    traffic_cache = []
    current_speeds = []

    for index, row in df.iterrows():
        coords = ast.literal_eval(row["coordinates"])
        fp = coords[0]
        first_point = (fp[1], fp[0])
        cached_data = find_nearby_traffic(traffic_cache, first_point)
        if cached_data:
            cur_speed = cached_data['current_speed']
        else:
            total += 1
            td = traffic.get_data(first_point)
            if td is not None:
                cur_speed = int(td['current_speed'])
            else:
                cur_speed = 50
                print(f"Problem in gathering data: {td}")
            
            traffic_cache.append({
                'coordinates': coords,
                'current_speed': cur_speed
            })        
        current_speeds.append(cur_speed)

    df[f'{time_of}'] = current_speeds

    print(total)

    filename = f"his_data/t_data_{timestamp}.csv"

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, sep=';', index=False)
    content = csv_buffer.getvalue()

    success = save_to_github(filename, content)
    
    if success:
        traffic_data_list.clear()
        return jsonify({'success': True, 'filename': filename})
    else:
        return jsonify({'success': False, 'message': 'Failed to save to GitHub.'})


def listify_crash_json(js):
    data = []
    if js is not None:
        for t in js["incidents"]:
            data.append({
                'coordinates': t['geometry']['coordinates'][0], 
                'description': t['properties']['events'][0]['description'],
                'startTime': t['properties']['startTime'],
                'endTime': t['properties']['endTime']
            })
        return data
    return []

def save_crash_data(data):
    data_list = listify_crash_json(data)
    timestamp = (datetime.now() + timedelta(hours=2)).strftime("%d_%m_%Y")
    filename = f"crash_data/c_data_{timestamp}.csv"
    existing_file = load_crashes(filename, True)
    for d in data_list:
        found_same = False
        for e in existing_file:
            if e['coordinates'] == d['coordinates'] and e['startTime'] == d['startTime']:
                if e['endTime'] != d['endTime']:
                    existing_file.remove(e)
                    break
                else:
                    found_same = True
        if not found_same:
            existing_file.append(d)
    content = 'coordinates;description;startTime;endTime\n'
    for d in existing_file:
        content += f"{d['coordinates']};{d['description']};{d['startTime']};{d['endTime']}\n"
    save_to_github(filename, content)

@app.route('/frontend.html')
def home():
    return render_template('frontend.html')

@app.route('/')
def frontend():
    return render_template('frontend.html')

@app.route('/about.html')
def about():
    return render_template('about.html')

@app.route('/map.html')
def map():
    return render_template('map_page.html')
    
@app.route('/data.html')
def data():
    return render_template('data.html')


def load_crashes(file_name, return_dict=False):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw"
    }    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        content = response.text
        df = pd.read_csv(io.StringIO(content), delimiter=";")
        data = []        
        for index, row in df.iterrows():
            data.append({
                'coordinates': ast.literal_eval(row["coordinates"]),          
                'description': row['description'],
                'startTime': row['startTime'],
                'endTime': row['endTime']            
            })        
        if return_dict:
            return data
        return jsonify({'incidents': [{'geometry': {'coordinates': t['coordinates']}, 'properties': {'startTime': t['startTime'], 'endTime': t['endTime'], 'events': [{'description': t['description']}]}} for t in traffic_data]})
    else:
        if return_dict:
            return []
        return jsonify({'incidents': [], 'message': 'File not found on GitHub.'})


@app.route('/get_crash_data', methods=['GET'])
def crash_data():
    data = crashes.get_crash_data()
    save_crash_data(data)
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
