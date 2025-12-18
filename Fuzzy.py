# --- Fuzzy.py ---

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import requests

# --- 0. UPDATED TEMPERATURE FETCH FUNCTION (OpenWeatherMap) ---

def fetch_current_temperature(lat, lon, api_key):
    """
    Fetches the current temperature using OpenWeatherMap API.
    """
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    try:
        response = requests.get(url, timeout=5).json()
        if response.get("cod") == 200:
            return float(response["main"]["temp"])
        return None
    except Exception:
        return None

# --- 1. DEFINE FUZZY LOGIC SYSTEM (FLS) ---

# Antecedent (Input) and Consequent (Output)
temp = ctrl.Antecedent(np.arange(-10, 41, 1), 'temperature')
percent_change = ctrl.Consequent(np.arange(-30, 21, 1), 'percent_change')

# Membership Functions (Input)
temp['Freezing'] = fuzz.trapmf(temp.universe, [-10, -10, 0, 5]) 
temp['Very_Cold'] = fuzz.trimf(temp.universe, [0, 5, 12])      
temp['Cold'] = fuzz.trimf(temp.universe, [8, 15, 22])       
temp['Moderate'] = fuzz.trimf(temp.universe, [18, 25, 32])      
temp['Hot'] = fuzz.trimf(temp.universe, [28, 35, 40])      
temp['Very_Hot'] = fuzz.trimf(temp.universe, [35, 40, 40])     

# Percentage Change Sets (Output) 
percent_change['Extreme_Decrease'] = fuzz.trimf(percent_change.universe, [-31, -30, -28]) 
percent_change['Large_Decrease'] = fuzz.trimf(percent_change.universe, [-25, -15, -10]) 
percent_change['Decrease'] = fuzz.trimf(percent_change.universe, [-15, -8, 0])    
percent_change['No_Change'] = fuzz.trimf(percent_change.universe, [-5, 0, 5])     
percent_change['Increase'] = fuzz.trimf(percent_change.universe, [0, 8, 15])      
percent_change['Large_Increase'] = fuzz.trimf(percent_change.universe, [10, 15, 20])   

# Fuzzy Rules 
rule0 = ctrl.Rule(temp['Freezing'], percent_change['Extreme_Decrease']) 
rule1 = ctrl.Rule(temp['Very_Cold'], percent_change['Large_Decrease'])
rule2 = ctrl.Rule(temp['Cold'], percent_change['Decrease'])
rule3 = ctrl.Rule(temp['Moderate'], percent_change['No_Change'])
rule4 = ctrl.Rule(temp['Hot'], percent_change['Increase'])
rule5 = ctrl.Rule(temp['Very_Hot'], percent_change['Large_Increase'])

# Control System Simulation
watering_ctrl = ctrl.ControlSystem([rule0, rule1, rule2, rule3, rule4, rule5])
watering_sim = ctrl.ControlSystemSimulation(watering_ctrl)

# --- FLS Calculation Function ---

def calculate_adjusted_water(base_quantity_ml, current_temp=None):
    """
    Runs FLS and returns: 
    (percent_adj, current_temp, final_qty_ml, temp_category, percent_category)
    """
    # Use 25°C (Moderate) as a safe fallback if temperature is missing
    if current_temp is None:
        current_temp = 25.0

    # 1. Apply Input to Simulation
    watering_sim.input['temperature'] = current_temp
    
    # 2. Crunch the numbers
    watering_sim.compute()
    percent_adj = watering_sim.output['percent_change']
    
    # 3. Calculate Final Quantity
    final_qty_ml = base_quantity_ml * (1 + (percent_adj / 100))

    # 4. Determine Categories (Finding the dominant Fuzzy Set)
    # Get membership levels for each category at the current temp
    temp_categories = {
        'Freezing': fuzz.interp_membership(temp.universe, temp['Freezing'].mf, current_temp),
        'Very Cold': fuzz.interp_membership(temp.universe, temp['Very_Cold'].mf, current_temp),
        'Cold': fuzz.interp_membership(temp.universe, temp['Cold'].mf, current_temp),
        'Moderate': fuzz.interp_membership(temp.universe, temp['Moderate'].mf, current_temp),
        'Hot': fuzz.interp_membership(temp.universe, temp['Hot'].mf, current_temp),
        'Very Hot': fuzz.interp_membership(temp.universe, temp['Very_Hot'].mf, current_temp)
    }
    temp_category = max(temp_categories, key=temp_categories.get)

    # Get membership levels for adjustment
    adj_categories = {
        'Extreme Decrease': fuzz.interp_membership(percent_change.universe, percent_change['Extreme_Decrease'].mf, percent_adj),
        'Large Decrease': fuzz.interp_membership(percent_change.universe, percent_change['Large_Decrease'].mf, percent_adj),
        'Decrease': fuzz.interp_membership(percent_change.universe, percent_change['Decrease'].mf, percent_adj),
        'No Change': fuzz.interp_membership(percent_change.universe, percent_change['No_Change'].mf, percent_adj),
        'Increase': fuzz.interp_membership(percent_change.universe, percent_change['Increase'].mf, percent_adj),
        'Large Increase': fuzz.interp_membership(percent_change.universe, percent_change['Large_Increase'].mf, percent_adj)
    }
    percent_category = max(adj_categories, key=adj_categories.get)

    return percent_adj, current_temp, final_qty_ml, temp_category, percent_category
