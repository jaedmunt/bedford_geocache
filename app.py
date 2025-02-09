import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geocoder
import requests
from folium import PolyLine
from math import radians, sin, cos, sqrt, atan2
import what3words
import os



st.title("Bedford Geocache")

# Initialize session state variables
if 'user_coords' not in st.session_state:
    st.session_state.user_coords = ''
if 'current_location' not in st.session_state:
    st.session_state.current_location = None
if 'df' not in st.session_state:
    st.session_state.df = None

# Check internet connectivity
def check_internet():
    try:
        requests.get("http://www.google.com", timeout=3)
        return True
    except requests.ConnectionError:
        return False

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return round(R * c, 2)

# Example coordinates and format
st.write("Test coordinates (Center Parcs): 50.9588, -1.2753")
message_format = """50.9588, -1.2753\n
                52.99648, -1.1581"""
                
st.info(f"Format: lat, long (comma separated) with each on a newline:\n{message_format}")

# Input coordinates
user_input = st.text_area("Enter coordinates", value=st.session_state.user_coords)

if user_input:
    st.session_state.user_coords = user_input
    
    # Copy button
    st.button("Copy Coordinates", on_click=lambda: st.write(
        '<script>navigator.clipboard.writeText(`' + user_input + '`);</script>', 
        unsafe_allow_html=True
    ))

    def prepare_coords(coords_text):
        coords = [line.strip().split(',') for line in coords_text.strip().split('\n') if line.strip()]
        return [[float(lat), float(lon)] for lat, lon in coords]

    try:
        coords = prepare_coords(user_input)
        
        # Create/Update DataFrame
        # Create/Update DataFrame and initialize What3Words key from dotenv
        W3W_KEY = st.secrets["WHAT3WORDS_API_KEY"]
        if not W3W_KEY:
            st.error("What3Words API key not found. Please set WHAT3WORDS_API_KEY in your .env file.")

        if st.session_state.df is None or st.session_state.df.empty:
            st.session_state.df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df["Assigned_To"] = "Unassigned"
            st.session_state.df["What3Words"] = ""
        else:
            # Update coordinates while preserving assignments and What3Words values
            temp_df = pd.DataFrame(coords, columns=["Latitude", "Longitude"])
            st.session_state.df[["Latitude", "Longitude"]] = temp_df
        # Get current location
        if check_internet() and st.button("Get Current Location"):
            try:
                g = geocoder.ip('me')
                if g.ok:
                    st.session_state.current_location = g.latlng
                    st.success(f"Current location: {g.latlng}")
            except Exception as e:
                st.error("Could not get current location")

        # People assignment
        st.subheader("Location Assignments")
        people = ['Unassigned', 'Tilly', 'Jaedon', 'Phil', 'Cally', 'Mitch', 'Freye']
        edited_df = st.data_editor(
            st.session_state.df,
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
        st.session_state.df = edited_df

        # Generate What3Words
        if st.button("Generate What3Words"):
            what3words_list = []
            w3w = what3words.Geocoder(W3W_KEY)
            for idx, row in edited_df.iterrows():
                try:
                    res = w3w.convert_to_3wa(f"{row['Latitude']},{row['Longitude']}")
                    words = res.get('words')
                    what3words_list.append(words)
                    edited_df.at[idx, 'What3Words'] = words
                    st.code(words, language=None)  # Displays in a copyable code block
                except Exception as e:
                    what3words_list.append('')
                    st.error(f"Error getting what3words for location {idx+1}")

            st.session_state.df = edited_df

        # Create map
        m = folium.Map(location=coords[0], zoom_start=10)
        colors = {'Tilly': 'red', 'Jaedon': 'blue', 'Phil': 'green', 
                 'Cally': 'purple', 'Mitch': 'orange', 'Freye': 'pink', 
                 'Unassigned': 'gray'}

        # Add current location and markers
        if st.session_state.current_location:
            folium.Marker(
                location=st.session_state.current_location,
                icon=folium.Icon(color='green', icon='home'),
                popup='Current Location'
            ).add_to(m)

        for idx, row in edited_df.iterrows():
            color = colors.get(row['Assigned_To'], 'gray')
            popup_text = f"Location {idx+1}<br>Assigned: {row['Assigned_To']}"
            if row['What3Words']:
                popup_text += f"<br>W3W: {row['What3Words']}"
            
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                icon=folium.Icon(color=color, icon='info-sign'),
                popup=popup_text
            ).add_to(m)

            if st.session_state.current_location:
                PolyLine(
                    locations=[st.session_state.current_location, 
                             [row['Latitude'], row['Longitude']]],
                    weight=2,
                    color=color,
                    opacity=0.8
                ).add_to(m)

        # Display map
        st_folium(m, width=700, height=500)

        # Display distances
        if st.session_state.current_location:
            st.subheader("Distances from current location")
            distances = []
            for idx, row in edited_df.iterrows():
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

        # Enable CSV download
        if not edited_df.empty:
            csv = edited_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "geocache_locations.csv",
                "text/csv"
            )

    except Exception as e:
        st.error(f"Error processing coordinates: {str(e)}")
