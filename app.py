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

# Initialize session state variables if they don't exist
if 'user_coords' not in st.session_state:
    st.session_state.user_coords = ''
if 'current_location' not in st.session_state:
    st.session_state.current_location = None
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(
        columns=["Latitude", "Longitude", "Assigned_To", "What3Words"]
    )

# A simple function to calculate distances (in km)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return round(R * c, 2)

# Function to parse user-entered coordinate text
def prepare_coords(coords_text):
    coords = []
    for line in coords_text.strip().split('\n'):
        if line.strip():
            parts = line.split(',')
            if len(parts) != 2:
                continue  # Skip lines that don't have two parts
            lat, lon = parts
            coords.append([float(lat.strip()), float(lon.strip())])
    return coords

# Display instructions and test coordinates
st.write("Test coordinates (Center Parcs): 50.9588, -1.2753")
message_format = "50.9588, -1.2753\n52.99648, -1.1581"
st.info(f"Format: lat, long (comma separated) with each on a newline:\n{message_format}")

# Text area for user to enter coordinates
user_input = st.text_area("Enter coordinates", value=st.session_state.user_coords)
if user_input:
    st.session_state.user_coords = user_input

    # Copy button to copy coordinates (using JS)
    st.button("Copy Coordinates", on_click=lambda: st.write(
        f'<script>navigator.clipboard.writeText(`{user_input}`);</script>',
        unsafe_allow_html=True
    ))
    
    try:
        # Parse the entered coordinates
        coords = prepare_coords(user_input)
        
        # Create or update the dataframe based on the number of coordinates
        if st.session_state.df.empty or len(st.session_state.df) != len(coords):
            st.session_state.df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df["Assigned_To"] = "Unassigned"
            st.session_state.df["What3Words"] = ""
        else:
            # If already created, update only the Latitude and Longitude values
            temp_df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df[["Latitude", "Longitude"]] = temp_df

        # Button to get current location via the browser
        if st.button("Get Current Location"):
            try:
                loc = get_geolocation()
                st.session_state.current_location = [
                    loc["coords"]["latitude"], loc["coords"]["longitude"]
                ]
                st.success(f"Current location: {st.session_state.current_location}")
            except Exception as e:
                st.error("Could not get current location from browser")

        st.subheader("Location Assignments")
        people = ['Unassigned', 'Tilly', 'Jaedon', 'Phil', 'Cally', 'Mitch', 'Freye']
        edited_df = st.data_editor(
            st.session_state.df,
            key="data_editor",
            column_config={
                "Assigned_To": st.column_config.SelectboxColumn(
                    "Assigned To", options=people, required=True
                ),
                "What3Words": st.column_config.TextColumn(
                    "What3Words", help="Click 'Generate What3Words' to populate"
                )
            }
        )
        # Update our session dataframe with any changes made in the editor
        st.session_state.df = edited_df

        # Button to generate What3Words addresses
        if st.button("Generate What3Words"):
            # Get your What3Words API key from Streamlit secrets
            W3W_KEY = st.secrets["WHAT3WORDS_API_KEY"]
            if not W3W_KEY:
                st.error("What3Words API key not found. Please set it in your secrets.")
            else:
                w3w = what3words.Geocoder(W3W_KEY)
                for idx, row in st.session_state.df.iterrows():
                    try:
                        # Call the What3Words API. Note: We pass a what3words.Coordinates object.
                        res = w3w.convert_to_3wa(
                            what3words.Coordinates(row['Latitude'], row['Longitude'])
                        )
                        words = res.get('words', '')
                        # Update the dataframe with the retrieved three-word address
                        st.session_state.df.at[idx, 'What3Words'] = words
                        st.code(f"Location {idx+1}: {words}")
                    except Exception as e:
                        st.error(f"Error getting What3Words for location {idx+1}: {str(e)}")
                st.success("What3Words generated successfully!")
                # Rerun the app so that the data editor (and map) refresh with updated What3Words values
                st.rerun()

        # Build the map if we have some coordinates
        if not st.session_state.df.empty:
            # Use the first coordinate as the map center
            center = [
                st.session_state.df.iloc[0]['Latitude'],
                st.session_state.df.iloc[0]['Longitude']
            ]
            m = folium.Map(location=center, zoom_start=10)
            colors = {
                'Tilly': 'red', 'Jaedon': 'blue', 'Phil': 'green',
                'Cally': 'purple', 'Mitch': 'orange', 'Freye': 'pink',
                'Unassigned': 'gray'
            }
            
            # Add a marker for the current location (if available)
            if st.session_state.current_location:
                folium.Marker(
                    location=st.session_state.current_location,
                    icon=folium.Icon(color='green', icon='home'),
                    popup='Current Location'
                ).add_to(m)
            
            # Add markers for each coordinate in the dataframe
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
                # Optionally, draw a line from current location to each coordinate
                if st.session_state.current_location:
                    PolyLine(
                        locations=[
                            st.session_state.current_location,
                            [row['Latitude'], row['Longitude']]
                        ],
                        weight=2,
                        color=color,
                        opacity=0.8
                    ).add_to(m)
            st_folium(m, width=700, height=500)

            # If current location is available, display distances
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

            # Allow CSV download of the updated dataframe
            csv = st.session_state.df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "geocache_locations.csv",
                "text/csv"
            )
            
    except Exception as e:
        st.error(f"Error processing coordinates: {str(e)}")