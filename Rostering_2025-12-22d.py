# -*- coding: utf-8 -*-
"""
Created on Thu Dec 18 12:25:41 2025

@author: Daniel
"""

import pdfplumber
import pandas as pd
import itertools
from scipy.optimize import linear_sum_assignment
import sys
import numpy as np
import streamlit as st
import csv
import re
import io

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def Create_Skills_Matrix(Roster_Availability_Export):
    if Roster_Availability_Export is None:
        return None

    try:
        # Decode the BytesIO object to strings for the csv reader
        stringio = io.StringIO(Roster_Availability_Export.getvalue().decode("utf-8"))
        
        Skills_Matrix_Uniform_Rows = []
        reader = csv.reader(stringio) 
        
        for row in reader:
            Uniform_Row = (row + [''] * 1)[:1] 
            Skills_Matrix_Uniform_Rows.append(Uniform_Row)
                
    except FileNotFoundError:
        st.warning("Error: The Roster Availability Export file was not found.")
    except Exception as e:
        st.warning(f"An unexpected error occurred during file reading: {e}")
        
    Header = Skills_Matrix_Uniform_Rows[0] 
    Data_Rows = Skills_Matrix_Uniform_Rows[1:]
    
    # Create DataFrame from CSV data
    Skills_Matrix_One_Col = pd.DataFrame(Data_Rows, columns=Header)
    Skills_Matrix_One_Col.fillna('', inplace=True)
    Skills_Matrix_One_Col = Skills_Matrix_One_Col.astype(str)
    Skills_Matrix = Skills_Matrix_One_Col['Roster Availability'].str.split('\t', expand=True)
    
    # Remove empty columns and top 2 miscelaneous rows
    Skills_Matrix = Skills_Matrix.iloc[2:]
    Skills_Matrix = Skills_Matrix.iloc[:, :-2]
    
    # Name colums
    Skills_Matrix2 = Skills_Matrix.rename(columns={0: 'Run', 1: 'Monday',2:'Tuesday',3:'Wednesday',4:'Thursday',5:'Friday',6:'Saturday',7:'Sunday'})
    Skills_Matrix3 = Skills_Matrix2.fillna(value='')
    
    # Remove empty rows
    rows_to_remove = (Skills_Matrix3 == '').all(axis=1)
    Skills_Matrix4 = Skills_Matrix3[~rows_to_remove]
    
    
    break_strings2 = Skills_Matrix4['Run'].to_list()
    break_strings3 = [item for item in break_strings2 if item]
    break_strings = set(break_strings3)
    
    # Create a boolean mask: True if the cell in 'col1' is in the set of break_strings
    mask = Skills_Matrix4['Run'].isin(break_strings)
    
    # Use cumsum to assign a unique group ID starting from the first True occurrence
    # The group ID changes every time a 'break string' is encountered
    group_ids = mask.cumsum()
    
    # Group by the generated IDs
    grouped = Skills_Matrix4.groupby(group_ids)
    
    # Create a dictionary of DataFrames for easy access, keyed by the first value in 'col1'
    dict_of_dfs = {group.iloc[0]['Run']: group for name, group in grouped}
        
    # =============================================================================
    # USE ROSTER AVAILABILITY EXTRACT TO BUILD SKILLS MATRIX
    # =============================================================================
    
    def abbreviate_keys(original_dict):
        new_dict = {}
        for key, value in original_dict.items():
            # Find first letter of words OR any sequence of digits
            parts = re.findall(r'\b[a-zA-Z]|\d+', key)
            new_key = "".join(parts).upper()
            new_dict[new_key] = value
        return new_dict
    
    # Example Usage
    
    transformed_dfs_dict = abbreviate_keys(dict_of_dfs)
    
    extracted_data = []
    
    for run_key, df in transformed_dfs_dict.items():
        # Use the run name from the dictionary key (or df.iloc[0,0])
        run_name = run_key 
        
        # Iterate through specified columns (indices 1 to 6)
        driver_cols = df.iloc[:, 1:7]
        
        for col in driver_cols:
            for entry in df[col].dropna():
                # Match "Firstname Lastname Integer"
                match = re.search(r'(.+)\s(\d+)$', str(entry).strip())
                if match:
                    driver_name = match.group(1).strip()
                    skill_level = int(match.group(2))
                    
                    extracted_data.append({
                        'Run': run_name,
                        'Driver': driver_name,
                        'Skill': skill_level
                    })
    
    # Create a long-format DataFrame
    temp_df = pd.DataFrame(extracted_data)
    
    # Create the intersection table
    final_df = temp_df.pivot_table(
        index='Driver', 
        columns='Run', 
        values='Skill', 
        aggfunc='first' # Since skill level is repeated, 'first' or 'max' works
    )
    
    # Optional: Fill missing values if a driver didn't participate in a specific run
    final_df = final_df.fillna(0)
    Skill_Matrix_Final = final_df.replace(0, np.nan)
    
    return Skill_Matrix_Final


def Extract_Ops_Roster(Ops_Roster_Path, Date_Selected):
    
    # List to collect data from rows from all pages
    Data_Rows = []
    Header = None
    
    with pdfplumber.open(Ops_Roster_Path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                # Capture the header from the first available table
                if Header is None:
                    Header = table[0]
                    Data_Rows.extend(table[1:]) # Add data skipping the first row
                else:
                    Data_Rows.extend(table[::])
    
    if Data_Rows:
        # Create master DataFrame from all collected rows
        Roster_Existing_Raw = pd.DataFrame(Data_Rows, columns=Header)
        Roster_Existing_Raw = Roster_Existing_Raw.rename(columns={'': 'Driver'})
        
        # Filter for the specific date column
        Date_Mask = Roster_Existing_Raw.columns.str.contains(Date_Selected)
    
        if not Date_Mask.any():
            st.warning(
                f"No column matching the selected date ({Date_Selected}) "
                "was found in the uploaded PDF. Please check your upload."
            )
            st.stop()
        
        Runs_Col = Roster_Existing_Raw.loc[:, Date_Mask]
        
        Roster_Existing = pd.concat([Roster_Existing_Raw['Driver'], Runs_Col], axis=1)
        Roster_Existing.columns = ['Driver', Date_Selected]
        
        # Remove incorrectl;y inputted rows + remove numbers from end of driver name 
        Roster_Existing = Roster_Existing.dropna(subset=[Date_Selected])
        Roster_Existing.loc[:, 'Driver'] = Roster_Existing['Driver'].str.replace(r'\d+', '', regex=True)
        return Roster_Existing
    else:
        st.warning("PDF upload failed, script terminated, report this to PH: 022 375 4934.")
        st.stop()



# =============================================================================
# USER INPUTS ROUND 1
# =============================================================================

st.info("Thank you for testing this programme, please share any changes that would improve your experience and report any bugs that you encounter.")

st.set_page_config(
    page_title="Last-Minute Rostering",
    page_icon="🚚",
    layout="wide"
)

st.title("Roster Suggest")
st.caption("Enable last minute roster changes that minimise driver movements whilst maintaining skill coverage")

# =============================================================================
# SIDEBAR INPUTS
# =============================================================================

st.sidebar.header("Inputs") 

Roster_Availability_Export = st.sidebar.file_uploader(
    "Upload Roster Availability Export",
    type="tsv"
)

Ops_Roster_Path = st.sidebar.file_uploader(
    "Upload Ops Roster PDF",
    type="pdf"
)

Date_Inputted = st.sidebar.date_input(
    "Select roster date",
    format="DD/MM/YYYY",
    value = None
)

if Date_Inputted:
    Date_Selected = Date_Inputted.strftime("%d/%m")


st.sidebar.divider()
st.sidebar.subheader("Replacement Rules")

Include_Auto_All_Not_Present_Drivers_As_Replacement = st.sidebar.checkbox(
    "Auto-include all non-rostered drivers",
    False
)

Include_Auto_Trainee_As_Replacement = st.sidebar.checkbox(
    "Include trainees as replacements",
    False
)

if Include_Auto_Trainee_As_Replacement == True and Include_Auto_All_Not_Present_Drivers_As_Replacement == True:
    Force_Use_Trainees = st.sidebar.checkbox(
        "Force use of trainees as replacements",
        False
    )
    if Force_Use_Depot == True:
        st.sidebar.info("Improvements are coming to the 'Force use of trainees' feature")

    
else:
    Force_Use_Trainees = False

Include_Allow_Depot_Run_Driver_As_Replacement_AND_Cancel_Depot_Run = st.sidebar.checkbox(
    "Cancel depot runs and include depot drivers",
    False
    )

if Include_Allow_Depot_Run_Driver_As_Replacement_AND_Cancel_Depot_Run == True and Include_Auto_All_Not_Present_Drivers_As_Replacement == True:
    Force_Use_Depot = st.sidebar.checkbox(
        "Force use of depot drivers as replacements",
        False
    )
    if Force_Use_Depot == True:
        st.sidebar.info("Improvements are coming to the 'Force use of depot drivers' feature")
    
else:
    Force_Use_Depot = False

Minimum_Skill_Level = st.sidebar.slider(
    "Minimum Replacement Skill Level Required",
    1, 10, 5
)

# =============================================================================
# LOAD DATA
# =============================================================================

if Ops_Roster_Path and Roster_Availability_Export and Date_Inputted is not None:
    Skills_Matrix = Create_Skills_Matrix(Roster_Availability_Export)
    Roster_Original = Extract_Ops_Roster(
        Ops_Roster_Path,
        Date_Selected
    )
    
else:
    st.info("Upload files, select a date and press the button to begin")
    st.stop()

Absent_Drivers = []
Replacement_Drivers = []

# =============================================================================
# MATCH NAME IN SKILLS MATRIX AND ROSTER ORIGINAL
# =============================================================================
if len(Skills_Matrix) == len(Roster_Original):
    Skills_Matrix.index = Roster_Original['Driver']
else:
    st.warning("Number of rows in skills matrix does not match number of rows in roster. It is likely that the Roster PDF was unable to be extracted")
Skills_Matrix = Skills_Matrix.filter(regex='^(DR\d|R[A-Z]|V\d|G|FW)', axis=1) # Only keep runs, remove Logistics Manager, Driver Trainer etc
Skills_Matrix = Skills_Matrix.dropna(how='all')
Skills_Matrix = Skills_Matrix.reset_index()

# =============================================================================
# FILTER DRIVERS ELIGIBLE TO BE ABSENT
# =============================================================================
Drivers_All = Roster_Original
Is_A_Driver = Drivers_All['Driver'].isin(Skills_Matrix['Driver'])

On_Original_Roster_Statuses = tuple(Skills_Matrix.columns.to_list())
Is_Scheduled_To_Work_Mask = Drivers_All[Date_Selected].str.startswith(
    On_Original_Roster_Statuses,
    na=False
)

Is_Not_Trainee_Mask = ~ (Drivers_All[Date_Selected].str.endswith('(T)', na=False))
Trainees = Drivers_All[~ (Is_Not_Trainee_Mask)]

if Include_Allow_Depot_Run_Driver_As_Replacement_AND_Cancel_Depot_Run:
    Is_Not_Depot_Run_Driver_Mask = ~Drivers_All[Date_Selected].str.startswith(
        'DR',
        na=False
    )
    Can_Be_Absent_Mask = (
        Is_Scheduled_To_Work_Mask &
        Is_Not_Trainee_Mask &
        Is_Not_Depot_Run_Driver_Mask
    )
else:
    Can_Be_Absent_Mask = (
        Is_Scheduled_To_Work_Mask &
        Is_Not_Trainee_Mask
    )

Drivers_Present_NonTrainee = Drivers_All[Can_Be_Absent_Mask]
Absent_Drivers_Select_From = Drivers_Present_NonTrainee['Driver'].tolist()

# =============================================================================
# FILTER DRIVERS ELIGIBLE TO BE REPLACEMENTS
# =============================================================================

Can_Be_Replacement_Mask = ~ Can_Be_Absent_Mask
Drivers_NotPresent_NonTrainee = Drivers_All[
    Can_Be_Replacement_Mask & Is_Not_Trainee_Mask & Is_A_Driver
]

Replacement_Drivers_To_Select_From = (
    Drivers_NotPresent_NonTrainee['Driver'].tolist()
)


if Include_Auto_All_Not_Present_Drivers_As_Replacement:
    Replacement_Drivers.extend(Replacement_Drivers_To_Select_From)

if Include_Auto_Trainee_As_Replacement:
    trainee_list = Trainees['Driver'].tolist()
    Replacement_Drivers_To_Select_From.extend(trainee_list)
    Replacement_Drivers.extend(trainee_list)

if Include_Allow_Depot_Run_Driver_As_Replacement_AND_Cancel_Depot_Run:
    depot_list = Drivers_All[
        Drivers_All[Date_Selected].str.startswith('DR', na=False)
    ]['Driver'].tolist()
    Replacement_Drivers_To_Select_From.extend(depot_list)
    Replacement_Drivers.extend(depot_list)

Replacement_Drivers = list(dict.fromkeys(Replacement_Drivers))
Replacement_Drivers_To_Select_From = list(
    dict.fromkeys(Replacement_Drivers_To_Select_From)
)

# =============================================================================
# USER SELECTIONS
# =============================================================================

st.sidebar.divider()
st.sidebar.subheader("Manual Selection")

Absent_Drivers = st.sidebar.multiselect(
    "Select absent drivers",
    options=Absent_Drivers_Select_From
)

Manual_Replacement_Drivers = st.sidebar.multiselect(
    "Select replacement drivers",
    options=Replacement_Drivers_To_Select_From,
    default=Replacement_Drivers
)

Keep_In_Run_Drivers = st.sidebar.multiselect(
    "Drivers to keep on original run (do not move)",
    options=Drivers_Present_NonTrainee['Driver'].tolist()
)

Replacement_Drivers = Manual_Replacement_Drivers

process = st.sidebar.button(
    "▶ Process Roster",
    width='stretch'
)

# =============================================================================
# FIND PREFERRED DRIVERS
# =============================================================================

Preferred_Drivers = set()

if Force_Use_Trainees:
    trainee_list = Trainees['Driver'].tolist()
    Preferred_Drivers.update(
        d for d in trainee_list if d in Replacement_Drivers
    )

if Force_Use_Depot:
    depot_list = Drivers_All[
        Drivers_All[Date_Selected].str.startswith('DR', na=False)
    ]['Driver'].tolist()

    Preferred_Drivers.update(
        d for d in depot_list if d in Replacement_Drivers
    )

Preferred_Drivers = list(Preferred_Drivers)
N_preferred = len(Preferred_Drivers)


# =============================================================================
# PROCESS ROSTER
# =============================================================================

if not process and not st.session_state.get("optimisation_done", False):
    st.stop()

st.subheader("Input Summary")

# =============================================================================
# VALIDATION
# =============================================================================

if not Replacement_Drivers:
    st.error("No replacement drivers selected.")
    st.stop()

Invalid_Replacement = (
    Drivers_Present_NonTrainee['Driver']
    .isin(Replacement_Drivers)
)

if Invalid_Replacement.any():
    invalid_names = (
        Drivers_Present_NonTrainee
        .loc[Invalid_Replacement, 'Driver']
        .unique()
        .tolist()
    )
    st.warning(
        "The following drivers are already assigned and "
        "will be removed from replacements:\n\n"
        + "\n".join(f"- {d}" for d in invalid_names)
    )
    Replacement_Drivers = [
        d for d in Replacement_Drivers
        if d not in invalid_names
    ]

# =============================================================================
# BUILD AVAILABLE DRIVERS
# =============================================================================

Available_Drivers = Drivers_Present_NonTrainee.copy()

for driver in Replacement_Drivers:
    row = Drivers_All[Drivers_All['Driver'] == driver]
    if not row.empty:
        Available_Drivers = pd.concat(
            [Available_Drivers, row],
            ignore_index=True
        )

Available_Drivers = Available_Drivers[
    ~Available_Drivers['Driver'].isin(Absent_Drivers)
].reset_index(drop=True)

# =============================================================================
# DRIVERS ELIGIBLE FOR DISPLAY ONLY (NOT OPTIMISED)
# =============================================================================

Display_Only_Drivers = set()

# Trainees (always display-eligible)
Display_Only_Drivers.update(Trainees['Driver'].tolist())

# Include Depot drivers only if depot runs are cancelled
if Include_Allow_Depot_Run_Driver_As_Replacement_AND_Cancel_Depot_Run:
    Display_Only_Drivers.update(
        Drivers_All[
            Drivers_All[Date_Selected].str.startswith('DR', na=False)
        ]['Driver'].tolist()
    )
    
# =============================================================================
# FIND UNFILLED RUNS
# =============================================================================

Unfilled_Runs = (
    Drivers_Present_NonTrainee
    .loc[
        Drivers_Present_NonTrainee['Driver'].isin(Absent_Drivers),
        Date_Selected
    ]
    .tolist()
)

Operating_Runs = (
    Drivers_Present_NonTrainee[Date_Selected]
    .unique()
    .tolist()
)

# =============================================================================
# DISPLAY BASIC STATS
# =============================================================================

col1, col2, col3, col4 = st.columns(4)

col1.metric("Operating Runs", len(Operating_Runs))
col2.metric("Absent Drivers", len(Absent_Drivers))
col3.metric("Replacement Pool", len(Replacement_Drivers))
col4.metric("Runs to Fill", len(Unfilled_Runs))

st.success("Inputs validated. Optimisation ready to run.")

# =============================================================================
# REMOVE UNAVAILABLE DRIVERS FROM SKILLS MATRIX
# =============================================================================

Skills_Matrix_Available = Skills_Matrix[
    Skills_Matrix['Driver'].isin(Available_Drivers['Driver'])
].reset_index(drop=True)

# Store original assignments
original_assignments_lookup = (
    Drivers_All
    .set_index('Driver')[Date_Selected]
    .to_dict()
)

# =============================================================================
# IDENTIFY UNFILLED RUNS
# =============================================================================

all_operating_runs = sorted(
    Drivers_Present_NonTrainee[Date_Selected].unique().tolist()
)

N_gaps = len(Unfilled_Runs)
N_backup_drivers = len(Replacement_Drivers)
Total_runs = len(all_operating_runs)
Staying_drivers = len(Drivers_Present_NonTrainee) - len(Absent_Drivers)

if N_gaps > N_backup_drivers:
    st.error("Not enough replacement drivers to fill all unassigned runs.")
    st.stop()

if Staying_drivers + N_gaps != Total_runs:
    st.error("Driver/run mismatch — optimisation matrix is not square.")
    st.stop()

# =============================================================================
# OPTIMISATION
# =============================================================================
if process:
    min_moves_found = np.inf
    summary_results = []
    detailed_solutions = []
    
    skills_lookup = Skills_Matrix_Available.set_index('Driver')
    
    with st.spinner("Optimising roster combinations..."):
        for combo in itertools.combinations(Replacement_Drivers, N_gaps):
    
            # Force preferred driver usage
            if Preferred_Drivers:
                combo_set = set(combo)
        
                if N_preferred >= N_gaps:
                    # Only preferred drivers allowed
                    if not combo_set.issubset(Preferred_Drivers):
                        continue
                else:
                    # All preferred drivers must be included
                    if not set(Preferred_Drivers).issubset(combo_set):
                        continue
    
            combo_name = ", ".join(combo)
    
            drivers_fixed = Available_Drivers[
                ~Available_Drivers['Driver'].isin(Replacement_Drivers)
            ][['Driver']]
    
            drivers_test = pd.concat(
                [drivers_fixed, pd.DataFrame({'Driver': combo})],
                ignore_index=True
            )
    
            skills_combo = (
                Skills_Matrix_Available
                .set_index('Driver')
                .loc[drivers_test['Driver']]
                .reset_index()
            )
            
            cost_matrix = skills_combo[all_operating_runs].copy()
            cost_matrix = cost_matrix.where(cost_matrix >= Minimum_Skill_Level, np.nan)
            cost_matrix = cost_matrix.where(cost_matrix.isna(), 1)
            
            # Staying put = cost 0
            for i, d in enumerate(skills_combo['Driver']):
                orig_run = original_assignments_lookup.get(d)
                if orig_run in all_operating_runs:
                    cost_matrix.at[i, orig_run] = 0
            
            # FORCE keep-in-run drivers (cannot be reassigned)
            for i, d in enumerate(skills_combo['Driver']):
                if d in Keep_In_Run_Drivers:
                    orig_run = original_assignments_lookup.get(d)
                    for run in all_operating_runs:
                        if run != orig_run:
                            cost_matrix.at[i, run] = 1e9
            
            cost_matrix = cost_matrix.fillna(1e9).values
    
            row_idx, col_idx = linear_sum_assignment(cost_matrix)
            total_cost = cost_matrix[row_idx, col_idx].sum()
    
            if total_cost >= 1e9:
                summary_results.append({
                    "Backup Drivers": combo_name,
                    "Moves": np.nan,
                    "Avg Skill": np.nan,
                    "Low Skill Runs": np.nan
                })
                continue
    
            moves = int((cost_matrix[row_idx, col_idx] == 1).sum())
    
            assignment = pd.DataFrame({
                "Driver": skills_combo.iloc[row_idx]['Driver'].values,
                "Assigned_Run": [all_operating_runs[i] for i in col_idx]
            })
    
            assignment["Original_Run"] = assignment["Driver"].map(
                original_assignments_lookup
            )
    
            assignment["Moved"] = (
                assignment["Assigned_Run"] != assignment["Original_Run"]
            )
    
            assignment["Skill_Level"] = assignment.apply(
                lambda r: skills_lookup.at[r.Driver, r.Assigned_Run],
                axis=1
            )
            
            optimised_driver_set = set(assignment["Driver"])
            
            # =============================================================================
            # APPEND DISPLAY-ONLY DRIVERS (NOT OPTIMISED, NOT ABSENT)
            # =============================================================================
            
            assigned_drivers = set(assignment["Driver"])
            absent_set = set(Absent_Drivers)
            
            extra_rows = []
            
            for d in Display_Only_Drivers:
                if (
                    d not in assigned_drivers and
                    d not in absent_set and
                    d in original_assignments_lookup
                ):
                    orig_run = original_assignments_lookup[d]
            
                    if pd.isna(orig_run):
                        continue
                    
                    skills_lookup_displayonly = Skills_Matrix.set_index('Driver')
                    
                    orig_run_modified = orig_run.removesuffix(" (T)") if isinstance(orig_run, str) else orig_run
                    
                    skill_level = np.nan
                    if d in skills_lookup_displayonly.index:
                        if orig_run in skills_lookup_displayonly.columns:
                            skill_level = skills_lookup_displayonly.at[d, orig_run]
                        elif orig_run_modified in skills_lookup_displayonly.columns:
                            skill_level = skills_lookup_displayonly.at[d, orig_run_modified]
                    
                    extra_rows.append({
                        "Driver": d,
                        "Original_Run": orig_run,
                        "Assigned_Run": orig_run,
                        "Moved": False,
                        "Skill_Level": skill_level
                    })
            
            if extra_rows:
                assignment = pd.concat(
                    [assignment, pd.DataFrame(extra_rows)],
                    ignore_index=True
                )
    
            optimised_rows = assignment[
                assignment["Driver"].isin(optimised_driver_set)
            ]
            
            avg_skill = optimised_rows["Skill_Level"].mean()
            
            low_skill = (
                optimised_rows["Skill_Level"] < 6
            ).sum()
            
            summary_results.append({
                "Backup Drivers": combo_name,
                "Moves": moves,
                "Avg Skill": avg_skill,
                "Low Skill Runs": low_skill
            })
    
            if moves <= min_moves_found:
                min_moves_found = min(min_moves_found, moves)
       
            detailed_solutions.append({
            "Name": combo_name,
            "Moves": moves,
            "Data": assignment
            })

    # ✅ STORE RESULTS
    st.session_state["summary_df"] = pd.DataFrame(summary_results)
    st.session_state["detailed_solutions"] = detailed_solutions
    st.session_state["min_moves_found"] = min_moves_found
    st.session_state["optimisation_done"] = True

# =============================================================================
# SUMMARY DISPLAY
# =============================================================================
if st.session_state.get("optimisation_done", False):
    summary_df = st.session_state["summary_df"]
    detailed_solutions = st.session_state["detailed_solutions"]
    min_moves_found = st.session_state["min_moves_found"]

st.subheader("Optimisation Summary")

summary_df = summary_df.sort_values(
    ["Moves", "Avg Skill"],
    ascending=[True, False]
).reset_index(drop=True)

col1, col2, col3 = st.columns(3)
min_moves_display = summary_df["Moves"].min()
if min_moves_display.is_integer():
    min_moves_display = int(min_moves_display)
col1.metric("Min Moves", (min_moves_display))
col2.metric("Feasible Solutions", len(detailed_solutions))
col3.metric("Runs Filled", N_gaps)

def highlight_moves(val):
    if pd.isna(val):
        return ""
    if val == 0:
        return "background-color:#c6f6d5"
    if val <= 2:
        return "background-color:#faf089"
    return "background-color:#fed7d7"

st.dataframe(
    summary_df.style
        .map(highlight_moves, subset=["Moves"])
        .format({"Avg Skill": "{:.2f}",
                 "Low Skill Runs": "{:.0f}"}),
    width='stretch',
    height='auto'
)

# =============================================================================
# DETAILED SOLUTION VIEW (SELECTOR-BASED)
# =============================================================================

st.subheader("Detailed Assignment")

if not detailed_solutions:
    st.warning("No feasible solutions found.")
    st.stop()

# Build lookup
detailed_lookup = {sol["Name"]: sol for sol in detailed_solutions}

# Filter to feasible solutions only and keep ranking from summary_df
feasible_summary = summary_df[
    summary_df["Moves"].notna() &
    np.isfinite(summary_df["Moves"])
]

if feasible_summary.empty:
    st.warning("No feasible solutions available.")
    st.stop()

# Build selector labels
solution_labels = feasible_summary.apply(
    lambda r: f"{r['Backup Drivers']}", #|  Moves: {int(r['Moves'])}  |  Avg Skill: {r['Avg Skill']:.2f}",
    axis=1
).tolist()

selected_idx = st.selectbox(
    "Select a feasible solution to inspect",
    options=range(len(solution_labels)),
    format_func=lambda i: solution_labels[i]
)

selected_name = feasible_summary.iloc[selected_idx]["Backup Drivers"]
selected_solution = detailed_lookup[selected_name]

df = selected_solution["Data"].copy()

def row_style(row):
    if row.Skill_Level < 6:
        return ["background-color:#feb2b2"] * len(row)
    if row.Moved:
        return ["background-color:#faf089"] * len(row)
    return [""] * len(row)

styled_df = (
    df[["Driver", "Original_Run", "Assigned_Run", "Skill_Level", "Moved"]]
    .style
    .apply(row_style, axis=1)
    .format({"Skill_Level": "{:.0f}"})
)

st.dataframe(styled_df, width="stretch")

low = df[df["Skill_Level"] < 6]
if not low.empty:
    st.warning(f"{len(low)} driver(s) skill level ≤ 5")




