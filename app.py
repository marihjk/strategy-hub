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

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="전략 정보 HUB", page_icon="🗓️", layout="wide")

st.title("🗓️ 주요 사업 공고")
st.markdown("유관기관 사업공고 실시간 모니터링 (KHIDI, NIPA, NIA, MSIT)")
st.divider()

# ==========================================
# 1. 개별 데이터 수집 함수 (독립성 강화)
# ==========================================

def safe_request_get(url, headers=None, impersonate="chrome120"):
    """공통 요청 함수: 실패 시 None 반환"""
    try:
        res = cffi_requests.get(
            url, 
            headers=headers, 
            impersonate=impersonate, 
            verify=False, 
            timeout=20,
            http2=False # Connection Reset 방지를 위해 HTTP/1.1 강제
        )
        if res.status_code == 200:
            return res
    except Exception as e:
        print(f"Request Error ({url}): {e}")
    return None

@st.cache_data(ttl=3600)
def get_khidi_data():
    url = "https://www.khidi.or.kr/kps/openAPI/requestxml?rowCnt=50&menuId=MENU01108"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}
    res = safe_request_get(url, headers)
    data = []
    if res:
        try:
            root = ET.fromstring(res.content)
            for row in root.findall('row'):
                title = row.findtext('title') or ""
                link = row.findtext('url') or ""
                date_str = (row.findtext('date') or "")[:10].replace('-', '.')
                data.append({"기관": "한국보건산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
        except: pass
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def get_nipa_data():
    all_data = []
    for page in range(1, 4): # 속도를 위해 페이지 수 조절
        url = f"https://www.nipa.kr/home/2-2?curPage={page}"
        res = safe_request_get(url)
        if res:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href*="View.do"]')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                link = urljoin("https://www.nipa.kr", a.get('href', ''))
                parent = a.find_parent(['li', 'tr', 'div'])
                p_text = parent.get_text(separator=' ', strip=True) if parent else ""
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', p_text)
                date_str = date_match.group().replace('-', '.') if date_match else "확인필요"
                all_data.append({"기관": "정보통신산업진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
    return pd.DataFrame(all_data)

@st.cache_data(ttl=3600)
def get_nia_data():
    all_data = []
    for page in range(1, 4):
        url = f"https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835&pageIndex={page}"
        res = safe_request_get(url)
        if res:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href*="View.do"]')
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 5: continue
                link = urljoin("https://www.nia.or.kr/site/nia_kor/ex/bbs/", a.get('href', ''))
                parent = a.find_parent(['li', 'tr', 'div'])
                p_text = parent.get_text(separator=' ', strip=True) if parent else ""
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', p_text)
                date_str = date_match.group().replace('-', '.') if date_match else "확인필요"
                all_data.append({"기관": "한국지능정보사회진흥원", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
    return pd.DataFrame(all_data)

@st.cache_data(ttl=3600)
def get_msit_data():
    all_data = []
    headers = {"Referer": "https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121"}
    for page in range(1, 4):
        url = f"https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121&pageIndex={page}&bbsSeqNo=100"
        res = safe_request_get(url, headers=headers)
        if res:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a[href*="view.do"]')
            for a in links:
                title = a.get_text(strip=True)
                link = urljoin("https://msit.go.kr/bbs/", a.get('href', ''))
                parent = a.find_parent(['tr'])
                p_text = parent.get_text(separator=' ', strip=True) if parent else ""
                date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', p_text)
                date_str = date_match.group().replace('-', '.') if date_match else "확인필요"
                all_data.append({"기관": "과학기술정보통신부", "공고일": date_str, "제목": title, "접수기간": "공고문 참조", "원문링크": link})
    return pd.DataFrame(all_data)

# ==========================================
# 2. 메인 실행 로직
# ==========================================

# 사이드바 검색
with st.sidebar:
    st.header("⚙️ 필터")
    search_query = st.text_input("🔍 검색어", "")

# 데이터 수집 (각각 독립적으로 실행하여 하나가 죽어도 나머지는 살림)
with st.spinner('데이터 수집 중...'):
    df1 = get_khidi_data()
    df2 = get_nipa_data()
    df3 = get_nia_data()
    df4 = get_msit_data()

# 모든 결과 병합 (빈 데이터프레임 포함하여 안전하게 결합)
all_dfs = []
for d in [df1, df2, df3, df4]:
    if isinstance(d, pd.DataFrame) and not d.empty:
        all_dfs.append(d)

if all_dfs:
    df_all = pd.concat(all_dfs, ignore_index=True)
    # 중복 제거 및 정렬
    df_all = df_all.drop_duplicates(subset=['제목']).sort_values(by="공고일", ascending=False)
    
    if search_query:
        df_all = df_all[df_all['제목'].str.contains(search_query, case=False)]
else:
    df_all = pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# ==========================================
# 3. UI 출력
# ==========================================

tabs = st.tabs(["📊 전체", "🏛️ KHIDI", "🏛️ NIPA", "🏛️ NIA", "🏛️ MSIT"])

with tabs[0]:
    if df_all.empty:
        st.warning("수집된 공고가 없습니다. 잠시 후 다시 시도하거나 로컬 환경을 확인하세요.")
    else:
        st.dataframe(df_all, column_config={"원문링크": st.column_config.LinkColumn("링크", display_text="원문보기")}, hide_index=True, use_container_width=True)

def render_tab(tab_obj, agency_name):
    with tab_obj:
        sub = df_all[df_all['기관'] == agency_name]
        if sub.empty: st.info(f"{agency_name} 공고가 없습니다.")
        else:
            for _, row in sub.iterrows():
                with st.expander(f"[{row['공고일']}] {row['제목']}"):
                    st.markdown(f"[🔗 원문 링크]({row['원문링크']})")

render_tab(tabs[1], "한국보건산업진흥원")
render_tab(tabs[2], "정보통신산업진흥원")
render_tab(tabs[3], "한국지능정보사회진흥원")
render_tab(tabs[4], "과학기술정보통신부")
