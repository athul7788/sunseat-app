import streamlit as st
import openrouteservice
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta
import math

ORS_API_KEY = st.secrets["ORS_API_KEY"]

def get_coords(place_name):
    geolocator = Nominatim(user_agent="sunseat")
    location = geolocator.geocode(place_name)
    if not location:
        raise ValueError(f"Could not find location: {place_name}")
    return (location.latitude, location.longitude)

def calculate_bearing(start, end):
    lat1 = math.radians(start[0])
    lat2 = math.radians(end[0])
    diff_long = math.radians(end[1] - start[1])
    x = math.sin(diff_long) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_long)
    bearing = math.atan2(x, y)
    return (math.degrees(bearing) + 360) % 360

def get_sun_azimuth(hour_float):
    if 6 <= hour_float <= 18:
        return (hour_float - 6) * 15
    return None

def decide_seat(bearing, sun_azimuth):
    if sun_azimuth is None:
        return "Any (Night)"
    diff = (sun_azimuth - bearing + 360) % 360
    return "Left" if 90 < diff < 270 else "Right"

def interpolate_position(route_coords, total_steps, step_index):
    index = int(step_index / total_steps * (len(route_coords) - 1))
    coord = route_coords[index]
    return (coord[1], coord[0])

def suggest_seat_schedule(from_place, to_place, start_time, duration_minutes):
    client = openrouteservice.Client(key=ORS_API_KEY)
    from_coords = get_coords(from_place)
    to_coords = get_coords(to_place)

    route = client.directions(
        coordinates=[(from_coords[1], from_coords[0]), (to_coords[1], to_coords[0])],
        profile='driving-car',
        format='geojson'
    )

    route_coords = route['features'][0]['geometry']['coordinates']
    total_steps = duration_minutes // 10
    current_time = start_time
    schedule = []
    last_seat = None
    interval_start = current_time

    for step in range(total_steps + 1):
        current_time = start_time + timedelta(minutes=step * 10)
        hour = current_time.hour + current_time.minute / 60
        sun_az = get_sun_azimuth(hour)
        pos = interpolate_position(route_coords, total_steps, step)
        bearing = calculate_bearing(pos, to_coords)
        seat = decide_seat(bearing, sun_az)

        if step == 0:
            last_seat = seat
        elif seat != last_seat:
            schedule.append((last_seat, interval_start.strftime('%H:%M'), current_time.strftime('%H:%M')))
            interval_start = current_time
            last_seat = seat

    end_time = start_time + timedelta(minutes=duration_minutes)
    schedule.append((last_seat, interval_start.strftime('%H:%M'), end_time.strftime('%H:%M')))
    return schedule

# Set page config
st.set_page_config(page_title="SunSeat", layout="centered")
st.title("🚌 SunSeat: Sit Smart. Avoid the Sun.")
st.caption("Get sunlight-aware seat suggestions for your trip.")

# Lock the default journey start time only once per session
if "default_time" not in st.session_state:
    st.session_state.default_time = datetime.now().time()

with st.form("sunseat_form"):
    from_place = st.text_input("From", placeholder="e.g., Times Square, New York")
    to_place = st.text_input("To", placeholder="e.g., Central Park, New York")
    time_input = st.time_input("Journey Start Time", value=st.session_state.default_time)
    duration = st.number_input("Journey Duration (minutes)", min_value=10, max_value=1440, value=60, step=10)
    submitted = st.form_submit_button("Suggest Seat")

if submitted:
    try:
        start_dt = datetime.combine(datetime.today(), time_input)
        schedule = suggest_seat_schedule(from_place, to_place, start_dt, duration)
        
        st.subheader("🪑 Seat Side Schedule")
        for seat, from_t, to_t in schedule:
            st.write(f"➡️ **{from_t} → {to_t}**: Sun is on the **{seat}** side of the vehicle")
    except Exception as e:
        st.error(f"❌ Error: {e}")

