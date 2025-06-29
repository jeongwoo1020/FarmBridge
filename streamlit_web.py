import streamlit as st
import pydeck as pdk
from streamlit_option_menu import option_menu
import pandas as pd
import folium
from streamlit_folium import folium_static
import openai
from geopy.geocoders import Nominatim
from math import radians, cos, sin, sqrt, atan2
import base64
import os
import random
import geopandas as gpd
import json
from shapely.geometry import shape


# OpenAI API 설정
client = openai.OpenAI(api_key='Your-API-Key')

# 페이지 구성
st.set_page_config(page_title="청년 Farm Planner", layout="wide")

# 제목 및 설명
st.markdown("""
# 청년 Farm Planner 🌾
**지금 바로 청년 Farm Planner와 함께 새로운 도전을 시작해보세요!** 🍀
""")
st.markdown("---")



# Navigation bar
selected = option_menu(
    menu_title=None,  # required
    options=["메인", "입지 추천", "컨설팅 리포트", "유통 센터 매칭"],
    icons=["house", "map", "file-earmark-text", "building"],
    menu_icon="cast", 
    default_index=0, 
    orientation="horizontal",
)


# 데이터 로드
@st.cache_data
def load_data():
    data = pd.read_csv('cluster_mapping_최종.csv').drop(columns='Unnamed: 0')
    data2 = pd.read_csv('유통센터_공판장_도매시장_정리.csv', encoding='euc-kr')
    data2.rename(columns={'위도': '위도', '경도': '경도', '종류': '종류', '명칭': '명칭'}, inplace=True)
    return data, data2

data, data2 = load_data()


# 작물 정보 매핑 로직
crop_to_regions = data.groupby('추천작물(한글)')['지점명'].apply(list).to_dict()


def load_geojson_to_gdf_fixed(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    geometries = [shape(feature["geometry"]) for feature in raw["features"]]
    properties = [feature["properties"] for feature in raw["features"]]

    df = pd.DataFrame(properties)
    geom_series = pd.Series(geometries, dtype="geometry")
    gdf = gpd.GeoDataFrame(df, geometry=geom_series, crs="EPSG:4326")
    return gdf

# 병합 및 지점명 생성
gdf_local = load_geojson_to_gdf_fixed("대한민국_기초자치단체_경계_2017.geojson")

# 병합 없이 지점명 생성
gdf_local['지점명'] = gdf_local['SIG_KOR_NM']

    
# 하버사인 거리 계산 함수
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # 지구 반지름 (km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# 주소를 위도와 경도로 변환
def get_lat_lon(address):
    import time
    geolocator = Nominatim(user_agent="geoapi", timeout=10)  # 타임아웃 설정
    time.sleep(1)  # 요청 간 대기
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    else:
        raise ValueError("주소를 찾을 수 없습니다. 정확한 주소를 입력하세요.")


if selected == "메인":
    st.markdown(
        """
        <div style="text-align: center;">
            <h1>청년 Farm Planner에 오신 것을 환영합니다!</h1>
            <p><strong>🌾 청년 농업의 새로운 시작, Farm Planner와 함께하세요! 🌾</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # # 이미지 추가
    # st.image("강아지.png", caption="청년 Farm Planner 소개", width=600)



    
    st.markdown("---")
    
    # 3열 구성으로 주요 기능 소개
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### **입지 추천**
        원하는 작물을 입력하면, 가장 적합한 입지를 추천해드립니다.  
        여러분의 성공적인 농업을 위한 최적의 환경을 찾아보세요!
        """)

    with col2:
        st.markdown("""
        ### **컨설팅 리포트**
        예산과 작물을 입력하면, 맞춤형 청년 농부 컨설팅 리포트를 제공합니다.  
        체계적이고 전문적인 분석으로 성공적인 귀농을 돕습니다.
        """)

    with col3:
        st.markdown("""
        ### **유통 센터 매칭**
        위치를 입력하면, 근처 유통 센터 정보를 한눈에 확인할 수 있습니다.  
        지역 유통망과의 연결로 효율적인 농업을 실현하세요!
        """)



# Content based on selection
elif selected == "입지 추천":
    st.header("작물에 알맞은 입지 추천")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("작물 선택")
        crop = st.text_input('원하는 작물을 입력하세요:')

        if crop in data['추천작물(한글)'].unique():
            matched = data[data['추천작물(한글)'] == crop]

            # 주소 분리
            all_addresses = []
            for row in matched['지점명']:
                for addr in row.split(','):
                    all_addresses.append(addr.strip())

            # 추천 목록 출력
            st.subheader("추천 지역 목록:")
            st.text("\n".join(sorted(all_addresses)))

            # 지오메트리 매칭
            matched_gdf = gdf_local[gdf_local['지점명'].isin(all_addresses)].copy()

            if matched_gdf.empty:
                st.warning("❗ 해당 작물의 시군구 데이터를 찾을 수 없습니다.")
            else:
                # pydeck용 좌표 리스트로 변환 (PolygonLayer용)
                matched_gdf['coordinates'] = matched_gdf['geometry'].apply(
                    lambda x: [list(coord) for coord in list(x.exterior.coords)] if x.geom_type == 'Polygon'
                    else [list(coord) for part in x.geoms for coord in list(part.exterior.coords)]
                )

        elif crop != "":
            st.error(f"'{crop}'에 대한 정보가 없습니다. 다른 작물을 입력하세요.")
        else:
            matched_gdf = pd.DataFrame()

    with col2:
        st.subheader("지도 시각화")

        if not matched_gdf.empty:
            try:
                layer = pdk.Layer(
                    "PolygonLayer",
                    data=matched_gdf,
                    get_polygon="coordinates",
                    get_fill_color='[34, 139, 34, 255]',
                    get_line_color='[255, 255, 255, 100]',
                    line_width_min_pixels=1,
                    pickable=True,
                    auto_highlight=True,
                    )

                # 중심 위치 설정 (첫 행정구역 중심 기준)
                center = matched_gdf['geometry'].centroid.iloc[0]
                view_state = pdk.ViewState(
                    latitude=center.y,
                    longitude=center.x,
                    zoom=7,
                    pitch=0,
                )

                st.pydeck_chart(pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",  # 밝은 지도 + 한국어 가능
                    tooltip={"text": "{지점명}"}
                ))

            except Exception as e:
                st.warning("시각화 중 오류가 발생했습니다: " + str(e))
        else:
            st.info("시각화를 위한 데이터가 없습니다.")





elif selected == "컨설팅 리포트":
    st.header("초보 농부 브랜딩 전략 리포트 생성기")

    # 1. 기본 정보 입력
    st.subheader("📍 1. 기본 정보")

    col1, col2, col3 = st.columns(3)
    with col1:
        crop = st.text_input("작물 (예: 감자, 딸기 등)")
    with col2:
        budget_input = st.text_input("예상 예산 (단위 : 만원)")
        try:
            budget = int(budget_input.replace(',', '').strip())
        except:
            budget = 0
    with col3:
        farming_type = st.selectbox("생산 방식", ["관행농", "유기농", "친환경", "스마트 노지"])

    # 2. 타겟 고객 정보
    st.subheader("🎯 2. 타겟 고객 정보")

    col1, col2, col3 = st.columns(3)
    with col1:
        customer_gender = st.selectbox("성별", ["무관", "남성", "여성", "가족"])
    with col2:
        customer_age = st.selectbox("연령대", ["10대", "20대", "30대", "40대", "50대", "60대 이상"])
    with col3:
        customer_area = st.selectbox("거주지 특성", ["수도권", "지방 중소도시", "농촌 지역", "해외 거주"])

    col4, col5 = st.columns(2)
    with col4:
        customer_usage = st.selectbox("주요 용도", [
            "가정 반찬용", "홈카페 디저트", "식당 납품용", 
            "유아 이유식", "건강식/영양보충", "선물용"
        ])
    with col5:
        customer_traits = st.multiselect("소비 성향", [
            "가성비 중시", "감성적 소비", "프리미엄志향", 
            "기능성 상품 선호", "지역 로컬푸드 선호", 
            "트렌디/SNS 인기", "윤리적/친환경 소비", "브랜드 충성도 높음"
        ])

    # 3. 농부 및 브랜드 성향
    st.subheader("🧽 3. 농부 및 브랜드 성향")

    col1, col2, col3 = st.columns(3)
    with col1:
        farm_traits = st.multiselect("나의 농장 성격", [
            "정직하고 신뢰가는", "감성적인 이야기 중심", "유쾌하고 개성있는", 
            "실용적이고 경제적인", "기술 기반 스마트팜", "지역 공동체와 연계", 
            "신기술 실험적 적용", "자연 생태 존중"
        ])
    with col2:
        competitive_edge = st.multiselect("경쟁 우위 요소", [
            "선명한 색감", "차별화된 맛", "합리적 가격", 
            "친환경 포장재 사용", "유기농/친환경 인증", 
            "소량 정예 생산", "당일 수확 당일 배송", "스토리텔링 콘텐츠"
        ])
    with col3:
        farm_values = st.text_input("가치관 메시지", placeholder="예: 우리 아이가 먹는다는 마음으로")


    # 4. 추가 메모
    st.subheader("💬 4. 추가 메모")
    extra_note = st.text_area("추가 메모 (선택)", height=100)

    if st.button("브랜딩 전략 리포트 생성하기"):
        if crop and budget and farming_type:
            prompt = f"""당신은 초보 농부의 브랜딩 전략을 설계하는 전문가입니다. 아래의 정보를 바탕으로, 직거래 플랫폼에서 효과적으로 판매할 수 있는 브랜드 전략 리포트를 작성하세요. 리포트는 시각적으로 이해하기 쉽게 구성되어야 하며, 각 항목은 구체적이고 실행 가능해야 합니다.

[작물 정보]
- 재배 작물: {crop}
- 예상 예산: {budget} 원
- 생산 방식: {farming_type}

[타겟 고객 정보]
- 성별: {', '.join(customer_gender)}
- 연령대: {', '.join(customer_age)}
- 거주지 특성: {', '.join(customer_area)}
- 주요 용도: {', '.join(customer_usage)}
- 소비 성향: {', '.join(customer_traits)}

[농부 및 브랜드 성향]
- 농장 성격 키워드: {', '.join(farm_traits)}
- 가치관 메시지: "{farm_values}"
- 경쟁 우위 요소: {', '.join(competitive_edge)}

[추가 메모]
{extra_note}

---

### 1. 브랜드 정체성
- 브랜드 이름 2가지 (이름 뒤에 간단한 의미 설명 포함)
- 각 브랜드 이름에 맞는 슬로건 1개씩
- 500자 이내의 브랜드 스토리 (기원, 철학, 가치관, 소비자와의 연결 메시지, 지역 친화적/환경 요소 포함)

---

### 2. 브랜드 포지셔닝 전략
- 타겟 소비자 페르소나 정의 (이 작물을 살 것 같은 대표적인 인물 묘사)
- 경쟁 제품과의 차별화 요소 설명
- 직거래 플랫폼에 사용할 마케팅 문구 (2개)

---

### 3. 시각/디자인 가이드
- 브랜드에 어울리는 컬러톤과 로고 스타일 설명
- 포장 또는 웹페이지 디자인 제안 (톤, 키워드, 강조 메시지 등)

---

### 4. 거래 플랫폼 연동 전략
- 상품 등록 예시: 상품명, 간단 소개 문구, 추천 해시태그
- 소비자 신뢰를 높이기 위한 정보 또는 인증 아이디어 (예: 생산자 소개 카드, 재배 인증 등)

---

[선택] 5. 간단한 생산 전략 (2~3줄)
해당 작물의 재배 시 주의점이나 초보자가 꼭 알아야 할 팁

리포트는 브랜드 주인의 진심이 느껴지도록 진정성 있게, 동시에 소비자와의 연결 가능성을 고려하여 매력적으로 구성하세요."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt}
            ],
            temperature=0.7,
        )

        report = response.choices[0].message.content
        st.subheader("📄 브랜딩 전략 리포트")
        st.write(report)
    else:
        st.warning("❗ 작물, 예산, 생산 방식을 모두 입력해 주세요.")


elif selected == "유통 센터 매칭":
    st.header("위치 기반 최적의 유통 센터 정보를 출력해보세요.")
    
    my_address = st.text_input("나의 위치를 입력해주세요 (예: 서울특별시 중구 세종대로 110): ")
    if my_address:
        try:
            # 주소를 위경도로 변환
            my_lat, my_lon = get_lat_lon(my_address)
            st.write(f"입력된 주소: {my_address}")
            st.write(f"위도: {my_lat}, 경도: {my_lon}")
            
            # 거리 계산
            data2['거리'] = data2.apply(
                lambda row: haversine(my_lat, my_lon, row['위도'], row['경도']), axis=1
            )
            
            # 거리 기준으로 필터링
            max_distances = {'유통센터': 50, '공판장': 35, '도매시장': 20}

            def filter_or_nearest(group, type_name):
                filtered = group[group['거리'] <= max_distances[type_name]]
                if not filtered.empty:
                    return filtered.nsmallest(3, '거리')
                return group.nsmallest(1, '거리')

            filtered_top_3_by_type = data2.groupby('종류', group_keys=False).apply(
                lambda group: filter_or_nearest(group, group.name)
            ).reset_index(drop=True)

            # 지도 생성
            m = folium.Map(location=[my_lat, my_lon], zoom_start=12)

            # 사용자의 위치 마커 추가
            folium.Marker(
                location=[my_lat, my_lon],
                popup=f"나의 위치: {my_address}",
                tooltip="나의 위치",
                icon=folium.Icon(color="red")
            ).add_to(m)

            # 추천 유통 센터 마커 추가
            for _, row in filtered_top_3_by_type.iterrows():
                marker_color = "blue" if row['종류'] == "유통센터" else "green" if row['종류'] == "공판장" else "gray"
                popup_content = f"""
                <b>이름:</b> {row['명칭']}<br>
                <b>종류:</b> {row['종류']}<br>
                <b>거리:</b> {row['거리']:.2f} km<br>
                <b>주소:</b> {row.get('주소', '정보 없음')}
                """
                folium.Marker(
                    location=[row['위도'], row['경도']],
                    popup=folium.Popup(popup_content, max_width=300),
                    tooltip=f"{row['명칭']} ({row['거리']:.2f} km)",
                    icon=folium.Icon(color=marker_color)
                ).add_to(m)

            # 지도 및 결과 출력
            folium_static(m)
            st.dataframe(filtered_top_3_by_type)
        except ValueError as e:
            st.error(str(e))


elif selected == "연구":
    st.write("연구 페이지입니다.")
elif selected == "산학/창업":
    st.write("산학/창업 페이지입니다.")
elif selected == "국제화":
    st.write("국제화 페이지입니다.")
elif selected == "대학생활":
    st.write("대학생활 페이지입니다.")
