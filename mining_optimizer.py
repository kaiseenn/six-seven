import csv
import ast
import argparse
import math
import sys

class AbyssalOptimizer:
    def __init__(self, filepath='merged.csv'):
        self.filepath = filepath
        self.data = []
        self.headers = []

    def load_data(self):
        """Loads the dataset using standard csv module."""
        print(f"Loading data from {self.filepath}...")
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.headers = reader.fieldnames
                self.data = [row for row in reader]
        except FileNotFoundError:
            print(f"Error: File {self.filepath} not found.")
            return False
        
        print(f"Loaded {len(self.data)} rows.")
        return True

    def _safe_eval(self, val):
        """Safely evaluates a string representation of a list."""
        if not val:
            return []
        try:
            # If it looks like a list, evaluate it
            if val.startswith('[') and val.endswith(']'):
                return ast.literal_eval(val)
            return val
        except (ValueError, SyntaxError):
            return []

    def _get_float(self, val):
        """Converts string to float, handling empty strings."""
        if not val:
            return 0.0
        try:
            return float(val)
        except ValueError:
            return 0.0

    def calculate_scores(self, weights=None):
        """
        Calculates a mining score for each cell.
        """
        if weights is None:
            weights = {
                'value': 1.0,
                'difficulty': 1.0,
                'impact': 2.0,
                'hazard': 2.0
            }
            
        print("Calculating scores...")
        
        # Helper to map hazard severity
        severity_map = {'low': 1, 'medium': 2, 'high': 3, 'extreme': 5}
        
        self.scored_data = []
        
        for row in self.data:
            # Parse relevant fields
            
            # 1. Resource Value
            # aggregated columns are strings resembling lists
            res_values = self._safe_eval(row.get('resource_economic_value', '[]'))
            res_abundance = self._safe_eval(row.get('resource_abundance', '[]'))
            res_purity = self._safe_eval(row.get('resource_purity', '[]'))
            
            total_value = 0.0
            if isinstance(res_values, list):
                count = len(res_values)
                for i in range(count):
                    v = float(res_values[i]) if i < len(res_values) and res_values[i] is not None else 0
                    a = float(res_abundance[i]) if i < len(res_abundance) and res_abundance[i] is not None else 0
                    p = float(res_purity[i]) if i < len(res_purity) and res_purity[i] is not None else 0
                    total_value += v * a * p

            # 2. Extraction Difficulty
            diff_list = self._safe_eval(row.get('resource_extraction_difficulty', '[]'))
            if isinstance(diff_list, list) and diff_list:
                clean_diff = [float(d) for d in diff_list if d is not None]
                avg_difficulty = sum(clean_diff) / len(clean_diff) if clean_diff else 0
            else:
                avg_difficulty = 0

            # 3. Environmental Impact
            res_impact_list = self._safe_eval(row.get('resource_environmental_impact', '[]'))
            if isinstance(res_impact_list, list):
                res_impact = sum([float(i) for i in res_impact_list if i is not None])
            else:
                res_impact = 0
            
            coral_cover = self._get_float(row.get('coral_coral_cover_pct', '0'))
            
            life_density_list = self._safe_eval(row.get('life_density', '[]'))
            if isinstance(life_density_list, list):
                life_density = sum([float(l) for l in life_density_list if l is not None])
            else:
                life_density = 0
            
            threat_level_list = self._safe_eval(row.get('life_threat_level', '[]'))
            if isinstance(threat_level_list, list):
                threat_level_sum = sum([float(t) for t in threat_level_list if t is not None])
            else:
                threat_level_sum = 0
            
            total_env_impact = res_impact + (coral_cover / 10.0) + (life_density * 10.0) + (threat_level_sum * 5.0)

            # 4. Hazards
            hazard_severity_list = self._safe_eval(row.get('hazard_severity', '[]'))
            hazard_score = 0
            if isinstance(hazard_severity_list, list):
                for h in hazard_severity_list:
                    if h in severity_map:
                        hazard_score += severity_map[h]
            
            # Final Score
            score = (total_value * weights['value']) - \
                    (avg_difficulty * weights['difficulty']) - \
                    (total_env_impact * weights['impact']) - \
                    (hazard_score * weights['hazard'])
            
            self.scored_data.append({
                'row': row['row'],
                'col': row['col'],
                'lat': row.get('lat', '0.0'),
                'lon': row.get('lon', '0.0'),
                'score': score,
                'total_value': total_value,
                'difficulty': avg_difficulty,
                'env_impact': total_env_impact,
                'hazard_score': hazard_score,
                'depth': row.get('depth_m', '0'),
                'biome': row.get('biome', 'unknown')
            })
            
        # Sort by score descending
        self.scored_data.sort(key=lambda x: x['score'], reverse=True)
        return self.scored_data

    def generate_html_map(self, output_file='mining_map.html', top_n=50):
        """Generates an HTML file with a Leaflet map of top locations."""
        if not self.scored_data:
            print("No data to map.")
            return

        print(f"Generating map for top {top_n} locations to {output_file}...")
        
        # Calculate map center from the top 1 location
        center_lat = self.scored_data[0]['lat']
        center_lon = self.scored_data[0]['lon']
        
        # Start HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Abyssal Mining Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .info {{ padding: 6px 8px; font: 14px/16px Arial, Helvetica, sans-serif; background: white; background: rgba(255,255,255,0.8); box-shadow: 0 0 15px rgba(0,0,0,0.2); border-radius: 5px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], 10);

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 18,
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var markers = [];
"""
        
        # Add markers for top N locations
        for i, item in enumerate(self.scored_data[:top_n]):
            lat = item['lat']
            lon = item['lon']
            score = item['score']
            biome = item['biome']
            depth = item['depth']
            
            # Popup content
            popup_html = f"<b>Rank: {i+1}</b><br>" \
                         f"Score: {score:.2f}<br>" \
                         f"Biome: {biome}<br>" \
                         f"Depth: {depth}m<br>" \
                         f"Value: {item['total_value']:.2f}<br>" \
                         f"Hazards: {item['hazard_score']:.2f}<br>" \
                         f"Loc: ({item['row']}, {item['col']})"
            
            # Color based on rank (green to red) - simple logic: top 10 green, others blue
            color = 'green' if i < 10 else 'blue'
            
            # Add marker JS
            html_content += f"""
        var marker = L.circleMarker([{lat}, {lon}], {{
            color: '{color}',
            fillColor: '{color}',
            fillOpacity: 0.5,
            radius: 8
        }}).addTo(map);
        marker.bindPopup("{popup_html}");
"""

        html_content += """
    </script>
</body>
</html>"""

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print("Map generated successfully.")
        except Exception as e:
            print(f"Error writing map file: {e}")

    def print_top_locations(self, n=10):
        if not self.scored_data:
            print("No scores calculated.")
            return
            
        print(f"\n--- Top {n} Mining Locations ---")
        print(f"{'Rank':<5} {'Loc(r,c)':<12} {'Score':<10} {'Value':<10} {'Diff':<8} {'Env':<8} {'Haz':<8} {'Biome':<10}")
        print("-" * 85)
        
        for i, item in enumerate(self.scored_data[:n]):
            r, c = item['row'], item['col']
            score = item['score']
            val = item['total_value']
            diff = item['difficulty']
            env = item['env_impact']
            haz = item['hazard_score']
            biome = item['biome']
            
            print(f"{i+1:<5} {f'({r},{c})':<12} {score:<10.2f} {val:<10.2f} {diff:<8.2f} {env:<8.2f} {haz:<8.2f} {biome:<10}")

        if not self.scored_data:
            print("No scores calculated.")
            return
            
        print(f"\n--- Top {n} Mining Locations ---")
        print(f"{'Rank':<5} {'Loc(r,c)':<12} {'Score':<10} {'Value':<10} {'Diff':<8} {'Env':<8} {'Haz':<8} {'Biome':<10}")
        print("-" * 85)
        
        for i, item in enumerate(self.scored_data[:n]):
            r, c = item['row'], item['col']
            score = item['score']
            val = item['total_value']
            diff = item['difficulty']
            env = item['env_impact']
            haz = item['hazard_score']
            biome = item['biome']
            
            print(f"{i+1:<5} {f'({r},{c})':<12} {score:<10.2f} {val:<10.2f} {diff:<8.2f} {env:<8.2f} {haz:<8.2f} {biome:<10}")

def main():
    parser = argparse.ArgumentParser(description='Abyssal Mining Optimizer')
    parser.add_argument('--file', default='merged.csv', help='Path to merged data file')
    parser.add_argument('--top', type=int, default=10, help='Number of top locations to show')
    parser.add_argument('--w_val', type=float, default=1.0, help='Weight for Resource Value')
    parser.add_argument('--w_diff', type=float, default=1.0, help='Weight for Extraction Difficulty')
    parser.add_argument('--w_env', type=float, default=5.0, help='Weight for Environmental Impact')
    parser.add_argument('--w_haz', type=float, default=10.0, help='Weight for Hazards')
    parser.add_argument('--output', help='Path to save results CSV')
    parser.add_argument('--map', help='Path to save HTML map (e.g. map.html)')
    
    args = parser.parse_args()
    
    optimizer = AbyssalOptimizer(args.file)
    if optimizer.load_data():
        weights = {
            'value': args.w_val,
            'difficulty': args.w_diff,
            'impact': args.w_env,
            'hazard': args.w_haz
        }
        optimizer.calculate_scores(weights)
        optimizer.print_top_locations(args.top)
        
        if args.output:
            print(f"Saving results to {args.output}...")
            with open(args.output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=optimizer.scored_data[0].keys())
                writer.writeheader()
                writer.writerows(optimizer.scored_data)
            print("Done.")

        if args.map:
            optimizer.generate_html_map(args.map, top_n=args.top)

if __name__ == "__main__":
    main()
