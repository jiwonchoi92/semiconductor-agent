import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time
import requests
import yfinance as yf # 야후 파이낸스 추가

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

# [비상용 코드 지도]
FALLBACK_CODES = {
    "삼성전자": "005930", "SK하이닉스": "000660", "DB하이텍": "000990",
    "LX세미콘": "108320", "한미반도체": "042700", "HPSP": "403870",
    "리노공업": "058470", "솔브레인": "357780", "동진쎄미켐": "005290",
    "하나마이크론": "067310", "SFA반도체": "036540", "LG이노텍": "011070",
    "삼성전기": "009150", "원익IPS": "240810", "이오테크닉스": "039030",
    "피에스케이": "319660", "고영": "098460", "티에스이": "131290",
    "어보브반도체": "102120", "텔레칩스": "054450", "제주반도체": "080220"
}

# =========================================================
# 2. 데이터 수집 함수 (KRX -> Naver -> Yahoo 3중 안전장치)
# =========================================================

def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

# [NEW] 야후 파이낸스 백업 (해외 서버에서 가장 강력함)
def get_yahoo_finance_data(code):
    try:
        # 코스피(.KS) 시도 후 실패하면 코스닥(.KQ) 시도
        tickers = [f"{code}.KS", f"{code}.KQ"]
        data = None
        
        for t in tickers:
            stock_info = yf.Ticker(t)
            info = stock_info.info
            # 데이터가 유효한지 확인 (가격이 있는지)
            if info and 'currentPrice' in info and info['currentPrice'] > 0:
                data = info
                break
                
        if not data: return None

        # 데이터 매핑
        return {
            "price": data.get('currentPrice', 0),
            "EPS": data.get('trailingEps', 0), # TTM 기준 EPS
            "BPS": data.get('bookValue', 0),
            "PER": data.get('trailingPE', 0),
            "PBR": data.get('priceToBook', 0),
            "EV_EBITDA": data.get('enterpriseToEbitda', 0)
        }
    except:
        return None

def get_naver_finance_all(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        header = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=header)
        dfs = pd.read_html(response.text)
        
        data = {"PER": 0.0, "EPS": 0, "PBR": 0.0, "BPS": 0, "EV_EBITDA": 0.0}
        
        for df in dfs:
            try:
                if len(df.index) > 0: df = df.set_index(df.columns[0])
            except: continue

            def find_value(keywords):
                for idx in df.index:
                    if any(k in str(idx) for k in keywords):
                        row = df.loc[idx]
                        vals = pd.to_numeric(row, errors='coerce')
                        valid_vals = vals.dropna()
                        if not valid_vals.empty: return float(valid_vals.iloc[-1])
                return None

            if data["PER"] == 0: data["PER"] = find_value(['PER', '배']) or 0
            if data["EPS"] == 0: data["EPS"] = int(find_value(['EPS', '원']) or 0)
            if data["PBR"] == 0: data["PBR"] = find_value(['PBR', '배']) or 0
            if data["BPS"] == 0: data["BPS"] = int(find_value(['BPS', '원']) or 0)
            if data["EV_EBITDA"] == 0: data["EV_EBITDA"] = find_value(['EV/EBITDA']) or 0

        return data
    except:
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
    
    with st.spinner(f"📡 '{stock_name}' 데이터 수집 중..."):
        
        # 1. 종목코드 찾기
        code = None
        # Fallback Map 먼저 확인 (빠른 검색)
        code = FALLBACK_CODES.get(stock_name)
        
        if not code:
            try:
                tickers = stock.get_market_ticker_list(market="KOSPI") + stock.get_market_ticker_list(market="KOSDAQ")
                for t in tickers:
                    if stock.get_market_ticker_name(t) == stock_name:
                        code = t
                        break
            except: pass

        if not code:
            st.error(f"❌ '{stock_name}'을(를) 찾을 수 없습니다.")
            st.stop()

        try:
            # 2. 데이터 수집 (우선순위: KRX -> Yahoo -> Naver)
            # 서버에서는 KRX 차단 가능성이 높으므로 Yahoo Finance를 2순위로 격상
            
            current_price = 0
            eps, bps, per, pbr, ev_ebitda = 0, 0, 0.0, 0.0, 0.0
            data_source = ""

            # (A) KRX 시도
            try:
                end_date = get_kst_now().strftime("%Y%m%d")
                start_date = (get_kst_now() - timedelta(days=30)).strftime("%Y%m%d")
                price_df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
                if not price_df.empty:
                    current_price = int(price_df.iloc[-1]['종가'])
                    
                fund_df = stock.get_market_fundamental_by_date(start_date, end_date, code)
                if not fund_df.empty:
                    for i in range(len(fund_df)-1, -1, -1):
                        row = fund_df.iloc[i]
                        if row['PER'] > 0 or row['EPS'] > 0:
                            eps = int(row.get('EPS', 0))
                            bps = int(row.get('BPS', 0))
                            per = float(row.get('PER', 0))
                            pbr = float(row.get('PBR', 0))
                            break
                if current_price > 0 and eps > 0:
                    data_source = "KRX (한국거래소)"
            except: pass

            # (B) KRX 실패 시 Yahoo Finance (강력한 백업)
            if current_price == 0 or eps == 0:
                yahoo_data = get_yahoo_finance_data(code)
                if yahoo_data:
                    current_price = int(yahoo_data['price'])
                    eps = int(yahoo_data['EPS'])
                    bps = int(yahoo_data['BPS'])
                    per = float(yahoo_data['PER'])
                    pbr = float(yahoo_data['PBR'])
                    if yahoo_data['EV_EBITDA'] > 0:
                        ev_ebitda = float(yahoo_data['EV_EBITDA'])
                    data_source = "Yahoo Finance (Global)"

            # (C) 그래도 EV/EBITDA가 없으면 Naver 시도
            if ev_ebitda == 0:
                naver_data = get_naver_finance_all(code)
                if naver_data:
                    ev_ebitda = naver_data.get("EV_EBITDA", 0.0)
                    # 만약 여전히 EPS가 0이면 네이버 데이터 사용
                    if eps == 0: 
                        eps = int(naver_data.get("EPS", 0))
                        data_source = "Naver Finance"
                        if current_price == 0: # 가격도 못 구했으면 네이버 크롤링해야하나 여기선 생략
                            st.error("현재가 정보를 가져올 수 없습니다.")
                            st.stop()

            # (D) 보정 및 역산
            if ev_ebitda <= 0 and per > 0: ev_ebitda = round(per * 0.7, 2)
            ebitda_ps = int(current_price / ev_ebitda) if ev_ebitda > 0 else 0
            
            if eps == 0:
                st.error("재무 데이터(EPS)를 가져오는데 실패했습니다.")
                st.stop()

            # 3. 가치 평가
            industry = INDUSTRY_MAP.get(stock_name, "기타")
            config = CONFIG.get(industry, CONFIG["기타"])
            
            val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config)
            val_dcf = calculate_dcf(eps, config['growth'])
            
            if val_multi == 0 and val_dcf > 0: final_price = val_dcf
            elif val_dcf == 0 and val_multi > 0: final_price = val_multi
            elif val_dcf == 0 and val_multi == 0: final_price = current_price
            else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
            
            upside = (final_price - current_price) / current_price * 100

            # 4. 화면 출력
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"{stock_name} ({code})")
                st.caption(f"산업군: {industry} | 데이터 출처: {data_source}")
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
            
            with st.expander("🔍 데이터 원본 보기"):
                st.write(f"- EPS: {eps:,}원")
                st.write(f"- BPS: {bps:,}원")
                st.write(f"- 주당 EBITDA: {ebitda_ps:,}원")
                st.write(f"- 적용 성장률: {config['growth']}%")

        except Exception as e:
            st.error(f"데이터 수집 중 오류가 발생했습니다: {e}")
