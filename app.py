import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
from curl_cffi import requests as cffi_requests
import time
from datetime import datetime, date

# 보안 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 기본 설정
st.set_page_config(page_title="전략 정보 HUB", page_icon="🗓️", layout="wide")

st.title("🗓️ 주요 사업 공고")
st.markdown("유관기관 사업공고 실시간 모니터링 대시보드")
st.divider()

# ==========================================
# 1. 데이터 수집 함수 (강력한 전천후 탐색 + 5페이지 루프)
# ==========================================

# [함수 1] 보건산업진흥원(KHIDI) - OpenAPI (기본 50건)
@st.cache_data(ttl=3600)
def get_khidi_data():
    url = "https://www.khidi.or.kr/kps/openAPI/requestxml?rowCnt=50&menuId=MENU01108"
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        data = []
        for row in root.findall('row'):
            title = row.findtext('title') or ""
            link = row.findtext('url') or ""
            date_str = (row.findtext('date') or "")[:10].replace('-', '.')
            data.append({"기관": "한국보건산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# [함수 2] 정보통신산업진흥원(NIPA) - 1~5페이지
@st.cache_data(ttl=3600)
def get_nipa_data():
    all_data = []
    for page in range(1, 6):
        url = f"https://www.nipa.kr/home/2-2?curPage={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome116", verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href*="View.do"], .board-list a, .board_list a, table a')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                href = a.get('href', '')
                link = "https://www.nipa.kr" + href if href.startswith('/') else url
                
                parent = a.find_parent(['li', 'tr', 'div'])
                parent_text = parent.get_text(separator=' ', strip=True) if parent else ""
                
                period_match = re.search(r'신청기간\s*[:]\s*([0-9\-\:\s~]+)', parent_text)
                period = period_match.group(1).strip() if period_match else "공고문 참조"
                
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', parent_text)
                date_str = date_match.group().replace('-', '.') if date_match else "날짜 확인 필요"
                
                all_data.append({"기관": "정보통신산업진흥원", "공고일": date_str, "제목": title, "접수기간": period, "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# [함수 3] 한국지능정보사회진흥원(NIA) - 1~5페이지
@st.cache_data(ttl=3600)
def get_nia_data():
    all_data = []
    for page in range(1, 6):
        url = f"https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835&pageIndex={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome116", verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href]')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                
                parent = a.find_parent(['li', 'tr', 'div'])
                parent_text = parent.get_text(separator=' ', strip=True) if parent else ""
                
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', parent_text)
                if not date_match: continue
                
                href = a.get('href', '')
                link = "https://www.nia.or.kr/site/nia_kor/ex/bbs/" + href if not href.startswith('http') else href
                date_str = date_match.group().replace('-', '.')
                
                all_data.append({"기관": "한국지능정보사회진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# [함수 4] 과학기술정보통신부(MSIT) - 1~5페이지
@st.cache_data(ttl=3600)
def get_msit_data():
    all_data = []
    msit_headers = {
        'Referer': 'https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    for page in range(1, 6):
        url = f"https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121&pageIndex={page}&bbsSeqNo=100"
        try:
            res = cffi_requests.get(url, impersonate="chrome120", headers=msit_headers, verify=False, timeout=15)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            rows = soup.find_all('tr')
            for row in rows:
                a_tag = row.select_one('a[href*="view.do"]')
                if not a_tag: continue
                
                title = a_tag.get_text(strip=True)
                if len(title) < 5: continue
                
                href = a_tag.get('href', '')
                link = "https://msit.go.kr" + href if href.startswith('/') else url
                
                row_text = row.get_text(separator=' ', strip=True)
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', row_text)
                date_str = date_match.group().replace('-', '.') if date_match else "날짜 확인 필요"
                
                all_data.append({"기관": "과학기술정보통신부", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
        
    df = pd.DataFrame(all_data)
    if not df.empty:
        return df.drop_duplicates(subset=['제목'])
    return pd.DataFrame()

# ==========================================
# 2. 데이터 처리 메인 로직 (날짜 필터 제거됨)
# ==========================================

# 사이드바 필터 설정
with st.sidebar:
    st.header("⚙️ 필터 설정")
    search_query = st.text_input("🔍 검색어 입력 (AI, 의료 등)", "")

# 데이터 수집
with st.spinner('실시간 데이터를 동기화 중입니다...'):
    df_khidi = get_khidi_data()
    df_nipa = get_nipa_data()
    df_nia = get_nia_data()
    df_msit = get_msit_data()

# 데이터 병합
dfs = [df for df in [df_khidi, df_nipa, df_nia, df_msit] if not df.empty]
df_all = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# 필터링 적용
if not df_all.empty:
    filtered_df = df_all.copy()
    
    # 검색어 필터링만 적용
    if search_query:
        filtered_df = filtered_df[filtered_df['제목'].str.contains(search_query, case=False)]
    
    # 최신순 정렬
    filtered_df = filtered_df.sort_values(by="공고일", ascending=False)
else:
    filtered_df = df_all

# ==========================================
# 3. 탭 구성
# ==========================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 전체보기", "🏛️ 한국보건산업진흥원", "🏛️ 정보통신산업진흥원", "🏛️ 한국지능정보사회진흥원", "🏛️ 과학기술정보통신부"
])

with tab1:
    st.subheader(f"통합 검색 결과: {len(filtered_df)}건")
    st.dataframe(
        filtered_df,
        column_config={"원문링크": st.column_config.LinkColumn("링크", display_text="원문 보기 →")},
        hide_index=True,
        use_container_width=True
    )

with tab2:
    st.markdown("### 한국보건산업진흥원(KHIDI) 공고")
    sub_df = filtered_df[filtered_df['기관'] == '한국보건산업진흥원']
    if sub_df.empty: st.info("공고가 없습니다.")
    for idx, row in sub_df.iterrows():
        with st.expander(f"[{row['공고일']}] {row['제목']}"):
            st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")

with tab3:
    st.markdown("### 정보통신산업진흥원(NIPA) 공고")
    sub_df = filtered_df[filtered_df['기관'] == '정보통신산업진흥원']
    if sub_df.empty: st.info("공고가 없습니다.")
    for idx, row in sub_df.iterrows():
        with st.expander(f"[{row['공고일']}] {row['제목']}"):
            st.write(f"**⏳ 신청기간:** {row['접수기간']}")
            st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")

with tab4:
    st.markdown("### 한국지능정보사회진흥원(NIA) 공고")
    sub_df = filtered_df[filtered_df['기관'] == '한국지능정보사회진흥원']
    if sub_df.empty: st.info("공고가 없습니다.")
    for idx, row in sub_df.iterrows():
        with st.expander(f"[{row['공고일']}] {row['제목']}"):
            st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")

with tab5:
    st.markdown("### 과학기술정보통신부(MSIT) 공고")
    sub_df = filtered_df[filtered_df['기관'] == '과학기술정보통신부']
    if sub_df.empty: st.info("공고가 없습니다.")
    for idx, row in sub_df.iterrows():
        with st.expander(f"[{row['공고일']}] {row['제목']}"):
            st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")
