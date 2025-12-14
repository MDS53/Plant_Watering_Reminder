# --- Fuzzy.py ---

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import requests
import re 

# --- 0. EXTERNAL TEMPERATURE FETCH FUNCTION ---

def fetch_current_temperature(location=""):
    """
    Fetches the current temperature from wttr.in.
    :return: Temperature in float (Celsius) or None on failure.
    """
    url = f"https://wttr.in/{location}?format=%t&0T" 
    
    try:
        response = requests.get(url, timeout=5) 
        response.raise_for_status()
        raw_temp_str = response.text.strip()
        match = re.search(r'([-+]?\d+)', raw_temp_str)
        if match:
            return float(match.group(1)) 
        else:
            return None
            
    except requests.exceptions.RequestException:
        return None

# --- 1. DEFINE FUZZY LOGIC SYSTEM (FLS) ---

temp = ctrl.Antecedent(np.arange(-10, 41, 1), 'temperature')
percent_change = ctrl.Consequent(np.arange(-30, 21, 1), 'percent_change')

# Membership Functions (Input)
temp['FZR'] = fuzz.trapmf(temp.universe, [-10, -10, 0, 5]) 
temp['VC'] = fuzz.trimf(temp.universe, [0, 5, 12])      
temp['C'] = fuzz.trimf(temp.universe, [8, 15, 22])       
temp['M'] = fuzz.trimf(temp.universe, [18, 25, 32])      
temp['H'] = fuzz.trimf(temp.universe, [28, 35, 40])      
temp['VH'] = fuzz.trimf(temp.universe, [35, 40, 40])     

# Percentage Change Sets (Output) 
percent_change['ED'] = fuzz.trimf(percent_change.universe, [-31, -30, -28]) 
percent_change['LD'] = fuzz.trimf(percent_change.universe, [-25, -15, -10]) 
percent_change['D'] = fuzz.trimf(percent_change.universe, [-15, -8, 0])    
percent_change['NC'] = fuzz.trimf(percent_change.universe, [-5, 0, 5])     
percent_change['I'] = fuzz.trimf(percent_change.universe, [0, 8, 15])      
percent_change['LI'] = fuzz.trimf(percent_change.universe, [10, 15, 20])   

# Fuzzy Rules 
rule0 = ctrl.Rule(temp['FZR'], percent_change['ED']) 
rule1 = ctrl.Rule(temp['VC'], percent_change['LD'])
rule2 = ctrl.Rule(temp['C'], percent_change['D'])
rule3 = ctrl.Rule(temp['M'], percent_change['NC'])
rule4 = ctrl.Rule(temp['H'], percent_change['I'])
rule5 = ctrl.Rule(temp['VH'], percent_change['LI'])

# Control System Simulation
watering_ctrl = ctrl.ControlSystem([rule0, rule1, rule2, rule3, rule4, rule5])
watering_sim = ctrl.ControlSystemSimulation(watering_ctrl)

# --- FLS Calculation Function (UPDATED) ---

def calculate_adjusted_water(base_quantity_ml):
    """
    Fetches temperature, runs FLS, and returns all calculation details, 
    including the dominant fuzzy categories for temperature and adjustment.
    
    :param base_quantity_ml: Base water quantity in mL (from Gemini).
    :return: Tuple (percent_adj, current_temp, final_quantity_ml, temp_category, percent_category) or None.
    """
    current_temp = fetch_current_temperature()
    
    # --- 1. Temperature Fetch Fallback ---
    if current_temp is None:
        # Fallback if temperature fetch fails (return base quantity with 0% adj)
        return 0.0, None, base_quantity_ml, 'N/A', 'N/A' 

    try:
        watering_sim.input['temperature'] = current_temp
        watering_sim.compute()
        percent_adj = watering_sim.output['percent_change']
        
        # Calculate final quantity
        adj_mL = base_quantity_ml * (percent_adj / 100.0)
        final_quantity = base_quantity_ml + adj_mL
        
        # --- 2. Determine Dominant Linguistic Category for Input (Temperature) ---
        max_membership_temp = -1.0
        temp_category = 'Undefined'
        
        for name, mf in temp.terms.items():
            mu = fuzz.interp_membership(temp.universe, mf.mf, current_temp)
            if mu > max_membership_temp:
                max_membership_temp = mu
                temp_category = name
                
        # --- 3. Determine Dominant Linguistic Category for Output (Percent Change) ---
        max_membership_percent = -1.0
        percent_category = 'Undefined'
        
        for name, mf in percent_change.terms.items():
            mu = fuzz.interp_membership(percent_change.universe, mf.mf, percent_adj)
            if mu > max_membership_percent:
                max_membership_percent = mu
                percent_category = name
        
        # --- 4. Return all calculated values and categories ---
        return percent_adj, current_temp, final_quantity, temp_category, percent_category
        
    except (ValueError, KeyError, ZeroDivisionError):
        # Fallback if FLS computation fails
        return 0.0, current_temp, base_quantity_ml, 'FLS_Error', 'FLS_Error'