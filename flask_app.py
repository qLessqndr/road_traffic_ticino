from flask import Flask, render_template_string, request, jsonify
import folium
import traffic
import get_speedbox
import route_calculator
import geopy.distance
import pandas as pd
from datetime import datetime
import os
import ast
from geopy.distance import geodesic

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


@app.route('/save_traffic_data', methods=['POST'])
def save_traffic_data():
    if not traffic_data_list:
        return jsonify({'success': False, 'message': 'No traffic data to save.'})
    timestamp = datetime.now().strftime("%d_%m_%Y_%H-%M")
    filename = f"his_data/t_data_{timestamp}.csv"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('coordinates;color;speed_limit;current_speed\n')
        for data in traffic_data_list:
            f.write(f"{data['coordinates']};{data['color']};{data['speed_limit']};{data['current_speed']}\n")
    traffic_data_list.clear()
    return jsonify({'success': True, 'filename': filename})


@app.route('/get_files_for_date')
def get_files_for_date():
    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({'files': []})
    formatted_date = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d_%m_%Y')    
    date_files = []
    for filename in os.listdir('his_data'):
        if formatted_date in filename and filename.endswith('.csv'):
            date_files.append(filename)
    return jsonify({'files': date_files})


@app.route('/load_traffic_data')
def load_traffic_data():
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'features': []})
    file_path = os.path.join('his_data', file_name)
    if not os.path.exists(file_path):
        return jsonify({'features': []})
    df = pd.read_csv(file_path, delimiter=";")
    traffic_data = []
    for index, row in df.iterrows():
        traffic_data.append({
            'coordinates': ast.literal_eval(row["coordinates"]),          
            'speed_limit': row['speed_limit'],
            'current_speed': row['current_speed'],
            'color': row['color']            
        })
    return jsonify({'features': [{'geometry': {'coordinates': t['coordinates']}, 'properties': {'speed_limit': t['speed_limit'], 'current_speed': t['current_speed'], 'color': t['color']}} for t in traffic_data]})



traffic_cache = []
def find_nearby_traffic(coords, radius_km=1):
    for cached_data in traffic_cache:
        cc = cached_data['coordinates'][0]
        cached_coords = (cc[1], cc[0])
        distance = geodesic(coords, cached_coords).km
        if distance <= radius_km:
            return cached_data
    return None


@app.route('/update_traffic_data', methods=['POST'])
def update_traffic_data():
    file_name = 'default_routes.csv'
    file_path = os.path.join('his_data', file_name)
    df = pd.read_csv(file_path, delimiter=";")    
    traffic_data = []
    traffic_data_list = []
    for index, row in df.iterrows():
        coords = ast.literal_eval(row["coordinates"])
        fp = coords[0]
        first_point = (fp[1],fp[0])
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
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('coordinates;color;speed_limit;current_speed\n')
        for data in traffic_data:
            f.write(f"{data['coordinates']};{data['color']};{data['speed_limit']};{data['current_speed']}\n")
    traffic_data_list.clear()
    return jsonify({'success': True, 'filename': filename})


if __name__ == '__main__':
    app.run(debug=True)
