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
# 2. [핵심] 엑셀 데이터 내장 (Hard-coded DB)
# =========================================================
# 업로드해주신 엑셀 파일의 데이터를 코드에 직접 삽입하고 컬럼명을 표준화
# (EV/EBITDA, PBR은 Target Multiples로 사용, EPS/BPS는 원천 데이터)
FINANCIAL_DB = {
    "LX세미콘": {"code": "108320", "industry": "설계(팹리스/IP)", "criteria": "2025(E)", "EPS": 5529, "BPS": 70707, "Target_EV_EBITDA": 6.05, "Target_PBR": 0.97, "Target_PER": 18.23}, 
    "어보브반도체": {"code": "102120", "industry": "설계(팹리스/IP)", "criteria": "2024(A)", "EPS": 481, "BPS": 4260, "Target_EV_EBITDA": 47.58, "Target_PBR": 3.69, "Target_PER": 32.7},
    "DB하이텍": {"code": "000990", "industry": "파운드리", "criteria": "2025(E)", "EPS": 5458, "BPS": 54734, "Target_EV_EBITDA": 4.81, "Target_PBR": 1.16, "Target_PER": 11.65},
    "삼성전자": {"code": "005930", "industry": "메모리/IDM", "criteria": "2025(E)", "EPS": 5529, "BPS": 57951, "Target_EV_EBITDA": 4.75, "Target_PBR": 1.1, "Target_PER": 13.5},
    "SK하이닉스": {"code": "000660", "industry": "메모리/IDM", "criteria": "2025(E)", "EPS": 53139, "BPS": 160838, "Target_EV_EBITDA": 3.2, "Target_PBR": 1.6, "Target_PER": 3.8}, 
    "한미반도체": {"code": "042700", "industry": "장비", "criteria": "2025(E)", "EPS": 2503, "BPS": 8927, "Target_EV_EBITDA": 51.54, "Target_PBR": 14.45, "Target_PER": 51.54},
    "피에스케이": {"code": "319660", "industry": "장비", "criteria": "2024(A)", "EPS": 5155, "BPS": 47181, "Target_EV_EBITDA": 2.06, "Target_PBR": 0.7, "Target_PER": 6.43},
    "동진쎄미켐": {"code": "005290", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 2081, "BPS": 20967, "Target_EV_EBITDA": 8.71, "Target_PBR": 1.91, "Target_PER": 19.29},
    "솔브레인": {"code": "357780", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 13600, "BPS": 141504, "Target_EV_EBITDA": 10.3, "Target_PBR": 1.9, "Target_PER": 21.73},
    "하나마이크론": {"code": "067310", "industry": "후공정(OSAT)", "criteria": "2024(A)", "EPS": 4923, "BPS": 3478, "Target_EV_EBITDA": 5.06, "Target_PBR": 5.06, "Target_PER": 40.03},
    "SFA반도체": {"code": "036540", "industry": "후공정(OSAT)", "criteria": "2024(A)", "EPS": 1535, "BPS": 19678, "Target_EV_EBITDA": 3.13, "Target_PBR": 1.22, "Target_PER": 40.06},
    "디아이": {"code": "003160", "industry": "검사/계측", "criteria": "2024(A)", "EPS": 5155, "BPS": 47181, "Target_EV_EBITDA": 2.06, "Target_PBR": 0.7, "Target_PER": 6.43},
    "삼성전기": {"code": "009150", "industry": "모듈/부품", "criteria": "2024(A)", "EPS": 5155, "BPS": 47181, "Target_EV_EBITDA": 2.06, "Target_PBR": 0.7, "Target_PER": 6.43},
    "LG이노텍": {"code": "011070", "industry": "모듈/부품", "criteria": "2024(A)", "EPS": 5155, "BPS": 47181, "Target_EV_EBITDA": 2.06, "Target_PBR": 0.7, "Target_PER": 6.43},
    "텔레칩스": {"code": "054450", "industry": "설계(팹리스/IP)", "criteria": "2025(E)", "EPS": -574, "BPS": 12602, "Target_EV_EBITDA": 119.03, "Target_PBR": 0.97, "Target_PER": 0},
    "칩스앤미디어": {"code": "094360", "industry": "설계(팹리스/IP)", "criteria": "2024(A)", "EPS": 481, "BPS": 4260, "Target_EV_EBITDA": 47.58, "Target_PBR": 3.69, "Target_PER": 32.7},
    "제주반도체": {"code": "080220", "industry": "설계(팹리스/IP)", "criteria": "2024(A)", "EPS": 567, "BPS": 4676, "Target_EV_EBITDA": 26.23, "Target_PBR": 1.65, "Target_PER": 15.72},
    "가온칩스": {"code": "399720", "industry": "설계(팹리스/IP)", "criteria": "2024(A)", "EPS": 0, "BPS": 5900, "Target_EV_EBITDA": 48.04, "Target_PBR": 5.9, "Target_PER": 0},
    "원익IPS": {"code": "240810", "industry": "장비", "criteria": "2025(E)", "EPS": 1535, "BPS": 19678, "Target_EV_EBITDA": 3.13, "Target_PBR": 1.22, "Target_PER": 40.06},
    "테스": {"code": "095610", "industry": "장비", "criteria": "2025(E)", "EPS": 3073, "BPS": 22700, "Target_EV_EBITDA": 1.82, "Target_PBR": 1.82, "Target_PER": 13.44},
    "유진테크": {"code": "084370", "industry": "장비", "criteria": "2025(E)", "EPS": 1984, "BPS": 19981, "Target_EV_EBITDA": 4.02, "Target_PBR": 4.02, "Target_PER": 40.47},
}


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

def calculate_multiple(eps, bps, current_price, config, company_targets):
    """
    멀티플 계산 (EPS, BPS, EV/EBITDA Target을 사용)
    """
    metrics = config['metrics']
    ranges = config['ranges']
    values = []
    used_metrics_str = []
    
    # 1. Target Multiples 정의 (엑셀 값 우선)
    target_per_val = company_targets.get('Target_PER') or (sum(ranges["PER"]) / 2)
    target_pbr_val = company_targets.get('Target_PBR') or (sum(ranges["PBR"]) / 2)
    target_ev_val = company_targets.get('Target_EV_EBITDA') or (sum(ranges["EV_EBITDA"]) / 2)
    
    # 2. EBITDA_PS 역산 (EV/EBITDA Target을 사용)
    # EBITDA_PS = Current Price / Target EV/EBITDA (EV=시총이라고 가정한 근사치)
    ebitda_ps = int(current_price / target_ev_val) if target_ev_val > 0 else 0


    # 3. 가치 계산
    
    # PER
    if "PER" in metrics:
        if eps > 0:
            values.append(eps * target_per_val)
            used_metrics_str.append(f"PER(×{target_per_val:.1f})")
        else:
            used_metrics_str.append(f"PER(적자제외)")
        
    # PBR
    if "PBR" in metrics and bps > 0:
        values.append(bps * target_pbr_val)
        used_metrics_str.append(f"PBR(×{target_pbr_val:.1f})")
        
    # EV/EBITDA
    if "EV_EBITDA" in metrics and ebitda_ps > 0:
        values.append(ebitda_ps * target_ev_val)
        used_metrics_str.append(f"EV/EBITDA(×{target_ev_val:.1f})")
        
    if not values: return 0, "평가 불가", ebitda_ps
    return int(sum(values) / len(values)), ", ".join(used_metrics_str), ebitda_ps

# =========================================================
# 4. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")

# CSS로 디자인 개선
st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp {
        background-color: #f7f9fd; 
        color: #1a1a2e;
    }
    /* 제목 */
    h1 {
        color: #3b82f6; 
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 5px;
    }
    /* Metric 카드 */
    [data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    /* 경고/성공/에러 박스 */
    .stAlert {
        border-radius: 8px;
        background-color: #eef2ff !important;
        border-left: 6px solid #3b82f6 !important;
        color: #1e3a8a !important;
    }
    .stSuccess {
        background-color: #ecfdf5 !important;
        border-left: 6px solid #10b981 !important;
    }
    .stError {
        background-color: #fef2f2 !important;
        border-left: 6px solid #ef4444 !important;
    }
</style>
""", unsafe_allow_html=True)


st.title("💎 반도체 가치 진단 에이전트")
st.caption(f"기준: 사용자 DB(2024/25 컨센서스) + KRX 실시간 주가")

# ---------------------------------------------------------
# [사이드바]
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 분석 기업 선택")
    
    # 엑셀 DB에 있는 기업만 선택 가능하게
    stock_list = list(FINANCIAL_DB.keys())
    target_stock = st.selectbox("분석할 기업을 선택하세요", stock_list, key='selectbox')
    
    st.markdown("---")
    
    # [수정] 데이터베이스 확인 체크박스 숨김
    # if st.checkbox("데이터베이스 확인 (전문가용)"):
    #     st.dataframe(pd.DataFrame(FINANCIAL_DB).T)
    

# ---------------------------------------------------------
# [메인] 분석 실행
# ---------------------------------------------------------
st.header("🚀 분석 실행")
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**선택 기업:** {target_stock}")

with col2:
    run_btn = st.button("가치 진단 시작 🚀", type="primary", use_container_width=True, key='analyze_btn')


if run_btn and target_stock:
    with st.spinner(f"📡 '{target_stock}' 실시간 주가 조회 중..."):
        
        company_info = FINANCIAL_DB.get(target_stock)
        
        code = company_info['code']
        industry = company_info['industry']
        criteria = company_info['criteria']
        
        # 1. 실시간 주가 수집 (KRX)
        current_price = get_realtime_price(code)
        if current_price == 0:
            st.error(f"실시간 주가를 가져올 수 없습니다. (종목코드: {code})")
            st.stop()

        # 2. 펀더멘탈 데이터 로드 (내장 DB)
        eps = company_info['EPS']
        bps = company_info['BPS']
        
        # 3. 가치 평가 계산
        config = CONFIG.get(industry, CONFIG["기타"])
        
        # 멀티플 계산 (EBITDA_PS와 Target Multiples 모두 사용)
        val_multi, multi_desc, ebitda_ps = calculate_multiple(eps, bps, current_price, config, company_info)
        val_dcf = calculate_dcf(eps, config['growth'])
        
        # 현재 지표 계산 (출력용)
        per_val = current_price / eps if eps > 0 else 0
        pbr_val = current_price / bps if bps > 0 else 0
        ev_ebitda_val = current_price / ebitda_ps if ebitda_ps > 0 else 0
        
        per_str = f"{per_val:.2f}배" if per_val > 0 else "N/A (적자)"
        pbr_str = f"{pbr_val:.2f}배" if pbr_val > 0 else "-"
        ev_ebitda_str = f"{ev_ebitda_val:.2f}배" if ev_ebitda_val > 0 else "-"

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
            st.caption(f"산업군: {industry} | 적용 실적: {criteria} 기준")
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
        st.write(f"#### 📊 투자 지표 상세 ({criteria})")
        
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
        
        with st.expander("🔍 데이터 원본 보기"):
            st.write(f"- EPS: {company_info['EPS']:,}원 ({criteria})")
            st.write(f"- BPS: {company_info['BPS']:,}원 ({criteria})")
            st.write(f"- 주당 EBITDA: {ebitda_ps:,}원 (Target EV/EBITDA를 이용해 현재가 기준 역산됨)")
            st.write(f"- DCF 성장률 가정: {config['growth']}%")
            st.write(f"- 멀티플 산출식: {multi_desc}")
