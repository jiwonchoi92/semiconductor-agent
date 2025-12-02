import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time

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
# 2. 기업 데이터베이스 (2025F 우선, 없으면 2024 사용)
# =========================================================
# criteria: 데이터 기준 시점 (화면에 표시됨)
FINANCIAL_DB = {
    # [메모리/IDM] - 25년 슈퍼사이클 반영
    "SK하이닉스": {"code": "000660", "industry": "메모리/IDM", "criteria": "2025(E)", "EPS": 53139, "BPS": 160838, "EV_EBITDA_R": 3.2, "PBR": 1.6}, 
    "삼성전자": {"code": "005930", "industry": "메모리/IDM", "criteria": "2025(E)", "EPS": 6500, "BPS": 61000, "EV_EBITDA_R": 4.5, "PBR": 1.1},
    
    # [설계/팹리스] - 25년 성장 반영
    "LX세미콘": {"code": "108320", "industry": "설계(팹리스/IP)", "criteria": "2025(E)", "EPS": 8800, "BPS": 52000, "EV_EBITDA_R": 5.2, "PBR": 1.4},
    "텔레칩스": {"code": "054450", "industry": "설계(팹리스/IP)", "criteria": "2025(E)", "EPS": 1350, "BPS": 11000, "EV_EBITDA_R": 8.5, "PBR": 1.8},
    "가온칩스": {"code": "393360", "industry": "설계(팹리스/IP)", "criteria": "2025(E)", "EPS": 1600, "BPS": 12500, "EV_EBITDA_R": 30.0, "PBR": 6.5},
    # 추정치 없는 중소형주 -> 2024 데이터 사용
    "어보브반도체": {"code": "102120", "industry": "설계(팹리스/IP)", "criteria": "2024(E)", "EPS": 450, "BPS": 7800, "EV_EBITDA_R": 12.0, "PBR": 1.3},
    "제주반도체": {"code": "080220", "industry": "설계(팹리스/IP)", "criteria": "2024(E)", "EPS": 350, "BPS": 4500, "EV_EBITDA_R": 15.0, "PBR": 3.5},
    "칩스앤미디어": {"code": "094360", "industry": "설계(팹리스/IP)", "criteria": "2024(E)", "EPS": 400, "BPS": 3500, "EV_EBITDA_R": 25.0, "PBR": 5.2},

    # [파운드리]
    "DB하이텍": {"code": "000990", "industry": "파운드리", "criteria": "2025(E)", "EPS": 4100, "BPS": 39000, "EV_EBITDA_R": 4.5, "PBR": 1.0},

    # [장비] - HBM 수혜주는 25년, 나머지는 24/25 혼용
    "한미반도체": {"code": "042700", "industry": "장비", "criteria": "2025(E)", "EPS": 4500, "BPS": 17000, "EV_EBITDA_R": 22.0, "PBR": 6.8},
    "HPSP": {"code": "403870", "industry": "장비", "criteria": "2025(E)", "EPS": 3100, "BPS": 13000, "EV_EBITDA_R": 18.0, "PBR": 4.5},
    "이오테크닉스": {"code": "039030", "industry": "장비", "criteria": "2025(E)", "EPS": 6200, "BPS": 45000, "EV_EBITDA_R": 11.0, "PBR": 3.5},
    "주성엔지니어링": {"code": "036930", "industry": "장비", "criteria": "2024(E)", "EPS": 2500, "BPS": 14000, "EV_EBITDA_R": 8.5, "PBR": 2.2},
    "원익IPS": {"code": "240810", "industry": "장비", "criteria": "2025(E)", "EPS": 2200, "BPS": 22000, "EV_EBITDA_R": 9.5, "PBR": 1.5},
    "피에스케이": {"code": "319660", "industry": "장비", "criteria": "2025(E)", "EPS": 3300, "BPS": 24000, "EV_EBITDA_R": 6.5, "PBR": 1.1},
    "테스": {"code": "095610", "industry": "장비", "criteria": "2024(E)", "EPS": 1200, "BPS": 18000, "EV_EBITDA_R": 7.0, "PBR": 1.2},
    "유진테크": {"code": "084370", "industry": "장비", "criteria": "2025(E)", "EPS": 2500, "BPS": 20000, "EV_EBITDA_R": 8.0, "PBR": 1.8},

    # [소재/케미칼]
    "솔브레인": {"code": "357780", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 22000, "BPS": 160000, "EV_EBITDA_R": 6.0, "PBR": 1.5},
    "동진쎄미켐": {"code": "005290", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 3500, "BPS": 27000, "EV_EBITDA_R": 5.5, "PBR": 1.4},
    "한솔케미칼": {"code": "014680", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 12000, "BPS": 80000, "EV_EBITDA_R": 7.5, "PBR": 2.0},
    "SKC": {"code": "011790", "industry": "소재/케미칼", "criteria": "2025(E)", "EPS": 3000, "BPS": 58000, "EV_EBITDA_R": 8.0, "PBR": 1.8},

    # [후공정(OSAT)]
    "하나마이크론": {"code": "067310", "industry": "후공정(OSAT)", "criteria": "2025(E)", "EPS": 1500, "BPS": 14000, "EV_EBITDA_R": 6.5, "PBR": 1.5},
    "두산테스나": {"code": "131970", "industry": "후공정(OSAT)", "criteria": "2025(E)", "EPS": 3800, "BPS": 30000, "EV_EBITDA_R": 5.5, "PBR": 1.6},
    "SFA반도체": {"code": "036540", "industry": "후공정(OSAT)", "criteria": "2024(E)", "EPS": 250, "BPS": 4200, "EV_EBITDA_R": 7.0, "PBR": 1.3},
    "네패스": {"code": "033640", "industry": "후공정(OSAT)", "criteria": "2024(E)", "EPS": -500, "BPS": 11000, "EV_EBITDA_R": 9.0, "PBR": 1.5},

    # [검사/계측]
    "리노공업": {"code": "058470", "industry": "검사/계측", "criteria": "2025(E)", "EPS": 11500, "BPS": 55000, "EV_EBITDA_R": 14.5, "PBR": 3.8},
    "파크시스템스": {"code": "140860", "industry": "검사/계측", "criteria": "2025(E)", "EPS": 6000, "BPS": 30000, "EV_EBITDA_R": 22.0, "PBR": 7.5},
    "고영": {"code": "098460", "industry": "검사/계측", "criteria": "2025(E)", "EPS": 750, "BPS": 7000, "EV_EBITDA_R": 12.0, "PBR": 2.5},
    "티에스이": {"code": "131290", "industry": "검사/계측", "criteria": "2024(E)", "EPS": 4200, "BPS": 32000, "EV_EBITDA_R": 5.5, "PBR": 1.2},
    "디아이": {"code": "003160", "industry": "검사/계측", "criteria": "2024(E)", "EPS": 1500, "BPS": 8500, "EV_EBITDA_R": 10.0, "PBR": 2.5},

    # [모듈/부품]
    "LG이노텍": {"code": "011070", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 31000, "BPS": 190000, "EV_EBITDA_R": 3.5, "PBR": 1.1},
    "삼성전기": {"code": "009150", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 10500, "BPS": 120000, "EV_EBITDA_R": 5.5, "PBR": 1.3},
    "심텍": {"code": "222800", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 1800, "BPS": 21000, "EV_EBITDA_R": 4.5, "PBR": 1.2},
    "ISC": {"code": "095340", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 3200, "BPS": 20000, "EV_EBITDA_R": 15.0, "PBR": 3.5},
    "월덱스": {"code": "101160", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 2500, "BPS": 16000, "EV_EBITDA_R": 6.5, "PBR": 1.6},
    "티씨케이": {"code": "064760", "industry": "모듈/부품", "criteria": "2025(E)", "EPS": 7000, "BPS": 48000, "EV_EBITDA_R": 9.0, "PBR": 2.2},
}

# =========================================================
# 2. 로직 함수 (실시간 주가만 KRX에서 가져오기)
# =========================================================

# 한국 시간 구하기
def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

def get_realtime_price(code):
    """
    KRX에서 실시간(또는 최근 종가) 가격만 가져옵니다.
    """
    try:
        for i in range(7): # 최근 7일 내 데이터 찾기
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
    # 5년치 현금흐름 할인
    for i in range(1, 6):
        curr_eps = curr_eps * (1 + growth_rate/100)
        fair_value += curr_eps / ((1 + discount_rate) ** i)
    # 영구가치
    fair_value += (curr_eps / discount_rate) / ((1 + discount_rate) ** 5)
    return int(fair_value)

def calculate_multiple(eps, bps, ebitda_ps, config):
    metrics = config['metrics']
    ranges = config['ranges']
    values = []
    used_metrics_str = []
    
    # 1. PER 계산
    if "PER" in metrics and eps > 0:
        target = sum(ranges["PER"]) / 2 
        values.append(eps * target)
        used_metrics_str.append(f"PER(×{target})")
        
    # 2. PBR 계산
    if "PBR" in metrics and bps > 0:
        target = sum(ranges["PBR"]) / 2 
        values.append(bps * target)
        used_metrics_str.append(f"PBR(×{target})")
        
    # 3. EV/EBITDA 계산
    if "EV_EBITDA" in metrics and ebitda_ps > 0:
        target = sum(ranges["EV_EBITDA"]) / 2 
        values.append(ebitda_ps * target)
        used_metrics_str.append(f"EV/EBITDA(×{target})")
        
    if not values: return 0, "데이터 부족"
    return int(sum(values) / len(values)), ", ".join(used_metrics_str)

# =========================================================
# 3. Streamlit UI
# =========================================================
st.set_page_config(page_title="반도체 가치 진단", page_icon="💎", layout="wide")

st.title("💎 반도체 실시간 가치 진단 에이전트")
st.caption(f"Server Date: 2025.12.02 (KST) | Data: 2024/25 Hybrid Consensus + Real-time Price")

with st.sidebar:
    st.header("🔍 기업 검색")
    stock_name = st.text_input("기업명 입력", placeholder="예: SK하이닉스")
    run_btn = st.button("진단 시작 🚀", type="primary", use_container_width=True)
    st.info("💡 종목별 가용한 최신 추정치(25F 또는 24F)를 반영하여 계산합니다.")

if run_btn and stock_name:
    stock_name = stock_name.strip()
    
    with st.spinner(f"📡 '{stock_name}' 분석 중..."):
        
        # 1. DB에서 기업 정보 확인
        company_info = FINANCIAL_DB.get(stock_name)
        
        if not company_info:
            st.error(f"❌ '{stock_name}'은(는) 분석 대상 기업 목록(14개+a)에 없습니다.")
            st.warning("이 에이전트는 주요 반도체 기업 30여 곳의 컨센서스 데이터를 보유하고 있습니다.")
            st.stop()

        code = company_info['code']
        industry = company_info['industry']
        criteria = company_info['criteria'] # 데이터 기준년도 (25E or 24E)
        
        # 2. 실시간 주가 수집 (KRX)
        current_price = get_realtime_price(code)
        if current_price == 0:
            st.error("실시간 주가 정보를 가져올 수 없습니다. (KRX 접속 실패)")
            st.stop()

        # 3. 펀더멘탈 데이터 로드
        eps = company_info['EPS']
        bps = company_info['BPS']
        ev_ebitda_ratio = company_info.get('EV_EBITDA_R', 0)
        pbr = company_info.get('PBR', 0)
        
        # PER (현재가 / DB상 EPS)
        per = current_price / eps if eps > 0 else 0
        
        # EBITDA 역산
        ebitda_ps = int(current_price / ev_ebitda_ratio) if ev_ebitda_ratio > 0 else 0

        # 4. 가치 평가 계산
        config = CONFIG.get(industry, CONFIG["기타"])
        
        # 멀티플 가치
        val_multi, multi_desc = calculate_multiple(eps, bps, ebitda_ps, config)
        
        # DCF 가치
        val_dcf = calculate_dcf(eps, config['growth'])
        
        # 최종 적정 주가
        if val_multi == 0: final_price = val_dcf
        elif val_dcf == 0: final_price = val_multi
        else: final_price = (val_dcf * config['w_dcf']) + (val_multi * config['w_multi'])
        
        upside = (final_price - current_price) / current_price * 100

        # 5. 결과 출력
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"{stock_name} ({code})")
            # 기준년도를 명시해줌 (유저 요청 해결)
            st.caption(f"산업군: {industry} | 적용 실적: {criteria} 기준")
        with c2:
            if upside > 15: st.success(f"✅ 저평가 (+{upside:.1f}%)")
            elif upside < -15: st.error(f"⚠️ 고평가 ({upside:.1f}%)")
            else: st.warning(f"⚖️ 적정 주가 ({upside:.1f}%)")
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("현재 주가 (Real-time)", f"{current_price:,}원")
        m2.metric("적정 주가 (Target)", f"{int(final_price):,}원", delta=f"{int(final_price-current_price):,}원")
        m3.metric("평가 비중", f"DCF {int(config['w_dcf']*100)}% : Multi {int(config['w_multi']*100)}%")
        
        st.markdown("---")
        st.write(f"#### 📊 투자 지표 ({criteria} Consensus)")
        
        metrics_data = {
            "구분": ["PER (주가수익비율)", "PBR (주가순자산비율)", "EV/EBITDA"],
            "현재 수치": [f"{per:.2f}배", f"{current_price/bps:.2f}배" if bps > 0 else "-", f"{current_price/ebitda_ps:.2f}배" if ebitda_ps > 0 else "-"],
            "적용 여부": [
                "✅ 핵심 지표" if "PER" in config['metrics'] else "ℹ️ 보조 지표",
                "✅ 핵심 지표" if "PBR" in config['metrics'] else "ℹ️ 보조 지표",
                "✅ 핵심 지표" if "EV/EBITDA" in config['metrics'] else "ℹ️ 보조 지표"
            ]
        }
        st.table(pd.DataFrame(metrics_data))
        
        with st.expander("🔍 데이터 원본 보기 (DB)"):
            st.write(f"- EPS ({criteria}): {eps:,}원")
            st.write(f"- BPS ({criteria}): {bps:,}원")
            st.write(f"- EBITDA 추정: {ebitda_ps:,}원")
            st.write(f"- 성장률 가정: {config['growth']}%")
            st.write(f"- 멀티플 산출식: {multi_desc}")
