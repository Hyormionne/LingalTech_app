import streamlit as st
import os
import time
import json
import requests  # together 대신 HTTP로 호출, streamlit cloud 오류로 인해 chromadb 제외

# --- Page Configuration ---
st.set_page_config(page_title="근로계약서 위험도 분석", page_icon="⚖️", layout="wide")

# --- API Key ---
api_key = os.environ.get("TOGETHER_API_KEY")

if not api_key:
    st.error("TOGETHER_API_KEY가 설정되지 않았습니다.")
    st.info("앱을 실행하기 전에 환경 변수를 설정하거나 Streamlit Cloud Secrets에 API 키를 등록하세요.")
    st.stop()

#--Together API 호출용 헬퍼 함수--

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

def call_together_chat(model_id: str, system_prompt: str, user_content: str) -> dict:
    """
    together 패키지 없이 HTTP로 직접 chat.completions 호출하는 함수
    JSON(dict) 전체를 그대로 반환하고, 에러 시 예외 발생시킴.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(TOGETHER_API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        # 스트림릿에 바로 보여줄 수 있도록 예외 메시지 예쁘게
        raise RuntimeError(f"Together API 요청 실패 (status={resp.status_code}): {resp.text[:500]}")
    return resp.json()


# --- (RAG 제거 버전) 법령 DB 검색 더미 함수 ---
def retrieve_relevant_laws(query_text: str, n_results: int = 5) -> str:
    """
    원래는 chromadb에서 관련 법령을 검색하던 자리.
    지금은 DB가 없으므로, 빈 문자열을 돌려서 '추가 컨텍스트 없음' 상태로 만들어 둠.
    나중에 혜은이가 DB 내용 보내주거나 해서 세팅 완료되면 여기만 다시 RAG 버전으로 바꾸면 됨.
    """
    return ""


# --- Labeling Manual (From Excel) ---
def get_labeling_manual():
    """
    Returns the structured labeling manual from the uploaded Excel file.
    This is the authoritative risk assessment guideline.
    """
    return """
[필수 라벨링 메뉴얼 - 위험도 판단 기준 (우선 적용)]

이 규칙은 Excel 라벨링 메뉴얼에서 추출되었으며, 모든 판단에서 최우선으로 적용되어야 합니다.

【제1조 근로개시일/계약기간】
고위험:
  • 근로개시일을 규정하지 않은 경우 → 필수 조항 누락
  • 기간의 정함이 있는 경우 계약기간이 1년을 초과했을 때 → 근로기준법 제16조 위반
  • 2년 초과 반복 갱신 → 무기계약 전환 명시 필요

【제2조 근무장소】
고위험:
  • 근무장소를 규정하지 않은 경우 → 필수 조항 누락
  • 여성과 18세 미만인 사람을 갱내에서 근로시킬 때 → 근로기준법 제72조 위반
중위험:
  • 근무장소를 포괄적 기재 시(전근 강제 해석 가능) → 주 근무지 명확히 기재 필요
저위험:
  • 보건, 의료, 복지 업무 등 법정 예외

【제3조 업무의 내용】
고위험:
  • 업무 내용을 규정하지 않은 경우 → 필수 조항 누락
  • 임신 중인 여성을 피폭방사선량 초과 업무에 사용 → 근로기준법 시행령 제40조 위반
  • 임신 중인 여성을 신체를 심하게 펴거나 굽히는 업무에 사용 → 보건상 유해/위험 사업 금지
중위험:
  • 포괄 규정으로 직무범위 불명확 → 주된 업무 구체적 명시 필요

【제4조 근로시간/휴게시간】
고위험:
  • 소정근로시간을 규정하지 않은 경우 → 필수 조항 누락
  • 탄력근무제가 도입되었는데 명시하지 않은 경우 → 근로기준법 제51조 위반
  • 1일 8시간, 1주 40시간을 초과하여 소정근로시간을 정한 경우 → 근로기준법 제50조 위반
  • 휴게시간이 법정 기준보다 적게 부여되거나 자유롭게 이용할 수 없는 경우 → 근로기준법 제54조 위반
  • 임산부에게 야간/휴일근로를 인가 없이 시키는 경우 → 근로기준법 제70조 위반
중위험:
  • 선택적 근로시간제 도입 시 근로자대표 서면합의 미명시
  • 18세 이상 여성 사원의 야간근로(22:00~06:00) → 동의 필수
  • 연장근로 주 12시간 한도 → 산후 1년 미만 여성은 1주 6시간 한도 준수 필요
  • 간주근로시간제 도입 시 연장근로수당 지급 조항 미명시
저위험:
  • 근무일과 근무요일이 비정형적인 경우 → 사업장 사정에 따라 가능

【제5조 근무일/휴일】
고위험:
  • 근무일 및 휴일을 규정하지 않은 경우 → 필수 조항 누락
  • 유급 주휴일을 부여하지 않거나 임금 산정에 미포함 → 근로기준법 제55조 위반
  • 주 7일 연속 근무 → 명백한 위반
저위험:
  • 유급 주휴일이 일요일이 아닌 경우 → 법적 문제 없음

【제6조 임금】
고위험:
  • 임금을 규정하지 않은 경우 → 필수 조항 누락
  • 임금 지급 주기가 월 1회 미만 (격월 지급 등) → 근로기준법 제43조 위반
  • 강제저금, 전차금 상계, 위약예정 조항 포함 → 근로기준법 제20~22조 위반
  • 퇴직금이나 연차 수당을 연봉에 포함 → 근로기준법 제15조 위반 (무효)
  • 야간근로(22:00~06:00)에 대해 50% 미만 가산 지급
  • 최저임금 미달 지급 (최저임금의 90% 미만)
중위험:
  • 토요일(주휴일 외 1일)을 무급으로 할지 유급으로 할지 명확히 규정하지 않은 경우 → 통상임금 산정 시 분쟁 가능
  • 포괄임금제 도입 시 연장/야간/휴일근로수당을 명확히 구분하지 않은 경우
  • 최저임금의 90%까지 지급하는 경우 → 수습기간 3개월 한도, 초과 시 위법
저위험:
  • 연장/야간/휴일근로에 대해 임금 대신 휴가를 주는 경우 → 근로자대표 서면합의 필요

【제7조 연차유급휴가】
고위험:
  • 연차유급휴가를 규정하지 않은 경우 → 필수 조항 누락
  • 육아기/임신기 근로시간 단축을 연차 산정 시 결근으로 간주 → 출근으로 봐야 함
  • 지각/조퇴/외출 누적을 결근으로 간주하여 연차 공제 → 모두 출근으로 봐야 함
  • 연차휴가를 전부 수당으로 지급하도록 강제 → 근로기준법 제60조 위반
  • 3년 이상 근속자에 대한 법정 가산휴가 미부여 또는 축소
  • 총 휴가일수 한도를 법정 기준(25일)보다 낮추는 경우
  • 법정 '유급' 가산휴가를 '무급'으로 변경
  • 부상/질병 휴업, 출산전후휴가, 육아휴직 등 출근으로 간주되는 기간 누락
  • 1년 미만 근로자에게 연차 미부여 또는 1개월 개근 시 1일 유급휴가 미부여
중위험:
  • 회사가 연차휴가일을 갈음하여 특정 근로일에 휴무시키는 경우 → 근로자대표 서면합의 필수
저위험:
  • 지각/조퇴/외출 누적 시간을 연차휴가로 공제하는 특약 → 노사 간 합의 시 가능

【제8조 사회보험】
중위험:
  • 4대보험 미가입 시 → 65세 이후/월 60시간 미만/60세 이후 고용 제외 여부 확인 필요

【제11조 기타/해고/징계】
고위험:
  • 직무 교육 시간을 근로 시간에서 제외 → 근로를 제공한 것으로 봐야 함
  • 근로계약 불이행에 대한 위약금/손해배상액 예정 → 근로기준법 제20조 위반 (무효)
중위험:
  • 5인 미만 사업장 명시 → 근로관계법령 미적용 가능
  • 예고 없는 해고 기재 → 3개월 미만 근속자는 해고예고 적용 제외 ('19.1.15. 시행)
  • 감봉(감급) 조항 명시 → 1회 액이 평균임금 1일분의 1/2, 총액이 1임금지급기의 1/10 초과 불가
저위험:
  • 통상해고와 징계해고에 관하여 기재 → 정당한 이유 필수
  • 경조사 휴가 미제공 기재 → 사업장 사정에 따라 달리 정할 수 있음
  • 복수 퇴직급여제도 존재 명시 → 법적 문제 없음
  • 징계 절차 재심절차 없음 명시 → 사업장 사정에 따라 가능
"""


# --- Helper Functions for Fixed Logic ---
def get_manual_fixed_advice(u):
    advice_list = []

    # A1. Nationality
    if u['nationality'] == '내국인':
        advice_list.append({
            "cond": "A1-1 내국인",
            "law": "근로기준법 제17조, 제43조",
            "summary": "내국인은 근로기준법 및 최저임금법의 일반적 근로조건이 적용됩니다.",
            "detail": "사용자는 근로계약 체결 시 근로조건(임금·근로시간 등)을 서면 명시해야 하며, 임금은 통화로, 직접, 전액을, 매월 1회 이상 일정한 날짜에 지급해야 합니다."
        })
    elif u['nationality'] == '외국인':
        advice_list.append({
            "cond": "A1-2 외국인",
            "law": "외국인고용법 제6~12조, 출입국관리법 제18조",
            "summary": "외국인 근로자는 고용허가제 절차 및 체류자격 확인이 필수입니다.",
            "detail": "고용허가제에 따라 고용주가 허가를 받아야 하며, 체류자격(E-9 등)에 따라 근로계약 가능 여부가 결정됩니다. 체류자격 외 취업은 불법입니다."
        })

    # A2. Gender
    if u['gender'] == '여성':
        advice_list.append({
            "cond": "A2-1 여성",
            "law": "근로기준법 제65조~제74조",
            "summary": "여성 근로자는 유해·위험 업무 제한, 출산휴가 및 보호를 받을 권리가 있습니다.",
            "detail": "임신·출산 여성의 유해·위험 업무 금지. 출산 전후 휴가(90일, 다태아 120일) 및 유산·사산휴가가 부여되어야 합니다."
        })
    elif u['gender'] == '남성':
        advice_list.append({
            "cond": "A2-2 남성",
            "law": "근로기준법 제50조, 제55조",
            "summary": "남성 근로자는 일반 근로시간 및 휴일 규정이 적용됩니다.",
            "detail": "1일 8시간, 주 40시간 초과 불가. 주 1회 이상 유급휴일이 보장되어야 합니다."
        })

    # A2-2. Pregnancy
    if u.get('pregnant') == '임산부 또는 출산 후 1년 이내':
        advice_list.append({
            "cond": "A2-2-1 임산부 등",
            "law": "근로기준법 제65조, 제70~74조, 남녀고용평등법 제19조, 고용보험법 제70조",
            "summary": "임산부는 유해·위험 업무 금지, 시간외근로 금지, 출산휴가 및 급여 보장 대상입니다.",
            "detail": "임산부는 유해·위험 사업 사용 금지. 시간외근로 금지. 출산전후휴가 90일(다태아 120일) 보장. 육아휴직 보장."
        })
    elif u['gender'] == '여성':
        advice_list.append({
            "cond": "A2-2-2 일반 여성",
            "law": "근로기준법 제65조",
            "summary": "일반 여성 근로자도 보건상 유해한 사업에 사용할 수 없습니다.",
            "detail": "사용자는 임산부가 아닌 18세 이상 여성이라도 임신·출산 기능에 유해한 사업에 사용할 수 없습니다."
        })

    # A3. Age
    if u['age'] == '만 18세 미만':
        advice_list.append({
            "cond": "A3-1 연소자",
            "law": "근로기준법 제64~70조, 청소년보호법 제29조",
            "summary": "연소근로자는 근로시간·업종 제한, 취직인허증 필요, 야간·휴일근로 금지됩니다.",
            "detail": "만15세 미만 고용 금지(취직인허증 예외). 1일 7시간, 주 35시간 제한. 야간·휴일 근로 금지."
        })
    elif u['age'] == '만 18세 이상 ~ 만 60세 미만':
        advice_list.append({
            "cond": "A3-2 일반 성인",
            "law": "근로기준법 제50조, 제53조",
            "summary": "일반 근로자 기준이 적용됩니다.",
            "detail": "1일 8시간, 주 40시간 초과 금지. 연장근로는 주 12시간 한도."
        })
    elif u['age'] == '만 60세 이상':
        advice_list.append({
            "cond": "A3-3 고령자",
            "law": "고령자고용촉진법 제19조, 제21조",
            "summary": "고령 근로자는 정년 후 재고용 및 임금조정 규정의 적용 대상입니다.",
            "detail": "정년 후 재고용 노력 의무. 임금피크제 등 고령 근로자 근로조건 완화 가능."
        })

    # A4. Disability
    if u['disability'] == '장애인':
        advice_list.append({
            "cond": "A4-1 장애인",
            "law": "장애인고용촉진법 제5조, 차별금지법 제10~12조",
            "summary": "장애인 근로자는 차별을 받지 않으며 정당한 편의를 제공받을 권리가 있습니다.",
            "detail": "장애인의 능력을 정당하게 평가하고 적정 고용 관리 의무. 정당한 편의(시설·장비, 근무시간 조정 등) 제공."
        })
    elif u['disability'] == '비장애인':
        advice_list.append({
            "cond": "A4-2 비장애인",
            "law": "근로기준법 제17조",
            "summary": "비장애인 근로자는 일반 기준에 따라 보호됩니다.",
            "detail": "일반 근로조건 명시 조항 적용."
        })

    # A5. Work Type
    if u['work_type'] == '포괄임금제':
        advice_list.append({
            "cond": "A5-1 포괄임금제",
            "law": "근로기준법 제56조",
            "summary": "포괄임금제라도 수당 포함 여부를 명시해야 합니다.",
            "detail": "연장·야간·휴일근로는 통상임금의 50% 이상 가산 지급해야 함이 원칙."
        })
    elif u['work_type'] == '유연근무제':
        advice_list.append({
            "cond": "A5-2 유연근무제",
            "law": "근로기준법 제52조",
            "summary": "유연근무제는 서면합의가 필수이며 정산기간 기준을 지켜야 합니다.",
            "detail": "근로자대표와 서면합의 필요. 1개월 단위 평균 주40시간 초과 금지."
        })
    elif u['work_type'] == '교대근무제':
        advice_list.append({
            "cond": "A5-3 교대근무제",
            "law": "근로기준법 제59조 제2항",
            "summary": "교대근무자는 11시간 연속휴식이 의무입니다.",
            "detail": "근로일 종료 후 다음 근로일까지 11시간 이상 연속휴식 보장해야 함."
        })
    elif u['work_type'] == '특별한 근로시간 유형에 해당 없음':
        advice_list.append({
            "cond": "A5-4 일반",
            "law": "근로기준법 제50조",
            "summary": "일반 법정근로시간 기준을 적용합니다.",
            "detail": "1일 8시간, 1주 40시간 기준. 연장 시 근로자 동의 필요."
        })

    return advice_list


# --- Main App Logic ---

if 'step' not in st.session_state:
    st.session_state.step = 1
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'contract_text' not in st.session_state:
    st.session_state.contract_text = ""


st.title("🏛️ 근로계약서 위험도 분석")
st.markdown("---")


# STEP A
if st.session_state.step == 1:
    st.subheader("📝 Step A. 근로자 기본 정보 입력")
    st.info("안녕하세요. 아래 단계별로 계약 당시 근로자 정보를 입력해 주세요.\n각 항목은 선택지 중 하나를 선택하여 답변하시면 됩니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nationality = st.radio("A1. 국적을 선택해 주세요.", ["내국인", "외국인"], index=None, key="a1")
        gender = st.radio("A2. 주민등록부에 기재된 성별을 선택해 주세요.", ["여성", "남성"], index=None, key="a2")
        
        pregnant_status = "해당 없음"
        if gender == "여성":
            st.markdown("---")
            st.markdown("**A2-2. (여성을 선택한 경우에만 표시)** 다음 중 해당되는 항목을 선택해 주세요.")
            pregnant_status = st.radio(
                "A2-2 선택",
                ["임산부 또는 출산 후 1년 이내", "위 항목에 해당하지 않음"],
                label_visibility="collapsed",
                index=None,
                key="a2_2"
            )
    
    with col2:
        age = st.radio("A3. 나이대를 선택해 주세요.", 
                        ["만 18세 미만", "만 18세 이상 ~ 만 60세 미만", "만 60세 이상"], 
                        index=None, key="a3")
        disability = st.radio("A4. 장애 유무를 선택해 주세요.", ["장애인", "비장애인"], index=None, key="a4")
        work_type = st.selectbox("A5. 근로시간 유형을 선택해 주세요.", 
                                    ["포괄임금제", "유연근무제", "교대근무제", "특별한 근로시간 유형에 해당 없음"],
                                    index=None, placeholder="선택해 주세요", key="a5")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    if st.button("다음 단계로 이동 (계약서 입력) 👉", type="primary"):
        missing_fields = []
        if not nationality: missing_fields.append("A1 국적")
        if not gender: missing_fields.append("A2 성별")
        if gender == "여성" and not pregnant_status: missing_fields.append("A2-2 임신여부")
        if not age: missing_fields.append("A3 나이")
        if not disability: missing_fields.append("A4 장애유무")
        if not work_type: missing_fields.append("A5 근로시간 유형")
        
        if missing_fields:
            st.error(f"다음 항목을 선택해 주세요: {', '.join(missing_fields)}")
        else:
            st.session_state.user_info = {
                "nationality": nationality,
                "gender": gender,
                "pregnant": pregnant_status,
                "age": age,
                "disability": disability,
                "work_type": work_type
            }
            st.session_state.step = 2
            st.rerun()


# STEP B
elif st.session_state.step == 2:
    st.subheader("📄 Step B. 계약서 입력")
    
    u = st.session_state.user_info
    preg_display = f"- A2-2: {u['pregnant']}" if u['gender'] == '여성' else ""
    
    st.success(f"""
    **[입력하신 내용은 다음과 같습니다]**
    - A1: {u['nationality']}
    - A2: {u['gender']}
    {preg_display}
    - A3: {u['age']}
    - A4: {u['disability']}
    - A5: {u['work_type']}
    """)
    
    st.info("계약서의 '조항번호'와 '조항 내용'을 각각 차례대로 입력해 주세요.")
    
    example_contract = """제1조 (근로개시일) 2025년 7월 3일부터 근무를 시작한다.
제2조 (근무장소) 갑의 사업장 내 지정된 장소.
제3조 (업무의 내용) 항만 하역 업무 및 중량물 취급.
제4조 (근로시간) 09:00부터 18:00까지로 하며 휴게시간은 점심시간 1시간으로 한다.
제5조 (근무일) 매주 월~토요일 근무하며, 토요일은 무급으로 한다.
제6조 (임금) 시급 12,000원으로 하며 매월 25일에 지급한다.
제7조 (기타) 임신 중인 경우라도 본인의 동의가 있으면 야간근로를 실시할 수 있다."""
    
    if st.button("📑 예시 계약서 불러오기"):
        st.session_state.contract_text = example_contract
        st.rerun()

    with st.form("contract_form"):
        contract_input = st.text_area(
            "계약서 내용 입력",
            value=st.session_state.contract_text,
            height=300,
            placeholder="예시) 1 – 계약 내용, 2 – 계약 내용 …"
        )
        
        col_submit1, col_submit2 = st.columns([1, 1])
        with col_submit1:
            if st.form_submit_button("👈 이전 단계로"):
                st.session_state.step = 1
                st.rerun()
        with col_submit2:
            analyze_clicked = st.form_submit_button("🚀 위험도 분석 시작")
            if analyze_clicked:
                if not contract_input.strip():
                    st.warning("계약서 내용을 입력해 주세요.")
                else:
                    st.session_state.contract_text = contract_input
                    st.session_state.step = 3
                    st.rerun()


# STEP C
elif st.session_state.step == 3:
    st.subheader("📊 Step C. 분석 결과")
    
    st.warning("""
    본 인공지능은 근로계약서의 주요 조항을 자동으로 분석하여, 관련 법령 
및 판례를 반영한 기준에 따른 조항별 리스크를 진단하고 개선방향을 
제시하는 시스템입니다. 
 
현재 시스템에는 근로기준법 등 일부 법률과 주요 판례만 반영된 
상태이며, 사용자(사업주·근로자) 입장별 맞춤 분석 기능은 개발 
중입니다. 현재 단계에서는 근로자 입장을 기준으로 위험도와 개선 
방향을 산출하고 있습니다. 
 
본 시스템은 「변호사법」 제34조 제5항 및 제109조를 준수하며, 
비변호사가 법률사무를 수행하거나 이를 알선하지 않도록 설계되어 
있습니다. 본 결과는 법률 자문이 아닌 참고용 분석 자료임을 
고려해주시기 부탁드립니다. 
 
계약으로 인해 실제 분쟁이 발생하여 법적 해석이 필요한 경우에는 
반드시 변호사 등 법률 전문가의 자문을 받으시기 바랍니다.
    """)
    
    u = st.session_state.user_info
    preg_str = f"({u['pregnant']})" if u['gender'] == '여성' else ""
    st.markdown(f"""
    ---
    ### 1. 근로자 및 계약 개요
    현재 입력된 계약서에서 이용자는 **"{u['nationality']}, {u['gender']}{preg_str}, {u['age']}, {u['disability']}, {u['work_type']}"** 으로 확인됩니다.
    """)
    
    st.markdown("### 2. 법률 참조 안내 (자동 산출 항목)")
    st.info("귀하의 입력 정보에 따라 다음 법령 조항이 자동으로 제안됩니다. 반드시 확인하십시오.")
    
    fixed_advice_list = get_manual_fixed_advice(u)
    for item in fixed_advice_list:
        with st.expander(f"📌 {item['summary']}", expanded=False):
            st.markdown(f"**적용 법령:** {item['law']}")
            st.write(item['detail'])
            
    st.markdown("---")
    st.markdown("### 3. 계약서 조항별 상세 위험도 분석")
    st.info("아래 라벨링 메뉴얼 기준에 따라 AI가 계약서를 분석합니다.")
    
    with st.spinner("🔍 라벨링 메뉴얼을 적용하여 분석 중입니다..."):
        rag_context = retrieve_relevant_laws(st.session_state.contract_text)
        labeling_manual = get_labeling_manual()
        
        SYSTEM_PROMPT = f"""당신은 대한민국 노동법 전문 변호사입니다.
계약서 분석 시 아래 '라벨링 메뉴얼'을 최우선 기준으로 삼으시기 바랍니다.

[근로자 프로필]
- 국적: {u['nationality']}
- 성별/임신여부: {u['gender']} / {u['pregnant']}
- 나이: {u['age']}
- 장애여부: {u['disability']}
- 근무형태: {u['work_type']}

{labeling_manual}

[참고 법령 DB 검색 결과]
{rag_context}

[필수 지시사항]
1. 계약서의 각 조항을 '라벨링 메뉴얼'과 대조하세요.
2. 메뉴얼에 명시된 위험도(고/중/저)를 그대로 따르세요. 메뉴얼의 판단이 우선입니다.
3. 메뉴얼에 해당하지 않는 내용은 법령과 DB 검색 결과에 근거하여 판단하세요.
4. 반드시 각 조항에 대해 구체적인 '법령 근거'를 명시하세요. 근거를 빈 값으로 두지 마세요.
5. 출력은 반드시 JSON 형식이어야 합니다.

출력 JSON 스키마:
{{
    "analysis": [
        {{
            "clause_number": "제O조",
            "clause_title": "조항 제목",
            "input_text": "입력된 조항 내용",
            "risk_level": 2,
            "risk_label": "고위험",
            "manual_reason": "라벨링 메뉴얼에 따른 판단 이유",
            "legal_reference": "근로기준법 제OO조, 근로기준법 시행령 제OO조 등 구체적 법령",
            "improvement": "개선 방안 (고위험/중위험일 경우 필수 작성)"
        }}
    ]
}}

주의사항:
- risk_level: 2(고위험), 1(중위험), 0(저위험)
- legal_reference 필드는 절대 비워두지 마세요. 반드시 구체적인 법령 조항을 명시하세요.
- 임산부 근로자의 경우 제3조, 제4조, 제6조는 특히 주의깊게 검토하세요."""
        
        model_id = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        
        try:
             # together SDK 대신 HTTP 헬퍼 사용
            response_json = call_together_chat(
                model_id=model_id,
                system_prompt=SYSTEM_PROMPT,
                user_content=st.session_state.contract_text,
            )

            raw_res = response_json["choices"][0]["message"]["content"].strip()
            res_json = json.loads(raw_res)
            analysis = res_json.get("analysis", [])
    
            
            # Display summary
            risk_counts = {"고위험": 0, "중위험": 0, "저위험": 0}
            for item in analysis:
                risk_label = item.get("risk_label", "")
                if risk_label in risk_counts:
                    risk_counts[risk_label] += 1
            
            total_clauses = len(analysis)
            summary_text = f"**전체 {total_clauses}개 조항** | 🚨 고위험 {risk_counts['고위험']}개 | ⚠️ 중위험 {risk_counts['중위험']}개 | ✅ 저위험 {risk_counts['저위험']}개"
            
            if risk_counts['고위험'] > 0:
                st.error(summary_text)
            elif risk_counts['중위험'] > 0:
                st.warning(summary_text)
            else:
                st.success(summary_text)
            
            st.markdown("---")
            
            # Display detailed analysis
            for idx, item in enumerate(analysis, 1):
                risk = item.get("risk_level", 0)
                risk_label = item.get("risk_label", "")
                clause_num = item.get("clause_number", f"조항 {idx}")
                clause_title = item.get("clause_title", "")
                input_text = item.get("input_text", "")
                explanation = item.get("manual_reason", "")
                ref = item.get("legal_reference", "")
                improvement = item.get("improvement", "")
                
                if risk == 2:
                    icon = "🚨 고위험"
                    bg_color = "#ffebee"
                    border_color = "#d32f2f"
                elif risk == 1:
                    icon = "⚠️ 중위험"
                    bg_color = "#fff3e0"
                    border_color = "#f57c00"
                else:
                    icon = "✅ 저위험"
                    bg_color = "#e8f5e9"
                    border_color = "#388e3c"
                
                st.markdown(f"""
                <div style="padding:15px; background-color:{bg_color}; border-left:5px solid {border_color}; border-radius:5px; margin-bottom:15px;">
                    <h4>{clause_num} {clause_title} - {icon}</h4>
                    <p><b>입력:</b> {input_text}</p>
                    <p><b>판단:</b> {explanation}</p>
                    <p><b>근거:</b> {ref if ref else '(법령 검토 필요)'}</p>
                    {f'<p style="color:#d32f2f; margin-top:8px;"><b>【개선】</b> {improvement}</p>' if improvement and risk > 0 else ''}
                </div>
                """, unsafe_allow_html=True)
                
        except json.JSONDecodeError as e:
            st.error(f"응답 형식 오류: {e}")
            st.info("AI 모델의 응답을 파싱할 수 없습니다. 다시 시도해 주세요.")
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
            st.info("기술적 오류가 발생했습니다. 나중에 다시 시도해 주세요.")

    st.markdown("---")
    
    if st.button("🔄 처음으로 돌아가기"):
        st.session_state.step = 1
        st.session_state.user_info = {}
        st.session_state.contract_text = ""
        st.rerun()
