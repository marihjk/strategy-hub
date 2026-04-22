import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
import urllib3
import time
from datetime import datetime, date
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from urllib.parse import urljoin

# 보안 경고 및 SSL 인증서 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# [설정] 페이지 기본 구성
st.set_page_config(page_title="전략 정보 HUB", page_icon="🗓️", layout="wide")

st.title("🗓️ 주요 사업 공고")
st.markdown("유관기관 사업공고 실시간 모니터링 대시보드")
st.divider()

# 공통 헤더 설정 (브라우저인 척 하기 위함)
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

# ==========================================
# 1. 데이터 수집 함수 (개별 기관별 최적화)
# ==========================================

# [함수 1] 한국보건산업진흥원 (KHIDI) - 서버 차단 우회 적용
@st.cache_data(ttl=3600)
def get_khidi_data():
    url = "https://www.khidi.or.kr/kps/openAPI/requestxml?rowCnt=50&menuId=MENU01108"
    try:
        # curl_cffi를 사용하여 TLS Fingerprint 차단 우회
        res = cffi_requests.get(url, headers=COMMON_HEADERS, impersonate="chrome120", verify=False, timeout=15)
        root = ET.fromstring(res.content)
        data = []
        for row in root.findall('row'):
            title = row.findtext('title') or ""
            link = row.findtext('url') or ""
            # 날짜 형식 정리 (YYYY.MM.DD)
            date_str = (row.findtext('date') or "")[:10].replace('-', '.')
            data.append({"기관": "한국보건산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"KHIDI 데이터 수집 중 오류: {e}")
        return pd.DataFrame()

# [함수 2] 정보통신산업진흥원 (NIPA) - 링크 추출 보강
@st.cache_data(ttl=3600)
def get_nipa_data():
    all_data = []
    base_url = "https://www.nipa.kr"
    for page in range(1, 6):
        url = f"{base_url}/home/2-2?curPage={page}"
        try:
            res = cffi_requests.get(url, headers=COMMON_HEADERS, impersonate="chrome120", verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            # 상세 페이지 링크(View.do)만 정확하게 타겟팅
            links = soup.select('a[href*="View.do"]')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                
                href = a.get('href', '')
                # urljoin을 사용하여 절대 경로 생성
                link = urljoin(base_url, href)
                
                parent = a.find_parent(['li', 'tr', 'div'])
                parent_text = parent.get_text(separator=' ', strip=True) if parent else ""
                
                period_match = re.search(r'신청기간\s*[:]\s*([0-9\-\:\s~]+)', parent_text)
                period = period_match.group(1).strip() if period_match else "공고문 참조"
                
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', parent_text)
                date_str = date_match.group().replace('-', '.') if date_match else "날짜 확인 필요"
                
                all_data.append({"기관": "정보통신산업진흥원", "공고일": date_str, "제목": title, "접수기간": period, "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# [함수 3] 한국지능정보사회진흥원 (NIA) - 링크 깨짐(#view) 수정
@st.cache_data(ttl=3600)
def get_nia_data():
    all_data = []
    base_url = "https://www.nia.or.kr"
    for page in range(1, 6):
        url = f"{base_url}/site/nia_kor/ex/bbs/List.do?cbIdx=99835&pageIndex={page}"
        try:
            res = cffi_requests.get(url, headers=COMMON_HEADERS, impersonate="chrome120", verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            # #view 같은 더미 링크를 피하기 위해 View.do가 포함된 링크만 선택
            links = soup.select('a[href*="View.do"]')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 5: continue
                
                parent = a.find_parent(['li', 'tr', 'div'])
                parent_text = parent.get_text(separator=' ', strip=True) if parent else ""
                
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', parent_text)
                if not date_match: continue
                
                href = a.get('href', '')
                # NIA 상세페이지 상대경로 문제를 해결하기 위해 명확한 베이스 주소 사용
                link = urljoin("https://www.nia.or.kr/site/nia_kor/ex/bbs/", href)
                
                date_str = date_match.group().replace('-', '.')
                all_data.append({"기관": "한국지능정보사회진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# [함수 4] 과학기술정보통신부 (MSIT) - Referer 헤더 필수 적용
@st.cache_data(ttl=3600)
def get_msit_data():
    all_data = []
    msit_base = "https://msit.go.kr"
    msit_headers = COMMON_HEADERS.copy()
    msit_headers['Referer'] = 'https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121'
    
    for page in range(1, 6):
        url = f"{msit_base}/bbs/list.do?sCode=user&mId=311&mPid=121&pageIndex={page}&bbsSeqNo=100"
        try:
            res = cffi_requests.get(url, headers=msit_headers, impersonate="chrome120", verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            rows = soup.find_all('tr')
            for row in rows:
                a_tag = row.select_one('a[href*="view.do"]')
                if not a_tag: continue
                
                title = a_tag.get_text(strip=True)
                href = a_tag.get('href', '')
                link = urljoin("https://msit.go.kr/bbs/", href)
                
                row_text = row.get_text(separator=' ', strip=True)
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', row_text)
                date_str = date_match.group().replace('-', '.') if date_match else "날짜 확인 필요"
                
                all_data.append({"기관": "과학기술정보통신부", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# ==========================================
# 2. 데이터 통합 및 필터링 (날짜 필터 제거 버전)
# ==========================================

# 사이드바 필터 (검색어만 남김)
with st.sidebar:
    st.header("⚙️ 필터 설정")
    search_query = st.text_input("🔍 검색어 입력 (예: AI, 의료, 반도체)", "")

# 데이터 로딩 로직
with st.spinner('실시간 데이터를 동기화 중입니다...'):
    df_khidi = get_khidi_data()
    df_nipa = get_nipa_data()
    df_nia = get_nia_data()
    df_msit = get_msit_data()

# 통합 데이터프레임 생성
dfs = [df for df in [df_khidi, df_nipa, df_nia, df_msit] if not df.empty]
if dfs:
    df_all = pd.concat(dfs, ignore_index=True)
else:
    df_all = pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# 필터링 및 정렬
if not df_all.empty:
    # 검색어 필터
    if search_query:
        df_all = df_all[df_all['제목'].str.contains(search_query, case=False)]
    
    # 공고일 기준 내림차순 정렬
    df_all = df_all.sort_values(by="공고일", ascending=False)

# ==========================================
# 3. 사용자 인터페이스 (UI) 출력
# ==========================================

# 탭 구성
tabs = st.tabs(["📊 전체보기", "🏛️ 보건산업진흥원", "🏛️ NIPA", "🏛️ NIA", "🏛️ 과학기술부"])

# 탭 1: 전체 테이블 보기
with tabs[0]:
    st.subheader(f"통합 공고 검색 결과: {len(df_all)}건")
    st.dataframe(
        df_all,
        column_config={"원문링크": st.column_config.LinkColumn("링크", display_text="원문 보기 →")},
        hide_index=True,
        use_container_width=True
    )

# 탭 2~5: 개별 기관별 Expanders UI
def render_agency_tab(agency_name):
    sub_df = df_all[df_all['기관'] == agency_name]
    st.markdown(f"### {agency_name} 최근 공고")
    if sub_df.empty:
        st.info("조건에 맞는 공고가 없습니다.")
    else:
        for _, row in sub_df.iterrows():
            with st.expander(f"[{row['공고일']}] {row['제목']}"):
                if row['접수기간'] != "공고문 참조":
                    st.write(f"**⏳ 신청기간:** {row['접수기간']}")
                st.markdown(f"[🔗 공고 원문 바로가기]({row['원문링크']})")

with tabs[1]: render_agency_tab("한국보건산업진흥원")
with tabs[2]: render_agency_tab("정보통신산업진흥원")
with tabs[3]: render_agency_tab("한국지능정보사회진흥원")
with tabs[4]: render_agency_tab("과학기술정보통신부")
