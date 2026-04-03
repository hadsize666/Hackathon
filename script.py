from fastapi import FastAPI, Request
import pandas as pd
import json
import random
import pymorphy3
from fuzzywuzzy import process
import uvicorn

app = FastAPI()
morph = pymorphy3.MorphAnalyzer()
MAX_LIMIT = 5

# --- ЗАГРУЗКА ДАННЫХ ---
file_path = 'City_Data_Summary.xlsx'
try:
    all_sheets = pd.read_excel(file_path, sheet_name=None)
    all_districts = set()
    for df in all_sheets.values():
        all_districts.update(df.iloc[:, 0].dropna().unique())
    districts_list = sorted(list(all_districts))

    parameters = []
    for sheet_name, df in all_sheets.items():
        for col in df.columns[1:]:
            parameters.append({'sheet': sheet_name, 'column': col})
except Exception as e:
    print(f"Ошибка загрузки Excel: {e}")

try:
    with open('intents.json', 'r', encoding='utf-8-sig') as f:
        intents = json.load(f)
except FileNotFoundError:
    intents = []


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

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


def extract_entities_multi(user_text, districts, parameters):
    all_found_districts = process.extract(user_text, districts, limit=10)
    final_districts = [d[0] for d in all_found_districts if d[1] > 65]
    final_districts = list(dict.fromkeys(final_districts))[:MAX_LIMIT]

    clean_text = user_text.lower()
    for d in final_districts:
        clean_text = clean_text.replace(d.lower()[:-1], "")

    stop_words = ["сравни", "покажи", "по", "и", "район", "районы", "плиз", "выведи", "стороны", "слабые", "сильные"]
    for word in stop_words:
        clean_text = clean_text.replace(word, "")

    normalized_input = normalize_text(clean_text)
    param_names = [p['column'] for p in parameters]
    norm_param_map = {normalize_text(p): p for p in param_names}

    all_found_params = process.extract(normalized_input, list(norm_param_map.keys()), limit=10)
    final_params = []
    seen_params = set()

    for p_norm, score in all_found_params:
        orig_param = norm_param_map[p_norm]
        if score > 55 and orig_param not in seen_params:
            target_obj = next(item for item in parameters if item['column'] == orig_param)
            final_params.append(target_obj)
            seen_params.add(orig_param)
        if len(final_params) >= MAX_LIMIT: break
    return final_districts, final_params


def compare_multi_logic(districts_names, target_param, sheets):
    df = sheets[target_param['sheet']]
    data = []
    for d_name in districts_names:
        val = float(df[df.iloc[:, 0] == d_name][target_param['column']].values[0])
        data.append({"name": d_name, "val": val})

    data = sorted(data, key=lambda x: x['val'], reverse=True)
    output = f"\n📊 **Параметр: '{target_param['column']}'**\n"
    leader = data[0]
    for i, item in enumerate(data):
        marker = "🏆" if i == 0 else "📍"
        line = f"{marker} {item['name']}: {item['val']}"
        if i > 0 and item['val'] != 0:
            diff_proc = round(((leader['val'] - item['val']) / item['val']) * 100, 2)
            line += f" (лидер выше на {diff_proc}%)"
        output += line + "\n"
    return output


def analyze_advantages(district_name, sheets):
    all_data = []
    for sheet_name, df in sheets.items():
        if district_name in df.iloc[:, 0].values:
            row = df[df.iloc[:, 0] == district_name]
            for col in df.columns[1:]:
                val = float(row[col].values[0])
                avg = df[col].mean()
                all_data.append({"param": col, "val": val, "diff": val - avg})

    sorted_data = sorted(all_data, key=lambda x: x['diff'], reverse=True)
    strong = sorted_data[:3]
    weak = sorted_data[-3:]

    res = f"📝 **Анализ района: {district_name}**\n"
    res += "\n✅ **Сильные стороны:**\n"
    for item in strong:
        res += f"- {item['param']}: {item['val']} (выше среднего на {round(item['diff'], 1)})\n"
    res += "\n⚠️ **Зоны роста:**\n"
    for item in weak[::-1]:  # Переворачиваем, чтобы самый худший был в конце
        res += f"- {item['param']}: {item['val']} (ниже среднего на {round(abs(item['diff']), 1)})\n"
    return res


# --- API ENDPOINT ---

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_query = data.get("query", "")
    json_district = data.get("district", "")  # Район из селектора сайта

    # 1. Сначала ищем районы в тексте
    found_dists, found_params = extract_entities_multi(user_query, districts_list, parameters)

    # 2. Логика приоритета: если в тексте нет района, берем из JSON
    if not found_dists and json_district:
        found_dists = [json_district]

    intent = get_intent(user_query)

    # Операция: Слабые/Сильные стороны
    swot_keywords = ["стороны", "слабые", "сильные", "плюсы", "минусы", "преимущества"]
    if any(word in user_query.lower() for word in swot_keywords):
        if found_dists:
            return {"answer": analyze_advantages(found_dists[0], all_sheets)}
        return {"answer": "Бот: Укажите район для анализа сторон."}

    # Операция: Сравнение
    if intent['tag'] == 'comparison' or len(found_dists) >= 2:
        if len(found_dists) >= 2 and found_params:
            res = ""
            for p_obj in found_params:
                res += compare_multi_logic(found_dists, p_obj, all_sheets)
            return {"answer": res}
        return {"answer": "Бот: Для сравнения нужно 2 района и параметр (например, 'Экология')."}

    # Приветствие
    if intent['tag'] == 'greeting':
        return {"answer": random.choice(intent['responses'])}

    return {
        "answer": f"Бот: Я распознал район {found_dists if found_dists else 'не определен'}. Уточните ваш запрос (сравнение или анализ сторон)."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)