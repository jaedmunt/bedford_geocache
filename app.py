import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from folium import PolyLine
from math import radians, sin, cos, sqrt, atan2
import what3words
from streamlit_js_eval import get_geolocation

st.title("Bedford Geocache")

# Initialize session state variables
if 'user_coords' not in st.session_state:
    st.session_state.user_coords = ''
if 'current_location' not in st.session_state:
    st.session_state.current_location = None
# Initialize our dataframe with the proper columns if not already set
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Latitude", "Longitude", "Assigned_To", "What3Words"])

# A simple distance function (in km)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 2)

# Helper to parse coordinates from a text string
def prepare_coords(coords_text):
    # Expecting each line to be "lat, long"
    coords = [line.strip().split(',') for line in coords_text.strip().split('\n') if line.strip()]
    return [[float(lat.strip()), float(lon.strip())] for lat, lon in coords]

# Instructions and test format
st.write("Test coordinates (Center Parcs): 50.9588, -1.2753")
message_format = "50.9588, -1.2753\n52.99648, -1.1581"
st.info(f"Format: lat, long (comma separated) with each on a newline:\n{message_format}")

# Input coordinates
user_input = st.text_area("Enter coordinates", value=st.session_state.user_coords)
if user_input:
    st.session_state.user_coords = user_input
    
    # A copy button (using JS to copy to clipboard)
    st.button("Copy Coordinates", on_click=lambda: st.write(
        '<script>navigator.clipboard.writeText(`' + user_input + '`);</script>', 
        unsafe_allow_html=True
    ))

    try:
        # Parse the entered coordinates
        coords = prepare_coords(user_input)
        
        # Create or update the dataframe based on the number of coordinates entered
        if st.session_state.df.empty or len(st.session_state.df) != len(coords):
            st.session_state.df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df["Assigned_To"] = "Unassigned"
            st.session_state.df["What3Words"] = ""
        else:
            # If the dataframe already exists, update only the coordinates while keeping assignments and words
            temp_df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df[["Latitude", "Longitude"]] = temp_df

        # Get current location (via browser geolocation)
        if st.button("Get Current Location"):
            try:
                loc = get_geolocation()
                st.session_state.current_location = [loc["coords"]["latitude"], loc["coords"]["longitude"]]
                st.success(f"Current location: {st.session_state.current_location}")
            except Exception as e:
                st.error("Could not get current location from browser")

        st.subheader("Location Assignments")
        people = ['Unassigned', 'Tilly', 'Jaedon', 'Phil', 'Cally', 'Mitch', 'Freye']
        # Use a fixed key for the data editor so that changes persist
        edited_df = st.data_editor(
            st.session_state.df,
            key="data_editor",
            column_config={
                "Assigned_To": st.column_config.SelectboxColumn(
                    "Assigned To",
                    options=people,
                    required=True
                ),
                "What3Words": st.column_config.TextColumn(
                    "What3Words",
                    help="Click 'Generate What3Words' to populate"
                )
            }
        )
        # Update the session dataframe from the editor
        st.session_state.df = edited_df

        # Generate What3Words for each coordinate when the button is clicked
        if st.button("Generate What3Words"):
            # Read your API key from secrets
            W3W_KEY = st.secrets.WHAT3WORDS["WHAT3WORDS_API_KEY"]
            if not W3W_KEY:
                st.error("What3Words API key not found. Please set WHAT3WORDS_API_KEY in your secrets.")
            else:
                w3w = what3words.Geocoder(W3W_KEY)
                for idx, row in st.session_state.df.iterrows():
                    try:
                        # Call the API using the latitude and longitude values
                        res = w3w.convert_to_3wa(coordinates={"lat": row['Latitude'], "lng": row['Longitude']})
                        words = res.get('words', '')
                        st.session_state.df.at[idx, 'What3Words'] = words
                    except Exception as e:
                        st.error(f"Error getting what3words for location {idx+1}: {str(e)}")
                st.success("What3Words generated successfully!")
                # Rerun the app so that the data editor (and later the map) shows the new values
                st.experimental_rerun()

        # Create the map only if we have some coordinates in our dataframe
        if not st.session_state.df.empty:
            # Use the first coordinate as the center
            center = [st.session_state.df.iloc[0]['Latitude'], st.session_state.df.iloc[0]['Longitude']]
            m = folium.Map(location=center, zoom_start=10)
            colors = {'Tilly': 'red', 'Jaedon': 'blue', 'Phil': 'green',
                      'Cally': 'purple', 'Mitch': 'orange', 'Freye': 'pink',
                      'Unassigned': 'gray'}

            # Add a marker for your current location (if available)
            if st.session_state.current_location:
                folium.Marker(
                    location=st.session_state.current_location,
                    icon=folium.Icon(color='green', icon='home'),
                    popup='Current Location'
                ).add_to(m)

            # Add a marker for each coordinate from the dataframe
            for idx, row in st.session_state.df.iterrows():
                color = colors.get(row['Assigned_To'], 'gray')
                popup_text = f"Location {idx+1}<br>Assigned: {row['Assigned_To']}"
                if row['What3Words']:
                    popup_text += f"<br>W3W: {row['What3Words']}"
                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    icon=folium.Icon(color=color, icon='info-sign'),
                    popup=popup_text
                ).add_to(m)
                # Draw a line from current location (if available) to the coordinate
                if st.session_state.current_location:
                    PolyLine(
                        locations=[st.session_state.current_location, [row['Latitude'], row['Longitude']]],
                        weight=2,
                        color=color,
                        opacity=0.8
                    ).add_to(m)
            st_folium(m, width=700, height=500)

            # If you have a current location, display a table with the distances
            if st.session_state.current_location:
                st.subheader("Distances from current location")
                distances = []
                for idx, row in st.session_state.df.iterrows():
                    distance = calculate_distance(
                        st.session_state.current_location[0],
                        st.session_state.current_location[1],
                        row['Latitude'],
                        row['Longitude']
                    )
                    distances.append({
                        'Location': f"Location {idx+1}",
                        'Assigned_To': row['Assigned_To'],
                        'Distance_km': distance,
                        'What3Words': row['What3Words']
                    })
                st.dataframe(pd.DataFrame(distances))

            # Enable CSV download of your dataframe
            csv = st.session_state.df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "geocache_locations.csv",
                "text/csv"
            )

    except Exception as e:
        st.error(f"Error processing coordinates: {str(e)}")
