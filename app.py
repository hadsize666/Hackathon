import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import json
import time
st.set_page_config(
    page_title="Система городского мониторинга", 
    page_icon="🏙️", 
    layout="wide"
)
@st.cache_data
def load_base_data():
    districts = pd.DataFrame({
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
    
    return districts, incidents

df_districts, df_incidents = load_base_data()

with st.sidebar:
    st.header("⚙️ Параметры анализа")
    st.write("Настройте приоритеты развития для расчета индекса:")
    
    w_eco = st.slider("🍀 Экологический фон", 0.1, 1.0, 0.5)
    w_trans = st.slider("🚌 Транспортная сеть", 0.1, 1.0, 0.8)
    w_light = st.slider("💡 Городское освещение", 0.1, 1.0, 0.6)
    w_sec = st.slider("🛡️ Общественная безопасность", 0.1, 1.0, 0.7)
    
    st.divider()
    st.info("Данная модель позволяет в реальном времени пересчитывать рейтинг районов на основе текущих гос. приоритетов.")

total_w = w_eco + w_trans + w_light + w_sec

if total_w > 0:
    df_districts['Индекс'] = (
        (df_districts['Экология'] * w_eco + 
         df_districts['Транспорт'] * w_trans + 
         df_districts['Освещение'] * w_light + 
         df_districts['Безопасность'] * w_sec) / total_w
    ).round(1)
else:
    df_districts['Индекс'] = 0.0

st.title("🏙️ Платформа ситуационного мониторинга города")
st.markdown("##### Аналитический дашборд для принятия управленческих решений")

m1, m2, m3, m4 = st.columns(4)

avg_index = df_districts['Индекс'].mean()
leader_region = df_districts.loc[df_districts['Индекс'].idxmax(), 'Район']

m1.metric("Средний индекс города", f"{avg_index:.1f}")
m2.metric("Активных инцидентов", len(df_incidents))
m3.metric("Район-лидер", str(leader_region))
m4.metric("Статус мониторинга", "Активен", delta="Online")

st.divider()

tab_geo, tab_det = st.tabs(["🌍 Геоинформационный слой", "📊 Детальная аналитика"])

with tab_geo:
    st.subheader("Карта удовлетворенности городской средой")
    
    col_map, col_list = st.columns([2, 1])
    
    with col_map:
        m = folium.Map(location=[43.2389, 76.9455], zoom_start=11, tiles="cartodbpositron")
        
        for _, row in df_districts.iterrows():
            color = "#27ae60" if row['Индекс'] >= 75 else "#f39c12" if row['Индекс'] >= 60 else "#e74c3c"
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=15,
                popup=f"<b>{row['Район']}</b><br>Индекс: {row['Индекс']}",
                color=color,
                fill=True,
                fill_opacity=0.7
            ).add_to(m)
        
        st_folium(m, width=700, height=500)
    
    with col_list:
        st.write("**Рейтинг территорий:**")
        df_sorted = df_districts[['Район', 'Индекс']].sort_values(by='Индекс', ascending=False)
        st.dataframe(df_sorted, hide_index=True, use_container_width=True)
        st.caption("Красный цвет на карте сигнализирует о необходимости немедленного вмешательства.")

with tab_det:
    selected_dist = st.selectbox("Выберите административный район для аудита:", df_districts['Район'])
    
    # Фильтрация данных по выбранному району
    dist_stats = df_districts[df_districts['Район'] == selected_dist].iloc[0]
    dist_incidents = df_incidents[df_incidents['Район'] == selected_dist]
    
    col_charts, col_text = st.columns([1, 1])
    
    with col_charts:
        st.write(f"**Профиль показателей: {selected_dist}**")
        chart_data = pd.DataFrame({
            'Показатель': ['Экология', 'Транспорт', 'Освещение', 'Безопасность'],
            'Баллы': [dist_stats['Экология'], dist_stats['Транспорт'], dist_stats['Освещение'], dist_stats['Безопасность']]
        })
        st.bar_chart(chart_data.set_index('Показатель'))
        
    with col_text:
        st.write("**Реестр обращений и инцидентов:**")
        if not dist_incidents.empty:
            for _, row in dist_incidents.iterrows():
                with st.expander(f"🚩 {row['Категория']}"):
                    st.write(row['Содержание'])
        else:
            st.success("На текущий момент критических инцидентов не зафиксировано.")

    st.divider()
    
    st.subheader("📑 Аналитическое резюме системы")
    if dist_stats['Индекс'] < 65:
        st.error(f"Внимание: Район {selected_dist} находится в зоне риска. Рекомендуется пересмотреть бюджет на развитие категории '{dist_incidents['Категория'].iloc[0] if not dist_incidents.empty else 'Инфраструктура'}'")
    else:
        st.success(f"Показатели района {selected_dist} соответствуют целевым значениям мастер-плана развития города.")


def ask_ai_server(payload):
    # Если запускаешь локально — localhost, если в облаке — адрес облака
    SERVER_URL = "http://localhost:8000/chat"
    try:
        # Отправляем запрос на наш ИИ-сервер
        response = requests.post(SERVER_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("answer")
        else:
            return "Ошибка сервера ИИ"
    except Exception as e:
        return f"Связь с ИИ не установлена: {str(e)}"

# 2. Определение диалогового окна
@st.dialog("Интеллектуальный помощник", width="large")
def ai_assistant_dialog():
    # Инициализация истории сообщений в сессии, если её нет
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Отображение истории переписки
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Контейнер для ввода параметров запроса
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.selectbox("Район", df_districts['Район'], key="ai_dist")
        with col2:
            cat = st.selectbox("Тема", ["Экология", "Транспорт", "Безопасность"], key="ai_cat")
        
        user_input = st.chat_input("Напишите уточнение к запросу...")

    if user_input:
        # Визуализируем сообщение пользователя
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # Формируем JSON-объект
        payload = {
            "district": dist,
            "category": cat,
            "query": user_input,
            "current_index": float(df_districts[df_districts['Район'] == dist]['Индекс'].iloc[0])
        }

        # Выводим отправляемый JSON для контроля (опционально)
        with st.expander("Отправленный JSON-пакет"):
            st.json(payload)

        # Получаем ответ от "сервера"
        with st.chat_message("assistant"):
            with st.spinner("ИИ анализирует данные..."):
                response_text = ask_ai_server(payload)
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

# 3. Кнопка запуска в Sidebar
with st.sidebar:
    st.divider()
    if st.button("🤖 Запустить ИИ-ассистента", use_container_width=True):
        ai_assistant_dialog()
