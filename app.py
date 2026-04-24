import streamlit as st
import requests
import pandas as pd
import urllib3

# 보안 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 생성하신 Cloud Run API 기본 주소
API_BASE_URL = "https://strategy-hub-api-357178181068.asia-northeast3.run.app"

# 페이지 기본 설정
st.set_page_config(page_title="전략 정보 HUB", page_icon="🗓️", layout="wide")

st.title("🗓️ 주요 사업 공고")
st.markdown("유관기관 사업공고 실시간 모니터링 대시보드")
st.divider()

# ==========================================
# 1. 데이터 수집 함수 (Cloud Run API 연동)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_data_from_api(endpoint, agency_name):
    # API 엔드포인트 URL 조합 (예: https://.../khidi)
    url = f"{API_BASE_URL}/{endpoint}"
    
    try:
        response = requests.get(url, timeout=15, verify=False)
        response.raise_for_status()
        
        # API가 JSON 형태의 리스트를 반환한다고 가정
        data = response.json() 
        df = pd.DataFrame(data)
        
        if not df.empty:
            # API 응답에 '기관' 컬럼이 없다면 프론트에서 추가
            if '기관' not in df.columns:
                df['기관'] = agency_name
                
            # 필수 컬럼 빈값 방지 처리
            for col in ["공고일", "제목", "접수기간", "원문링크"]:
                if col not in df.columns:
                    df[col] = "공고문 참조"
                    
        return df
    
    except Exception as e:
        st.warning(f"⚠️ {agency_name} 데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

# ==========================================
# 2. 데이터 처리 메인 로직
# ==========================================
with st.spinner('서버에서 최신 공고 데이터를 수집 중입니다...'):
    # 실제 API 라우팅 주소에 맞게 endpoint("khidi", "nipa" 등)를 수정해 주세요.
    df_khidi = fetch_data_from_api("khidi", "한국보건산업진흥원")
    df_nipa = fetch_data_from_api("nipa", "정보통신산업진흥원")
    df_nia = fetch_data_from_api("nia", "한국지능정보사회진흥원")
    df_msit = fetch_data_from_api("msit", "과학기술정보통신부")

# 모든 기관 데이터 병합
dfs = [df for df in [df_khidi, df_nipa, df_nia, df_msit] if not df.empty]

if dfs:
    df_all = pd.concat(dfs, ignore_index=True)
    # 공고일 기준 최신순 정렬
    df_all = df_all.sort_values(by="공고일", ascending=False)
else:
    df_all = pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# 검색어 필터링
search_query = st.text_input("🔍 검색어 입력 (예: AI, 클라우드, 보안, 의료데이터)", "")

if search_query and not df_all.empty:
    filtered_df = df_all[df_all['제목'].str.contains(search_query, case=False, na=False)]
else:
    filtered_df = df_all

# ==========================================
# 3. 탭 구성 (Expander 스타일 적용)
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 전체보기", "🏛️ 한국보건산업진흥원", "🏛️ 정보통신산업진흥원", "🏛️ 한국지능정보사회진흥원", "🏛️ 과학기술정보통신부"
])

with tab1:
    st.subheader(f"통합 검색 결과: {len(filtered_df)}건")
    if not filtered_df.empty:
        st.dataframe(
            filtered_df[["기관", "공고일", "제목", "접수기간", "원문링크"]], # 순서 고정
            column_config={
                "원문링크": st.column_config.LinkColumn("링크", display_text="원문 보기 →")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("검색된 데이터가 없습니다.")

# 중복 코드를 줄이기 위한 탭 렌더링 헬퍼 함수
def render_agency_tab(df, agency_name):
    st.markdown(f"### {agency_name} 공고")
    sub_df = df[df['기관'] == agency_name]
    
    if sub_df.empty:
        st.info("해당 기관의 공고가 없습니다.")
    else:
        for _, row in sub_df.iterrows():
            # 요청하신 expander 형식 적용
            with st.expander(f"[{row['공고일']}] {row['제목']}"):
                st.write(f"**접수기간:** {row['접수기간']}")
                st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")

with tab2:
    render_agency_tab(filtered_df, "한국보건산업진흥원")

with tab3:
    render_agency_tab(filtered_df, "정보통신산업진흥원")

with tab4:
    render_agency_tab(filtered_df, "한국지능정보사회진흥원")

with tab5:
    render_agency_tab(filtered_df, "과학기술정보통신부")
