import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time
import os

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

# =========================================================
# 2. 엑셀 데이터 로드 및 DB 구축
# =========================================================
@st.cache_data
def load_financial_data(filepath):
    try:
        df = pd.read_excel(filepath)
        # 컬럼명 공백 제거 및 표준화
        df.columns = df.columns.str.strip().str.replace(' ', '')
        
        db = {}
        for _, row in df.iterrows():
            name = row.get('종목명')
            if pd.isna(name): continue
            
            code = str(row.get('종목코드', '')).zfill(6) # 6자리 문자열로 변환
            if code == '000nan': # 코드가 없는 경우 매핑 테이블 참고 (임시)
                 # 실제로는 엑셀에 코드가 있어야 하지만, 없으면 이름으로 매핑 시도
                 pass 

            # 산업군 매핑
            industry = row.get('세부산업군', '기타')

            # 25년 추정치 우선, 없으면 24년 데이터 사용
            # 엑셀 컬럼명에 따라 수정 필요 (예: '25(E)EPS', '24(A)EPS' 등)
            # 여기서는 일반적인 패턴을 가정하고 작성합니다. 실제 엑셀 헤더를 확인해야 정확합니다.
            
            # EPS
            eps_25 = row.get('25(E)EPS', 0)
            eps_24 = row.get('24(A)EPS', 0) # 또는 24(E)EPS
            
            if pd.notna(eps_25) and eps_25 != 0:
                eps = eps_25
                criteria = "2025(E)"
            else:
                eps = eps_24
                criteria = "2024(A)"
            
            # BPS
            bps_25 = row.get('25(E)BPS', 0)
            bps_24 = row.get('24(A)BPS', 0)
            
            if pd.notna(bps_25) and bps_25 != 0:
                bps = bps_25
            else:
                bps = bps_24
                
            # Target Multiples (엑셀에 있으면 가져오고 없으면 CONFIG 기본값 사용)
            # 엑셀에 'TargetPER', 'TargetPBR', 'TargetEV/EBITDA' 컬럼이 있다고 가정
            target_per = row.get('TargetPER', 0)
            target_pbr = row.get('TargetPBR', 0)
            target_ev_ebitda = row.get('TargetEV/EBITDA', 0)
            
            # EBITDA_PS (엑셀에 없으면 0으로 두고 나중에 역산)
            ebitda_ps = row.get('EBITDA_PS', 0)
            if pd.isna(ebitda_ps): ebitda_ps = 0

            db[name] = {
                "code": code,
                "industry": industry,
                "criteria": criteria,
                "EPS": int(eps) if pd.notna(eps) else 0,
                "BPS": int(bps) if pd.notna(bps) else 0,
                "EBITDA_PS": int(ebitda_ps),
                "Target_PER": float(target_per) if pd.notna(target_per) else 0,
                "Target_PBR": float(target_pbr) if pd.notna(target_pbr) else 0,
                "Target_EV_EBITDA": float(target_ev_ebitda) if pd.notna(target_ev_ebitda) else 0
            }
            
        return db
    except Exception as e:
        st.error(f"엑셀 파일 로드 실패: {e}")
        return {}

# 엑셀 파일명 (같은 폴더에 위치해야 함)
EXCEL_FILE = '반도체 주가 가치 진단 에이전트 샘플기업.xlsx'

# DB 로드 (앱 실행 시 한 번만 수행)
if os.path.exists(EXCEL_FILE):
    FINANCIAL_DB = load_financial_data(EXCEL_FILE)
else:
    st.warning(f"'{EXCEL_FILE}' 파일을 찾을 수 없습니다. 기본 데이터로 실행합니다.")
    # (기존 하드코딩된 FINANCIAL_DB를 여기에 백업으로 넣어두셔도 됩니다)
    FINANCIAL_DB = {} 

# =========================================================
# 3. 로직 함수 (실시간 주가 수집)
# =========================================================

def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

def get_realtime_price(code):
    """KRX에서 실시간(또는 최근 종가) 가격만 가져옵니다."""
    try:
        for i in range(7):
            target_date = (get_kst_now() - timedelta(days=i)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(target_date, target_date, code)
            if not df.empty and df.iloc[-1]['종가'] > 0:
                return int(df.iloc[-1]['종가'])
        return 0
    except:
        return 0

def calculate_dcf(eps, growth_rate):
    discount_rate = 0.10
    fair_value = 0
    curr_eps = eps
    for i in range(1, 6):
        curr_eps = curr_eps * (1 + growth_rate/100)
        fair_value += curr_eps / ((1 + discount_rate) ** i)
    fair_value += (curr_eps / discount_rate) / ((1 + discount_rate) ** 5)
    return int(fair_value)

def calculate_multiple(eps, bps, ebitda_ps, config, company_targets):
    metrics = config['metrics']
    ranges = config['ranges']
    values = []
    used_metrics_str = []
    
    # 엑셀에 Target 멀티플이 있으면 그걸 우선 사용, 없으면 산업군 평균 사용
    
    # 1. PER
    if "PER" in metrics:
        if eps > 0:
            target = company_targets.get('Target_PER')
            if not target or target == 0: target = sum(ranges["PER"]) / 2
            
            values.append(eps * target)
            used_metrics_str.append(f"PER(×{target:.1f})")
        else:
            used_metrics_str.append(f"PER(적자제외)")
        
    # 2. PBR
    if "PBR" in metrics and bps > 0:
        target = company_targets.get('Target_PBR')
        if not target or target == 0: target = sum(ranges["PBR"]) / 2
        
        values.append(bps * target)
        used_metrics_str.append(f"PBR(×{target:.1f})")
        
    # 3. EV/EBITDA
    if "EV_EBITDA" in metrics:
        target = company_targets.get('Target_EV_EBITDA')
        if not target or target == 0: target = sum(ranges["EV_EBITDA"]) / 2
        
        if ebitda_ps > 0:
            values.append(ebitda_ps * target)
            used_metrics_str.append(f"EV/EBITDA(×{target:.1f})")
        
    if not values: return 0, "데이터 부족"
    return int(sum(values) / len(values)), ", ".join(used_metrics_str)

# =========================================================
# 4. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")

st.title("💎 반도체 실시간 가치 진단 에이전트")
st.caption(f"Server Date: 2025.12.02 (KST) | Data: Excel Database + Real-time Price")

with st.sidebar:
    st.header("🔍 기업 검색")
    # 엑셀 DB에 있는 기업만 선택 가능하게
    stock_list = list(FINANCIAL_DB.keys())
    stock_name = st.selectbox("기업 선택", stock_list) if stock_list else st.text_input("기업명 입력")
    
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.info(f"📂 로드된 엑셀 데이터: {len(FINANCIAL_DB)}개 기업")

if run_btn and stock_name:
    with st.spinner(f"📡 '{stock_name}' 분석 중..."):
        
        company_info = FINANCIAL_DB.get(stock_name)
        
        if not company_info:
            st.error("DB에서 기업 정보를 찾을 수 없습니다.")
            st.stop()

        code = company_info['code']
        industry = company_info['industry']
        criteria = company_info['criteria']
        
        # 1. 실시간 주가 수집 (KRX)
        # 엑셀에 코드가 없으면 종목명으로 찾기 시도 (보완 로직)
        if not code or code == '000nan':
             try:
                today_str = get_kst_now().strftime("%Y%m%d")
                tickers = stock.get_market_ticker_list(today_str, market="KOSPI") + stock.get_market_ticker_list(today_str, market="KOSDAQ")
                for t in tickers:
                    if stock.get_market_ticker_name(t) == stock_name:
                        code = t
                        break
             except: pass
        
        current_price = get_realtime_price(code)
        if current_price == 0:
            st.error("실시간 주가 정보를 가져올 수 없습니다. (KRX 접속 실패)")
            st.stop()

        # 2. 펀더멘탈 데이터 (엑셀)
        eps = company_info['EPS']
        bps = company_info['BPS']
        ebitda_ps = company_info['EBITDA_PS']
        
        # EBITDA_PS가 엑셀에 없으면(0이면) 역산 시도
        # 역산하려면 Target EV/EBITDA가 필요함
        target_ev = company_info['Target_EV_EBITDA']
        if ebitda_ps == 0 and target_ev > 0:
             # 현재가 기준 역산 (단순화)
             ebitda_ps = int(current_price / target_ev)
        
        # 현재 지표 계산
        per_val = current_price / eps if eps > 0 else 0
        pbr_val = current_price / bps if bps > 0 else 0
        ev_ebitda_val = current_price / ebitda_ps if ebitda_ps > 0 else 0
        
        per_str = f"{per_val:.2f}배" if per_val > 0 else "N/A (적자)"
        pbr_str = f"{pbr_val:.2f}배" if pbr_val > 0 else "-"
        ev_ebitda_str = f"{ev_ebitda_val:.2f}배" if ev_ebitda_val > 0 else "-"

        # 3. 가치 평가 계산
        config = CONFIG.get(industry, CONFIG["기타"])
        
        val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config, company_info)
        val_dcf = calculate_dcf(eps, config['growth'])
        
        # 최종 적정 주가
        final_price = 0
        verdict_msg = ""
        verdict_color = "gray"

        if val_multi == 0 and val_dcf <= 0:
            final_price = 0
            verdict_msg = "⚠️ 적자 지속으로 평가 불가"
        else:
            if val_multi == 0: final_price = val_dcf
            elif val_dcf <= 0: final_price = val_multi
            else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
            
            upside = (final_price - current_price) / current_price * 100
            
            if upside > 15: 
                verdict_msg = f"✅ 저평가 (+{upside:.1f}%)"
                verdict_color = "green"
            elif upside < -15: 
                verdict_msg = f"⚠️ 고평가 ({upside:.1f}%)"
                verdict_color = "red"
            else: 
                verdict_msg = f"⚖️ 적정 주가 ({upside:.1f}%)"
                verdict_color = "orange"

        # 4. 결과 출력
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"{stock_name} ({code})")
            st.caption(f"산업군: {industry} | 적용 실적: {criteria} (Excel)")
        with c2:
            if final_price > 0:
                if verdict_color == "green": st.success(verdict_msg)
                elif verdict_color == "red": st.error(verdict_msg)
                else: st.warning(verdict_msg)
            else:
                st.error("평가 불가 (적자)")
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("현재 주가 (Real-time)", f"{current_price:,}원")
        if final_price > 0:
            m2.metric("적정 주가 (Target)", f"{int(final_price):,}원", delta=f"{int(final_price-current_price):,}원")
            m3.metric("평가 비중", f"DCF {int(config['w_dcf']*100)}% : Multi {int(config['w_multi']*100)}%")
        else:
            m2.metric("적정 주가", "산출 불가")
            m3.metric("이유", "예상 실적 적자")
        
        st.markdown("---")
        st.write(f"#### 📊 투자 지표 ({criteria})")
        
        metrics_data = {
            "구분": ["PER", "PBR", "EV/EBITDA"],
            "현재 수치": [per_str, pbr_str, ev_ebitda_str],
            "적용 여부": [
                "✅ 핵심 지표" if "PER" in config['metrics'] else "ℹ️ 보조 지표",
                "✅ 핵심 지표" if "PBR" in config['metrics'] else "ℹ️ 보조 지표",
                "✅ 핵심 지표" if "EV/EBITDA" in config['metrics'] else "ℹ️ 보조 지표"
            ]
        }
        st.table(pd.DataFrame(metrics_data))
        
        with st.expander("🔍 엑셀 데이터 원본 보기"):
            st.write(f"- EPS: {eps:,}원")
            st.write(f"- BPS: {bps:,}원")
            st.write(f"- EBITDA 추정: {ebitda_ps:,}원")
            st.write(f"- 성장률 가정: {config['growth']}%")
            st.write(f"- 멀티플 산출식: {multi_desc}")
