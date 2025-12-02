import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time
import os
import io

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
def load_financial_data(uploaded_file):
    """업로드된 엑셀 파일을 읽고 재무 데이터를 DB로 변환합니다."""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            # 기본 XLSX 파일 로드 (가장 흔한 형식)
            df = pd.read_excel(uploaded_file)
            
        # 컬럼명 공백 제거 및 표준화
        df.columns = df.columns.str.strip().str.replace(' ', '')
        
        db = {}
        for _, row in df.iterrows():
            name = row.get('종목명')
            if pd.isna(name): continue
            
            # --- 펀더멘탈 데이터 추출 (25년 추정치 우선) ---
            # 엑셀 파일 스니펫 기반 컬럼명 사용
            eps_25 = row.get('25(E)EPS', row.get('25EPS', 0))
            eps_24 = row.get('24(A)EPS', row.get('24EPS', 0))
            bps_25 = row.get('25(E)BPS', row.get('25BPS', 0))
            bps_24 = row.get('24(A)BPS', row.get('24BPS', 0))

            # EPS 및 기준년도 설정
            if pd.notna(eps_25) and eps_25 != 0:
                eps, criteria = eps_25, "2025(E)"
                bps = bps_25
            else:
                eps, criteria = eps_24, "2024(A)"
                bps = bps_24

            # --- Target Multiples 및 EBITDA_PS 데이터 추출 ---
            # 엑셀 파일 스니펫 기반 컬럼명 사용 (25년 EV/EBITTA와 PBR을 Target 값으로 사용)
            target_ev_ebitda = row.get('25(E)EV/EBITTA', row.get('25EV/EBITTA', 0))
            target_pbr = row.get('25(E)PBR', row.get('25PBR', 0))
            
            # EBITDA_PS는 엑셀에 해당 컬럼이 없으므로 일단 0으로 둡니다 (후에 역산 예정)
            ebitda_ps = 0 
            
            # Target_PER은 엑셀에 없으므로, 해당 종목의 25(E) PER 값을 TargetPER로 사용 (약식)
            target_per = row.get('25(E)PER', row.get('25PER', 0))


            # --- 최종 DB 저장 ---
            db[name] = {
                "code": str(row.get('단축코드(6자리)', '')).zfill(6),
                "industry": row.get('세부산업군', '기타'),
                "criteria": criteria,
                "EPS": int(eps) if pd.notna(eps) else 0,
                "BPS": int(bps) if pd.notna(bps) else 0, # PBR 계산 필수
                "EBITDA_PS": int(ebitda_ps), # 0으로 저장 후 나중에 역산
                "Target_PER": float(target_per) if pd.notna(target_per) else 0,
                "Target_PBR": float(target_pbr) if pd.notna(target_pbr) else 0,
                "Target_EV_EBITDA": float(target_ev_ebitda) if pd.notna(target_ev_ebitda) else 0
            }
            
        return db
    except Exception as e:
        st.error(f"⚠️ 파일 처리 오류. 컬럼명을 확인해주세요: {e}")
        return {}
    
# =========================================================
# 3. 로직 함수
# =========================================================

def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

@st.cache_data(ttl=300) # 5분 TTL 설정
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
    
    # Target 멀티플은 엑셀, 없으면 CONFIG 산업군 평균 사용
    
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
        
    if not values: return 0, "평가 불가"
    return int(sum(values) / len(values)), ", ".join(used_metrics_str)

# =========================================================
# 4. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")

st.title("💎 반도체 가치 진단 에이전트")
st.caption(f"기준: 사용자 업로드 데이터(Excel) + 실시간 주가")

# ---------------------------------------------------------
# [사이드바] 파일 업로드 및 데이터 처리
# ---------------------------------------------------------
with st.sidebar:
    st.header("1. 엑셀 데이터 업로드")
    st.warning("⚠️ 엑셀에 '종목코드', '25(E)EPS', '25(E)BPS', '25(E)EV/EBITTA' 컬럼이 있어야 합니다.")
    
    uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx', 'xls', 'csv'], key='uploader')
    
    current_db = {}
    if uploaded_file is not None:
        current_db = load_financial_data(uploaded_file)
        
    if current_db:
        st.success(f"✅ {len(current_db)}개 기업 데이터 로드 완료!")

# ---------------------------------------------------------
# [메인] 분석 실행
# ---------------------------------------------------------

st.header("2. 분석 기업 선택 및 실행")

if not current_db:
    st.warning("데이터베이스가 로드되지 않았습니다. 사이드바에서 엑셀 파일을 업로드해주세요.")
    st.stop()
    
stock_list = list(current_db.keys())
col1, col2 = st.columns([3, 1])

with col1:
    target_stock = st.selectbox("분석할 기업을 선택하세요", stock_list)

with col2:
    st.write("") 
    st.write("") 
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True, key='analyze_btn')


if run_btn and target_stock:
    with st.spinner(f"📡 '{target_stock}' 실시간 주가 조회 중..."):
        
        company_info = current_db.get(target_stock)
        
        code = company_info['code']
        industry = company_info['industry']
        criteria = company_info['criteria']
        
        # 1. 실시간 주가 수집 (KRX)
        current_price = get_realtime_price(code)
        if current_price == 0:
            st.error(f"실시간 주가를 가져올 수 없습니다. (종목코드: {code})")
            st.stop()

        # 2. 펀더멘탈 데이터 (엑셀)
        eps = company_info['EPS']
        bps = company_info['BPS']
        ebitda_ps = company_info['EBITDA_PS'] # 초기값은 0
        target_ev = company_info['Target_EV_EBITDA']
        
        # --- 핵심 로직: EBITDA_PS가 엑셀에 없으면 역산 ---
        if ebitda_ps == 0 and target_ev > 0:
             # EV/EBITDA = Price / EBITDA_PS 이므로, EBITDA_PS = Price / EV/EBITDA_Target
             ebitda_ps = int(current_price / target_ev) if target_ev != 0 else 0
        
        # 현재 지표 계산 (출력용)
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
        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"{target_stock} ({code})")
            st.caption(f"산업군: {industry} | 적용 실적: {criteria} (Excel)")
        with c2:
            if final_price > 0:
                if verdict_color == "green": st.success(verdict_msg)
                elif verdict_color == "red": st.error(verdict_msg)
                else: st.warning(verdict_msg)
            else:
                st.error("평가 불가 (적자)")
        
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
            "적용 대상 목표 멀티플": [
                f"{company_info.get('Target_PER', sum(config['ranges']['PER'])/2):.1f}배 (or 산업평균)" if "PER" in config['metrics'] else "-",
                f"{company_info.get('Target_PBR', sum(config['ranges']['PBR'])/2):.1f}배 (or 산업평균)" if "PBR" in config['metrics'] else "-",
                f"{company_info.get('Target_EV_EBITDA', sum(config['ranges']['EV_EBITDA'])/2):.1f}배 (or 산업평균)" if "EV/EBITDA" in config['metrics'] else "-",
            ],
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
            st.write(f"- EBITDA 추정: {ebitda_ps:,}원 (EV/EBITDA Target을 이용해 역산됨)")
            st.write(f"- 성장률 가정: {config['growth']}%")
            st.write(f"- 멀티플 산출식: {multi_desc}")
