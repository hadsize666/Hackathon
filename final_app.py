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

# --- ЗАГРУЗКА ДАННЫХ ---
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
                params_list.append({'sheet': sheet_name, 'column': col})
        dist_list = sorted(list(all_districts))
    except Exception as e:
        st.error(f"Файл City_Data_Summary.xlsx не найден. Ошибка: {e}")
        sheets, dist_list, params_list = {}, [], []

    # РАСШИРЕННЫЙ СПИСОК ИНТЕНТОВ (ВСТРОЕННЫЙ)
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

# --- ЛОГИКА ИИ ---

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

def compare_multi_logic(districts_names, target_param, sheets):
    df = sheets[target_param['sheet']]
    data = []
    for d_name in districts_names:
        try:
            val = float(df[df.iloc[:, 0] == d_name][target_param['column']].values[0])
            data.append({"name": d_name, "val": val})
        except: continue

    if not data: return ""
    data = sorted(data, key=lambda x: x['val'], reverse=True)
    output = f"\n📊 **Параметр: '{target_param['column']}'**\n"
    leader = data[0]
    for i, item in enumerate(data):
        marker = "🏆" if i == 0 else "📍"
        line = f"{marker} {item['name']}: {item['val']}"
        if i > 0 and item['val'] != 0:
            diff = round(((leader['val'] - item['val']) / item['val']) * 100, 2)
            line += f" (лидер выше на {diff}%)"
        output += line + "\n"
    return output

def analyze_advantages(district_name, sheets):
    all_data = []
    for sheet_name, df in sheets.items():
        if district_name in df.iloc[:, 0].values:
            row = df[df.iloc[:, 0] == district_name]
            for col in df.columns[1:]:
                try:
                    val = float(row[col].values[0])
                    avg = df[col].mean()
                    all_data.append({"param": col, "val": val, "diff": val - avg})
                except: continue

    if not all_data: return "Данные по району не найдены."
    sorted_data = sorted(all_data, key=lambda x: x['diff'], reverse=True)
    res = f"📝 **Анализ района: {district_name}**\n\n✅ **Сильные стороны:**\n"
    for item in sorted_data[:3]:
        res += f"- {item['param']}: {item['val']} (+{round(item['diff'], 1)} к среднему)\n"
    res += "\n⚠️ **Зоны роста:**\n"
    for item in sorted_data[-3:][::-1]:
        res += f"- {item['param']}: {item['val']} (-{round(abs(item['diff']), 1)} от среднего)\n"
    return res

# --- ИНТЕРФЕЙС STREAMLIT ---

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

# --- ИИ-АССИСТЕНТ (ОБНОВЛЕННЫЙ) ---

def process_ai_logic(payload):
    user_query = payload.get("query", "").lower()
    json_district = payload.get("district", "")

    found_dists, found_params = extract_entities_multi(user_query, districts_list, parameters)
    target_district = found_dists[0] if found_dists else json_district
    intent = get_intent(user_query)

    # 1. Плюсы и минусы (интент advantages + ключевые слова)
    if intent['tag'] == 'advantages' or any(word in user_query for word in ["плюс", "минус", "сторона", "косяк", "проблем"]):
        if target_district:
            prefix = random.choice(intent['responses']) if intent['tag'] == 'advantages' else "📝 Анализ:"
            return f"{prefix}\n\n{analyze_advantages(target_district, all_sheets)}"
        return "Укажите район для анализа."

    # 2. Улучшение (интент improvement)
    if intent['tag'] == 'improvement' or "улучшить" in user_query:
        if target_district:
            prefix = random.choice(intent['responses'])
            analysis = analyze_advantages(target_district, all_sheets)
            return f"{prefix}\n\nЧтобы сделать район **{target_district}** лучше, обратите внимание на следующие показатели:\n\n{analysis}"
        return "Укажите район, требующий улучшений."

    # 3. Сравнение (интент comparison)
    if intent['tag'] == 'comparison' or len(found_dists) >= 2:
        if len(found_dists) >= 2:
            res = random.choice(intent['responses']) + "\n"
            if not found_params:
                res += "Для точного сравнения укажите параметр (например, 'по экологии')."
            for p_obj in found_params: 
                res += compare_multi_logic(found_dists, p_obj, all_sheets)
            return res
        return "Для сравнения нужно 2 района."

    # 4. Приветствие
    if intent['tag'] == 'greeting': 
        return random.choice(intent['responses'])

    return f"Я определил район **{target_district}**. Попробуйте спросить о его 'плюсах и минусах' или 'как улучшить' ситуацию."

@st.dialog("Интеллектуальный помощник", width="large")
def ai_assistant_dialog():
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.write(msg["content"])

    with st.container(border=True):
        c1, c2 = st.columns(2)
        dist = c1.selectbox("Район контекста", df_districts['Район'], key="ai_dist")
        cat = c2.selectbox("Тема", ["Экология", "Транспорт", "Безопасность"], key="ai_cat")
        user_input = st.chat_input("Спросите о районах...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.write(user_input)

        payload = {"district": dist, "query": user_input}
        with st.chat_message("assistant"):
            with st.spinner("Анализирую данные..."):
                response_text = process_ai_logic(payload)
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

with st.sidebar:
    st.divider()
    if st.button("🤖 Запустить ИИ-ассистента", use_container_width=True):
        ai_assistant_dialog()
