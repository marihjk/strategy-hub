import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
from curl_cffi import requests as cffi_requests
from datetime import datetime

# 보안 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 설정
st.set_page_config(page_title="전략 정보 HUB", page_icon="🗓️", layout="wide")

# 대제목 노출 (로딩 전 즉시 노출)
st.title("🗓️ 주요 사업 공고")
st.markdown("### 유관기관 사업공고 실시간 모니터링 대시보드")
st.divider()

# ==========================================
# 1. 데이터 수집 함수 정의
# ==========================================

@st.cache_data(ttl=3600)
def get_khidi_data():
    url = "https://www.khidi.or.kr/kps/openAPI/requestxml?rowCnt=50&menuId=MENU01108"
    try:
        response = requests.get(url, timeout=15)
        root = ET.fromstring(response.content)
        data = []
        for row in root.findall('row'):
            title = row.findtext('title') or ""
            link = row.findtext('url') or ""
            date_str = (row.findtext('date') or "")[:10].replace('-', '.')
            data.append({"기관": "한국보건산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        return pd.DataFrame(data)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_nipa_data():
    all_data = []
    for page in range(1, 6):
        url = f"https://www.nipa.kr/home/2-2?curPage={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome120", verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.board-list ul li, .board_list tbody tr, table tbody tr, a[href*="View.do"]')
            for item in items:
                a_tag = item if item.name == 'a' else item.select_one('a')
                if not a_tag: continue
                title = a_tag.get_text(strip=True)
                if len(title) < 10: continue
                href = a_tag.get('href', '')
                link = "https://www.nipa.kr" + href if href.startswith('/') else url
                row_text = item.get_text(separator=' ', strip=True)
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', row_text)
                date_str = date_match.group().replace('-', '.') if date_match else datetime.now().strftime('%Y.%m.%d')
                all_data.append({"기관": "정보통신산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

@st.cache_data(ttl=3600)
def get_nia_data():
    all_data = []
    for page in range(1, 6):
        url = f"https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835&pageIndex={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome120", verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href*="View.do"], .board_list a, .tit a')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                href = a.get('href', '')
                link = "https://www.nia.or.kr/site/nia_kor/ex/bbs/" + href if not href.startswith('http') else href
                parent = a.find_parent(['li', 'tr', 'div'])
                parent_text = parent.get_text() if parent else ""
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', parent_text)
                date_str = date_match.group().replace('-', '.') if date_match else datetime.now().strftime('%Y.%m.%d')
                all_data.append({"기관": "한국지능정보사회진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

@st.cache_data(ttl=3600)
def get_msit_data():
    all_data = []
    headers = {'Referer': 'https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121'}
    for page in range(1, 6):
        url = f"https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121&pageIndex={page}&bbsSeqNo=100"
        try:
            res = cffi_requests.get(url, impersonate="chrome120", headers=headers, verify=False, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('tr')
            for row in rows:
                a = row.select_one('a[href*="view.do"]')
                if not a: continue
                title = a.get_text(strip=True)
                if len(title) < 5: continue
                href = a.get('href', '')
                link = "https://msit.go.kr" + href if href.startswith('/') else url
                row_text = row.get_text(separator=' ', strip=True)
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', row_text)
                date_str = date_match.group().replace('-', '.') if date_match else datetime.now().strftime('%Y.%m.%d')
                all_data.append({"기관": "과학기술정보통신부", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['제목']) if all_data else pd.DataFrame()

# ==========================================
# 2. 데이터 처리 영역
# ==========================================

with st.sidebar:
    st.header("⚙️ 검색 설정")
    # [변경] 날짜 필터 제거, 검색어 위젯만 유지
    search_query = st.text_input("🔍 검색어 입력 (AI, 클라우드 등)", "")

with st.spinner('유관기관 최신 데이터를 불러오고 있습니다...'):
    df_khidi = get_khidi_data()
    df_nipa = get_nipa_data()
    df_nia = get_nia_data()
    df_msit = get_msit_data()

# 데이터 통합
dfs = [df for df in [df_khidi, df_nipa, df_nia, df_msit] if not df.empty]
df_all = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

if not df_all.empty:
    # [변경] 날짜 필터링 로직 제거
    # 검색어 필터만 수행
    if search_query:
        df_all = df_all[df_all['제목'].str.contains(search_query, case=False)]
    
    # 공고일 기준 최신순 정렬
    df_all = df_all.sort_values(by="공고일", ascending=False)

# ==========================================
# 3. 결과 출력 (탭 구성)
# ==========================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 전체보기", 
    "🏛️ 한국보건산업진흥원(KHIDI)", 
    "🏛️ 정보통신산업진흥원(NIPA)", 
    "🏛️ 한국지능정보사회진흥원(NIA)", 
    "🏛️ 과학기술정보통신부(MSIT)"
])

with tab1:
    st.subheader(f"전체 공고: {len(df_all)}건")
    st.dataframe(
        df_all[["기관", "공고일", "제목", "원문링크"]],
        column_config={"원문링크": st.column_config.LinkColumn("링크", display_text="원문 보기 →")},
        hide_index=True, use_container_width=True
    )

org_list = ["한국보건산업진흥원", "정보통신산업진흥원", "한국지능정보사회진흥원", "과학기술정보통신부"]
for tab, org in zip([tab2, tab3, tab4, tab5], org_list):
    with tab:
        st.markdown(f"### {org} 최신 공고")
        sub_df = df_all[df_all['기관'] == org]
        if sub_df.empty:
            st.info("해당하는 공고가 없습니다.")
        else:
            for _, row in sub_df.iterrows():
                with st.expander(f"[{row['공고일']}] {row['제목']}"):
                    st.write(f"**⏳ 접수기간:** {row['접수기간']}")
                    st.markdown(f"[🔗 공고 원문 보러가기]({row['원문링크']})")
