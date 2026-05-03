import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Photon
from datetime import datetime
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# --- 1. CẤU HÌNH GIAO DIỆN WEB ---
st.set_page_config(page_title="GOBRUH - Đặt Xe AI", page_icon="🚕", layout="centered")

st.title("🚕 GOBRUH AI TOÀN QUỐC")
st.markdown("**Định giá thông minh - Đồng Hành Trên Mọi Nẻo Đường**")
st.divider()

# --- 2. HỆ THỐNG FUZZY LOGIC (LOGIC MỜ) ---
def get_fuzzy_surge(current_hour, weather_score):
    # Khai báo các biến đầu vào và đầu ra
    time = ctrl.Antecedent(np.arange(0, 24.1, 0.1), 'time')
    weather = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'weather')
    surge = ctrl.Consequent(np.arange(0.8, 2.1, 0.1), 'surge')

    # Hàm liên thuộc cho Thời gian (Giờ)
    time['night'] = fuzz.trapmf(time.universe, [0, 0, 5, 6.5])
    time['morning_peak'] = fuzz.trimf(time.universe, [6, 7.5, 9])
    time['day_normal'] = fuzz.trapmf(time.universe, [8, 10, 15, 17])
    time['evening_peak'] = fuzz.trimf(time.universe, [16, 17.5, 19])
    time['late_night'] = fuzz.trapmf(time.universe, [18, 20, 24, 24])

    # Hàm liên thuộc cho Thời tiết (Điểm 0-10)
    weather['good'] = fuzz.trapmf(weather.universe, [0, 0, 3, 5])
    weather['normal'] = fuzz.trimf(weather.universe, [3, 5, 7])
    weather['bad'] = fuzz.trapmf(weather.universe, [5, 8, 10, 10])

    # Hàm liên thuộc cho Hệ số giá (Surge)
    surge['low'] = fuzz.trimf(surge.universe, [0.8, 0.9, 1.1])
    surge['normal'] = fuzz.trimf(surge.universe, [1.0, 1.2, 1.4])
    surge['high'] = fuzz.trimf(surge.universe, [1.3, 1.6, 2.0])

    # Tạo Luật Mờ (Fuzzy Rules)
    rule1 = ctrl.Rule(weather['bad'] | time['morning_peak'] | time['evening_peak'], surge['high'])
    rule2 = ctrl.Rule(weather['good'] & (time['night'] | time['late_night']), surge['low'])
    rule3 = ctrl.Rule(weather['normal'] | time['day_normal'], surge['normal'])
    rule4 = ctrl.Rule(weather['good'] & time['day_normal'], surge['normal'])

    # Khởi tạo bộ điều khiển và tính toán
    surge_ctrl = ctrl.ControlSystem([rule1, rule2, rule3, rule4])
    surge_sim = ctrl.ControlSystemSimulation(surge_ctrl)

    surge_sim.input['time'] = current_hour
    surge_sim.input['weather'] = weather_score
    surge_sim.compute()

    return surge_sim.output['surge']

# --- 3. HÀM GỬI THÔNG BÁO TELEGRAM ---
def send_telegram_alert(message):
    bot_token = "MÃ_TOKEN_CỦA_BẠN"  # <-- ĐIỀN TOKEN VÀO ĐÂY
    chat_id = "CHAT_ID_CỦA_BẠN"     # <-- ĐIỀN CHAT ID VÀO ĐÂY
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

# --- 4. KHỞI TẠO BẢN ĐỒ PHOTON ---
geolocator = Photon(user_agent="gobruh_ai_app", timeout=10)

# --- 5. GIAO DIỆN NHẬP LIỆU ---
with st.form("booking_form"):
    st.subheader("📍 Nhập thông tin lộ trình")
    
    city = st.selectbox("🌆 Chọn Khu Vực:", ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Cần Thơ", "Tìm tự do (Toàn quốc)"])
    start_place = st.text_input("🏠 Điểm đi:", placeholder="VD: 279 Nguyễn Tri Phương")
    end_place = st.text_input("🏁 Điểm đến:", placeholder="VD: Sân bay...")
    
    col1, col2 = st.columns(2)
    with col1:
        vehicle = st.selectbox("🛵 Chọn loại xe:", ["Bike", "Car"])
    with col2:
        weather_score = st.slider("⛅ Đánh giá thời tiết (0: Đẹp ➡ 10: Bão):", 0.0, 10.0, 3.0, 0.5)
        
    promo_code = st.text_input("🎟️ Mã khuyến mãi (GIAMGIA15, DEAL15):", placeholder="Nhập mã tại đây...")
    
    submitted = st.form_submit_button("🚀 TÌM ĐƯỜNG & TÍNH GIÁ AI", use_container_width=True)

# --- 6. XỬ LÝ KHI BẤM NÚT ---
if submitted:
    if not start_place or not end_place:
        st.warning("⚠️ Vui lòng nhập đầy đủ cả điểm đi và điểm đến nhé!")
    else:
        with st.spinner("🧠 AI đang phân tích logic mờ và định vị bản đồ..."):
            
            # --- Xử lý địa chỉ (Linh hoạt theo Tỉnh/Thành phố) ---
            if city == "Tìm tự do (Toàn quốc)":
                search_start = start_place
                search_end = end_place
            else:
                search_start = f"{start_place}, {city}" if city.lower() not in start_place.lower() else start_place
                search_end = f"{end_place}, {city}" if city.lower() not in end_place.lower() else end_place

            start_loc = geolocator.geocode(search_start, timeout=10)
            end_loc = geolocator.geocode(search_end, timeout=10)
            
            if not start_loc or not end_loc:
                st.error(f"❌ Không tìm thấy địa chỉ tại {city}. Vui lòng nhập chi tiết hơn (tên đường, quận/huyện)!")
                st.stop()
                
            start_point = (start_loc.latitude, start_loc.longitude)
            end_point = (end_loc.latitude, end_loc.longitude)
            
            # --- Xử lý khuyến mãi ---
            discount = 0
            if promo_code.strip().upper() in ["GIAMGIA15", "DEAL15"]:
                discount = 0.15
                st.success("🎉 Áp mã thành công! Giảm 15%.")
            elif promo_code.strip():
                st.error("❌ Mã không hợp lệ hoặc đã hết hạn.")
                
            # --- Tính giá bằng AI Fuzzy Logic ---
            current_hour = datetime.now().hour + (datetime.now().minute / 60.0) 
            ai_surge_factor = get_fuzzy_surge(current_hour, weather_score)
            
            # --- Gọi API OSRM tìm đường ---
            start_lon_lat = f"{start_point[1]},{start_point[0]}"
            end_lon_lat = f"{end_point[1]},{end_point[0]}"
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon_lat};{end_lon_lat}?overview=full&geometries=geojson"
            
            try:
                response = requests.get(url)
                data = response.json()
                if data.get("code") != "Ok":
                    st.error("❌ Không thể tìm đường đi bằng xe cộ giữa 2 điểm này!")
                    st.stop()
                    
                route_data = data["routes"][0]
                distance_km = route_data["distance"] / 1000
                osrm_time_min = route_data["duration"] / 60
                route_coords = [(coord[1], coord[0]) for coord in route_data["geometry"]["coordinates"]]
            except Exception as e:
                st.error("❌ Lỗi kết nối vệ tinh tìm đường!")
                st.stop()
                
            # --- Tính Tiền ---
            if vehicle == "Bike":
                base, per_km, per_min, vehicle_factor = 12000, 4200, 344, 1.0
            else:
                base, per_km, per_min, vehicle_factor = 28000, 9800, 442, 1.6
                
            base_price = base + (distance_km * per_km) + (osrm_time_min * per_min)
            price = base_price * ai_surge_factor * vehicle_factor
            
            final_price = price * (1 - discount)
            
            # --- HIỂN THỊ KẾT QUẢ ---
            st.divider()
            st.subheader("🧾 THÔNG TIN CHUYẾN ĐI (AI TÍNH TOÁN)")
            
            st.info(f"**🟢 Đón ({city}):** {start_loc.address}\n\n**🔴 Đến ({city}):** {end_loc.address}")
            
            col3, col4, col5 = st.columns(3)
            col3.metric("📏 Khoảng cách", f"{round(distance_km, 2)} km")
            col4.metric("🧠 Hệ số AI", f"x{round(ai_surge_factor, 2)}")
            
            if discount > 0:
                col5.metric("💵 Tổng tiền", f"{format(round(final_price), ',')} đ", delta="-15% Mã KM", delta_color="inverse")
            else:
                col5.metric("💵 Tổng tiền", f"{format(round(final_price), ',')} đ")
                
            # --- GỬI TELEGRAM CHO TÀI XẾ ---
            msg = (
                f"🚨 <b>[GOBRUH AI] CÓ KHÁCH ĐẶT XE!</b> 🚨\n\n"
                f"🌆 <b>Khu vực:</b> {city}\n"
                f"🛵 <b>Loại xe:</b> {vehicle}\n"
                f"⛅ <b>Điểm thời tiết:</b> {weather_score}/10\n"
                f"🟢 <b>Đón tại:</b> {start_place}\n"
                f"🔴 <b>Đi đến:</b> {end_place}\n"
                f"📏 <b>Quãng đường:</b> {round(distance_km, 2)} km\n"
                f"💵 <b>Giá tiền:</b> {format(round(final_price), ',')} VNĐ\n"
            )
            send_telegram_alert(msg)
            st.toast('Đã nổ cuốc về điện thoại tài xế!', icon='📲')

            # --- VẼ BẢN ĐỒ ---
            st.subheader("🗺️ BẢN ĐỒ LỘ TRÌNH")
            mid_point = ((start_point[0] + end_point[0])/2, (start_point[1] + end_point[1])/2)
            m = folium.Map(location=mid_point, zoom_start=13, tiles="CartoDB positron")
            
            folium.PolyLine(route_coords, color="#0088FF", weight=6, opacity=0.8).add_to(m)
            folium.Marker(location=start_point, popup="Điểm đi", icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker(location=end_point, popup="Điểm đến", icon=folium.Icon(color="red", icon="stop")).add_to(m)
            m.fit_bounds(route_coords)
            
            st_folium(m, width=700, height=500, returned_objects=[])
