import csv
import ast

class AbyssalOptimizer:
    def __init__(self, filepath='merged.csv'):
        self.filepath = filepath
        self.data = []
        self.scored_data = []

    def load_data(self):
        """Loads the dataset using standard csv module."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.data = [row for row in reader]
            return True
        except FileNotFoundError:
            return False

    def _safe_eval(self, val):
        """Safely evaluates a string representation of a list."""
        if not val:
            return []
        try:
            if val.startswith('[') and val.endswith(']'):
                return ast.literal_eval(val)
            return val
        except (ValueError, SyntaxError):
            return []

    def _get_float(self, val):
        if not val:
            return 0.0
        try:
            return float(val)
        except ValueError:
            return 0.0

    def calculate_scores(self, weights):
        """Calculates scores for each cell based on weights."""
        # Helper to map hazard severity
        severity_map = {'low': 1, 'medium': 2, 'high': 3, 'extreme': 5}
        
        self.scored_data = []
        
        for row in self.data:
            # 1. Resource Value
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
            
            # Pass basic info plus score details
            # Using 'hazard_type' list for frontend tags
            hazards = self._safe_eval(row.get('hazard_type', '[]'))
            resources = self._safe_eval(row.get('resource_type', '[]'))
            life = self._safe_eval(row.get('life_species', '[]'))

            self.scored_data.append({
                'row': int(row['row']),
                'col': int(row['col']),
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'depth': float(row['depth_m']),
                'biome': row['biome'],
                'pressure': float(row['pressure_atm']),
                'temp': float(row['temperature_c']),
                
                # Optimization details
                'score': score,
                'total_value': total_value,
                'difficulty': avg_difficulty,
                'env_impact': total_env_impact,
                'hazard_score': hazard_score,
                
                # Lists for UI
                'hazards': hazards,
                'resources': resources,
                'life': life
            })
            
        # Normalize scores for heatmap (0-1 range if needed, but raw score is fine for now)
        # Let's sort by score just in case, though grid order is usually preferred for maps
        # We won't sort here to keep grid order if possible, but DeckGL handles points so order doesn't matter much.
        # Sorting helps if we want to return "Top N"
        self.scored_data.sort(key=lambda x: x['score'], reverse=True)
        
        return self.scored_data

