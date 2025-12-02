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

INDUSTRY_MAP = {
    "LX세미콘": "설계(팹리스/IP)", "텔레칩스": "설계(팹리스/IP)", "칩스앤미디어": "설계(팹리스/IP)", 
    "어보브반도체": "설계(팹리스/IP)", "제주반도체": "설계(팹리스/IP)", "가온칩스": "설계(팹리스/IP)",
    "삼성전자": "메모리/IDM", "SK하이닉스": "메모리/IDM",
    "DB하이텍": "파운드리", 
    "한미반도체": "장비", "주성엔지니어링": "장비", "HPSP": "장비", "이오테크닉스": "장비", 
    "원익IPS": "장비", "피에스케이": "장비", "테스": "장비", "유진테크": "장비",
    "솔브레인": "소재/케미칼", "동진쎄미켐": "소재/케미칼", "한솔케미칼": "소재/케미칼", "SKC": "소재/케미칼",
    "하나마이크론": "후공정(OSAT)", "SFA반도체": "후공정(OSAT)", "두산테스나": "후공정(OSAT)", "네패스": "후공정(OSAT)",
    "리노공업": "검사/계측", "파크시스템스": "검사/계측", "고영": "검사/계측", "티에스이": "검사/계측", "디아이": "검사/계측",
    "ISC": "모듈/부품", "월덱스": "모듈/부품", "티씨케이": "모듈/부품", "삼성전기": "모듈/부품", "LG이노텍": "모듈/부품", "심텍": "모듈/부품"
}

# =========================================================
# 2. 유틸리티 함수 (데이터 수집 보조)
# =========================================================

# 최근 영업일 찾기 및 종목 리스트 확보 (핵심 수정)
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_valid_tickers_and_date():
    # 오늘부터 7일 전까지 역순으로 조회하여 데이터가 있는 날짜 찾기
    for i in range(7):
        try:
            target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            # KOSPI 종목 리스트 조회 시도
            kospi = stock.get_market_ticker_list(target_date, market="KOSPI")
            kosdaq = stock.get_market_ticker_list(target_date, market="KOSDAQ")
            
            if kospi and kosdaq: # 데이터가 존재하면
                return kospi + kosdaq, target_date
        except:
            continue
    return [], None

def get_naver_finance_all(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        header = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=header)
        dfs = pd.read_html(response.text)
        
        data = {"PER": 0.0, "EPS": 0, "PBR": 0.0, "BPS": 0, "EV_EBITDA": 0.0}
        
        for df in dfs:
            try:
                if not isinstance(df.index, pd.Index) or len(df.index) == 0 or isinstance(df.index[0], int):
                    df = df.set_index(df.columns[0])
            except:
                continue

            def find_value(keywords):
                for idx in df.index:
                    if any(k in str(idx) for k in keywords):
                        row = df.loc[idx]
                        vals = pd.to_numeric(row, errors='coerce')
                        valid_vals = vals.dropna()
                        if not valid_vals.empty:
                            return float(valid_vals.iloc[-1])
                return None

            if data["PER"] == 0: 
                val = find_value(['PER', '배'])
                if val: data["PER"] = val
            
            if data["EPS"] == 0: 
                val = find_value(['EPS', '원'])
                if val: data["EPS"] = int(val)
            
            if data["PBR"] == 0: 
                val = find_value(['PBR', '배'])
                if val: data["PBR"] = val
            
            if data["BPS"] == 0: 
                val = find_value(['BPS', '원'])
                if val: data["BPS"] = int(val)
                
            if data["EV_EBITDA"] == 0:
                val = find_value(['EV/EBITDA'])
                if val: data["EV_EBITDA"] = val

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
        
    if not values: return 0, "지표 부족 (적자 등)"
    return int(sum(values) / len(values)), ", ".join(used_metrics_str)

# =========================================================
# 4. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")

st.title("💎 반도체 실시간 가치 진단 에이전트")
st.caption("Source: KRX(우선) + Naver Finance(백업)")

with st.sidebar:
    st.header("🔍 기업 검색")
    stock_name = st.text_input("기업명 입력", placeholder="예: 삼성전자")
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True)

if run_btn and stock_name:
    # 입력값 공백 제거
    stock_name = stock_name.strip()
    
    with st.spinner(f"📡 '{stock_name}' 데이터 수집 중..."):
        
        # 1. 종목코드 찾기 (안전한 방식 적용)
        tickers, valid_date = get_valid_tickers_and_date()
        
        if not tickers:
            st.error("KRX 서버 접속에 실패했습니다. 잠시 후 다시 시도해주세요.")
            st.stop()

        code = None
        for t in tickers:
            # KRX에서 종목명 가져오기
            if stock.get_market_ticker_name(t) == stock_name:
                code = t
                break
        
        if not code:
            st.error(f"❌ '{stock_name}'을(를) 찾을 수 없습니다. (정확한 종목명을 입력해주세요)")
            st.stop()

        try:
            # 2. 데이터 수집
            # 유효한 날짜(valid_date)를 기준으로 조회
            
            # (A) 주가
            price_df = stock.get_market_ohlcv_by_date(valid_date, valid_date, code)
            if price_df.empty:
                # 만약 valid_date에도 주가가 없다면(거래정지 등) 최근 30일치 다시 조회
                start_date = (datetime.strptime(valid_date, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
                price_df = stock.get_market_ohlcv_by_date(start_date, valid_date, code)
            
            if price_df.empty:
                st.error("주가 데이터를 가져올 수 없습니다.")
                st.stop()
                
            current_price = int(price_df.iloc[-1]['종가'])

            # (B) 펀더멘탈 (KRX)
            eps, bps, per, pbr = 0, 0, 0.0, 0.0
            
            # 검색 기간을 넉넉하게 잡아서 최신 데이터 확보
            start_date_fund = (datetime.strptime(valid_date, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
            fund_df = stock.get_market_fundamental_by_date(start_date_fund, valid_date, code)
            
            if not fund_df.empty:
                # 0이 아닌 값이 있는 가장 최신 행 찾기
                for i in range(len(fund_df)-1, -1, -1):
                    row = fund_df.iloc[i]
                    if row['PER'] > 0 or row['EPS'] > 0:
                        eps = int(row.get('EPS', 0))
                        bps = int(row.get('BPS', 0))
                        per = float(row.get('PER', 0))
                        pbr = float(row.get('PBR', 0))
                        break

            # (C) 네이버 백업
            naver_data = get_naver_finance_all(code)
            ev_ebitda = 0.0
            if naver_data:
                ev_ebitda = naver_data.get("EV_EBITDA", 0.0)
                if eps == 0: eps = int(naver_data.get("EPS", 0))
                if bps == 0: bps = int(naver_data.get("BPS", 0))
                if per == 0: per = float(naver_data.get("PER", 0.0))
                if pbr == 0: pbr = float(naver_data.get("PBR", 0.0))

            # (D) 보정 및 역산
            if ev_ebitda <= 0 and per > 0: ev_ebitda = round(per * 0.7, 2)
            ebitda_ps = int(current_price / ev_ebitda) if ev_ebitda > 0 else 0
            
            # 3. 가치 평가
            industry = INDUSTRY_MAP.get(stock_name, "기타")
            config = CONFIG.get(industry, CONFIG["기타"])
            
            val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config)
            val_dcf = calculate_dcf(eps, config['growth'])
            
            if val_multi == 0 and val_dcf > 0: final_price = val_dcf
            elif val_dcf == 0 and val_multi > 0: final_price = val_multi
            elif val_dcf == 0 and val_multi == 0: final_price = current_price
            else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
            
            upside = (final_price - current_price) / current_price * 100 if current_price > 0 else 0

            # 4. 출력
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"{stock_name} ({code})")
                st.caption(f"산업군: {industry}")
            with c2:
                if upside > 15:
                    st.success(f"✅ 저평가 (+{upside:.1f}%)")
                elif upside < -15:
                    st.error(f"⚠️ 고평가 ({upside:.1f}%)")
                else:
                    st.warning(f"⚖️ 적정 주가 ({upside:.1f}%)")
            
            st.divider()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("현재 주가", f"{current_price:,}원")
            m2.metric("적정 주가", f"{int(final_price):,}원", delta=f"{int(final_price-current_price):,}원")
            m3.metric("평가 비중", f"DCF {int(config['w_dcf']*100)}% : Multi {int(config['w_multi']*100)}%")
            
            st.markdown("---")
            st.write("#### 📊 투자 지표 상세")
            
            metrics_data = {
                "구분": ["PER (주가수익비율)", "PBR (주가순자산비율)", "EV/EBITDA"],
                "현재 수치": [f"{per:.2f}배", f"{pbr:.2f}배", f"{ev_ebitda:.2f}배"],
                "적용 여부": [
                    "✅ 핵심 지표" if "PER" in config['metrics'] else "ℹ️ 보조 지표",
                    "✅ 핵심 지표" if "PBR" in config['metrics'] else "ℹ️ 보조 지표",
                    "✅ 핵심 지표" if "EV/EBITDA" in config['metrics'] else "ℹ️ 보조 지표"
                ]
            }
            st.table(pd.DataFrame(metrics_data))
            
            with st.expander("🔍 데이터 원본 보기 (KRX/Naver)"):
                st.write(f"- EPS: {eps:,}원 | BPS: {bps:,}원 | 주당 EBITDA: {ebitda_ps:,}원")
                st.write(f"- 멀티플 산출식: {multi_desc}")
                st.write(f"- DCF 성장률: {config['growth']}%")

        except Exception as e:
            st.error(f"오류 발생: {e}")
