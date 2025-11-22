import streamlit as st
from datetime import date, timedelta
import pandas as pd
import random 
import sys # 引入 sys 模組，用於輸出調試信息到控制台

# --- 1. 頁面設定與樣式 ---
st.set_page_config(page_title="週期推算小幫手", page_icon="🩸", layout="centered")

# 使用 CSS 來美化按鈕和標題
TAILWIND_PINK = "rgba(236, 72, 153, 1)" # Tailwind pink-500 equivalent

st.markdown(f"""
    <style>
    /* Custom button styles for a better look */
    .stButton>button {{
        background-color: #FF4B4B; /* Streamlit default red */
        color: white;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease-in-out;
    }}
    .stButton>button:hover {{
        background-color: {TAILWIND_PINK};
        border-color: {TAILWIND_PINK};
    }}
    /* Style for the delete button specifically */
    .delete-button > button {{
        background-color: #ef4444 !important; /* Tailwind red-500 */
        color: white !important;
    }}
    .delete-button > button:hover {{
        background-color: #b91c1c !important; /* Tailwind red-700 */
    }}
    /* 確保 Success Box 內容清晰 */
    div[data-testid="stSuccess"] {{
        border-left: 6px solid #10b981 !important; /* Tailwind emerald-500 */
    }}
    </style>
""", unsafe_allow_html=True)

# --- 2. 狀態初始化與刪除/儲存函式 ---

# 狀態初始化：periods 儲存字典列表 [{'start': date, 'end': date}, ...]
if 'periods' not in st.session_state:
    st.session_state.periods = []
if 'avg_cycle' not in st.session_state:
    st.session_state.avg_cycle = 28 # 預設平均週期
if 'avg_period_length' not in st.session_state:
    st.session_state.avg_period_length = 5 # 預設經期平均長度
if 'query_date' not in st.session_state:
    st.session_state.query_date = date.today()

def save_period():
    """將新的經期開始日和結束日儲存到列表中。"""
    new_start_date = st.session_state.new_period_start
    new_end_date = st.session_state.new_period_end
    
    if new_start_date and new_end_date and new_start_date <= new_end_date:
        new_record = {'start': new_start_date, 'end': new_end_date}
        
        if not any(r['start'] == new_start_date for r in st.session_state.periods):
            st.session_state.periods.append(new_record)
            st.rerun()
        else:
            st.warning("此經期開始日已存在紀錄中，請刪除舊紀錄後再新增。")
    elif new_start_date and new_end_date and new_start_date > new_end_date:
        st.error("❌ 錯誤：結束日期不能早於開始日期，請修正。")

def delete_period(target_date_str):
    """根據開始日從紀錄中刪除指定的週期紀錄。"""
    try:
        target_date = date.fromisoformat(target_date_str)
        original_length = len(st.session_state.periods)
        st.session_state.periods = [
            r for r in st.session_state.periods if r['start'] != target_date
        ]
        
        if len(st.session_state.periods) < original_length:
            st.success(f"已刪除紀錄：{target_date.isoformat()}")
            st.rerun()
        else:
            st.warning("找不到要刪除的紀錄。")
    except ValueError:
        st.error("日期格式錯誤，無法刪除。")

def get_chinese_weekday(d):
    """根據日期物件返回中文星期幾。"""
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return "週" + weekdays[d.weekday()]

# --- 3. 核心計算邏輯與貼心小提醒 ---

def get_contextual_tip(stage):
    """根據當前週期階段提供對應的貼心注意事項。"""
    tips = {
        "🔴 **月經期**": "建議多休息、保暖，多喝溫水，避免過度勞累及生冷食物，讓身體好好休息。",
        "🟡 **排卵期**": "排卵期可能伴隨輕微腹痛或分泌物增多。請注意身體訊號，若有備孕/避孕需求請特別留意。",
        "🟢 **濾泡期**": "身體狀態逐漸恢復，精力充沛。這是安排運動、挑戰新目標的最佳時期，多補充蛋白質。",
        "🔵 **黃體期**": "這是經前症候群 (PMS) 好發期。保持心情愉悅，減少咖啡因攝取，注意情緒波動，準備迎接下次經期。",
        "⚠️ **週期可能延遲**": "週期已超過平均天數。請確認是否有新紀錄未輸入，或考慮尋求專業醫療建議。",
    }
    # 移除階段標籤以匹配字典
    clean_stage = stage.split('(')[0].strip() 
    return tips.get(clean_stage, "請保持良好生活習慣，並確保輸入最新紀錄以獲得最準確的推算。")


def calculate_predictions(periods, avg_cycle, target_date):
    """根據紀錄計算最近的週期和預測，並針對目標日 (target_date) 進行階段判斷。"""
    
    # 預設結果結構
    result = {
        'last_period_date': None,
        'next_period_start': None,
        'avg_cycle': avg_cycle,
        'avg_period_length': st.session_state.avg_period_length, # 使用 session state 的預設值
        'current_stage': "無紀錄",
        'stage_detail': "請新增一筆紀錄後開始推算。",
        'day_since_start': 0,
        'last_period_end_date': None,
        'target_date': target_date,
        'days_to_next_period': None
    }
    
    if not periods:
        return result

    # 1. 整理數據並計算平均值
    sorted_periods = sorted(periods, key=lambda x: x['start'], reverse=True)
    last_period_record = sorted_periods[0]
    last_period_date = last_period_record['start']
    last_period_end_date = last_period_record['end']
    result['last_period_date'] = last_period_date
    result['last_period_end_date'] = last_period_end_date
    
    # 計算平均週期長度和平均經期長度
    start_dates = [r['start'] for r in sorted_periods]
    if len(start_dates) > 1:
        # 平均週期長度
        total_cycle_length = sum((start_dates[i] - start_dates[i+1]).days for i in range(len(start_dates) - 1))
        avg_cycle = round(total_cycle_length / (len(start_dates) - 1))
        st.session_state.avg_cycle = avg_cycle
        result['avg_cycle'] = avg_cycle

    # 平均經期長度 (新加入)
    if len(periods) > 0:
        total_period_length = sum((r['end'] - r['start']).days + 1 for r in periods)
        avg_period_length = round(total_period_length / len(periods))
        st.session_state.avg_period_length = avg_period_length
        result['avg_period_length'] = avg_period_length
    
    projected_menses_duration = st.session_state.avg_period_length # 使用計算出的平均經期長度

    # 3. 判斷目標日期的階段
    
    day_in_entire_history = (target_date - last_period_date).days + 1
    result['day_since_start'] = day_in_entire_history

    if target_date < last_period_date:
        # 目標日早於最近的紀錄
        result['current_stage'] = (f"🕒 **歷史查詢**")
        result['stage_detail'] = f"查詢日 ({target_date.isoformat()}) 早於最近的經期紀錄 ({last_period_date.isoformat()})。"
        
        # 預計下次經期 (基於上次紀錄)
        projected_next_period_start = last_period_date + timedelta(days=avg_cycle)
        result['next_period_start'] = projected_next_period_start
        result['days_to_next_period'] = (projected_next_period_start - target_date).days if projected_next_period_start > target_date else None
        
    elif target_date <= last_period_end_date:
        # 目標日落在已紀錄的經期期間 (舊紀錄，已經輸入結束日)
        result['current_stage'] = (f"🔴 **月經期** (第 {day_in_entire_history} 天)")
        result['stage_detail'] = f"目標日屬於上次**已紀錄**的經期期間 ({last_period_date.isoformat()} - {last_period_end_date.isoformat()})。"
        
        # 預計下次經期
        projected_next_period_start = last_period_date + timedelta(days=avg_cycle)
        result['next_period_start'] = projected_next_period_start
        result['days_to_next_period'] = (projected_next_period_start - target_date).days if projected_next_period_start > target_date else 0
        
    else:
        # 目標日在上次結束日之後，開始持續推算 (未來預測)
        
        # 週期內第幾天 (1 to avg_cycle)
        day_in_projected_cycle = (day_in_entire_history - 1) % avg_cycle + 1
        
        # 找出目標日所在的預計週期開始日 (P.C.S)
        cycles_passed = (day_in_entire_history - 1) // avg_cycle
        projected_cycle_start = last_period_date + timedelta(days=cycles_passed * avg_cycle)
        
        # 找出下一個預計週期開始日 (P.N.P.S)
        projected_next_period_start = projected_cycle_start + timedelta(days=avg_cycle)
        
        # 設定預測日期和天數
        result['days_to_next_period'] = (projected_next_period_start - target_date).days
        result['next_period_start'] = projected_next_period_start
        
        # 預計經期結束日 (根據平均經期長度計算)
        projected_menses_end = projected_cycle_start + timedelta(days=projected_menses_duration - 1)
        
        # 計算階段日期 (基於標準 14 天黃體期)
        projected_ovulation_date = projected_next_period_start - timedelta(days=14)
        projected_fertile_start = projected_ovulation_date - timedelta(days=5)
        projected_fertile_end = projected_ovulation_date
        
        # --- 階段判斷主邏輯 (V3.2 最終修正：加入對「預計經期結束日」的判斷) ---

        # 1. 最高優先級：檢查目標日是否落在預計經期期間
        if target_date >= projected_cycle_start and target_date <= projected_menses_end:
            result['current_stage'] = (f"🔴 **月經期** (預計週期日 {day_in_projected_cycle})")
            result['stage_detail'] = "查詢日落在預計經期期間。"
            
        # 2. 檢查週期是否延遲 (目標日已經超過了下一次預計經期開始日 P.N.P.S)
        elif target_date >= projected_next_period_start:
             # 注意：projected_cycle_start 已經被 Menses 檢查覆蓋，所以這裡只會捕捉到延遲的情況
             result['current_stage'] = (f"⚠️ **週期可能延遲** (第 {day_in_projected_cycle} 天)")
             result['stage_detail'] = "請注意，預計經期已過，建議留意身體狀況，並新增最新紀錄。"
             result['days_to_next_period'] = 0
             
        # 3. 檢查黃體期 (Luteal Phase: Ovulation End + 1 ~ PNPS - 1)
        elif target_date > projected_fertile_end:
            result['current_stage'] = (f"🔵 **黃體期** (預計週期日 {day_in_projected_cycle})")
            days_to_next_period_luteal = (projected_next_period_start - target_date).days
            result['stage_detail'] = f"妳正在預計週期日 **{day_in_projected_cycle}**，正值黃體期，離下次經期還有約 {days_to_next_period_luteal} 天。"

        # 4. 檢查排卵期 (Ovulation/Fertile Phase: Fertile Start ~ Fertile End)
        elif target_date >= projected_fertile_start and target_date <= projected_fertile_end:
            result['current_stage'] = (f"🟡 **排卵期** (預計週期日 {day_in_projected_cycle})")
            result['stage_detail'] = f"妳正在預計週期日 **{day_in_projected_cycle}**，正值排卵期，請留意身體訊號。"
        
        # 5. 檢查濾泡期 (Follicular Phase: Last Menses End + 1 ~ Fertile Start - 1)
        elif target_date < projected_fertile_start:
            result['current_stage'] = (f"🟢 **濾泡期** (預計週期日 {day_in_projected_cycle})")
            days_to_fertile = (projected_fertile_start - target_date).days
            result['stage_detail'] = f"妳正在預計週期日 **{day_in_projected_cycle}**，正值濾泡期，離排卵期還有約 {days_to_fertile} 天。"

    return result


# --- 4. Streamlit UI 介面 ---

st.title("🩸 月經週期推算小幫手")
st.markdown("---")

# 1. 輸入新的經期開始日與結束日
with st.expander("🗓️ 新增經期紀錄 (開始日與結束日)"):
    with st.form("new_period_form", clear_on_submit=True):
        col_start, col_end = st.columns(2)

        with col_start:
            st.date_input(
                "1. 經期開始日期 (LMP)",
                date.today(),
                max_value=date.today(),
                key="new_period_start" 
            )
        with col_end:
            st.date_input(
                "2. 經期結束日期",
                date.today(),
                max_value=date.today(),
                key="new_period_end" 
            )

        submitted = st.form_submit_button("💾 儲存此紀錄")
        if submitted:
            save_period()


# --- 4a. 今日狀態 (獨立顯示區塊 - 佈局精簡) ---
st.subheader("--- 今日狀態 ---")

today_data = calculate_predictions(
    st.session_state.periods, 
    st.session_state.avg_cycle, 
    date.today()
)

if today_data['last_period_date']:
    current_stage_for_today = today_data['current_stage']
    today_weekday = get_chinese_weekday(date.today())
    
    # 1. 今日狀態 (日期、星期)
    st.markdown(f"## {date.today().isoformat()} ({today_weekday})")
    
    # 2. 現在是某階段
    st.info(f"現在是：**{current_stage_for_today.split('(')[0].strip()}**")
    
    # 3. 貼心小提醒
    if current_stage_for_today != "無紀錄" and "歷史查詢" not in current_stage_for_today:
        tip = get_contextual_tip(current_stage_for_today)
        st.success(f"**💖 貼心小提醒：** {tip}")
    
    # 4. 距離下次經期
    days_to_next = today_data['days_to_next_period']
    # 針對今天的日期進行判斷
    if "週期可能延遲" in current_stage_for_today:
         st.markdown("### ⏳ **經期可能遲到，請注意身體變化。**")
    elif "月經期" in current_stage_for_today and today_data['target_date'] <= today_data['last_period_end_date']:
         st.markdown("### 🔴 **妳目前正值月經期中。**")
    elif days_to_next is not None and days_to_next == 0 and "月經期" in current_stage_for_today:
        st.markdown("### ⚠️ **今天就是預計經期日！**")
    elif days_to_next is not None and days_to_next > 0:
        st.markdown(f"### ⏳ 距離下次經期還有 **{days_to_next}** 天")
    
    st.markdown("---")
else:
    st.warning("⚠️ 目前沒有任何經期開始日紀錄。請在上方新增一筆紀錄後開始推算。")
    st.markdown("---")


# --- 4b. 查詢特定日期 (隱藏式設計) ---
# 標題已更改為「妳想查哪一天呢」
with st.expander("🔍 妳想查哪一天呢"):

    # 查詢特定日期欄位
    st.date_input(
        "選擇您想查詢的日期",
        value=st.session_state.query_date,
        key="query_date_expander_input" 
    )
    
    query_target_date = st.session_state.query_date_expander_input
    
    query_data = calculate_predictions(
        st.session_state.periods, 
        st.session_state.avg_cycle, 
        query_target_date
    )

    if query_data['last_period_date']:
        query_weekday = get_chinese_weekday(query_target_date)
        current_stage_for_query = query_data['current_stage']
        query_days_to_next = query_data['days_to_next_period']
        
        # 1. 查詢的日期(星期)
        st.markdown(f"## 查詢日期：{query_target_date.isoformat()} ({query_weekday})")
        
        # 2. 查詢日期的階段
        st.info(f"查詢結果階段：**{current_stage_for_query.split('(')[0].strip()}**")
        
        # 3. 查詢日期距離下次經期約幾天
        # 只有在非「月經期」和「週期可能延遲」且有天數時才顯示
        if "月經期" not in current_stage_for_query and "週期可能延遲" not in current_stage_for_query and query_days_to_next is not None and query_days_to_next > 0:
            st.markdown(f"### ⏳ 距離下次經期還有約 **{query_days_to_next}** 天")
        elif "月經期" in current_stage_for_query:
            # 顯示預計經期結束日
            menses_duration = query_data['avg_period_length']
            # 計算預計經期結束日
            days_since_start = (query_target_date - query_data['last_period_date']).days
            cycles_passed = days_since_start // query_data['avg_cycle']
            projected_cycle_start = query_data['last_period_date'] + timedelta(days=cycles_passed * query_data['avg_cycle'])
            
            projected_menses_end = projected_cycle_start + timedelta(days=menses_duration - 1)
            
            # 確保只顯示在預計結束日當天或之後的天數
            if query_target_date <= projected_menses_end:
                 st.markdown(f"### 🔴 預計經期持續到 **{projected_menses_end.isoformat()}**")
            else:
                 st.markdown(f"### 🔴 經期已結束，正在等待下次預計開始日。")
        elif "週期可能延遲" in current_stage_for_query:
             st.markdown("### ⚠️ **經期已過，正在等待或已開始。**")
        
    st.markdown("---")


# --- 4c. 預測結果 (移到查詢日期之後) ---
if today_data['last_period_date']:
    # 標題已更改為「預計下次經期」
    st.subheader("預計下次經期")
    
    # 顯示距離今天最近的下一個預計開始日
    days_since_last = (date.today() - today_data['last_period_date']).days
    cycles_passed_since_last = days_since_last // st.session_state.avg_cycle
    projected_start = today_data['last_period_date'] + timedelta(days=cycles_passed_since_last * st.session_state.avg_cycle)
    
    if projected_start <= date.today() and date.today() > today_data['last_period_end_date']:
        # 如果 projected_start 在今天之前或等於今天，且今天已經不是上次的經期結束日，則顯示下一次的開始日
        display_next_menses_date = projected_start + timedelta(days=st.session_state.avg_cycle)
    elif date.today() <= today_data['last_period_end_date']:
        # 如果今天還在上次的經期內，顯示下一次的開始日
        display_next_menses_date = today_data['last_period_date'] + timedelta(days=st.session_state.avg_cycle)
    else:
        display_next_menses_date = projected_start
        
    st.markdown(f"下一個預計經期開始日：**{display_next_menses_date.isoformat()}**")
    
    st.markdown("---")


# --- 5. 趣味內容顯示 (錄影中請微笑 - 移到歷史紀錄上方) ---

FUN_CONTENTS = [
    "什麼動物最愛問為什麼？🤔 長頸鹿，因為牠的脖子伸得很長，好奇心也長！🦒",
    "什麼東西越洗越髒？💧 肥皂。",
    "為什麼圖書館的書架很高？📚 因為知識是無止境的！",
    "什麼時候時鐘不會走？🕰️ 壞掉的時候。",
    "你知道貓最喜歡喝什麼嗎？🍵 喵～茶。",
    "誰最喜歡問問題？💡 老師，因為他每天都在出題！",
    "什麼東西有頭沒有腦？🧠 火柴。",
    "一個人從飛機上掉下來，為什麼沒事？☁️ 因為他掉在草地上，不是掉在地上。",
]

# 隨機選擇一個趣味內容
random_fun_content = random.choice(FUN_CONTENTS)

# 標題設定為「錄影中請微笑」
st.markdown(f"**😀 錄影中請微笑**")
st.success(f"**{random_fun_content}**") 

st.markdown("---")


# 6. 歷史紀錄與管理 (位置不變)
with st.expander("📜 歷史紀錄與管理"):
    if st.session_state.periods:
        sorted_periods = sorted(st.session_state.periods, key=lambda x: x['start'], reverse=True)
        
        # 顯示平均週期長度和平均經期長度
        st.info(f"**💡 系統計算的平均週期：** {st.session_state.avg_cycle} 天 | **平均經期長度：** {st.session_state.avg_period_length} 天 (基於您的紀錄)")
        
        for i, p_record in enumerate(sorted_periods):
            p_start_date_str = p_record['start'].isoformat()
            p_end_date_str = p_record['end'].isoformat()
            
            col1, col2 = st.columns([0.7, 0.3])
            
            with col1:
                st.markdown(f"**{i+1}.** 開始日：{p_start_date_str} / 結束日：{p_end_date_str}")
            
            with col2:
                st.button(
                    "🗑️ 刪除",
                    key=f"delete_{p_start_date_str}",
                    on_click=delete_period,
                    args=(p_start_date_str,),
                    help="點擊以刪除此筆完整的週期紀錄",
                )
    else:
        st.info("尚無歷史紀錄。")

st.caption("版本：v3.2 (核心邏輯最終修正) | Streamlit App")
