import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime

# --- CẤU HÌNH GIAO DIỆN WEB ---
st.set_page_config(page_title="GOBRUH - Đặt Xe Siêu Tốc", page_icon="🚕", layout="centered")

st.title("🚕 GOBRUH")
st.markdown("**Đồng Hành Cùng Bạn Trên Mọi Nẻo Đường**")
st.divider()

# --- CÁC HÀM XỬ LÝ (Giữ nguyên logic của bạn) ---
def get_surge_factor():
    hour = datetime.now().hour
    if 0 <= hour < 6: return 0.9, 1.2
    elif 6 <= hour < 9: return 1.4, 0.6
    elif 16 <= hour < 19: return 1.6, 0.5
    elif 19 <= hour < 22: return 1.2, 0.9
    else: return 1.0, 1.0

def fuel_factor():
    return 1.0

def weather_factor(w_type):
    if w_type == "Rất xấu": return 1.3
    elif w_type == "Bình thường": return 1.15
    else: return 1.0

# Khởi tạo định vị
geolocator = Nominatim(user_agent="grab_ai_pro")

# --- FORM NHẬP LIỆU ---
with st.form("booking_form"):
    st.subheader("📍 Nhập thông tin lộ trình")
    
    start_place = st.text_input("🏠 Nhập địa chỉ điểm đi:", placeholder="Ví dụ: Chợ Bến Thành, Quận 1")
    end_place = st.text_input("🏁 Nhập địa chỉ điểm đến:", placeholder="Ví dụ: Landmark 81, Bình Thạnh")
    
    col1, col2 = st.columns(2)
    with col1:
        vehicle = st.selectbox("🛵 Chọn loại xe:", ["Bike", "Car"])
    with col2:
        weather_type = st.selectbox("⛅ Thời tiết hôm nay:", ["Đẹp", "Bình thường", "Rất xấu"])
        
    promo_code = st.text_input("🎟️ Nhập mã khuyến mãi (nếu có):", placeholder="Thử nhập: GIAMGIA15 hoặc DEAL15")
    
    # Nút bấm submit
    submitted = st.form_submit_button("🔍 TÌM ĐƯỜNG & TÍNH GIÁ", use_container_width=True)

# --- XỬ LÝ KHI BẤM NÚT ---
if submitted:
    if not start_place or not end_place:
        st.warning("⚠️ Vui lòng nhập đầy đủ cả điểm đi và điểm đến nhé!")
    else:
        with st.spinner("Đang kết nối vệ tinh và tính toán lộ trình tối ưu..."):
            # 1. Tìm tọa độ
            start_loc = geolocator.geocode(start_place)
            end_loc = geolocator.geocode(end_place)
            
            if not start_loc or not end_loc:
                st.error("❌ Không tìm thấy địa chỉ. Vui lòng thử nhập chi tiết hơn (Thêm Tên Đường, Quận, TP).")
                st.stop()
                
            start_point = (start_loc.latitude, start_loc.longitude)
            end_point = (end_loc.latitude, end_loc.longitude)
            
            # 2. Xử lý khuyến mãi
            discount = 0
            valid_codes = ["GIAMGIA15", "DEAL15"]
            if promo_code.strip().upper() in valid_codes:
                discount = 0.15
                st.success("🎉 Áp mã thành công! Bạn được giảm 15% tổng hóa đơn.")
            elif promo_code.strip():
                st.error("❌ Mã không hợp lệ hoặc đã hết hạn.")
                
            # 3. Tính toán các hệ số
            surge_price_factor, speed_factor = get_surge_factor()
            weather = weather_factor(weather_type)
            
            # 4. Gọi API OSRM tìm đường
            start_lon_lat = f"{start_point[1]},{start_point[0]}"
            end_lon_lat = f"{end_point[1]},{end_point[0]}"
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon_lat};{end_lon_lat}?overview=full&geometries=geojson"
            
            try:
                response = requests.get(url)
                data = response.json()
                
                if data.get("code") != "Ok":
                    st.error("❌ Lỗi: Không thể tìm thấy đường đi bộ/xe chạy giữa 2 điểm này!")
                    st.stop()
                    
                route_data = data["routes"][0]
                distance_km = route_data["distance"] / 1000
                osrm_time_min = route_data["duration"] / 60
                
                coords_from_api = route_data["geometry"]["coordinates"]
                route_coords = [(coord[1], coord[0]) for coord in coords_from_api]
                
            except Exception as e:
                st.error(f"❌ Đã xảy ra lỗi khi kết nối hệ thống tìm đường: {e}")
                st.stop()
                
            # 5. Tính giá tiền
            if vehicle == "Bike":
                base, per_km, per_min, vehicle_factor = 12000, 4200, 344, 1.0
            else:
                base, per_km, per_min, vehicle_factor = 28000, 9800, 442, 1.6
                
            actual_time_min = osrm_time_min * (1 / speed_factor)
            
            base_price = base + (distance_km * per_km) + (actual_time_min * per_min)
            price = base_price * surge_price_factor * weather * fuel_factor() * vehicle_factor
            
            final_price = price * (1 - discount)
            
            # --- HIỂN THỊ KẾT QUẢ ---
            st.divider()
            st.subheader("🧾 THÔNG TIN CHUYẾN ĐI")
            
            st.info(f"**🟢 Điểm đi:** {start_loc.address}\n\n**🔴 Điểm đến:** {end_loc.address}")
            
            col3, col4, col5 = st.columns(3)
            col3.metric("📏 Khoảng cách", f"{round(distance_km, 2)} km")
            col4.metric("⏳ Thời gian (dự kiến)", f"{round(actual_time_min, 1)} phút")
            
            if discount > 0:
                col5.metric("💵 Tổng tiền", f"{format(round(final_price), ',')} đ", delta="-15% Khuyến mãi", delta_color="inverse")
            else:
                col5.metric("💵 Tổng tiền", f"{format(round(final_price), ',')} đ")
                
            # --- VẼ BẢN ĐỒ ---
            st.subheader("🗺️ BẢN ĐỒ LỘ TRÌNH")
            mid_point = ((start_point[0] + end_point[0])/2, (start_point[1] + end_point[1])/2)
            m = folium.Map(location=mid_point, zoom_start=13, tiles="CartoDB positron")
            
            folium.PolyLine(route_coords, color="#0088FF", weight=6, opacity=0.8).add_to(m)
            
            folium.Marker(location=start_point, popup="Điểm đi", icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker(location=end_point, popup="Điểm đến", icon=folium.Icon(color="red", icon="stop")).add_to(m)
            
            m.fit_bounds(route_coords)
            
            # Render map trên web
            st_folium(m, width=700, height=500, returned_objects=[])