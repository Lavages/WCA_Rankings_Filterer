import streamlit as st
import requests
from io import StringIO
import pandas as pd
import traceback


# Load TSV files from Dropbox links
@st.cache_data
def load_data():
    dtypes_results = {
        'personId': 'string',
        'eventId': 'string',
        'personCountryId': 'string',
        'best': 'int32',
        'personName': 'string'  # Add personName to load it
    }
    dtypes_ranks = {
        'personId': 'string',
        'eventId': 'string',
        'countryRank': 'float32',
        'best': 'int32'
    }
    
    # Dropbox links - update these with your direct links (append '?dl=1' at the end of Dropbox share links)
    ranks_link = "https://www.dropbox.com/scl/fi/69fuhncnag3nelmvwzxb8/WCA_export_RanksSingle.tsv?rlkey=2t2bnehdbi25a40qyc659jxhv&st=on2qn571&dl=1"
    results_link = "https://www.dropbox.com/scl/fi/js90qjcxckuld3gmxi3lg/WCA_export_Results.tsv?rlkey=hdx54ocgglhhlg7bhp47t6ig6&st=dvu8mqhg&dl=1"

    # Function to read file from a Dropbox link
    def read_tsv_from_dropbox(link, dtype, usecols):
        try:
            response = requests.get(link)
            response.raise_for_status()  # Ensure the request succeeded
            return pd.read_csv(StringIO(response.text), sep="\t", dtype=dtype, usecols=usecols)
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching data from Dropbox: {e}")
            st.stop()

    # Load data from Dropbox
    results_df = read_tsv_from_dropbox(results_link, dtypes_results, ['personId', 'eventId', 'personCountryId', 'best', 'personName'])
    ranks_df = read_tsv_from_dropbox(ranks_link, dtypes_ranks, ['personId', 'eventId', 'countryRank', 'best'])
    
    return results_df, ranks_df


# Clear cache before loading fresh data
st.cache_data.clear()

# Load data
results_df, ranks_df = load_data()

# Check if the merged data is empty
if results_df.empty or ranks_df.empty:
    st.error("Error: One or both datasets are empty!")
    st.stop()

# Merge DataFrames on 'personId', 'eventId', and 'best' columns
@st.cache_data
def merge_data(results_df, ranks_df):
    return pd.merge(
        results_df,
        ranks_df,
        on=["personId", "eventId", "best"],
        how="inner"
    )

merged_df = merge_data(results_df, ranks_df)

# Get unique options for dropdowns
available_events = merged_df['eventId'].unique()
available_regions = merged_df['personCountryId'].unique()

# Function to format rank
def format_rank(rank):
    rank = int(rank)  # Ensure it's an integer
    if rank == 1:
        return f"{rank}st"
    elif rank == 2:
        return f"{rank}nd"
    elif rank == 3:
        return f"{rank}rd"
    else:
        return f"{rank}th"

# Function to format time for non-333mbf events
def format_time(centiseconds):
    centiseconds = int(centiseconds)  # Ensure centiseconds is an integer
    minutes, centiseconds = divmod(centiseconds, 6000)
    seconds, fractional = divmod(centiseconds, 100)
    return f"{minutes}:{seconds:02d}.{fractional:02d}" if minutes > 0 else f"{seconds}.{fractional:02d}"

# Function to decode and format the 333mbf result
def format_mbf_result(best):
    best_str = f"{int(best):08d}"  # Pad to ensure 8 digits
    total_points = int(best_str[:2])          # First two digits
    total_time_seconds = int(best_str[2:-2])  # Middle part
    missed_cubes = int(best_str[-2:])         # Last two digits

    solved_cubes = 99 - total_points + missed_cubes
    attempted_cubes = solved_cubes + missed_cubes
    minutes, seconds = divmod(total_time_seconds, 60)
    formatted_time = f"{minutes}:{seconds:02d}"
    return f"{solved_cubes}/{attempted_cubes} {formatted_time}"

# Function to format the best result based on event type
def format_best_result(event_id, best):
    if event_id == "333mbf":
        return format_mbf_result(best)
    elif event_id == "333fm":
        return str(best) if best < 100 else f"{best}"  # Directly display 2-digit results
    else:
        return format_time(best)

# Function to format the event name
def format_event_name(event_id):
    EVENT_DISPLAY_NAMES = {
        "333": "3x3",
        "222": "2x2",
        "444": "4x4",
        "555": "5x5",
        "666": "6x6",
        "777": "7x7",
        "333bf": "3x3 Blindfolded",
        "333fm": "3x3 Fewest Moves",
        "333oh": "3x3 One-Handed",
        "clock": "Clock",
        "minx": "Megaminx",
        "pyram": "Pyraminx",
        "skewb": "Skewb",
        "sq1": "Square-1",
        "444bf": "4x4 Blindfolded",
        "555bf": "5x5 Blindfolded",
        "333mbf": "3x3 Multi-Blind",
        "333mbo": "3x3 Multi-Blind Old Style",
        "magic": "Magic",
        "mmagic": "Master Magic",
        "333ft": "3x3 With Feet"
    }
    return EVENT_DISPLAY_NAMES.get(event_id, event_id)  # Default to event_id if not found in mapping

# Function to get the person at a specific rank
@st.cache_data
def get_person_by_rank(event_id, region, rank_number):
    filtered_df = merged_df.query("eventId == @event_id and personCountryId == @region")
    if rank_number == "lowest":
        rank_number = filtered_df['countryRank'].max()
    
    person_at_rank = filtered_df.loc[filtered_df['countryRank'] == rank_number].head(1)
    return person_at_rank.squeeze() if not person_at_rank.empty else None

# Streamlit App Layout
st.title("WCA Rankings Search")
st.markdown("Search WCA rankings by event, region, and rank with an easy-to-use interface.")

# Sidebar for inputs
st.sidebar.header("Search Criteria")

# Format the event dropdown with display names
formatted_events = {eid: format_event_name(eid) for eid in available_events}
event_id_display = st.sidebar.selectbox(
    "Select Event ID:",
    options=list(formatted_events.values()),  # Show user-friendly names
    index=0,
    help="Choose an event, e.g., '3x3' for 3x3x3 Cube."
)

# Get the internal eventId for processing
event_id = list(formatted_events.keys())[list(formatted_events.values()).index(event_id_display)]

# Region dropdown remains unchanged
region = st.sidebar.selectbox(
    "Select Region (Country ID):",
    options=available_regions,
    index=0,
    help="Choose a region, e.g., 'US' for United States."
)

# Rank number input remains unchanged
rank_number = st.sidebar.text_input(
    "Enter Rank Number (or 'lowest'):",
    "lowest",
    help="Enter the rank number or type 'lowest' for the lowest rank."
)

# Fetch and display results on button click
if st.sidebar.button("Search"):
    with st.spinner("Searching..."):
        try:
            # Convert rank_number to integer if it's not 'lowest'
            if rank_number.lower() != "lowest":
                rank_number = int(rank_number)
            else:
                rank_number = "lowest"

            # Get the person at the specified rank
            person_info = get_person_by_rank(event_id, region, rank_number)

            if person_info is not None:
                st.subheader(f"Rank Info for {person_info['personName']}")
                # Display information without "Field" and "Value" labels
                st.write(f"**Name**: {person_info['personName']}")
                st.write(f"**Event**: {format_event_name(person_info['eventId'])}")
                st.write(f"**Country**: {person_info['personCountryId']}")
                st.write(f"**Rank**: {format_rank(person_info['countryRank'])}")
                st.write(f"**Best Result**: {format_best_result(person_info['eventId'], person_info['best'])}")
            else:
                st.warning("No person found with the specified criteria.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.text(traceback.format_exc())  # Print the full traceback for debugging
