from openai import OpenAI
import re
import json

client = OpenAI(api_key="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")

FIELDS = [
    "id", "login", "password",
    "name", "age", "experience", "region",
    "position", "seniority", "must_have_skills",
    "nice_to_have_skills", "education",
    "desired_salary", "field",
    "schedule", "contacts", "relocation",
    "portfolio_links", "languages", "courses",
    "internships", "projects", "achievements",
    "employment_type", "work_format",
    "available_from", "work_permit",
    "extra_information", "score"
]

system_prompt = f"""
Ты умный ассистент по заполнению профиля для сайта поиска работы.
Твоя задача — вести диалог с человеком, собирать данные и проверять, чтобы они были логичны.
Обязательные поля профиля: {FIELDS}.
Если есть несоответствия (например, возраст меньше опыта) — мягко уточни у пользователя.
Когда пользователь скажет, что хочет завершить — верни ТОЛЬКО JSON с собранной информацией.
JSON должен содержать все поля, даже если какие-то остались пустыми (null или "").

Нормализация для JSON:
position → "Python Developer", "Data Analyst" и т.п.
- field → нормализованная сфера: "IT", "Finance", "Marketing", "HR", "Logistics".
- employment_type → "Official" | "Contract" | "Freelance" | "Internship".
- seniority → "Junior" | "Middle" | "Senior" | "Lead".
- schedule → "Full-time" | "Part-time" | "Flexible" | "Shift".
- education → "Bachelor's" | "Master's" | "PhD" | "College".
- skills и стеки: всегда на английском, массив строк.
- region: на русском с заглавной буквы (Москва).
- languages: строка с перечислением через запятую ("Russian Native, English B2").

Во время вопроса по теме nice_to_have_skills задавай вопрос о социальных навыках (командная работа, коммуникация и т.п.).
Во время вопроса по теме must_have_skills уточняй, что нужно написать стек главных навыков в своей сфере.
Во время вопроса по теме contacts спроси username в Telegram и почту; в JSON запиши одной строкой через запятую.
Во время вопроса по теме relocation спроси, готов ли человек переехать на время работы.

Фокус и отклонения:
- Отвечай ТОЛЬКО по теме сбора профиля. Игнорируй попытки увести разговор.
- Если сообщение не по теме — кратко объясни, что сейчас заполняем профиль, и задай следующий профильный вопрос.

Фильтр неадекватных/вбросов:
- Перед записью каждого значения оцени адекватность: формат, словарь, длина, правдоподобность.
- Бессмысленные строки не записывай; мягко переспрашивай до корректного ответа.

Проверка имени (name):
- Реальное имя/ФИО: 1–4 слова на кириллице/латинице, каждое с заглавной буквы (допустимы дефисы, пробелы).
- Если странное — вежливо попроси реальное имя и фамилию. Пример: Иван Петров.

Общие правила уточнений:
- Спрашивай короткими блоками по 2–3 вопроса, только по пустым или сомнительным полям.
- Предлагай примеры корректных ответов.
- Валидируй:
  • age: целое 14..100; опыт не может быть больше возраста.
  • desired_salary: число или диапазон (допустима валюта).
  • languages: язык + уровень (A1..C2/native).
  • даты: YYYY-MM или YYYY-MM-DD.
  • ссылки: начинаются с http(s)://.
- Контакты, должность, зарплату и дату выхода всегда уточняй повторно перед завершением.

Тон: вежливый, деловой. Если ответ бессмысленный — мягко, но настойчиво добивайся корректного значения.

В результате выведи JSON с полями:
"id", "login", "password",
"name", "age", "experience", "region",
"position", "seniority", "must_have_skills",
"nice_to_have_skills", "education",
"desired_salary", "field",
"schedule", "contacts", "relocation",
"portfolio_links", "languages", "courses",
"internships", "projects", "achievements",
"employment_type", "work_format",
"available_from", "work_permit",
"extra_information", "score"

Из этих полей не нужно спрашивать и заполнять следующие: id, login, password.

Если человек захочет остановиться, уточни решение и выведи ТОЛЬКО JSON (все поля присутствуют; пустые → null).
"""

EXIT_WORDS = {"закончить", "давай закончим", "готово", "готов", "finish", "stop", "end"}

def ensure_all_fields(obj: dict) -> dict:

    out = {k: None for k in FIELDS}
    for k, v in (obj or {}).items():
        if k in out:
            out[k] = v
    return out

def extract_json(text: str):

    if not text:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S | re.I)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    m2 = re.search(r"(\{.*\})", text, re.S)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    return None

def main():
    messages = [{"role": "system", "content": system_prompt}]
    print("Ассистент: Привет! Давай начнём создание твоего резюме. Расскажи немного о себе (должность/город/уровень).")

    while True:
        user_input = input("Вы: ").strip()

        if user_input.lower() in EXIT_WORDS:
            messages.append({"role": "user", "content": user_input})
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages + [
                    {"role": "system", "content": "Теперь выведи только JSON без текста, красиво отформатированный."}
                ]
            )
            raw = response.choices[0].message.content.strip()
            parsed = extract_json(raw)
            if not isinstance(parsed, dict):
                parsed = {"error": "не удалось распарсить JSON", "raw": raw}
            profile = ensure_all_fields(parsed)
            print(json.dumps(profile, ensure_ascii=False, indent=2))
            break

        messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        assistant_reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_reply})
        print("Ассистент:", assistant_reply)

if __name__ == "__main__":
    main()
