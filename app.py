import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time
import requests

# =========================================================
# 1. 설정 (산업군, 핵심 지표, 가중치)
# =========================================================
CONFIG = {
    "설계(팹리스/IP)": {
        "metrics": ["PER"], 
        "ranges": {"PER": [20, 35], "PBR": [2.5, 5.0], "EV_EBITDA": [15, 25]}, 
        "growth": 12.5, "w_dcf": 0.6, "w_multi": 0.4
    },
    "파운드리": {
        "metrics": ["EV_EBITDA"], 
        "ranges": {"PER": [10, 20], "PBR": [1.0, 2.5], "EV_EBITDA": [6, 10]}, 
        "growth": 8.0, "w_dcf": 0.55, "w_multi": 0.45
    },
    "메모리/IDM": {
        "metrics": ["PBR", "EV_EBITDA"], 
        "ranges": {"PER": [8, 15], "PBR": [1.1, 1.8], "EV_EBITDA": [3.5, 6.0]}, 
        "growth": 3.5, "w_dcf": 0.4, "w_multi": 0.6
    },
    "장비": {
        "metrics": ["PER"], 
        "ranges": {"PER": [15, 25], "PBR": [2.0, 4.0], "EV_EBITDA": [10, 18]}, 
        "growth": 9.0, "w_dcf": 0.55, "w_multi": 0.45
    },
    "소재/케미칼": {
        "metrics": ["PER"], 
        "ranges": {"PER": [12, 20], "PBR": [1.5, 3.5], "EV_EBITDA": [8, 15]}, 
        "growth": 6.0, "w_dcf": 0.5, "w_multi": 0.5
    },
    "후공정(OSAT)": {
        "metrics": ["PER", "PBR"], 
        "ranges": {"PER": [10, 18], "PBR": [1.2, 2.2], "EV_EBITDA": [6, 12]}, 
        "growth": 4.5, "w_dcf": 0.4, "w_multi": 0.6
    },
    "검사/계측": {
        "metrics": ["PER"], 
        "ranges": {"PER": [20, 35], "PBR": [3.0, 6.0], "EV_EBITDA": [15, 25]}, 
        "growth": 10.0, "w_dcf": 0.6, "w_multi": 0.4
    },
    "모듈/부품": {
        "metrics": ["PER"], 
        "ranges": {"PER": [8, 14], "PBR": [1.0, 2.0], "EV_EBITDA": [5, 10]}, 
        "growth": 4.0, "w_dcf": 0.45, "w_multi": 0.55
    },
    "기타": {
        "metrics": ["PER"], 
        "ranges": {"PER": [10, 15], "PBR": [1.0, 1.5], "EV_EBITDA": [5, 8]}, 
        "growth": 3.0, "w_dcf": 0.5, "w_multi": 0.5
    }
}

# 기업별 산업군 매핑
INDUSTRY_MAP = {
    "LX세미콘": "설계(팹리스/IP)", "어보브반도체": "설계(팹리스/IP)", "텔레칩스": "설계(팹리스/IP)", "제주반도체": "설계(팹리스/IP)", "가온칩스": "설계(팹리스/IP)",
    "삼성전자": "메모리/IDM", "SK하이닉스": "메모리/IDM",
    "DB하이텍": "파운드리",
    "한미반도체": "장비", "피에스케이": "장비", "주성엔지니어링": "장비", "HPSP": "장비", "이오테크닉스": "장비", "원익IPS": "장비",
    "동진쎄미켐": "소재/케미칼", "솔브레인": "소재/케미칼", "한솔케미칼": "소재/케미칼", "SKC": "소재/케미칼",
    "하나마이크론": "후공정(OSAT)", "SFA반도체": "후공정(OSAT)", "두산테스나": "후공정(OSAT)", "네패스": "후공정(OSAT)",
    "디아이": "검사/계측", "리노공업": "검사/계측", "고영": "검사/계측", "파크시스템스": "검사/계측", "티에스이": "검사/계측",
    "삼성전기": "모듈/부품", "LG이노텍": "모듈/부품", "심텍": "모듈/부품", "ISC": "모듈/부품", "월덱스": "모듈/부품", "티씨케이": "모듈/부품"
}

# [서버 비상용] KRX 리스트 조회 실패 시 사용할 종목 코드 (선생님 엑셀 파일 전체 반영)
FALLBACK_CODES = {
    "LX세미콘": "108320", "어보브반도체": "102120", "텔레칩스": "054450", "제주반도체": "080220", "가온칩스": "393360",
    "삼성전자": "005930", "SK하이닉스": "000660",
    "DB하이텍": "000990",
    "한미반도체": "042700", "피에스케이": "319660", "주성엔지니어링": "036930", "HPSP": "403870", "이오테크닉스": "039030", "원익IPS": "240810",
    "동진쎄미켐": "005290", "솔브레인": "357780", "한솔케미칼": "014680", "SKC": "011790",
    "하나마이크론": "067310", "SFA반도체": "036540", "두산테스나": "131970", "네패스": "033640",
    "디아이": "003160", "리노공업": "058470", "고영": "098460", "파크시스템스": "140860", "티에스이": "131290",
    "삼성전기": "009150", "LG이노텍": "011070", "심텍": "222800", "ISC": "095340", "월덱스": "101160", "티씨케이": "064760"
}

# =========================================================
# 2. 데이터 수집 함수 (리얼 크롤링)
# =========================================================

# 한국 시간(KST) 구하기
def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

# 네이버 금융에서 '컨센서스(추정치)' 크롤링
def get_naver_finance_real(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        # 브라우저 위장 헤더
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9', # 한국어 요청
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'euc-kr' # 한글 깨짐 방지
        
        dfs = pd.read_html(response.text)
        
        data = {"PER": 0.0, "EPS": 0, "PBR": 0.0, "BPS": 0, "EV_EBITDA": 0.0}
        
        target_df = None
        # '최근 연간 실적' 테이블 찾기
        for df in dfs:
            if '최근 연간 실적' in str(df.columns) or '주요재무제표' in str(df.columns):
                target_df = df
                break
        
        if target_df is None: return None

        # 인덱스 정리
        if not isinstance(target_df.index, pd.Index) or len(target_df.index) == 0:
            target_df = target_df.set_index(target_df.columns[0])

        # 값 추출 (가장 오른쪽 값 = 미래 추정치)
        def extract_val(keywords):
            for idx in target_df.index:
                if any(k in str(idx) for k in keywords):
                    row = target_df.loc[idx]
                    # 숫자로 변환
                    vals = pd.to_numeric(row, errors='coerce')
                    valid_vals = vals.dropna()
                    if not valid_vals.empty:
                        # 2025년(미래) 추정치가 있으면 그걸 가져옴
                        return float(valid_vals.iloc[-1])
            return 0

        data["PER"] = extract_val(['PER', '배'])
        data["EPS"] = int(extract_val(['EPS', '원']))
        data["PBR"] = extract_val(['PBR', '배'])
        data["BPS"] = int(extract_val(['BPS', '원']))
        data["EV_EBITDA"] = extract_val(['EV/EBITDA'])
        
        return data
    except Exception as e:
        return None

# =========================================================
# 3. 계산 함수
# =========================================================

def calculate_dcf(eps, growth_rate):
    discount_rate = 0.10
    fair_value = 0
    curr_eps = eps
    for i in range(1, 6):
        curr_eps = curr_eps * (1 + growth_rate/100)
        fair_value += curr_eps / ((1 + discount_rate) ** i)
    fair_value += (curr_eps / discount_rate) / ((1 + discount_rate) ** 5)
    return int(fair_value)

def calculate_multiple(eps, bps, ebitda_ps, config):
    metrics = config['metrics']
    ranges = config['ranges']
    values = []
    used_metrics_str = []
    
    if "PER" in metrics and eps > 0:
        target = sum(ranges["PER"]) / 2 
        values.append(eps * target)
        used_metrics_str.append(f"PER(×{target})")
        
    if "PBR" in metrics and bps > 0:
        target = sum(ranges["PBR"]) / 2 
        values.append(bps * target)
        used_metrics_str.append(f"PBR(×{target})")
        
    if "EV_EBITDA" in metrics and ebitda_ps > 0:
        target = sum(ranges["EV_EBITDA"]) / 2 
        values.append(ebitda_ps * target)
        used_metrics_str.append(f"EV/EBITDA(×{target})")
        
    if not values: return 0, "데이터 부족"
    return int(sum(values) / len(values)), ", ".join(used_metrics_str)

# =========================================================
# 4. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")
st.title("💎 반도체 실시간 가치 진단 에이전트")
st.caption(f"Server Time (KST): {get_kst_now().strftime('%Y-%m-%d %H:%M')}")

with st.sidebar:
    st.header("🔍 기업 검색")
    stock_name = st.text_input("기업명 입력", placeholder="예: 삼성전자")
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True)

if run_btn and stock_name:
    stock_name = stock_name.strip()
    with st.spinner(f"📡 '{stock_name}' 데이터 크롤링 중..."):
        
        # 1. 코드 찾기 (Fallback Map 우선 -> 실패시 KRX 조회)
        code = FALLBACK_CODES.get(stock_name)
        
        if not code:
            # KRX 리스트에서 찾기 시도
            try:
                today_str = get_kst_now().strftime("%Y%m%d")
                tickers = stock.get_market_ticker_list(today_str, market="KOSPI") + stock.get_market_ticker_list(today_str, market="KOSDAQ")
                for t in tickers:
                    if stock.get_market_ticker_name(t) == stock_name:
                        code = t
                        break
            except: pass
        
        if not code:
            st.error("❌ 기업 코드를 찾을 수 없습니다. (상장폐지 또는 종목명 확인 필요)")
            st.stop()

        try:
            # 2. 데이터 수집 (KRX 주가 + 네이버 재무)
            current_price = 0
            
            # (A) 주가 (KRX)
            try:
                end_date = get_kst_now().strftime("%Y%m%d")
                start_date = (get_kst_now() - timedelta(days=10)).strftime("%Y%m%d")
                price_df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
                if not price_df.empty: 
                    current_price = int(price_df.iloc[-1]['종가'])
            except: pass

            if current_price == 0:
                st.error("주가 데이터를 가져오지 못했습니다. (KRX 접속 실패)")
                st.stop()

            # (B) 재무 데이터 (네이버 금융 크롤링 - 컨센서스)
            n_data = get_naver_finance_real(code)
            
            if not n_data or n_data['EPS'] == 0:
                st.error("재무 데이터를 크롤링하지 못했습니다. (네이버 금융 접속 차단)")
                st.stop()

            eps = n_data['EPS']
            bps = n_data['BPS']
            per = n_data['PER']
            pbr = n_data['PBR']
            ev_ebitda = n_data['EV_EBITDA']

            # (C) 데이터 보정
            if ev_ebitda <= 0 and per > 0: ev_ebitda = round(per * 0.7, 2)
            ebitda_ps = int(current_price / ev_ebitda) if ev_ebitda > 0 else 0
            
            # 3. 가치 평가
            industry = INDUSTRY_MAP.get(stock_name, "기타")
            config = CONFIG.get(industry, CONFIG["기타"])
            
            val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config)
            val_dcf = calculate_dcf(eps, config['growth'])
            
            if val_multi == 0: final_price = val_dcf
            elif val_dcf == 0: final_price = val_multi
            else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
            
            upside = (final_price - current_price) / current_price * 100

            # 4. 출력
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"{stock_name} ({code})")
                st.caption(f"산업군: {industry} | 데이터: 네이버 금융 실시간 크롤링")
            with c2:
                if upside > 15: st.success(f"✅ 저평가 (+{upside:.1f}%)")
                elif upside < -15: st.error(f"⚠️ 고평가 ({upside:.1f}%)")
                else: st.warning(f"⚖️ 적정 주가 ({upside:.1f}%)")
            
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("현재 주가", f"{current_price:,}원")
            m2.metric("적정 주가", f"{int(final_price):,}원", delta=f"{int(final_price-current_price):,}원")
            m3.metric("비중", f"DCF {int(config['w_dcf']*100)} : Multi {int(config['w_multi']*100)}")
            
            st.markdown("---")
            st.write("#### 📊 투자 지표")
            metrics_data = {
                "구분": ["PER", "PBR", "EV/EBITDA"],
                "수치": [f"{per:.2f}배", f"{pbr:.2f}배", f"{ev_ebitda:.2f}배"],
                "비고": ["✅ 핵심" if "PER" in config['metrics'] else "ℹ️ 참고",
                        "✅ 핵심" if "PBR" in config['metrics'] else "ℹ️ 참고",
                        "✅ 핵심" if "EV/EBITDA" in config['metrics'] else "ℹ️ 참고"]
            }
            st.table(pd.DataFrame(metrics_data))
            
            with st.expander("🔍 데이터 원본 보기"):
                st.write(f"- EPS: {eps:,}원")
                st.write(f"- BPS: {bps:,}원")
                st.write(f"- 주당 EBITDA: {ebitda_ps:,}원")
                st.write(f"- 성장률: {config['growth']}%")

        except Exception as e:
            st.error(f"오류: {e}")
