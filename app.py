import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
from curl_cffi import requests as cffi_requests
import time

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

# [함수 2] 정보통신산업진흥원(NIPA) - 1~2페이지
@st.cache_data(ttl=3600)
def get_nipa_data():
    all_data = []
    for page in range(1, 3):
        url = f"https://www.nipa.kr/home/2-2?curPage={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome116", verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 본문 영역의 모든 링크 탐색
            links = soup.select('a[href*="View.do"], .board-list a, .board_list a, table a')
            
            for a in links:
                title = a.get_text(strip=True)
                if len(title) < 10: continue
                
                href = a.get('href', '')
                link = "https://www.nipa.kr" + href if href.startswith('/') else url
                
                # 1. 부모 요소를 <tr>(테이블 행 전체)로 명확히 지정하여 탐색 범위를 넓힘
                tr = a.find_parent('tr')
                
                if not tr:
                    continue
                
                # 2. [핵심] 캡처 화면에서 확인된 <span class="bco"> 태그를 직접 찌름 (가장 정확)
                date_span = tr.select_one('span.bco')
                
                if date_span:
                    date_str = date_span.get_text(strip=True).replace('-', '.')
                else:
                    # 혹시 span.bco가 없는 예외 케이스를 대비해 정규식 플랜B 가동
                    tr_text = tr.get_text(separator=' ', strip=True)
                    date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', tr_text)
                    date_str = date_match.group().replace('-', '.') if date_match else "날짜 확인 필요"
                
                # 3. 신청기간 추출 (행 전체 텍스트에서 정규식으로 뽑아냄)
                full_text = tr.get_text(separator=' ', strip=True)
                period_match = re.search(r'신청기간\s*[:]\s*([0-9\-\:\s~]+)', full_text)
                period = period_match.group(1).strip() if period_match else "공고문 참조"
                
                all_data.append({
                    "기관": "정보통신산업진흥원", 
                    "공고일": date_str, 
                    "제목": title, 
                    "접수기간": period, 
                    "원문링크": link
                })
        except: continue
        
    df = pd.DataFrame(all_data)
    if not df.empty:
        return df.drop_duplicates(subset=['제목'])
    return pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# [함수 3] 한국지능정보사회진흥원(NIA) - 1~2페이지
@st.cache_data(ttl=3600)
def get_nia_data():
    all_data = []
    # NIA 공고 목록 페이지
    list_url = "https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        res = cffi_requests.get(list_url, impersonate="chrome120", headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 표의 행(tr) 또는 리스트(li) 단위를 모두 탐색
        items = soup.find_all(['tr', 'li'])
        
        for item in items:
            item_text = item.get_text(separator=' ', strip=True)
            
            # 해당 줄에 'YYYY-MM-DD' 또는 'YYYY.MM.DD' 형식의 날짜가 있는지 확인
            date_match = re.search(r'\d{4}[\-\.]\d{2}[\-\.]\d{2}', item_text)
            
            # 날짜가 있고, 그 안에 링크(a 태그)가 있다면 100% 게시물 행입니다.
            if date_match:
                a_tag = item.find('a')
                if not a_tag: continue
                
                title = a_tag.get_text(strip=True)

                # 'new2026' 같은 아이콘 텍스트나 '조회수'라는 단어를 기점으로 문자열을 쪼갠 후 앞부분만 가져옵니다.
                title = re.split(r'new20\d{2}|조회수', title)[0].strip()
                
                # 가끔 "새글" 같은 아이콘 텍스트가 딸려오는 경우 제거
                title = re.sub(r'새글|첨부파일', '', title).strip()
                
                # 제목이 너무 짧으면 패스 (예: 단순 번호나 메뉴)
                if len(title) < 5: continue
                
                date_str = date_match.group().replace('-', '.')
                
                all_data.append({
                    "기관": "한국지능정보사회진흥원", 
                    "공고일": date_str, 
                    "제목": title, 
                    "접수기간": "공고 목록에서 확인", 
                    "원문링크": list_url # 상세페이지 에러를 피하기 위해 무조건 목록으로 연결
                })
                
    except Exception as e:
        # 에러 발생 시 앱이 죽지 않도록 조용히 넘김
        pass
        
    df = pd.DataFrame(all_data)
    
    if not df.empty:
        # 중복 제거 후 가장 최신 데이터 반환
        return df.drop_duplicates(subset=['제목'])
        
    return pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

# [함수 4] 과학기술정보통신부(MSIT) - 1~2페이지
@st.cache_data(ttl=3600)
def get_msit_data():
    all_data = []
    # 과기부 전용 헤더 추가 (Referer 필수)
    msit_headers = {
        'Referer': 'https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    for page in range(1, 3):
        url = f"https://msit.go.kr/bbs/list.do?sCode=user&mId=311&mPid=121&pageIndex={page}&bbsSeqNo=100"
        try:
            # impersonate="chrome120"과 전용 헤더 사용
            res = cffi_requests.get(url, impersonate="chrome120", headers=msit_headers, verify=False, timeout=15)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 모든 'view.do' 링크가 포함된 행(tr)을 싹 훑습니다.
            rows = soup.find_all('tr')
            for row in rows:
                a_tag = row.select_one('a[href*="view.do"]')
                if not a_tag: continue
                
                title = a_tag.get_text(strip=True)
                if len(title) < 5: continue # 너무 짧은 텍스트 제외
                
                href = a_tag.get('href', '')
                link = "https://msit.go.kr" + href if href.startswith('/') else url
                
                # 2. 날짜 찾기: 행 내에서 YYYY-MM-DD 패턴을 가진 모든 텍스트 검색
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
# 2. 데이터 처리 메인 로직
# ==========================================

with st.spinner('유관기관 최신 데이터를 5페이지씩 정밀 수집 중입니다...'):
    df_khidi = get_khidi_data()
    df_nipa = get_nipa_data()
    df_nia = get_nia_data()
    df_msit = get_msit_data()

# 모든 기관 데이터 병합
dfs = [df for df in [df_khidi, df_nipa, df_nia, df_msit] if not df.empty]
df_all = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=["기관", "공고일", "제목", "접수기간", "원문링크"])

if not df_all.empty:
    df_all = df_all.sort_values(by="공고일", ascending=False)

# 검색어 필터링
search_query = st.text_input("🔍 검색어 입력 (예: AI, 클라우드, 보안, 의료데이터)", "")
filtered_df = df_all[df_all['제목'].str.contains(search_query, case=False)] if search_query else df_all

# ==========================================
# 3. 탭 구성 (요청하신 expander 스타일)
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
