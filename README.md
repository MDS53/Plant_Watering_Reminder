# Plant Watering Reminder 

Project done by Shruthi Mailaram, Mohammad Salman, Priyanka Masina
## Steps to run this application


## Project Structure
```text
Plant_Watering_scheduler/
│
├── app.py                     # Main application file (entry point)
├── Fuzzy.py                   # Fuzzy logic implementation
├── requirements.txt           # List of required Python libraries
├── README.md                  # Project documentation and usage guide
│
├── Fuzzy Internal working.pdf # Detailed explanation of fuzzy logic workflow
├── Fuzzy Evaluation.pdf       # Fuzzy evaluation process and rule analysis
├── UI Navigation flow.pdf     # UI screens and navigation flow documentation
│
├── env/                       # API Key available here to copy and paste in UI 
```
##  Step 1: Create a Virtual Environment

It is recommended to use a virtual environment to avoid dependency conflicts.

### 🔹 Windows (PowerShell / CMD)

```sh
python -m venv venv
```
```sh
venv\Scripts\activate
```

### 🔹 macOS / Linux

```sh
python3 -m venv venv
```
```sh
source venv/bin/activate
```
##  Step 2: Install Required Libraries

All required libraries are listed in the `requirements.txt` file.

### 📄 List of Libraries
- Managed via `requirements.txt`

###  Installation Command

```sh
pip install -r requirements.txt
```
##  Step 3: Navigate to the Project Directory

Make sure your terminal is pointing to the folder containing `app.py`.

Example:

```sh
cd Plant_Watering_scheduler
```

##  Step 4: Run the Application (`app.py`)

This application is built using **Streamlit**, a Python framework for creating interactive web applications.

Running the application will:
- Start a local Streamlit server
- Open the app automatically in your default web browser
- Serve the application at: `http://localhost:8501`

---

###  Recommended Command (All OS)

```sh
streamlit run app.py
```

###  macOS (Alternative & Reliable Commands)

If the above command does not work on macOS, use one of the following:

#### 🔹 Using Python Module (Recommended for Virtual Environments)

```sh
python3 -m streamlit run app.py
```


