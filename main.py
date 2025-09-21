import json
import re
import tkinter as t
from tkinter import messagebox
from openai import OpenAI
from fulfiling import seed_all

from db.connections import connect_to_db, load_config, ensure_database_exists
from db.queries import (
    add_row, delete_row, select_row, edit_row,
    add_vacancy, delete_vacancy, select_vacancy, edit_vacancy
)

DB_NAME = load_config().get("database", "t1v7")

hr_login = None
hr_password = None

seeker_login = None
seeker_id = None

client = OpenAI(api_key="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")
AI_MODEL = "gpt-4o-mini"
EXIT_WORDS = {"закончить", "давай закончим", "готово", "готов", "finish", "stop", "end"}

AI_FIELDS = [
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


AI_SYSTEM_PROMPT_CANDIDATE = f"""
Ты умный ассистент по заполнению профиля кандидата.
Обязательные поля: {AI_FIELDS}.
Нормализация: field∈{{{{IT,Finance,Marketing,HR,Logistics}}}}, employment_type∈{{{{Official,Contract,Freelance,Internship}}}},
seniority∈{{{{Junior,Middle,Senior,Lead}}}}, schedule∈{{{{Full-time,Part-time,Flexible,Shift}}}}, education∈{{{{Bachelor's,Master's,PhD,College}}}}.
skills и стеки — массивы строк (англ), region — город (рус, с заглавной), languages — строка через запятую.
Контакты: Telegram username + email, одной строкой.
relocation — true/false/null.
Валидация и вопросы блоками по 2–3. Возраст 14..100, опыт ≤ возраст, salary — число/вилка. Ссылки http/https.
В финале выведи ТОЛЬКО JSON со всеми полями (пустые → null). Не спрашивай id/login/password.
"""


AI_VAC_FIELDS = [
    "login", "password", "region", "position", "field", "seniority",
    "must_have_skills", "nice_to_have_skills", "education", "desired_salary",
    "schedule", "contacts", "relocation", "languages", "employment_type",
    "work_format", "extra_information", "min_age", "max_age",
    "min_experience", "max_experience"
]

AI_SYSTEM_PROMPT_VACANCY = f"""
Ты помощник HR по созданию вакансии. Собери поля: {AI_VAC_FIELDS}.
Нормализация: те же справочники, skills — массивы строк (англ), languages — строка через запятую.
relocation — true/false/null. Возраст/опыт/зарплата — целые числа или null. Проверяй min ≤ max.
Вопросы блоками по 2–3 с подсказками. В финале выведи ТОЛЬКО JSON (пустые → null). login/password можно null — система подставит.
"""

HR_REQ_FIELDS = [
    "field", "employment_type", "experience", "region", "desired_salary",
    "position", "seniority", "must_have_skills", "nice_to_have_skills",
    "education", "schedule", "languages", "relocation"
]

HR_REQ_SYSTEM = f"""
Ты — дружелюбный ассистент для HR-специалиста.
Твоя задача — вести диалог с рекрутером и СОБРАТЬ ТРЕБОВАНИЯ ДЛЯ ПОИСКА КАНДИДАТОВ, а не заполнять профиль.
В результате ты должен вернуть единый JSON с полями: {HR_REQ_FIELDS}.

Основные правила:
- Общайся тепло, подтверждай ответы, предлагай варианты, не спрашивай много вопросов за одно сообщение, ты мужского рода, отвечай понял, а не поняла.
- Спрашивай как HR-ассистент: «Кого ищем?», «Сколько опыта нужно?», «В каком регионе?» и т.п.
- Обязательно уточняй тип оформления: Official / Contract / Freelance / Internship.
- Подсказывай дефолты и озвучивай их.
- Отсеивай нелепые значения.

Нормализация:
- field ∈ {"IT","Finance","Marketing","HR","Logistics"}
- employment_type ∈ {"Official","Contract","Freelance","Internship"}
- seniority ∈ {"Junior","Middle","Senior","Lead"}
- schedule ∈ {"Full-time","Part-time","Flexible","Shift"}
- education ∈ {"Bachelor's","Master's","PhD","College"}
- skills — строки (англ), region — город (рус, с заглавной), languages — строка через запятую
- desired_salary — целое > 0
- relocation — true/false
- nice_to_have_skills — строка (софт-скиллы), must_have_skills — стек (жёсткие навыки)
Все значения по старту null.

Перед «готово» выведи читабельный список на русском, потом попроси подтвердить и при подтверждении верни ТОЛЬКО чистый JSON без ```.
"""

HR_RANK_SYSTEM = """
Режим: ранжирование кандидатов.
Вход:
- requirements (JSON) — параметры вакансии;
- candidates (JSON array) — список кандидатов (поля могут быть шире);
- top_k (int).

Правила:
- Рассчитать score в [0,1] для КАЖДОГО кандидата.
- Отсортировать по убыванию score.
- Вернуть ranked_candidates и top_k_candidates (первые top_k).
- Сравнение region — строгое равенство строк.
- Учитывать: position/field/seniority, must_have_skills, nice_to_have_skills, experience, desired_salary,
  schedule, employment_type, languages, education, region, relocation.
- Не менять структуру кандидатов внутри "candidate".

Верни ТОЛЬКО JSON:
{
  "requirements": { ... },
  "ranked_candidates": [ { "score": 0.92, "reasons": ["..."], "candidate": { ... } } ],
  "top_k_candidates": [ { "score": 0.92, "reasons": ["..."], "candidate": { ... } } ],
  "ranked_list_text": "(можно игнорировать)",
  "top_k": <int>
}
"""

def ensure_database_exists():
    try:
        con = connect_to_db(DB_NAME)
        con.close()
        return
    except Exception:
        try:
            con = connect_to_db("postgres")
            con.autocommit = True
            cur = con.cursor()
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            cur.close()
            con.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать БД '{DB_NAME}':\n{e}")
            raise

def ensure_tables():
    con = connect_to_db(DB_NAME)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id                  SERIAL PRIMARY KEY,
        login               TEXT NOT NULL,
        password            TEXT NOT NULL,
        name                TEXT NULL,
        age                 INT  NULL,
        experience          INT  NULL,
        region              TEXT NULL,
        position            TEXT NULL,
        seniority           TEXT NULL,
        must_have_skills    TEXT NULL,
        nice_to_have_skills TEXT NULL,
        education           TEXT NULL,
        desired_salary      INT  NULL,
        field               TEXT NULL,
        schedule            TEXT NULL,
        contacts            TEXT NULL,
        relocation          BOOLEAN NULL,
        portfolio_links     TEXT NULL,
        languages           TEXT NULL,
        courses             TEXT NULL,
        internships         TEXT NULL,
        projects            TEXT NULL,
        achievements        TEXT NULL,
        employment_type     TEXT NULL,
        work_format         TEXT NULL,
        extra_information   TEXT NULL,
        score               INT  NULL,
        CONSTRAINT cand_field_chk      CHECK (field IS NULL OR field IN ('IT','Finance','Marketing','HR','Logistics')),
        CONSTRAINT cand_emp_chk        CHECK (employment_type IS NULL OR employment_type IN ('Official','Contract','Freelance','Internship')),
        CONSTRAINT cand_seniority_chk  CHECK (seniority IS NULL OR seniority IN ('Junior','Middle','Senior','Lead')),
        CONSTRAINT cand_schedule_chk   CHECK (schedule IS NULL OR schedule IN ('Full-time','Part-time','Flexible','Shift')),
        CONSTRAINT cand_education_chk  CHECK (education IS NULL OR education IN ('Bachelor''s','Master''s','PhD','College'))
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vacancies (
        id                  SERIAL PRIMARY KEY,
        login               TEXT NOT NULL,
        password            TEXT NOT NULL,
        region              TEXT NULL,
        position            TEXT NULL,
        field               TEXT NULL,
        seniority           TEXT NULL,
        must_have_skills    TEXT NULL,
        nice_to_have_skills TEXT NULL,
        education           TEXT NULL,
        desired_salary      INT  NULL,
        schedule            TEXT NULL,
        contacts            TEXT NULL,
        relocation          BOOLEAN NULL,
        languages           TEXT NULL,
        employment_type     TEXT NULL,
        work_format         TEXT NULL,
        extra_information   TEXT NULL,
        min_age             INT  NULL,
        max_age             INT  NULL,
        min_experience      INT  NULL,
        max_experience      INT  NULL,
        CONSTRAINT vac_field_chk      CHECK (field IS NULL OR field IN ('IT','Finance','Marketing','HR','Logistics')),
        CONSTRAINT vac_emp_chk        CHECK (employment_type IS NULL OR employment_type IN ('Official','Contract','Freelance','Internship')),
        CONSTRAINT vac_seniority_chk  CHECK (seniority IS NULL OR seniority IN ('Junior','Middle','Senior','Lead')),
        CONSTRAINT vac_schedule_chk   CHECK (schedule IS NULL OR schedule IN ('Full-time','Part-time','Flexible','Shift')),
        CONSTRAINT vac_education_chk  CHECK (education IS NULL OR education IN ('Bachelor''s','Master''s','PhD','College'))
    );
    """)

    con.commit()
    cur.close()
    con.close()

def _to_int_or_none(s):
    try:
        s = str(s).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None

def _to_bool_or_none(s):
    if s is None:
        return None
    s = str(s).strip().lower()
    if s == "":
        return None
    return s in ("true", "1", "t", "yes", "y", "да")

def _join_if_list(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return v

def _extract_json(text: str):

    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S | re.I)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    m2 = re.search(r"(\{.*\})", text, re.S)
    if m2:
        try: return json.loads(m2.group(1))
        except: pass
    try:
        return json.loads(text)
    except:
        return None

def fetch_all_candidates_as_json():
    cols = [
        "id","login","name","age","experience","region","position","seniority",
        "must_have_skills","nice_to_have_skills","education","desired_salary",
        "field","schedule","contacts","relocation","languages","employment_type",
        "work_format"
    ]
    rows = []
    try:
        con = connect_to_db(DB_NAME); cur = con.cursor()
        cur.execute(f"SELECT {', '.join(cols)} FROM candidates ORDER BY id ASC")
        data = cur.fetchall()
        cur.close(); con.close()
        for r in data:
            row = {}
            for i, c in enumerate(cols):
                row[c] = r[i]
            rows.append(row)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить кандидатов:\n{e}")
    return rows

def candidates_window(parent, role: str):
    parent.withdraw()
    cw = t.Toplevel(parent)
    cw.title("Candidates")

    frame = t.Frame(cw)
    frame.pack(pady=8)

    headers_admin = [
        "id","login*","password*","name","age","experience","region","position",
        "seniority","must_have_skills","nice_to_have_skills","education","desired_salary",
        "field","schedule","contacts","relocation","portfolio_links","languages","courses",
        "internships","projects","achievements","employment_type","work_format",
        "extra_information","score"
    ]
    headers_hr = [
        "id","login*","password*","name","age","experience","region","position",
        "seniority","education","desired_salary","field","schedule","contacts",
        "relocation","languages","employment_type","work_format","extra_information","score"
    ]
    headers = headers_admin if role == 'admin' else headers_hr
    for i, h in enumerate(headers):
        t.Label(frame, text=h).grid(row=0, column=i, padx=4)

    e = [t.Entry(frame) for _ in range(27)]
    for i, w in enumerate(e):
        w.grid(row=1, column=i, padx=4)

    def collect_all():
        return [x.get() for x in e]

    btns = t.Frame(cw)
    btns.pack(pady=6)
    if role == 'admin':
        t.Button(btns, text="insert", command=lambda: add_row(DB_NAME, *collect_all())).pack(side="left", padx=4)
        t.Button(btns, text="delete", command=lambda: delete_row(DB_NAME, *collect_all())).pack(side="left", padx=4)
        t.Button(btns, text="edit",   command=lambda: edit_row(DB_NAME, *collect_all())).pack(side="left", padx=4)
    t.Button(btns, text="select", command=lambda: select_row(DB_NAME, *collect_all())).pack(side="left", padx=4)

    def back():
        cw.destroy()
        parent.deiconify()
    t.Button(cw, text="Назад", command=back).pack(pady=4)
    cw.protocol("WM_DELETE_WINDOW", back)

def vacancies_window(parent, role: str):
    parent.withdraw()
    vw = t.Toplevel(parent)
    vw.title("Vacancies")

    frame = t.Frame(vw)
    frame.pack(pady=8)

    headers = [
        "position","field","region",
        "min_age","max_age","min_experience","max_experience",
        "seniority","must_have_skills","nice_to_have_skills","education","desired_salary",
        "schedule","contacts","relocation","languages","employment_type","work_format",
        "extra_information","login","password"
    ]
    for i, h in enumerate(headers):
        t.Label(frame, text=h).grid(row=0, column=i, padx=4)

    widgets = [t.Entry(frame) for _ in headers]
    for i, w in enumerate(widgets):
        w.grid(row=1, column=i, padx=4)

    def vals():
        return [w.get() for w in widgets]

    filt = t.Frame(vw)
    filt.pack(pady=6)
    t.Label(filt, text="position").grid(row=0, column=0); q_pos = t.Entry(filt); q_pos.grid(row=0, column=1, padx=4)
    t.Label(filt, text="field").grid(row=0, column=2); q_field = t.Entry(filt); q_field.grid(row=0, column=3, padx=4)
    t.Label(filt, text="region").grid(row=0, column=4); q_reg = t.Entry(filt); q_reg.grid(row=0, column=5, padx=4)
    t.Label(filt, text="min_age").grid(row=1, column=0); q_minage = t.Entry(filt, width=8); q_minage.grid(row=1, column=1)
    t.Label(filt, text="max_age").grid(row=1, column=2); q_maxage = t.Entry(filt, width=8); q_maxage.grid(row=1, column=3)
    t.Label(filt, text="min_exp").grid(row=1, column=4); q_minexp = t.Entry(filt, width=8); q_minexp.grid(row=1, column=5)
    t.Label(filt, text="max_exp").grid(row=1, column=6); q_maxexp = t.Entry(filt, width=8); q_maxexp.grid(row=1, column=7)
    t.Label(filt, text="min_salary").grid(row=1, column=8); q_minsal = t.Entry(filt, width=10); q_minsal.grid(row=1, column=9)
    t.Label(filt, text="seniority").grid(row=1, column=10); q_sen = t.Entry(filt, width=10); q_sen.grid(row=1, column=11)
    t.Label(filt, text="education").grid(row=1, column=12); q_edu = t.Entry(filt, width=10); q_edu.grid(row=1, column=13)
    t.Label(filt, text="schedule").grid(row=1, column=14); q_sch = t.Entry(filt, width=10); q_sch.grid(row=1, column=15)
    t.Label(filt, text="relocation").grid(row=1, column=16); q_reloc = t.Entry(filt, width=8); q_reloc.grid(row=1, column=17)

    btns = t.Frame(vw)
    btns.pack(pady=6)
    if role == 'admin':
        t.Button(btns, text="insert", command=lambda: add_vacancy(DB_NAME, *vals())).pack(side="left", padx=4)
        t.Button(btns, text="delete", command=lambda: delete_vacancy(DB_NAME, *vals())).pack(side="left", padx=4)
        t.Button(btns, text="edit",   command=lambda: edit_vacancy(DB_NAME, *vals())).pack(side="left", padx=4)
    t.Button(btns, text="select", command=lambda: select_vacancy(
        DB_NAME,
        position=q_pos.get(), field=q_field.get(), region=q_reg.get(),
        min_age=q_minage.get(), max_age=q_maxage.get(),
        min_experience=q_minexp.get(), max_experience=q_maxexp.get(),
        min_salary=q_minsal.get(), education=q_edu.get(), schedule=q_sch.get(),
        seniority=q_sen.get(), relocation=q_reloc.get(),
        login=(hr_login if role != 'admin' and hr_login else None)
    )).pack(side="left", padx=4)

    def back():
        vw.destroy()
        parent.deiconify()
    t.Button(vw, text="Назад", command=back).pack(pady=4)
    vw.protocol("WM_DELETE_WINDOW", back)

def admin_panel(root):
    ap = t.Toplevel(root)
    ap.title("Admin")
    t.Button(ap, text="Кандидаты (CRUD)", command=lambda: candidates_window(ap, 'admin')).pack(pady=8, padx=10)
    t.Button(ap, text="Вакансии (CRUD)",  command=lambda: vacancies_window(ap, 'admin')).pack(pady=8, padx=10)
    ap.protocol("WM_DELETE_WINDOW", lambda: (ap.destroy(), root.deiconify()))

def hr_login_then_panel(root):
    login_win = t.Toplevel(root)
    login_win.title("Вход HR")

    t.Label(login_win, text="Логин").grid(row=0, column=0, padx=8, pady=6)
    t.Label(login_win, text="Пароль").grid(row=1, column=0, padx=8, pady=6)

    e_login = t.Entry(login_win); e_login.grid(row=0, column=1, padx=8, pady=6)
    e_pass  = t.Entry(login_win, show="*"); e_pass.grid(row=1, column=1, padx=8, pady=6)

    def proceed():
        global hr_login, hr_password
        login = e_login.get().strip()
        pwd   = e_pass.get().strip()
        if not login or not pwd:
            messagebox.showerror("Ошибка", "Введите логин и пароль")
            return
        hr_login, hr_password = login, pwd
        login_win.destroy()
        hr_panel(root)

    t.Button(login_win, text="Войти", command=proceed).grid(row=2, column=0, columnspan=2, pady=10)
    login_win.protocol("WM_DELETE_WINDOW", lambda: (login_win.destroy(), root.deiconify()))

def hr_panel(root):
    hp = t.Toplevel(root)
    hp.title("HR панель")
    t.Button(hp, text="Мои вакансии (просмотр/ред.)", width=28, command=lambda: hr_my_vacancies_window(hp)).pack(pady=8)
    t.Button(hp, text="Поиск кандидатов (ручной)", width=28, command=lambda: candidates_window(hp, 'hr')).pack(pady=8)
    t.Button(hp, text="Создать вакансию вручную", width=28, command=lambda: create_vacancy_window(hp)).pack(pady=8)
    t.Button(hp, text="Создать вакансию с ИИ", width=28, command=lambda: hr_ai_vacancy_chat(hp)).pack(pady=8)
    # НОВОЕ:
    t.Button(hp, text="Интеллектуальный поиск кандидатов (ИИ)", width=28, command=lambda: hr_ai_candidates_search(hp)).pack(pady=8)
    hp.protocol("WM_DELETE_WINDOW", lambda: (hp.destroy(), root.deiconify()))

def show_my_vacancies():
    if not hr_login:
        messagebox.showerror("Ошибка", "HR не авторизован")
        return
    select_vacancy(DB_NAME, login=hr_login)

def create_vacancy_window(parent):
    if not hr_login or not hr_password:
        messagebox.showerror("Ошибка", "HR не авторизован")
        return

    cv = t.Toplevel(parent)
    cv.title("Создать вакансию")

    labels = [
        "position*","field","region",
        "min_age","max_age","min_experience","max_experience",
        "seniority","must_have_skills","nice_to_have_skills","education","desired_salary",
        "schedule","contacts","relocation(true/false/пусто)","languages","employment_type","work_format",
        "extra_information","login(HR)","password(HR)"
    ]
    hints = [
        "Backend Developer","IT/Finance/Marketing/HR/Logistics","Город",
        "18","65","1","10",
        "Junior/Middle/Senior/Lead","Python, SQL","Docker, Kubernetes","Bachelor's/...","200000",
        "Full-time/...","телефон/e-mail","true/false или пусто","Русский, Английский",
        "Official/...","Remote/Office/Hybrid","свободный текст","",""
    ]
    entries = []
    for i, (lab, ph) in enumerate(zip(labels, hints)):
        t.Label(cv, text=lab).grid(row=i, column=0, sticky="e", padx=6, pady=3)
        e = t.Entry(cv, width=44); e.grid(row=i, column=1, padx=6, pady=3)
        if ph:
            e.insert(0, ph)
        entries.append(e)

    entries[-2].insert(0, hr_login); entries[-1].insert(0, hr_password)
    entries[-2].config(state="disabled"); entries[-1].config(state="disabled")

    tip = t.Label(cv, fg="#666", justify="left",
                  text=("Подсказки:\n"
                        "• Навыки/языки — через запятую.\n"
                        "• Возраст/опыт — числа; можно пустыми.\n"
                        "• Поля field/education/schedule/seniority/employment_type — придерживайся вариантов."))
    tip.grid(row=len(labels), column=0, columnspan=2, padx=6, pady=6, sticky="w")

    def on_create():
        vals = [e.get().strip() for e in entries]
        if not vals[0]:
            messagebox.showerror("Ошибка", "position обязателен")
            return
        add_vacancy(DB_NAME, *vals)
        cv.destroy()
        hr_my_vacancies_window(parent)

    t.Button(cv, text="Создать", command=on_create).grid(row=len(labels)+1, column=0, columnspan=2, pady=10)

def hr_my_vacancies_window(parent):
    if not hr_login:
        messagebox.showerror("Ошибка", "HR не авторизован")
        return
    mw = t.Toplevel(parent)
    mw.title("Мои вакансии")

    lst = t.Listbox(mw, width=80, height=20)
    lst.pack(side="left", fill="both", expand=True, padx=6, pady=6)
    sb = t.Scrollbar(mw, command=lst.yview); sb.pack(side="right", fill="y")
    lst.config(yscrollcommand=sb.set)

    data = []
    try:
        con = connect_to_db(DB_NAME); cur = con.cursor()
        cur.execute("""
            SELECT id, position, region, field, seniority, desired_salary
            FROM vacancies
            WHERE login=%s
            ORDER BY id DESC
        """, (hr_login,))
        data = cur.fetchall()
        cur.close(); con.close()
    except Exception as e:
        messagebox.showerror("Ошибка", str(e)); mw.destroy(); return

    for r in data:
        vid, pos, reg, fld, sen, sal = r
        lst.insert("end", f"#{vid} | {pos or '-'} | {reg or '-'} | {fld or '-'} | {sen or '-'} | {sal or '-'}")

    def open_selected():
        i = lst.curselection()
        if not i:
            return
        idx = i[0]
        vacancy_id = data[idx][0]
        vacancy_view_window(mw, vacancy_id, editable=True)

    t.Button(mw, text="Открыть", command=open_selected).pack(pady=6)

def vacancy_view_window(parent, vacancy_id: int, editable: bool):
    try:
        con = connect_to_db(DB_NAME); cur = con.cursor()
        cur.execute("""
            SELECT id, login, password, region, position, field, seniority,
                   must_have_skills, nice_to_have_skills, education, desired_salary,
                   schedule, contacts, relocation, languages, employment_type, work_format,
                   extra_information, min_age, max_age, min_experience, max_experience
            FROM vacancies WHERE id=%s
        """, (vacancy_id,))
        row = cur.fetchone(); cur.close(); con.close()
        if not row:
            messagebox.showerror("Ошибка", "Вакансия не найдена"); return
    except Exception as e:
        messagebox.showerror("Ошибка", str(e)); return

    vw = t.Toplevel(parent); vw.title(f"Вакансия #{vacancy_id}")

    fields = [
        ("login", 1), ("password", 2), ("region", 3), ("position", 4), ("field", 5),
        ("seniority", 6), ("must_have_skills", 7), ("nice_to_have_skills", 8),
        ("education", 9), ("desired_salary",10), ("schedule",11), ("contacts",12),
        ("relocation",13), ("languages",14), ("employment_type",15), ("work_format",16),
        ("extra_information",17), ("min_age",18), ("max_age",19),
        ("min_experience",20), ("max_experience",21)
    ]
    entries = []
    for i, (name, idx) in enumerate(fields):
        t.Label(vw, text=name).grid(row=i, column=0, sticky="e", padx=6, pady=3)
        e = t.Entry(vw, width=48); e.grid(row=i, column=1, padx=6, pady=3)
        val = row[idx]; e.insert(0, "" if val is None else str(val))
        if not editable or (name in ("login", "password") and hr_login != row[1]):
            e.config(state="disabled")
        entries.append((name, e))

    def on_save():
        if not editable:
            vw.destroy(); return
        if hr_login != row[1]:
            messagebox.showerror("Ошибка", "Можно редактировать только свои вакансии"); return

        vals = {name: ent.get().strip() for name, ent in entries}
        try:
            con2 = connect_to_db(DB_NAME); cur2 = con2.cursor()
            cur2.execute("""
                UPDATE vacancies SET
                    region=%s, position=%s, field=%s, seniority=%s,
                    must_have_skills=%s, nice_to_have_skills=%s, education=%s, desired_salary=%s,
                    schedule=%s, contacts=%s, relocation=%s, languages=%s, employment_type=%s,
                    work_format=%s, extra_information=%s,
                    min_age=%s, max_age=%s, min_experience=%s, max_experience=%s
                WHERE id=%s AND login=%s
            """, (
                vals["region"] or None, vals["position"] or None, vals["field"] or None, vals["seniority"] or None,
                vals["must_have_skills"] or None, vals["nice_to_have_skills"] or None, vals["education"] or None, _to_int_or_none(vals["desired_salary"]),
                vals["schedule"] or None, vals["contacts"] or None, _to_bool_or_none(vals["relocation"]), vals["languages"] or None, vals["employment_type"] or None,
                vals["work_format"] or None, vals["extra_information"] or None,
                _to_int_or_none(vals["min_age"]), _to_int_or_none(vals["max_age"]), _to_int_or_none(vals["min_experience"]), _to_int_or_none(vals["max_experience"]),
                vacancy_id, hr_login
            ))
            con2.commit(); cur2.close(); con2.close()
            messagebox.showinfo("OK", "Сохранено"); vw.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    t.Button(vw, text="Сохранить" if editable else "Закрыть", command=on_save).grid(row=len(fields), column=0, columnspan=2, pady=10)

def seeker_or_admin_login(root):
    login_win = t.Toplevel(root)
    login_win.title("Вход")

    t.Label(login_win, text="Логин").grid(row=0, column=0, padx=8, pady=6)
    t.Label(login_win, text="Пароль").grid(row=1, column=0, padx=8, pady=6)

    e_login = t.Entry(login_win); e_login.grid(row=0, column=1, padx=8, pady=6)
    e_pass  = t.Entry(login_win, show="*"); e_pass.grid(row=1, column=1, padx=8, pady=6)

    def try_login():
        global seeker_login, seeker_id
        login = e_login.get().strip()
        pwd   = e_pass.get().strip()
        if not login or not pwd:
            messagebox.showerror("Ошибка", "Введите логин и пароль")
            return

        # Админ
        if login == "admin" and pwd == "admin":
            login_win.destroy()
            admin_panel(root)
            return

        # Кандидат
        try:
            con = connect_to_db(DB_NAME)
            cur = con.cursor()
            cur.execute("SELECT id, password FROM candidates WHERE login=%s LIMIT 1", (login,))
            row = cur.fetchone()

            if row is None:
                cur.execute("""
                    INSERT INTO candidates (login, password, name)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (login, pwd, login))
                seeker_id = cur.fetchone()[0]
                con.commit()
                seeker_login = login
                ok = True
            else:
                seeker_id = row[0]
                seeker_login = login
                ok = (row[1] == pwd)

            cur.close(); con.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Проблема с подключением к базе:\n{e}")
            return

        if ok:
            login_win.destroy()
            seeker_panel(root)
        else:
            messagebox.showerror("Ошибка", "Неверный пароль")

    t.Button(login_win, text="Войти", command=try_login).grid(row=2, column=0, columnspan=2, pady=10)
    login_win.protocol("WM_DELETE_WINDOW", lambda: (login_win.destroy(), root.deiconify()))

def seeker_panel(root):
    sp = t.Toplevel(root)
    sp.title("Панель кандидата")

    t.Button(sp, text="Заполнить резюме с ИИ", width=24, command=lambda: seeker_ai_chat(sp)).pack(pady=8)
    t.Button(sp, text="Резюме (ручное)", width=24, command=lambda: seeker_resume_window(sp)).pack(pady=8)
    t.Button(sp, text="Поиск вакансий ручной", width=24, command=lambda: vacancies_window(sp, 'seeker')).pack(pady=8)
    t.Button(sp, text="Поиск вакансий с ИИ", width=24, command=lambda: seeker_ai_vacancies_search(sp)).pack(pady=8)

    sp.protocol("WM_DELETE_WINDOW", lambda: (sp.destroy(), root.deiconify()))

def seeker_resume_window(parent):
    if not seeker_login or seeker_id is None:
        messagebox.showerror("Ошибка", "Кандидат не авторизован")
        return
    try:
        con = connect_to_db(DB_NAME)
        cur = con.cursor()
        cur.execute("""
            SELECT name, age, experience, region, position, seniority, education,
                   desired_salary, field, schedule, contacts, relocation, languages,
                   courses, internships, projects, achievements, employment_type,
                   work_format, extra_information, score
            FROM candidates WHERE id=%s
        """, (seeker_id,))
        row = cur.fetchone()
        cur.close(); con.close()
        if row is None:
            messagebox.showerror("Ошибка", "Профиль не найден")
            return
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))
        return

    rw = t.Toplevel(parent)
    rw.title("Моё резюме")

    labels = [
        "Имя","Возраст","Опыт (лет)","Регион","Позиция","Грейд","Образование",
        "Желаемая з/п","Сфера","График","Контакты","Релокация (true/false)",
        "Языки","Курсы","Стажировки","Проекты","Достижения","Тип занятости",
        "Формат работы","Доп. инфо","Скор"
    ]
    entries = []
    for i, lab in enumerate(labels):
        t.Label(rw, text=lab).grid(row=i, column=0, sticky="e", padx=6, pady=3)
        e = t.Entry(rw, width=44)
        e.grid(row=i, column=1, padx=6, pady=3)
        val = row[i]
        e.insert(0, "" if val is None else str(val))
        entries.append(e)

    def on_save():
        v = [e.get().strip() for e in entries]
        try:
            con2 = connect_to_db(DB_NAME)
            cur2 = con2.cursor()
            cur2.execute("""
                UPDATE candidates SET
                    name=%s, age=%s, experience=%s, region=%s, position=%s, seniority=%s,
                    education=%s, desired_salary=%s, field=%s, schedule=%s, contacts=%s,
                    relocation=%s, languages=%s, courses=%s, internships=%s, projects=%s,
                    achievements=%s, employment_type=%s, work_format=%s, extra_information=%s, score=%s
                WHERE id=%s
            """, (
                (v[0] or seeker_login),
                _to_int_or_none(v[1]), _to_int_or_none(v[2]),
                (v[3] or None), (v[4] or None), (v[5] or None),
                (v[6] or None), _to_int_or_none(v[7]),
                (v[8] or None), (v[9] or None), (v[10] or None),
                _to_bool_or_none(v[11]),
                (v[12] or None), (v[13] or None), (v[14] or None), (v[15] or None),
                (v[16] or None), (v[17] or None), (v[18] or None), (v[19] or None),
                _to_int_or_none(v[20]), seeker_id
            ))
            con2.commit()
            cur2.close(); con2.close()
            messagebox.showinfo("OK", "Резюме сохранено")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    t.Button(rw, text="Сохранить", command=on_save).grid(row=len(labels), column=0, columnspan=2, pady=10)

def seeker_ai_chat(parent):
    if not seeker_login or seeker_id is None:
        messagebox.showerror("Ошибка", "Кандидат не авторизован")
        return

    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT_CANDIDATE}]

    cw = t.Toplevel(parent)
    cw.title("Заполнение резюме с ИИ")
    cw.geometry("720x540")

    history = t.Text(cw, state="disabled", wrap="word", bg="#1f1f1f", fg="#eaeaea")
    history.pack(fill="both", expand=True, padx=8, pady=8)

    entry = t.Entry(cw)
    entry.pack(fill="x", padx=8, pady=6)

    def append(role, content):
        history.config(state="normal")
        prefix = "Вы: " if role == "user" else "ИИ: "
        history.insert("end", f"{prefix}{content}\n\n")
        history.see("end")
        history.config(state="disabled")

    def save_ai_profile_to_db(profile: dict):
        for k in ("must_have_skills", "nice_to_have_skills", "languages"):
            profile[k] = _join_if_list(profile.get(k))
        try:
            con = connect_to_db(DB_NAME); cur = con.cursor()
            cur.execute("""
                UPDATE candidates SET
                    name=%s, age=%s, experience=%s, region=%s, position=%s, seniority=%s,
                    must_have_skills=%s, nice_to_have_skills=%s, education=%s, desired_salary=%s,
                    field=%s, schedule=%s, contacts=%s, relocation=%s, portfolio_links=%s,
                    languages=%s, courses=%s, internships=%s, projects=%s, achievements=%s,
                    employment_type=%s, work_format=%s, extra_information=%s, score=%s
                WHERE id=%s
            """, (
                profile.get("name") or seeker_login,
                _to_int_or_none(profile.get("age")),
                _to_int_or_none(profile.get("experience")),
                (profile.get("region") or None),
                (profile.get("position") or None),
                (profile.get("seniority") or None),
                (profile.get("must_have_skills") or None),
                (profile.get("nice_to_have_skills") or None),
                (profile.get("education") or None),
                _to_int_or_none(profile.get("desired_salary")),
                (profile.get("field") or None),
                (profile.get("schedule") or None),
                (profile.get("contacts") or None),
                _to_bool_or_none(profile.get("relocation")),
                (profile.get("portfolio_links") or None),
                (profile.get("languages") or None),
                (profile.get("courses") or None),
                (profile.get("internships") or None),
                (profile.get("projects") or None),
                (profile.get("achievements") or None),
                (profile.get("employment_type") or None),
                (profile.get("work_format") or None),
                (profile.get("extra_information") or None),
                _to_int_or_none(profile.get("score")),
                seeker_id
            ))
            con.commit(); cur.close(); con.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить профиль:\n{e}")
            return False
        return True

    def finish_if_json(reply_text: str):
        profile = _extract_json(reply_text)
        if isinstance(profile, dict):
            ok = save_ai_profile_to_db(profile)
            if ok:
                cw.destroy()
                vacancies_window(parent, "seeker")
            return True
        return False

    def send():
        user_input = entry.get().strip()
        if not user_input:
            return
        entry.delete(0, "end")
        append("user", user_input)
        messages.append({"role": "user", "content": user_input})

        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            messagebox.showerror("Ошибка ИИ", str(e))
            return

        append("assistant", reply)
        messages.append({"role": "assistant", "content": reply})

        if user_input.lower() in EXIT_WORDS:
            try:
                resp2 = client.chat.completions.create(
                    model=AI_MODEL,
                    messages=messages + [{"role": "system", "content": "Теперь выведи только JSON без текста, красиво отформатированный."}]
                )
                only_json = resp2.choices[0].message.content.strip()
                if finish_if_json(only_json):
                    return
            except Exception as e:
                messagebox.showerror("Ошибка ИИ", str(e))
                return

        finish_if_json(reply)

    append("assistant", "Привет! Давай начнём. Расскажи кратко: должность / город / грейд.")
    t.Button(cw, text="Отправить", command=send).pack(pady=6)
    entry.bind("<Return>", lambda _: send())

def hr_ai_vacancy_chat(parent):
    if not hr_login or not hr_password:
        messagebox.showerror("Ошибка", "HR не авторизован")
        return

    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT_VACANCY}]

    cw = t.Toplevel(parent); cw.title("Создание вакансии с ИИ"); cw.geometry("720x540")
    history = t.Text(cw, state="disabled", wrap="word", bg="#1f1f1f", fg="#eaeaea"); history.pack(fill="both", expand=True, padx=8, pady=8)
    entry = t.Entry(cw); entry.pack(fill="x", padx=8, pady=6)

    def append(role, content):
        history.config(state="normal")
        prefix = "Вы: " if role == "user" else "ИИ: "
        history.insert("end", f"{prefix}{content}\n\n")
        history.see("end")
        history.config(state="disabled")

    def insert_vacancy_and_open(vac: dict):
        vac["must_have_skills"]  = _join_if_list(vac.get("must_have_skills"))
        vac["nice_to_have_skills"] = _join_if_list(vac.get("nice_to_have_skills"))
        vac["languages"] = _join_if_list(vac.get("languages"))
        login = vac.get("login") or hr_login
        password = vac.get("password") or hr_password

        try:
            con = connect_to_db(DB_NAME); cur = con.cursor()
            cur.execute("""
                INSERT INTO vacancies (
                    login, password, region, position, field, seniority,
                    must_have_skills, nice_to_have_skills, education, desired_salary,
                    schedule, contacts, relocation, languages, employment_type, work_format,
                    extra_information, min_age, max_age, min_experience, max_experience
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s
                )
                RETURNING id
            """, (
                login, password,
                (vac.get("region") or None),
                (vac.get("position") or None),
                (vac.get("field") or None),
                (vac.get("seniority") or None),
                (vac.get("must_have_skills") or None),
                (vac.get("nice_to_have_skills") or None),
                (vac.get("education") or None),
                _to_int_or_none(vac.get("desired_salary")),
                (vac.get("schedule") or None),
                (vac.get("contacts") or None),
                _to_bool_or_none(vac.get("relocation")),
                (vac.get("languages") or None),
                (vac.get("employment_type") or None),
                (vac.get("work_format") or None),
                (vac.get("extra_information") or None),
                _to_int_or_none(vac.get("min_age")), _to_int_or_none(vac.get("max_age")),
                _to_int_or_none(vac.get("min_experience")), _to_int_or_none(vac.get("max_experience"))
            ))
            new_id = cur.fetchone()[0]
            con.commit(); cur.close(); con.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить вакансию:\n{e}")
            return

        cw.destroy()
        vacancy_view_window(parent, new_id, editable=True)

    def finish_if_json(reply_text: str):
        vac = _extract_json(reply_text)
        if isinstance(vac, dict):
            insert_vacancy_and_open(vac)
            return True
        return False

    def send():
        user_input = entry.get().strip()
        if not user_input:
            return
        entry.delete(0, "end")
        append("user", user_input)
        messages.append({"role": "user", "content": user_input})

        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            messagebox.showerror("Ошибка ИИ", str(e)); return

        append("assistant", reply)
        messages.append({"role": "assistant", "content": reply})

        if user_input.lower() in EXIT_WORDS:
            try:
                resp2 = client.chat.completions.create(
                    model=AI_MODEL,
                    messages=messages + [{"role": "system", "content": "Теперь выведи только JSON без текста, красиво отформатированный."}]
                )
                only_json = resp2.choices[0].message.content.strip()
                if finish_if_json(only_json): return
            except Exception as e:
                messagebox.showerror("Ошибка ИИ", str(e)); return

        finish_if_json(reply)

    append("assistant", "Ок, давайте опишем вакансию. Сначала: позиция, регион и сфера (IT/Finance/Marketing/HR/Logistics).")
    t.Button(cw, text="Отправить", command=send).pack(pady=6)
    entry.bind("<Return>", lambda _: send())

def fetch_all_vacancies_as_json():
    """Возвращает список словарей-вакансий из БД (для ИИ-ранжирования)."""
    cols = [
        "id","login","region","position","field","seniority",
        "must_have_skills","nice_to_have_skills","education","desired_salary",
        "schedule","contacts","relocation","languages","employment_type",
        "work_format","extra_information","min_age","max_age",
        "min_experience","max_experience"
    ]
    rows = []
    try:
        con = connect_to_db(DB_NAME); cur = con.cursor()
        cur.execute(f"SELECT {', '.join(cols)} FROM vacancies ORDER BY id ASC")
        data = cur.fetchall()
        cur.close(); con.close()
        for r in data:
            item = {}
            for i, c in enumerate(cols):
                item[c] = r[i]
            rows.append(item)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить вакансии:\n{e}")
    return rows

def seeker_ai_vacancies_search(parent):
    """
    Интеллектуальный ПОИСК ВАКАНСИЙ для кандидата:
    - свободный чат (без JSON), кандидат описывает «работу мечты» как хочет
    - ассистент подтверждает, советует, что уточнить (3–6 пунктов)
    - кандидат может написать «покажи топ-7» и т.п. (запомним top_k)
    - по «готово» ассистент выводит в ЭТОМ ЖЕ ЧАТЕ список топ-N вакансий
    """
    if not seeker_login or seeker_id is None:
        messagebox.showerror("Ошибка", "Кандидат не авторизован"); return

    SYSTEM = """
Ты — вежливый карьерный ассистент. Общайся естественно, по-человечески.
Пользователь — кандидат. Он в свободной форме описывает, какую работу хочет:
позиция/роль, стек, грейд, опыт, регион, бюджет, график, формат (офис/удалёнка), готовность к релокации, языки, желательная сфера.
Твоя тактика:
  • Коротко подтверждай понимание.
  • Дай 3–6 точечных рекомендаций, что ещё стоит уточнить.
  • Не предлагай меню и не проси «выбрать из списка» (Junior/Middle…): спрашивай естественно.
  • Не говори о JSON и служебных форматах.
Когда кандидат напишет «готово», подведи итог и выведи список найденных вакансий в чате.
Формат для каждой вакансии:
1) <Название/позиция> (id=..., регион)
   Сфера/грейд: ...
   Зарплата: ...
   Навыки (must): ...
   Навыки (nice): ...
   Score: 0.xx
Выводи максимум top_k (если человек не указал — 10).
"""

    messages = [{"role": "system", "content": SYSTEM}]
    desired_top_k = 10  # можно менять словами "покажи топ-7" и т.п.

    win = t.Toplevel(parent); win.title("ИИ-поиск вакансий"); win.geometry("820x580")
    history = t.Text(win, state="disabled", wrap="word", bg="#1f1f1f", fg="#eaeaea")
    history.pack(fill="both", expand=True, padx=8, pady=8)
    entry = t.Entry(win); entry.pack(fill="x", padx=8, pady=6)

    def append(role, content):
        history.config(state="normal")
        prefix = "Вы: " if role == "user" else "ИИ: "
        history.insert("end", f"{prefix}{content}\n\n")
        history.see("end")
        history.config(state="disabled")

    def parse_top_k(text: str):
        import re
        m = re.search(r"(?:топ|top|покажи|хочу)\s*[- ]?\s*(\d{1,3})", text.lower())
        if m:
            try:
                k = int(m.group(1))
                if 1 <= k <= 100: return k
            except: pass
        return None

    def fetch_vacancies():
        return fetch_all_vacancies_as_json()

    def rank_and_show(user_need_text: str, top_k: int):
        vac_list = fetch_vacancies()

        rank_messages = [
            {"role": "system", "content": """
Ты — ассистент кандидата. У тебя есть его «запрос мечты» и список вакансий.
Задача: выбрать наиболее релевантные вакансии и вывести их КРАСИВО в чат.
Для оценки учитывай: позиция/роль, стек (must/nice), грейд, опыт, регион,
зарплата, график, формат, язык, сфера, возраст/опытные ограничения.
Формат каждой вакансии:
1) <position> (id=..., регион)
   Сфера/грейд: <field>/<seniority>   |   График/формат: <schedule>/<work_format>
   Зарплата: <desired_salary>
   Навыки (must): <must_have_skills>
   Навыки (nice): <nice_to_have_skills>
   Прочее: <employment_type>, релокация: <relocation>, языки: <languages>
   Score: 0.xx
Покажи только top_k лучших по убыванию score. Никаких JSON и служебных пояснений.
"""},
            {"role": "user", "content": f"Запрос кандидата: {user_need_text}"},
            {"role": "user", "content": f"Список вакансий:\n{json.dumps(vac_list, ensure_ascii=False)}"},
            {"role": "user", "content": f"top_k = {top_k}"}
        ]

        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=rank_messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"Ошибка при поиске вакансий: {e}"

        append("assistant", reply)

    def send():
        nonlocal desired_top_k
        user_input = entry.get().strip()
        if not user_input: return
        entry.delete(0, "end")
        append("user", user_input)
        messages.append({"role": "user", "content": user_input})

        maybe_k = parse_top_k(user_input)
        if maybe_k is not None:
            desired_top_k = maybe_k

        if user_input.lower() in EXIT_WORDS or user_input.lower() in ["готово", "всё", "закончить"]:
            whole_need = " ".join(m["content"] for m in messages if m["role"] == "user")
            rank_and_show(whole_need, top_k=desired_top_k)
            return

        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"Ошибка ИИ: {e}"

        if maybe_k is not None:
            reply += f"\n\nПонял. Покажу ТОП-{desired_top_k} релевантных вакансий."

        append("assistant", reply)
        messages.append({"role": "assistant", "content": reply})

    append("assistant", "Опишите максимально подробно, какую работу вы хотите: позиция/роль, стек, опыт, регион, вилка зарплаты, график, формат, релокация, языки, сфера и т.п. Когда будете готовы — напишите «готово». Если хотите ограничить выдачу, добавьте: «покажи топ-7».")
    t.Button(win, text="Отправить", command=send).pack(pady=6)
    entry.bind("<Return>", lambda _: send())

def hr_ai_candidates_search(parent):
    """
    Интеллектуальный поиск кандидатов для HR:
    - Свободный чат без JSON и служебных вопросов
    - HR описывает кого ищет
    - ИИ даёт рекомендации, что уточнить
    - По 'готово' → ассистент сам выводит в чат список кандидатов (топ-N или все)
    """
    if not hr_login:
        messagebox.showerror("Ошибка", "HR не авторизован"); return

    SYSTEM = """
Ты — виртуальный помощник HR, твоя задача — помочь найти подходящих кандидатов.
Общайся в свободной форме, как человек: подтверждай ответы HR, предлагай, что ещё можно уточнить.
Не задавай вопросы в формате выбора из списка (Lead/Junior и т.п.) — спрашивай естественно.
В конце, когда HR скажет "готово", подведи итог и выведи список найденных кандидатов (как будто ты сам их нашёл).
Формат выдачи: список с краткой информацией (id, имя, позиция, регион, навыки, score).
"""

    messages = [{"role": "system", "content": SYSTEM}]
    cw = t.Toplevel(parent); cw.title("ИИ-поиск кандидатов"); cw.geometry("820x580")

    history = t.Text(cw, state="disabled", wrap="word", bg="#1f1f1f", fg="#eaeaea")
    history.pack(fill="both", expand=True, padx=8, pady=8)
    entry = t.Entry(cw); entry.pack(fill="x", padx=8, pady=6)

    def append(role, content):
        history.config(state="normal")
        prefix = "Вы: " if role == "user" else "ИИ: "
        history.insert("end", f"{prefix}{content}\n\n")
        history.see("end")
        history.config(state="disabled")

    def fetch_candidates():
        return fetch_all_candidates_as_json()

    def rank_and_show(req_text: str, top_k: int = 10):
        cand_list = fetch_candidates()

        rank_messages = [
            {"role": "system", "content": """
Ты — ассистент HR. Сейчас у тебя есть описание вакансии от HR и список кандидатов.
Твоя задача: выбрать наиболее подходящих кандидатов и вывести их в чат списком.
Формат для каждого кандидата:
1) Имя (id=...) — Позиция, Регион
   Навыки: ...
   Score: 0.xx
Выведи только лучших, максимум top_k.
"""},
            {"role": "user", "content": f"Описание вакансии: {req_text}"},
            {"role": "user", "content": f"Список кандидатов:\n{json.dumps(cand_list, ensure_ascii=False)}"},
            {"role": "user", "content": f"top_k = {top_k}"}
        ]

        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=rank_messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"Ошибка при поиске кандидатов: {e}"

        append("assistant", reply)

    def send():
        user_input = entry.get().strip()
        if not user_input: return
        entry.delete(0, "end")
        append("user", user_input)
        messages.append({"role": "user", "content": user_input})

        # Завершение
        if user_input.lower() in ["готово", "всё", "закончить", "finish", "end"]:
            req_text = " ".join(m["content"] for m in messages if m["role"] == "user")
            rank_and_show(req_text, top_k=10)
            return

        # Обычный ответ ИИ
        try:
            resp = client.chat.completions.create(model=AI_MODEL, messages=messages)
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"Ошибка ИИ: {e}"

        append("assistant", reply)
        messages.append({"role": "assistant", "content": reply})

    append("assistant", "Опишите максимально подробно, кого вы ищете. Когда захотите завершить и получить список кандидатов — напишите «готово».")
    t.Button(cw, text="Отправить", command=send).pack(pady=6)
    entry.bind("<Return>", lambda _: send())


def view_candidate_window(parent, cand_id):
    if not cand_id:
        messagebox.showinfo("Кандидат", "Нет id кандидата"); return
    try:
        con = connect_to_db(DB_NAME); cur = con.cursor()
        cur.execute("""
            SELECT id, login, name, position, seniority, region, experience, desired_salary,
                   field, schedule, contacts, languages, relocation
            FROM candidates WHERE id=%s
        """, (cand_id,))
        r = cur.fetchone(); cur.close(); con.close()
        if not r:
            messagebox.showinfo("Кандидат", f"Кандидат id={cand_id} не найден"); return
    except Exception as e:
        messagebox.showerror("Ошибка", str(e)); return

    w = t.Toplevel(parent); w.title(f"Кандидат #{r[0]}")
    labels = [
        ("login", r[1]), ("name", r[2]), ("position", r[3]), ("seniority", r[4]),
        ("region", r[5]), ("experience", r[6]), ("desired_salary", r[7]),
        ("field", r[8]), ("schedule", r[9]), ("contacts", r[10]),
        ("languages", r[11]), ("relocation", r[12]),
    ]
    for i, (k, v) in enumerate(labels):
        t.Label(w, text=f"{k}:").grid(row=i, column=0, sticky="e", padx=6, pady=3)
        t.Label(w, text=f"{'' if v is None else v}").grid(row=i, column=1, sticky="w", padx=6, pady=3)
    t.Button(w, text="Закрыть", command=w.destroy).grid(row=len(labels), column=0, columnspan=2, pady=10)

def build_auth_ui(root):
    root.title("Авторизация")
    root.geometry("640x280")

    try:
        ensure_database_exists()
        ensure_tables()
        seed_all()
    except Exception:
        pass

    t.Label(root, text="Кто вы?", font=("Arial", 14)).pack(pady=12)
    btns = t.Frame(root); btns.pack(pady=10)
    t.Button(btns, text="Я HR", width=28, command=lambda: (root.withdraw(), hr_login_then_panel(root))).grid(row=0, column=0, padx=6, pady=6)
    t.Button(btns, text="Я ищу работу / Админ", width=28, command=lambda: (root.withdraw(), seeker_or_admin_login(root))).grid(row=0, column=1, padx=6, pady=6)

if __name__ == "__main__":
    root = t.Tk()
    build_auth_ui(root)
    root.mainloop()

