# --- Gemi.py ---

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import dns.resolver
from apscheduler.schedulers.background import BackgroundScheduler
import json

# -------------------- IMPORT FUZZY LOGIC MODULE --------------------
# NOTE: This assumes Fuzzy.py (with updated return values) is in the same directory.
from Fuzzy import calculate_adjusted_water 

# -------------------- NEW GEMINI IMPORTS --------------------
from google import genai
from google.genai import types 
from google.genai.errors import APIError

# -------------------- Scheduler Setup --------------------
scheduler = BackgroundScheduler()
scheduler.start()

# --- Placeholder/Initialization for Gemini Client ---
client = None

# --- UPDATED send_reminder_email FUNCTION ---

def send_reminder_email(user_email, plant, date, time_str, base_qty_str, temp_c, percent_adj, final_qty_ml, temp_category, percent_category):
    """
    Send reminder email including Fuzzy Logic calculation details and categories.
    """
    
    # Format the fuzzy logic variables for the email body
    temp_display = f"{temp_c:.1f} °C" if temp_c is not None else "N/A (Fetch Failed)"
    percent_display = f"{percent_adj:+.2f}%"
    final_qty_display = f"{final_qty_ml:.0f} mL"
    
    # Category Displays for Email
    temp_cat_display = f"({temp_category})"
    percent_cat_display = f"({percent_category})"
    
    try:
        # NOTE: REPLACE THESE WITH YOUR ACTUAL GMAIL AND APP PASSWORD
        sender_email = "plantwateringremainder@gmail.com"        
        sender_password = "egbr wiiv xzye mrgo"       # Gmail app password (NOT your regular password)

        # --- HTML Body (Recommended for better formatting) ---
        html_body = f"""
        <html>
        <body>
        <p>Hello! Here is your plant watering reminder for <b>{plant}</b>.</p>
        <p>🗓️ Scheduled Time: {date} at {time_str}</p>
        
        <hr style="border: 1px solid #ccc;">
        
        <h3>💧 Watering Calculation (Environment Adjusted)</h3>
        
        <p>1. Base Quantity (from AI): <b>{base_qty_str}</b></p>
        <p>2. Current Temperature (Auto-Detected): <b>{temp_display}</b> <span style="color: #007bff; font-weight: bold;">{temp_cat_display}</span></p>
        <p>3. Adjustment Suggestion (Fuzzy Logic): <b>{percent_display}</b> <span style="color: #28a745; font-weight: bold;">{percent_cat_display}</span></p>
        
        <h2 style="color: #dc3545;">Final Suggested Quantity: {final_qty_display}</h2>
        
        <hr style="border: 1px solid #ccc;">
        
        <p>Remember to check your soil before watering!</p>
        </body>
        </html>
        """

        # --- Plain Text Body (Fallback) ---
        plain_body = f"""
        Hello! Here is your plant watering reminder for {plant}.
        
        Scheduled Time: {date} at {time_str}
        
        --- Watering Calculation ---
        
        1. Base Quantity (from AI): {base_qty_str} 
        2. Current Temperature (Auto-Detected): {temp_display} {temp_cat_display}
        3. Adjustment Suggestion (Fuzzy Logic): {percent_display} {percent_cat_display}
        
        Final Suggested Quantity: {final_qty_display}
        
        -----------------------------
        
        Remember to check your soil before watering!
        """
        
        # Use MIMEMultipart to send both HTML and plain text
        from email.mime.multipart import MIMEMultipart
        message = MIMEMultipart("alternative")
        
        message['Subject'] = f"🌿 Reminder: Water {plant} - {final_qty_display} Needed"
        message['From'] = sender_email
        message['To'] = user_email
        
        message.attach(MIMEText(plain_body, 'plain'))
        message.attach(MIMEText(html_body, 'html')) # Attach HTML version

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_email, message.as_string())
        print(f"Reminder sent for {plant} at {date} {time_str} to {user_email}. Final Qty: {final_qty_display}")
        
    except Exception as e:
        print(f"Error sending email: {e}")

# Note: You must ensure you use the full import for MIMEMultipart at the top of Gemi.py:
# from email.mime.multipart import MIMEMultipart

# -------------------- Email Validation --------------------
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def domain_exists(email):
    try:
        domain = email.split('@')[1]
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except Exception:
        return False

# -------------------- API Key and Client Initialization --------------------
def initialize_gemini_client(api_key):
    global client
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            return True
        except Exception as e:
            client = None
            return False
    client = None
    return False

# 2. Function to call Gemini API
def get_plant_details_from_gemini(plant_name, pot_size):
    """
    Calls the Gemini API to get structured plant care details, considering pot size.
    """
    global client
    if not client:
        st.error("Gemini client not initialized. Please enter a valid API key.")
        return None, None 

    # Define the desired JSON structure for the model's output
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "description": types.Schema(type=types.Type.STRING, description="A general description of the plant and its typical environment (1-2 sentences)."),
            "times_per_week": types.Schema(type=types.Type.NUMBER, description="The recommended watering frequency as a floating-point number (e.g., 0.5 for every two weeks, 1.5 for 1-2 times per week)."),
            "water_quantity": types.Schema(type=types.Type.STRING, description="The recommended water quantity per watering session, including units (e.g., '0.2 L (200 ml)'). This quantity MUST be adjusted based on the pot size provided."),
            "adjustments": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="A list of 3 key adjustment notes based on temperature, humidity, or season.")
        },
        required=["description", "times_per_week", "water_quantity", "adjustments"]
    )

    prompt = f"""
    Provide the care details for the plant named '{plant_name}', assuming it is in a {pot_size} pot.
    Format the response strictly as a JSON object matching the provided schema.
    The 'times_per_week' should be an accurate numerical average.
    The 'water_quantity' must be specifically tailored for a {pot_size} pot.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        plant_details = json.loads(response.text)

        frequency = plant_details.get("times_per_week", 1.0)
        water_qty = plant_details.get("water_quantity", f"0.2 L for a {pot_size} pot")
        adjustments = plant_details.get("adjustments", ["No AI care notes provided."])
        description = plant_details.get("description", "No description found.")

        # Calculate Total Water per Week (Approx.)
        total_water_per_week_str = "Custom - Calculated"
        try:
            qty_value = water_qty.split(' ')[0]
            if qty_value.replace('.', '', 1).isdigit(): 
                 total_water = float(qty_value) * frequency
                 total_water_per_week_str = f"{total_water:.2f} L/week (Approx.)"
        except:
             pass 

        # Create the structured data for your app
        new_plants_data = {plant_name: {"times_per_week": frequency}}
        new_plants_data_ = {
            plant_name: {
                "schedule": {
                    "💦 How Many Times/Week": [f"{frequency} time(s)/week (AI recommendation)"],
                    "🧴 Water Quantity (Litres per Time)": [water_qty],
                    "🌤 Total Water per Week (Approx.)": [total_water_per_week_str]
                },
                "adjustments": [f"**AI Description:** {description}", f"**Pot Size Used:** {pot_size}"] + adjustments
            }
        }

        return new_plants_data, new_plants_data_

    except APIError as e:
        st.error(f"Gemini API Error (Code: {e.code}): Could not fetch details for {plant_name}. Please check your API key and quota.")
        return None, None
    except Exception as e:
        st.error(f"Error fetching plant details: {e}")
        return None, None


# -------------------- Utility: Extract Base Quantity (mL) --------------------
def parse_base_quantity_ml(water_qty_str):
    """
    Parses the water quantity string (e.g., '0.2 L (200 ml)') to get the base quantity in mL.
    Returns 500 mL as a safe default if parsing fails.
    """
    # Look for 'ml' or 'mL'
    ml_match = re.search(r'\(?(\d+)\s*m[lL]\)?', water_qty_str, re.IGNORECASE)
    if ml_match:
        return int(ml_match.group(1))
    
    # Look for 'L' and convert to mL
    l_match = re.search(r'(\d*\.?\d+)\s*L', water_qty_str, re.IGNORECASE)
    if l_match:
        return int(float(l_match.group(1)) * 1000)
    
    # Default fallback
    return 500


# -------------------- Streamlit Main Function --------------------

def main():
    st.set_page_config(page_title="Plant Watering Reminder", layout="wide")
    st.title("🌿 Plant Watering Reminder")
    st.write("Select plants, dates, times, add reminders, send full schedule, and get automatic watering emails.")

    # -------------------- Session State --------------------
    if "watering_schedule" not in st.session_state:
        # UPDATED: Added Temp Category and Adj Category columns
        st.session_state["watering_schedule"] = pd.DataFrame(columns=[
            "Plant", 
            "Date", 
            "Time", 
            "Water Quantity", 
            "Base Qty (mL)", 
            "Temp (°C)", 
            "Adj (%)", 
            "Final Qty (mL)",
            "Temp Category", 
            "Adj Category"
        ])
    if "selected_plant" not in st.session_state:
        st.session_state["selected_plant"] = "Select a plant"
    if "selected_dates" not in st.session_state:
        st.session_state["selected_dates"] = []
    if "watering_times" not in st.session_state:
        st.session_state["watering_times"] = []
    if "custom_plant_name" not in st.session_state:
        st.session_state["custom_plant_name"] = ""
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = ""
    if "plants_data" not in st.session_state:
        st.session_state["plants_data"] = {
            "Aloe Vera": {"times_per_week": 0.5},
            "Peace Lily": {"times_per_week": 2},
            "Snake Plant (Sansevieria)": {"times_per_week": 0.5},
            "Spider Plant (Chlorophytum)": {"times_per_week": 1},
            "Money Plant (Pothos)": {"times_per_week": 1.5}
        }
    if "plants_data_" not in st.session_state:
        st.session_state["plants_data_"] = {
            "Aloe Vera": {
                "schedule": {
                    "💦 How Many Times/Week": ["0.5 times/week (≈ once every 2 weeks)"],
                    "🧴 Water Quantity (Litres per Time)": ["0.1 L (100 ml)"],
                    "🌤 Total Water per Week (Approx.)": ["0.05 L/week (50 ml)"]
                },
                "adjustments": [
                    "Temperature < 16°C → reduce watering, keep indoors.",
                    "Temperature > 30°C → increase frequency slightly but avoid sunburn.",
                    "Humidity high → allow soil to dry completely before next watering."
                ]
            },
            "Peace Lily": {
                "schedule": {
                    "💦 How Many Times/Week": ["2 times/week"],
                    "🧴 Water Quantity (Litres per Time)": ["0.2 L (200 ml)"],
                    "🌤 Total Water per Week (Approx.)": ["0.4 L/week"]
                },
                "adjustments": [
                    "Temperature < 18°C → reduce watering frequency.",
                    "High humidity → maintain normal watering.",
                    "Low humidity → mist leaves occasionally."
                ]
            },
            "Snake Plant (Sansevieria)": {
                "schedule": {
                    "💦 How Many Times/Week": ["0.5 times/week (≈ once every 2 weeks)"],
                    "🧴 Water Quantity (Litres per Time)": ["0.1 L (100 ml)"],
                    "🌤 Total Water per Week (Approx.)": ["0.05 L/week (50 ml)"]
                },
                "adjustments": [
                    "Water sparingly in winter or cold conditions.",
                    "High temperatures → may water slightly more often."
                ]
            },
            "Spider Plant (Chlorophytum)": {
                "schedule": {
                    "💦 How Many Times/Week": ["1–2 times/week"],
                    "🧴 Water Quantity (Litres per Time)": ["0.15 L (150 ml)"],
                "🌤 Total Water per Week (Approx.)": ["0.2 L/week (200 ml)"]
                },
                "adjustments": [
                    "Temperature extremes → reduce watering.",
                    "Low humidity → occasional misting recommended."
                ]
            },
            "Money Plant (Pothos)": {
                "schedule": {
                    "💦 How Many Times/Week": ["1–2 times/week"],
                    "🧴 Water Quantity (Litres per Time)": ["0.15–0.2 L (150–200 ml)"],
                    "🌤 Total Water per Week (Approx.)": ["0.25–0.3 L/week"]
                },
                "adjustments": [
                    "Hot, dry conditions → water more frequently.",
                    "Cool or rainy → reduce watering."
                ]
            }
        }

    # -------------------- API Key Input and Client Setup Section --------------------

    gemini_key = st.text_input(
        "🔑 **Enter your Gemini API Key:** (Needed for custom plant search)", 
        type="password", 
        value=st.session_state["gemini_api_key"],
        help="Get a key from Google AI Studio. The key is required to use the 'AI Care Schedule' feature."
    )

    if gemini_key:
        if st.session_state["gemini_api_key"] != gemini_key:
            st.session_state["gemini_api_key"] = gemini_key
            if initialize_gemini_client(gemini_key):
                st.success("Gemini client initialized successfully!")
            else:
                st.warning("Could not initialize Gemini client. Custom plant search may not work.")
        else:
            initialize_gemini_client(gemini_key)
    else:
        st.info("Please enter your API key to enable the AI Care Schedule feature.")


    # -------------------- Plant Selection (First Interaction) --------------------
    plant_names = ["Select a plant"] + list(st.session_state["plants_data"].keys())
    selected_plant = st.selectbox("🌱 Select a plant:", plant_names, index=plant_names.index(st.session_state.selected_plant) if st.session_state.selected_plant in plant_names else 0)
    st.session_state.selected_plant = selected_plant

    # -------------------- Custom Plant Input Feature (Secondary Interaction) --------------------
    st.markdown("---") 
    st.markdown("#### 🤔 Couldn't find your plant? Get AI help!")

    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            new_plant_name = st.text_input("📝 Enter the name of your new plant:", value="", key="new_plant_name_input", help="If your plant isn't listed above, type its name here.")
        
        with col2:
            pot_size = st.selectbox(
                "📏 Select Approximate Pot Size (Diameter):",
                options=["10 cm (Small)", "15 cm (Medium)", "20 cm (Large)", "25+ cm (Very Large)"],
                key="pot_size_input",
                index=1, 
                help="Pot size helps the AI estimate the correct water volume."
            )

        if new_plant_name and new_plant_name not in st.session_state["plants_data"]:
            
            if st.button(f"🔍 Get AI Care Schedule for **{new_plant_name}**"):
                
                with st.spinner(f"Please wait while the AI fetches the best care schedule for **{new_plant_name}** for a {pot_size} pot..."):
                    
                    new_data_dict, new_data_details_dict = get_plant_details_from_gemini(new_plant_name, pot_size)

                if new_data_dict and new_data_details_dict:
                    st.session_state["plants_data"].update(new_data_dict)
                    st.session_state["plants_data_"].update(new_data_details_dict)

                    st.session_state.selected_plant = new_plant_name 
                    st.session_state["custom_plant_name"] = new_plant_name 
                    st.success(f"Plant **{new_plant_name}** added! Schedule generated by AI for a {pot_size} pot.")
                    st.rerun() 
                else:
                    DEFAULT_FREQUENCY = 1.0  
                    DEFAULT_WATER_QTY = f"0.2 L (200 ml) for {pot_size} pot" 
                    
                    st.session_state["plants_data"][new_plant_name] = {"times_per_week": DEFAULT_FREQUENCY}
                    st.session_state["plants_data_"][new_plant_name] = {
                        "schedule": {
                            "💦 How Many Times/Week": [f"{DEFAULT_FREQUENCY} time/week (Manual Fallback)"],
                            "🧴 Water Quantity (Litres per Time)": [DEFAULT_WATER_QTY],
                            "🌤 Total Water per Week (Approx.)": ["Custom - Based on Manual Default"]
                        },
                        "adjustments": [
                            "**Custom Plant (Manual Fallback):** The schedule above uses a default of 1 water per week. Please adjust dates/times manually to fit your plant's specific needs.",
                            "Add your own care notes here."
                        ]
                    }
                    st.session_state.selected_plant = new_plant_name
                    st.session_state["custom_plant_name"] = new_plant_name
                    st.warning(f"AI failed or key missing. Plant **{new_plant_name}** added with a manual fallback schedule.")
                    st.rerun() 
                    
        st.markdown("---")

    # -------------------- Plant Details and Scheduling Logic --------------------
    plants_data = st.session_state["plants_data"]
    plants_data_ = st.session_state["plants_data_"]

    if selected_plant != "Select a plant":
        
        if selected_plant in plants_data:
            frequency = plants_data[selected_plant]["times_per_week"]
            days_needed = max(1, int(round(frequency))) 
            
            st.info(f"💡 **{selected_plant}** needs watering {days_needed} time(s) per week.")

            plant_info = plants_data_[selected_plant]
            with st.container():
                st.markdown(f"### 🌿 {selected_plant} Care Schedule")
                df = pd.DataFrame(plant_info["schedule"])
                st.table(df)

                st.markdown("**💡 Adjustment Notes:**")
                for note in plant_info["adjustments"]:
                    st.markdown(f"- {note}")


    # -------------------- Select Dates --------------------
            st.markdown(f"### 📅 Select {days_needed} date(s) for watering:")
            
            today = datetime.today()
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            
            week_dates = [start_date + timedelta(days=i) for i in range(7)]
            week_dates_str = [d.strftime("%A, %d %b %Y") for d in week_dates]

            selected_dates = st.multiselect(
                f"Select exactly {days_needed} date(s):",
                options=week_dates_str,
                default=st.session_state.selected_dates
            )
            st.session_state.selected_dates = selected_dates

            if len(selected_dates) > days_needed:
                st.warning(f"⚠️ You can only select {days_needed} date(s) for this plant.")
            elif len(selected_dates) < days_needed:
                st.info(f"Select {days_needed} date(s) for full coverage.")

            # -------------------- Select Times --------------------
            watering_times = []
            if selected_dates and len(selected_dates) <= days_needed:
                st.markdown("### ⏰ Select watering time for each date:")
                num_selected = len(selected_dates)
                
                if len(st.session_state.watering_times) < num_selected:
                    st.session_state.watering_times.extend([time(9, 0).strftime("%H:%M")] * (num_selected - len(st.session_state.watering_times)))
                    
                for i, date_str in enumerate(selected_dates):
                    
                    default_time_obj = time(9, 0)
                    if i < len(st.session_state.watering_times):
                        time_str_val = st.session_state.watering_times[i]
                        try:
                            default_time_obj = datetime.strptime(time_str_val, "%H:%M").time()
                        except ValueError:
                            default_time_obj = time(9, 0)

                    t = st.time_input(f"Time for {date_str}:", value=default_time_obj, key=f"time_{selected_plant}_{i}")
                    watering_times.append(t.strftime("%H:%M"))

            st.session_state.watering_times = watering_times

            # -------------------- Add Reminder to Schedule --------------------
            if st.button("✅ Add Reminder to Schedule"):
                if len(selected_dates) != days_needed:
                    st.error(f"Please select exactly {days_needed} date(s) to add reminder.")
                else:
                    base_qty_str = plant_info["schedule"]["🧴 Water Quantity (Litres per Time)"][0]
                    base_qty_ml = parse_base_quantity_ml(base_qty_str) # Get the base quantity in mL

                    # UPDATED: Run FLS calculation and UNPACK ALL 5 RETURN VALUES
                    percent_adj, current_temp, final_qty_ml, temp_category, percent_category = calculate_adjusted_water(base_qty_ml)

                    new_rows = []
                    for date, wtime in zip(selected_dates, watering_times):
                        new_rows.append({
                                "Plant": selected_plant,
                                "Date": date,
                                "Time": wtime,
                                "Water Quantity": base_qty_str, # Keep original AI quantity for reference
                                "Base Qty (mL)": base_qty_ml,
                                "Temp (°C)": current_temp,
                                "Adj (%)": percent_adj,
                                "Final Qty (mL)": final_qty_ml,
                                "Temp Category": temp_category,     # NEW
                                "Adj Category": percent_category    # NEW
                            })
                    
                    new_df = pd.DataFrame(new_rows)
                    st.session_state["watering_schedule"] = pd.concat([st.session_state["watering_schedule"], new_df], ignore_index=True)

                    st.success(f"Reminder added! **FLS Suggestion: {final_qty_ml:.0f} mL** (Temp: {temp_category}, Adj: {percent_category})")

                    # Reset selections
                    st.session_state.selected_plant = "Select a plant"
                    st.session_state.selected_dates = []
                    st.session_state.watering_times = []
                    st.rerun() 

    # -------------------- Display Current Schedule --------------------
    if not st.session_state["watering_schedule"].empty:
        st.markdown("---") 
        st.markdown("### 📋 Current Watering Schedule")
        # Display the full schedule with FLS results, excluding only the Base Qty in mL
        display_df = st.session_state["watering_schedule"].drop(columns=["Base Qty (mL)"]).drop_duplicates()
        st.table(display_df) 

        # -------------------- User Email Input --------------------
        user_email = st.text_input("📧 Enter your email to send full schedule and get automatic reminders:")

        if st.button("📨 Send Full Schedule and Schedule Reminders"):
            if not user_email:
                st.error("Please enter an email address.")
            elif not is_valid_email(user_email):
                st.error("⚠️ Invalid email format!")
            else:
                try:
                    # 1️⃣ Send full schedule immediately
                    sender_email = "plantwateringremainder@gmail.com"
                    sender_password = "egbr wiiv xzye mrgo" 

                    message = MIMEMultipart("alternative")
                    message['Subject'] = "🌿 Your Full Plant Watering Schedule"
                    message['From'] = sender_email
                    message['To'] = user_email

                    html_table = display_df.to_html(index=False)
                    html_content = f"""
                    <html>
                    <body>
                    <p>Hello! Here is your full watering schedule so far:</p>
                    {html_table}
                    <p>You will also receive automatic email reminders for each scheduled time.</p>
                    </body>
                    </html>
                    """
                    message.attach(MIMEText(html_content, "html"))

                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                        server.login(sender_email, sender_password)
                        server.sendmail(sender_email, user_email, message.as_string())

                    st.success("✅ Full schedule sent successfully!")

                    # 2️⃣ Schedule automatic email reminders (MODIFIED to pass FLS results and categories)
                    for idx, row in st.session_state["watering_schedule"].drop_duplicates().iterrows():
                        
                        # FLS variables from the stored DataFrame row
                        base_qty_str = row['Water Quantity'] 
                        temp_c = row['Temp (°C)']
                        percent_adj = row['Adj (%)']
                        final_qty_ml = row['Final Qty (mL)']
                        temp_category = row['Temp Category']        # NEW
                        percent_category = row['Adj Category']      # NEW
                        
                        plant = row['Plant']
                        date_str = row['Date']
                        time_str = row['Time']
                        
                        full_datetime_str = f"{date_str} {time_str}" 
                        reminder_datetime = datetime.strptime(full_datetime_str, "%A, %d %b %Y %H:%M")
                        
                        if reminder_datetime > datetime.now():
                            job_id = f"reminder_{idx}_{plant.replace(' ', '_')}_{reminder_datetime.timestamp()}"
                            scheduler.add_job(send_reminder_email, 'date', run_date=reminder_datetime,
                                            # UPDATED ARGS: includes the new categories
                                            args=[user_email, plant, date_str, time_str, base_qty_str, temp_c, percent_adj, final_qty_ml, temp_category, percent_category], 
                                            id=job_id, 
                                            replace_existing=True)
                    st.info("⏰ Automatic reminders scheduled, including environment-adjusted quantities and fuzzy categories.")

                except Exception as e:
                    st.error(f"Error sending email/scheduling: {e}")


if __name__ == "__main__":
    main()