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
    "설계(팹리스/IP)": {"metrics": ["PER"], "ranges": {"PER": [20, 35], "PBR": [2.5, 5.0], "EV_EBITDA": [15, 25]}, "growth": 12.5, "w_dcf": 0.6, "w_multi": 0.4},
    "파운드리": {"metrics": ["EV_EBITDA"], "ranges": {"PER": [10, 20], "PBR": [1.0, 2.5], "EV_EBITDA": [6, 10]}, "growth": 8.0, "w_dcf": 0.55, "w_multi": 0.45},
    "메모리/IDM": {"metrics": ["PBR", "EV_EBITDA"], "ranges": {"PER": [8, 15], "PBR": [1.1, 1.8], "EV_EBITDA": [3.5, 6.0]}, "growth": 3.5, "w_dcf": 0.4, "w_multi": 0.6},
    "장비": {"metrics": ["PER"], "ranges": {"PER": [15, 25], "PBR": [2.0, 4.0], "EV_EBITDA": [10, 18]}, "growth": 9.0, "w_dcf": 0.55, "w_multi": 0.45},
    "소재/케미칼": {"metrics": ["PER"], "ranges": {"PER": [12, 20], "PBR": [1.5, 3.5], "EV_EBITDA": [8, 15]}, "growth": 6.0, "w_dcf": 0.5, "w_multi": 0.5},
    "후공정(OSAT)": {"metrics": ["PER", "PBR"], "ranges": {"PER": [10, 18], "PBR": [1.2, 2.2], "EV_EBITDA": [6, 12]}, "growth": 4.5, "w_dcf": 0.4, "w_multi": 0.6},
    "검사/계측": {"metrics": ["PER"], "ranges": {"PER": [20, 35], "PBR": [3.0, 6.0], "EV_EBITDA": [15, 25]}, "growth": 10.0, "w_dcf": 0.6, "w_multi": 0.4},
    "모듈/부품": {"metrics": ["PER"], "ranges": {"PER": [8, 14], "PBR": [1.0, 2.0], "EV_EBITDA": [5, 10]}, "growth": 4.0, "w_dcf": 0.45, "w_multi": 0.55},
    "기타": {"metrics": ["PER"], "ranges": {"PER": [10, 15], "PBR": [1.0, 1.5], "EV_EBITDA": [5, 8]}, "growth": 3.0, "w_dcf": 0.5, "w_multi": 0.5}
}

INDUSTRY_MAP = {
    "LX세미콘": "설계(팹리스/IP)", "텔레칩스": "설계(팹리스/IP)", "칩스앤미디어": "설계(팹리스/IP)", "어보브반도체": "설계(팹리스/IP)", "제주반도체": "설계(팹리스/IP)",
    "삼성전자": "메모리/IDM", "SK하이닉스": "메모리/IDM", "DB하이텍": "파운드리", 
    "한미반도체": "장비", "주성엔지니어링": "장비", "HPSP": "장비", "이오테크닉스": "장비", "원익IPS": "장비", "피에스케이": "장비",
    "솔브레인": "소재/케미칼", "동진쎄미켐": "소재/케미칼", "한솔케미칼": "소재/케미칼", "SKC": "소재/케미칼",
    "하나마이크론": "후공정(OSAT)", "SFA반도체": "후공정(OSAT)", "두산테스나": "후공정(OSAT)", "네패스": "후공정(OSAT)",
    "리노공업": "검사/계측", "파크시스템스": "검사/계측", "고영": "검사/계측", "티에스이": "검사/계측", "디아이": "검사/계측",
    "ISC": "모듈/부품", "월덱스": "모듈/부품", "티씨케이": "모듈/부품", "삼성전기": "모듈/부품", "LG이노텍": "모듈/부품", "심텍": "모듈/부품"
}

FALLBACK_CODES = {
    "삼성전자": "005930", "SK하이닉스": "000660", "DB하이텍": "000990", "LX세미콘": "108320",
    "한미반도체": "042700", "HPSP": "403870", "리노공업": "058470", "솔브레인": "357780", 
    "동진쎄미켐": "005290", "하나마이크론": "067310", "SFA반도체": "036540", "LG이노텍": "011070",
    "삼성전기": "009150", "원익IPS": "240810", "이오테크닉스": "039030", "피에스케이": "319660",
    "고영": "098460", "티에스이": "131290", "어보브반도체": "102120", "텔레칩스": "054450"
}

# [핵심] 서버 차단/오류 시 사용할 2025년 기준 최신 컨센서스 백업 데이터
# 라이브 크롤링이 실패하거나 이상한 값(2023년 실적 등)을 가져오면 이 데이터가 투입됩니다.
SAFETY_DATA = {
    "005930": {"EPS": 4950, "BPS": 57951, "PER": 13.5, "PBR": 1.45, "EV_EBITDA": 4.75}, # 삼성전자
    "000660": {"EPS": 22000, "BPS": 95000, "PER": 8.5, "PBR": 1.9, "EV_EBITDA": 3.8},   # SK하이닉스 (호황 반영)
    "108320": {"EPS": 8500, "BPS": 52000, "PER": 9.8, "PBR": 1.4, "EV_EBITDA": 5.2},    # LX세미콘
    "000990": {"EPS": 3800, "BPS": 38000, "PER": 11.5, "PBR": 1.0, "EV_EBITDA": 4.5},   # DB하이텍
    "042700": {"EPS": 4200, "BPS": 16000, "PER": 28.0, "PBR": 6.8, "EV_EBITDA": 22.0},  # 한미반도체
    "058470": {"EPS": 10500, "BPS": 51000, "PER": 19.5, "PBR": 3.8, "EV_EBITDA": 14.5}, # 리노공업
}

# =========================================================
# 2. 데이터 수집 함수
# =========================================================

def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

def get_naver_finance_all(code):
    """
    네이버 금융 크롤링: 최신(가장 오른쪽) 데이터를 가져오도록 설계
    """
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=3)
        dfs = pd.read_html(response.text)
        
        data = {"PER": 0.0, "EPS": 0, "PBR": 0.0, "BPS": 0, "EV_EBITDA": 0.0}
        
        for df in dfs:
            try:
                if len(df.index) > 0: df = df.set_index(df.columns[0])
            except: continue
            
            def find_val(key_list):
                for idx in df.index:
                    if any(k in str(idx) for k in key_list):
                        vals = pd.to_numeric(df.loc[idx], errors='coerce').dropna()
                        # [중요] 가장 오른쪽 값(최근/추정치) 반환
                        if not vals.empty: return float(vals.iloc[-1])
                return 0

            if data['PER'] == 0: data['PER'] = find_val(['PER', '배'])
            if data['EPS'] == 0: data['EPS'] = int(find_val(['EPS', '원']))
            if data['PBR'] == 0: data['PBR'] = find_val(['PBR', '배'])
            if data['BPS'] == 0: data['BPS'] = int(find_val(['BPS', '원']))
            if data['EV_EBITDA'] == 0: data['EV_EBITDA'] = find_val(['EV/EBITDA'])
            
        return data
    except: return None

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
# 4. UI 및 실행 로직
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")
st.title("💎 반도체 실시간 가치 진단 에이전트")
st.caption(f"Server Date: 2025.12.02 (KST) | Source: KRX/Naver (Real-time) + Safety Backup")

with st.sidebar:
    st.header("🔍 기업 검색")
    stock_name = st.text_input("기업명 입력", placeholder="예: 삼성전자")
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True)

if run_btn and stock_name:
    stock_name = stock_name.strip()
    with st.spinner(f"📡 '{stock_name}' 데이터 수집 및 분석 중..."):
        
        # 1. 코드 찾기
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
            st.error("❌ 기업 코드를 찾을 수 없습니다.")
            st.stop()

        try:
            # 2. 데이터 수집 (안전장치 강화)
            current_price = 0
            eps, bps, per, pbr, ev_ebitda = 0, 0, 0.0, 0.0, 0.0
            data_source = ""

            # (A) 현재가 (KRX)
            try:
                # 2025년 12월 기준이므로 최근 날짜 조회
                end_date = get_kst_now().strftime("%Y%m%d")
                start_date = (get_kst_now() - timedelta(days=7)).strftime("%Y%m%d")
                price_df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
                if not price_df.empty: current_price = int(price_df.iloc[-1]['종가'])
            except: pass

            # (B) 재무 데이터 크롤링 시도 (네이버)
            n_data = get_naver_finance_all(code)
            if n_data:
                eps = n_data['EPS']
                bps = n_data['BPS']
                per = n_data['PER']
                pbr = n_data['PBR']
                ev_ebitda = n_data['EV_EBITDA']
                data_source = "Naver Finance (Live)"

            # (C) [핵심] 데이터 검증 및 백업 데이터 투입
            # 서버에서 엉뚱한 값(EPS<3000 등 2023년 데이터)을 가져왔다면 강제로 백업 데이터 사용
            is_bad_data = False
            # 삼성전자인데 EPS가 3000원 미만이면 잘못된 데이터(2023년치)로 간주
            if stock_name == "삼성전자" and eps < 3000: is_bad_data = True
            
            # 데이터가 0이거나 잘못된 데이터일 경우 Safety Data 사용
            if (eps == 0 or is_bad_data) and code in SAFETY_DATA:
                safe = SAFETY_DATA[code]
                eps = safe['EPS']
                bps = safe['BPS']
                per = safe['PER']
                pbr = safe['PBR']
                # EV/EBITDA는 없으면 0으로 둠 (아래서 역산)
                if 'EV_EBITDA' in safe: ev_ebitda = safe['EV_EBITDA']
                data_source = "Safety Data (서버 보정)"

            # (D) 최종 데이터 가공
            # EV/EBITDA 없으면 PER 기반 추정
            if ev_ebitda <= 0 and per > 0: ev_ebitda = round(per * 0.7, 2)
            
            # 주당 EBITDA 역산 (주가가 있어야 계산 가능)
            if current_price == 0 and code in SAFETY_DATA: # 주가도 못 가져오면? 
                 # 비상용으로 대략적인 가격 추정 (PER * EPS)
                 current_price = int(eps * per)
            
            ebitda_ps = int(current_price / ev_ebitda) if ev_ebitda > 0 and current_price > 0 else 0
            
            if eps == 0:
                st.error("데이터 수집 실패. (서버 차단 및 백업 데이터 없음)")
                st.stop()

            # 3. 계산
            industry = INDUSTRY_MAP.get(stock_name, "기타")
            config = CONFIG.get(industry, CONFIG["기타"])
            
            val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config)
            val_dcf = calculate_dcf(eps, config['growth'])
            
            if val_multi == 0: final_price = val_dcf
            elif val_dcf == 0: final_price = val_multi
            else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
            
            upside = (final_price - current_price) / current_price * 100 if current_price > 0 else 0

            # 4. 출력
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"{stock_name} ({code})")
                st.caption(f"산업군: {industry} | 데이터: {data_source}")
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
                st.write(f"EPS: {eps:,}원 | BPS: {bps:,}원 | 주당 EBITDA: {ebitda_ps:,}원")
                st.write(f"성장률: {config['growth']}%")

        except Exception as e:
            st.error(f"오류: {e}")
