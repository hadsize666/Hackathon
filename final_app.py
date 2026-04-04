import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import random
import pymorphy3
from fuzzywuzzy import process
import time

st.set_page_config(
    page_title="Система городского мониторинга",
    page_icon="🏙️",
    layout="wide"
)

morph = pymorphy3.MorphAnalyzer()
MAX_LIMIT = 5

@st.cache_data
def load_all_data():
    districts_geo = pd.DataFrame({
        'Район': ['Бостандыкский', 'Медеуский', 'Турксибский', 'Алмалинский', 'Ауэзовский'],
        'lat': [43.2100, 43.2300, 43.3400, 43.2500, 43.2200],
        'lon': [76.9000, 76.9600, 76.9500, 76.9300, 76.8500],
        'Экология': [70, 90, 40, 50, 60],
        'Транспорт': [90, 70, 60, 95, 85],
        'Освещение': [85, 70, 40, 90, 75],
        'Безопасность': [80, 85, 50, 70, 65]
    })

    incidents = pd.DataFrame([
        ['Турксибский', 'Неисправность линий наружного освещения на ул. Сейфуллина', 'Инфраструктура'],
        ['Турксибский', 'Зафиксировано превышение норм задымления (частный сектор)', 'Экология'],
        ['Медеуский', 'Необходима установка дополнительных малых архитектурных форм', 'Благоустройство'],
        ['Алмалинский', 'Превышение допустимого уровня шума в ночное время', 'Правопорядок'],
        ['Ауэзовский', 'Нарушение интервалов движения общественного транспорта', 'Транспорт'],
        ['Бостандыкский', 'Запрос на реставрацию парковой зоны', 'Озеленение']
    ], columns=['Район', 'Содержание', 'Категория'])

    try:
        sheets = pd.read_excel('City_Data_Summary.xlsx', sheet_name=None)
        all_districts = set()
        params_list = []
        for sheet_name, df in sheets.items():
            all_districts.update(df.iloc[:, 0].dropna().unique())
            for col in df.columns[1:]:
                if "unnamed" not in str(col).lower():
                    params_list.append({'sheet': sheet_name, 'column': col})
        dist_list = sorted(list(all_districts))
    except Exception as e:
        st.error(f"Файл City_Data_Summary.xlsx не найден. Ошибка: {e}")
        sheets, dist_list, params_list = {}, [], []

    intents_data = [
        {
            "tag": "greeting",
            "patterns": ["привет", "здравствуй", "добрый день", "салем", "сәлем", "ку", "хай", "приветствую", "начать", "старт", "hi", "hello", "здравствуйте", "йо", "алло", "ты тут?", "эй", "помоги"],
            "responses": ["Привет! Какой район проанализируем?", "Здравствуйте! Я готов к работе. О каком районе хотите узнать?", "Приветствую! Чем могу помочь в мониторинге?"]
        },
        {
            "tag": "advantages",
            "patterns": ["плюсы и минусы", "сильные стороны", "слабые стороны", "преимущества", "недостатки", "что хорошего", "что плохого", "подробный отчет", "особенности района", "какие проблемы", "достоинства", "неудобства", "косяки", "фишки", "стоит ли там жить", "чем хорош", "анализ", "честный обзор"],
            "responses": ["Провожу глубокий аудит района...", "Вот ключевые особенности этого района:", "Выделил сильные и слабые стороны на основе данных:"]
        },
        {
            "tag": "improvement",
            "patterns": ["как улучшить", "как исправить", "что сделать", "рекомендации", "советы", "развитие", "модернизация", "оптимизация", "как поднять рейтинг", "стратегия", "как решить проблемы", "пути решения", "что посоветуешь", "как прокачать", "апгрейд", "что подтянуть", "на что обратить внимание"],
            "responses": ["На основе слабых мест подготовил рекомендации:", "Вот приоритетные шаги по улучшению ситуации:", "Для повышения показателей рекомендую следующее:"]
        },
        {
            "tag": "comparison",
            "patterns": ["сравни районы", "где лучше ситуация", "какая ситуация у", "хочу сравнить", "какой район круче", "выбери лучший", "кто лидер", "у кого выше рейтинг", "сравни показатели", "сопоставь районы", "разница между", "сравнение", "кто лучше по"],
            "responses": ["Секунду, сейчас сопоставлю данные...", "Уже сравниваю. Вот что получилось:", "Анализирую показатели выбранных локаций..."]
        }
    ]

    return districts_geo, incidents, sheets, dist_list, params_list, intents_data

df_districts, df_incidents, all_sheets, districts_list, parameters, intents = load_all_data()

def normalize_text(text):
    words = text.split()
    res = []
    for word in words:
        clean_word = word.strip('.,?!').lower()
        res.append(morph.parse(clean_word)[0].normal_form)
    return " ".join(res)

def get_intent(user_text):
    best_match = {"tag": None, "score": 0, "responses": []}
    for intent in intents:
        result = process.extractOne(user_text.lower(), intent['patterns'])
        if result and result[1] > 70:
            if result[1] > best_match['score']:
                best_match = {"tag": intent['tag'], "score": result[1], "responses": intent['responses']}
    return best_match

def extract_entities_multi(user_text, districts, params):
    all_found_districts = process.extract(user_text, districts, limit=10)
    final_districts = [d[0] for d in all_found_districts if d[1] > 65]
    final_districts = list(dict.fromkeys(final_districts))[:MAX_LIMIT]

    clean_text = user_text.lower()
    for d in final_districts: clean_text = clean_text.replace(d.lower()[:-1], "")

    normalized_input = normalize_text(clean_text)
    param_names = [p['column'] for p in params]
    norm_param_map = {normalize_text(p): p for p in param_names}

    all_found_params = process.extract(normalized_input, list(norm_param_map.keys()), limit=10)
    final_params = []
    seen_params = set()
    for p_norm, score, *extra in all_found_params:
        orig_p = norm_param_map[p_norm]
        if score > 55 and orig_p not in seen_params:
            target_obj = next(item for item in params if item['column'] == orig_p)
            final_params.append(target_obj)
            seen_params.add(orig_p)
        if len(final_params) >= MAX_LIMIT: break
    return final_districts, final_params

def is_ignored_metric(col_name):
    ignored = ['итого', 'всего', 'в работе', 'конкурс', 'другое', 'прочее', 'unnamed', 'статус']
    return any(kw in str(col_name).lower() for kw in ignored)

def is_negative_metric(sheet_name, col_name):
    neg_keywords = [
        'краж', 'преступ', 'дтп', 'авари', 'жалоб', 'шум', 'загрязн', 
        'безработ', 'нарушен', 'смерт', 'убийст', 'грабеж', 'наркот', 
        'мошеннич', 'хулиган', 'насил', 'корруп', 'ущерб', 'пожар', 
        'травм', 'опасн', 'суицид', 'разбой', 'вымогател', 'угон',
        'правонаруш', 'инцидент', 'болезн', 'заболеван', 'криминал',
        'истек', 'просроч', 'отложен', 'отмен', 'долг', 'задолжен'
    ]
    text_to_check = f"{sheet_name} {col_name}".lower()
    return any(kw in text_to_check for kw in neg_keywords)

def compare_multi_logic(districts_names, target_param, sheets):
    df = sheets[target_param['sheet']]
    data = []
    for d_name in districts_names:
        try:
            val = float(df[df.iloc[:, 0] == d_name][target_param['column']].values[0])
            if pd.isna(val): continue
            data.append({"name": d_name, "val": val})
        except: continue

    if not data: return ""
    
    is_neg = is_negative_metric(target_param['sheet'], target_param['column'])
    
    data = sorted(data, key=lambda x: x['val'], reverse=not is_neg)
    output = f"\n📊 **Параметр: '{target_param['column']}'**\n"
    leader = data[0]
    for i, item in enumerate(data):
        marker = "🏆" if i == 0 else "📍"
        line = f"{marker} {item['name']}: {item['val']}"
        if i > 0 and item['val'] != 0:
            diff = round((abs(leader['val'] - item['val']) / item['val']) * 100, 2)
            word = "лучше" if is_neg else "выше"
            line += f" (лидер {word} на {diff}%)"
        output += line + "\n"
    return output

def analyze_comparison_general(dist1, dist2, sheets, mode="all"):
    all_data = []
    for sheet_name, df in sheets.items():
        if dist1 in df.iloc[:, 0].values and dist2 in df.iloc[:, 0].values:
            row1 = df[df.iloc[:, 0] == dist1]
            row2 = df[df.iloc[:, 0] == dist2]
            for col in df.columns[1:]:
                if is_ignored_metric(col): continue
                try:
                    val1 = float(row1[col].values[0])
                    val2 = float(row2[col].values[0])
                    if pd.isna(val1) or pd.isna(val2): continue
                    
                    is_neg = is_negative_metric(sheet_name, col)
                    diff = (val2 - val1) if is_neg else (val1 - val2)
                    all_data.append({"param": col, "val1": val1, "val2": val2, "diff": diff, "is_neg": is_neg})
                except: continue

    if not all_data: return "Недостаточно данных для сравнения этих районов."
    
    sorted_data = sorted(all_data, key=lambda x: x['diff'], reverse=True)
    res = f"📝 **Сравнение: {dist1} против {dist2}**\n"
    
    if mode in ["all", "positive"]:
        res += f"\n✅ **В чем {dist1} обходит конкурента:**\n"
        count = 0
        for item in sorted_data:
            if item['diff'] > 0 and not item['is_neg']:
                res += f"- Выше показатель \"{item['param']}\": {item['val1']} против {item['val2']}\n"
                count += 1
            if count >= 3: break
        if count == 0: res += "- Явных преимуществ не найдено.\n"
                
    if mode in ["all", "negative"]:
        res += f"\n⚠️ **В чем {dist1} уступает:**\n"
        count = 0
        for item in sorted_data[::-1]:
            if item['diff'] < 0:
                if item['is_neg']:
                    res += f"- Хуже ситуация с \"{item['param']}\": {item['val1']} против {item['val2']}\n"
                else:
                    res += f"- Ниже показатель \"{item['param']}\": {item['val1']} против {item['val2']}\n"
                count += 1
            if count >= 3: break
        if count == 0: res += "- Явных отставаний не найдено.\n"
    return res

def analyze_specific(district_name, sheets, mode="all"):
    all_data = []
    for sheet_name, df in sheets.items():
        if district_name in df.iloc[:, 0].values:
            row = df[df.iloc[:, 0] == district_name]
            for col in df.columns[1:]:
                if is_ignored_metric(col): continue
                try:
                    val = float(row[col].values[0])
                    avg = df[col].mean()
                    if pd.isna(val) or pd.isna(avg): continue
                    
                    is_neg = is_negative_metric(sheet_name, col)
                    diff = (avg - val) if is_neg else (val - avg)
                    all_data.append({"param": col, "val": val, "diff": diff, "is_neg": is_neg})
                except: continue

    if not all_data: return "Данные по району не найдены."
    
    sorted_data = sorted(all_data, key=lambda x: x['diff'], reverse=True)
    res = f"📝 **Анализ района: {district_name}**\n"
    
    if mode in ["all", "positive"]:
        res += "\n✅ **Сильные стороны (преимущества):**\n"
        count = 0
        for item in sorted_data:
            if item['diff'] > 0 and not item['is_neg']:
                res += f"- Высокий показатель \"{item['param']}\": {item['val']} (+{round(item['diff'], 1)} к среднему)\n"
                count += 1
            if count >= 3: break
        if count == 0: res += "- Выдающихся положительных метрик не найдено.\n"
                
    if mode in ["all", "negative"]:
        res += "\n⚠️ **Слабые стороны (зоны роста):**\n"
        count = 0
        for item in sorted_data[::-1]:
            if item['diff'] < 0:
                if item['is_neg']:
                    res += f"- Проблема (высокий уровень) с \"{item['param']}\": {item['val']} (хуже среднего на {round(abs(item['diff']), 1)})\n"
                else:
                    res += f"- Отставание по \"{item['param']}\": {item['val']} (-{round(abs(item['diff']), 1)} от среднего)\n"
                count += 1
            if count >= 3: break
        if count == 0: res += "- Критичных проблем не выявлено.\n"
    return res

with st.sidebar:
    st.header("⚙️ Параметры анализа")
    w_eco = st.slider("🍀 Экология", 0.1, 1.0, 0.5)
    w_trans = st.slider("🚌 Транспорт", 0.1, 1.0, 0.8)
    w_light = st.slider("💡 Освещение", 0.1, 1.0, 0.6)
    w_sec = st.slider("🛡️ Безопасность", 0.1, 1.0, 0.7)
    st.divider()

total_w = w_eco + w_trans + w_light + w_sec
df_districts['Индекс'] = ((df_districts['Экология'] * w_eco + df_districts['Транспорт'] * w_trans +
                           df_districts['Освещение'] * w_light + df_districts['Безопасность'] * w_sec) / total_w).round(1)

st.title("🏙️ Платформа ситуационного мониторинга города")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Средний индекс", f"{df_districts['Индекс'].mean():.1f}")
m2.metric("Активных инцидентов", len(df_incidents))
m3.metric("Лидер", str(df_districts.loc[df_districts['Индекс'].idxmax(), 'Район']))
m4.metric("Мониторинг", "Online")

tab_geo, tab_det = st.tabs(["🌍 Карта", "📊 Аналитика"])

with tab_geo:
    col_map, col_list = st.columns([2, 1])
    with col_map:
        m = folium.Map(location=[43.2389, 76.9455], zoom_start=11, tiles="cartodbpositron")
        for _, row in df_districts.iterrows():
            color = "#27ae60" if row['Индекс'] >= 75 else "#f39c12" if row['Индекс'] >= 60 else "#e74c3c"
            folium.CircleMarker([row['lat'], row['lon']], radius=15, popup=f"{row['Район']}: {row['Индекс']}",
                                color=color, fill=True, fill_opacity=0.7).add_to(m)
        st_folium(m, width=700, height=500)
    with col_list:
        st.dataframe(df_districts[['Район', 'Индекс']].sort_values(by='Индекс', ascending=False), hide_index=True)

with tab_det:
    selected_dist = st.selectbox("Выберите район для аудита:", df_districts['Район'])
    dist_stats = df_districts[df_districts['Район'] == selected_dist].iloc[0]
    col_charts, col_text = st.columns([1, 1])
    with col_charts:
        chart_data = pd.DataFrame({'Показатель': ['Экология', 'Транспорт', 'Освещение', 'Безопасность'],
                                   'Баллы': [dist_stats['Экология'], dist_stats['Транспорт'], dist_stats['Освещение'],
                                             dist_stats['Безопасность']]})
        st.bar_chart(chart_data.set_index('Показатель'))
    with col_text:
        dist_inc = df_incidents[df_incidents['Район'] == selected_dist]
        if not dist_inc.empty:
            for _, r in dist_inc.iterrows():
                with st.expander(f"🚩 {r['Категория']}"): st.write(r['Содержание'])
        else:
            st.success("Инцидентов нет.")

def process_ai_logic(payload):
    user_query = payload.get("query", "").lower()
    json_district = payload.get("district", "")

    found_dists, found_params = extract_entities_multi(user_query, districts_list, parameters)
    intent = get_intent(user_query)

    metric_word = None
    if "безопасн" in user_query: metric_word = "Безопасность"
    elif "эколог" in user_query or "чист" in user_query: metric_word = "Экология"
    elif "транспорт" in user_query or "пробк" in user_query or "автобус" in user_query: metric_word = "Транспорт"
    elif "освещен" in user_query or "свет" in user_query: metric_word = "Освещение"

    if metric_word and not found_params:
        is_global = any(word in user_query for word in ["самый", "самая", "лучший", "всего", "больше", "максимальн", "где"])
        
        if is_global and len(found_dists) < 2 and "или" not in user_query:
            best_row = df_districts.loc[df_districts[metric_word].idxmax()]
            return f"🏆 Самый высокий показатель «{metric_word}» имеет **{best_row['Район']}** район (оценка: {best_row[metric_word]} из 100)."
        
        dists_to_compare = found_dists if len(found_dists) >= 2 else ([json_district, found_dists[0]] if json_district and found_dists and json_district != found_dists[0] else [])
        if len(dists_to_compare) >= 2:
            dist1, dist2 = dists_to_compare[0], dists_to_compare[1]
            val1 = df_districts[df_districts['Район'] == dist1][metric_word].values[0]
            val2 = df_districts[df_districts['Район'] == dist2][metric_word].values[0]
            if val1 > val2:
                return f"🛡️ По показателю «{metric_word}» **{dist1}** ({val1}/100) обходит **{dist2}** ({val2}/100). Разница: {round(val1 - val2, 1)} бал."
            elif val2 > val1:
                return f"🛡️ По показателю «{metric_word}» **{dist2}** ({val2}/100) обходит **{dist1}** ({val1}/100). Разница: {round(val2 - val1, 1)} бал."
            else:
                return f"⚖️ По показателю «{metric_word}» районы равны (оба имеют {val1}/100)."
                
        target = found_dists[0] if found_dists else json_district
        if target:
            val = df_districts[df_districts['Район'] == target][metric_word].values[0]
            return f"📊 Оценка по показателю «{metric_word}» для района **{target}**: {val} из 100."

    pos_words = ["плюс", "преимуществ", "сильн", "положительн", "достоинств", "хорош", "лучше", "превосход", "обход", "выигрыва"]
    neg_words = ["минус", "недостатк", "хуже", "плох", "отрицательн", "косяк", "проблем", "слаб", "улучш", "рекомендац", "уступа", "проигрыва", "отстает"]

    is_comparison_context = any(word in user_query for word in ["перед", "чем", "сравнению", "против", "сравни", "или"])
    
    if is_comparison_context or intent['tag'] == 'comparison' or len(found_dists) >= 2:
        dists_to_compare = found_dists if len(found_dists) >= 2 else ([json_district, found_dists[0]] if json_district and found_dists else [])
        if len(dists_to_compare) >= 2:
            if not found_params:
                has_pos = any(word in user_query for word in pos_words)
                has_neg = any(word in user_query for word in neg_words)
                
                if has_pos and not has_neg:
                    return analyze_comparison_general(dists_to_compare[0], dists_to_compare[1], all_sheets, mode="positive")
                elif has_neg and not has_pos:
                    return analyze_comparison_general(dists_to_compare[0], dists_to_compare[1], all_sheets, mode="negative")
                else:
                    return analyze_comparison_general(dists_to_compare[0], dists_to_compare[1], all_sheets, mode="all")
            else:
                res = "📊 Сравниваю показатели:\n"
                for p_obj in found_params:
                    res += compare_multi_logic(dists_to_compare, p_obj, all_sheets)
                return res

    target_district = found_dists[0] if found_dists else json_district

    has_pos = any(word in user_query for word in pos_words)
    has_neg = any(word in user_query for word in neg_words)

    if has_pos and not has_neg:
        return analyze_specific(target_district, all_sheets, mode="positive")
    elif has_neg and not has_pos:
        return analyze_specific(target_district, all_sheets, mode="negative")
    elif has_pos and has_neg:
        return analyze_specific(target_district, all_sheets, mode="all")

    if intent['tag'] == 'advantages':
        if target_district:
            return analyze_specific(target_district, all_sheets, mode="all")
        return "Укажите район для анализа."

    if intent['tag'] == 'improvement':
        if target_district:
            return analyze_specific(target_district, all_sheets, mode="negative")
        return "Укажите район."

    return f"Я определил район **{target_district}**. Что вы хотите узнать?"

@st.dialog("Интеллектуальный помощник", width="large")
def ai_assistant_dialog():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_boundary = st.container(height=500)

    with chat_boundary:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    with st.container():
        st.divider()
        col1, col2 = st.columns(2)
        dist = col1.selectbox("Район контекста", df_districts['Район'], key="ai_dist_dialog")
        cat = col2.selectbox("Тема", ["Экология", "Транспорт", "Безопасность"], key="ai_cat_dialog")
        
        user_input = st.chat_input("Спросите о районах...")

    if user_input:
        with chat_boundary:
            with st.chat_message("user"):
                st.write(user_input)
        
        payload = {"district": dist, "query": user_input}
        response_text = process_ai_logic(payload)
        
        with chat_boundary:
            with st.chat_message("assistant"):
                st.write(response_text)
        
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "assistant", "content": response_text})

with st.sidebar:
    st.divider()
    if st.button("🤖 Запустить ИИ-ассистента", use_container_width=True):
        ai_assistant_dialog()
