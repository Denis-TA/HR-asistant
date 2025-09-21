from tkinter import messagebox
from db.connections import connect_to_db

# ======== CANDIDATES CRUD ========

def add_row(dbname, *args):
    """
    add candidate row
    Args order (UI): id, login, password, name, age, experience, region, position, seniority,
                     must_have_skills, nice_to_have_skills, education, desired_salary, field,
                     schedule, contacts, relocation, portfolio_links, languages, courses,
                     internships, projects, achievements, employment_type, work_format,
                     extra_information, score
    """
    try:
        (id_, login, password, name, age, exp, region, position, seniority,
         must_have, nice_to_have, education, salary, field, schedule, contacts,
         relocation, portfolio_links, languages, courses, internships, projects,
         achievements, employment_type, work_format, extra_information, score) = args

        con = connect_to_db(dbname); cur = con.cursor()

        cols = ["login","password","name","age","experience","region","position","seniority",
                "must_have_skills","nice_to_have_skills","education","desired_salary","field",
                "schedule","contacts","relocation","portfolio_links","languages","courses",
                "internships","projects","achievements","employment_type","work_format",
                "extra_information","score"]
        vals = [login, password,
                (name or None),
                (int(age) if str(age).strip() else None),
                (int(exp) if str(exp).strip() else None),
                (region or None),
                (position or None),
                (seniority or None),
                (must_have or None),
                (nice_to_have or None),
                (education or None),
                (int(salary) if str(salary).strip() else None),
                (field or None),
                (schedule or None),
                (contacts or None),
                (None if str(relocation).strip()=="" else (str(relocation).lower() in ("true","1","t","yes","y"))),
                (portfolio_links or None),
                (languages or None),
                (courses or None),
                (internships or None),
                (projects or None),
                (achievements or None),
                (employment_type or None),
                (work_format or None),
                (extra_information or None),
                (int(score) if str(score).strip() else None)
                ]

        if str(id_).strip():
            cols = ["id"] + cols
            vals = [int(id_)] + vals

        placeholders = ", ".join(["%s"] * len(vals))
        cur.execute(f"INSERT INTO candidates ({', '.join(cols)}) VALUES ({placeholders})", tuple(vals))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Кандидат добавлен")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def delete_row(dbname, *args):
    """Удаление кандидатов по любому подмножеству условий (OR)."""
    try:
        (id_, login, password, name, age, exp, region, position, seniority,
         must_have, nice_to_have, education, salary, field, schedule, contacts,
         relocation, portfolio_links, languages, courses, internships, projects,
         achievements, employment_type, work_format, extra_information, score) = args

        con = connect_to_db(dbname); cur = con.cursor()

        conds, params = [], []
        def add(cond, val, cast=int):
            if val is not None and str(val).strip() != "":
                params.append(cast(val) if cast else val); conds.append(cond)

        add("id = %s", id_)
        add("login = %s", login, cast=None)
        add("password = %s", password, cast=None)
        add("name = %s", name, cast=None)
        add("age = %s", age)
        add("experience = %s", exp)
        add("region = %s", region, cast=None)
        add("position = %s", position, cast=None)
        add("seniority = %s", seniority, cast=None)
        add("education = %s", education, cast=None)
        add("desired_salary = %s", salary)
        add("field = %s", field, cast=None)
        add("schedule = %s", schedule, cast=None)

        if relocation is not None and str(relocation).strip() != "":
            params.append(str(relocation).lower() in ("true","1","t","yes","y"))
            conds.append("relocation = %s")

        if not conds:
            messagebox.showwarning("Нет фильтра", "Укажите условия для удаления"); return

        cur.execute("DELETE FROM candidates WHERE " + " OR ".join(conds), tuple(params))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Удалено")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def select_row(dbname, *args):
    """Поиск кандидатов (AND-фильтры по заполненным полям)."""
    try:
        (id_, login, password, name, age, exp, region, position, seniority,
         must_have, nice_to_have, education, salary, field, schedule, contacts,
         relocation, portfolio_links, languages, courses, internships, projects,
         achievements, employment_type, work_format, extra_information, score) = args

        con = connect_to_db(dbname); cur = con.cursor()

        query = "SELECT id, login, name, position, region, seniority, field, desired_salary FROM candidates"
        conds, params = [], []
        def add(cond, val, cast=int):
            if val is not None and str(val).strip() != "":
                params.append(cast(val) if cast else val); conds.append(cond)

        add("id = %s", id_)
        add("login = %s", login, cast=None)
        add("password = %s", password, cast=None)
        add("name ILIKE %s", f"%{name}%" if name else None, cast=None)
        add("age = %s", age)
        add("experience >= %s", exp)
        add("region = %s", region, cast=None)
        add("position ILIKE %s", f"%{position}%" if position else None, cast=None)
        add("seniority = %s", seniority, cast=None)
        add("education = %s", education, cast=None)
        add("desired_salary >= %s", salary)
        add("field = %s", field, cast=None)
        add("schedule = %s", schedule, cast=None)
        if relocation is not None and str(relocation).strip() != "":
            params.append(str(relocation).lower() in ("true","1","t","yes","y"))
            conds.append("relocation = %s")

        if conds: query += " WHERE " + " AND ".join(conds)

        cur.execute(query, tuple(params))
        rows = cur.fetchall(); cur.close(); con.close()

        if not rows:
            messagebox.showinfo("Результат", "Ничего не найдено.")
        else:
            result = "\n".join([f"ID:{r[0]} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} | {r[5] or ''} | {r[6] or ''} | {r[7] or ''}" for r in rows])
            messagebox.showinfo("Найдено", result)
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def edit_row(dbname, *args):
    """UPDATE кандидата по фильтру (id/login/password должны быть заданы как фильтр)."""
    try:
        (id_, login, password, name, age, exp, region, position, seniority,
         must_have, nice_to_have, education, salary, field, schedule, contacts,
         relocation, portfolio_links, languages, courses, internships, projects,
         achievements, employment_type, work_format, extra_information, score) = args

        where_conds, where_params = [], []
        if str(id_).strip():       where_conds.append("id = %s");       where_params.append(int(id_))
        if str(login).strip():     where_conds.append("login = %s");    where_params.append(login)
        if str(password).strip():  where_conds.append("password = %s"); where_params.append(password)
        if not where_conds:
            messagebox.showwarning("Фильтр", "Нужно задать id/login/password"); return

        set_cols, set_params = [], []
        def put(col, val, cast=None):
            if val is not None and str(val).strip() != "":
                set_cols.append(f"{col} = %s"); set_params.append(cast(val) if cast else val)

        put("name", name)
        put("age", age, cast=int); put("experience", exp, cast=int)
        put("region", region); put("position", position); put("seniority", seniority)
        put("must_have_skills", must_have); put("nice_to_have_skills", nice_to_have)
        put("education", education); put("desired_salary", salary, cast=int)
        put("field", field); put("schedule", schedule); put("contacts", contacts)
        if relocation is not None and str(relocation).strip() != "":
            set_cols.append("relocation = %s")
            set_params.append(str(relocation).lower() in ("true","1","t","yes","y"))
        put("portfolio_links", portfolio_links); put("languages", languages)
        put("courses", courses); put("internships", internships)
        put("projects", projects); put("achievements", achievements)
        put("employment_type", employment_type); put("work_format", work_format)
        put("extra_information", extra_information); put("score", score, cast=int)

        if not set_cols:
            messagebox.showwarning("Нет изменений", "Заполните поля для обновления"); return

        con = connect_to_db(dbname); cur = con.cursor()
        q = "UPDATE candidates SET " + ", ".join(set_cols) + " WHERE " + " AND ".join(where_conds)
        cur.execute(q, tuple(set_params + where_params))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Обновлено")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


# ======== VACANCIES CRUD (min/max возраст/опыт) ========

def add_vacancy(dbname, *args):
    """
    add vacancy row
    Args order (UI create form):
      position, field, region,
      min_age, max_age, min_experience, max_experience,
      seniority, must_have_skills, nice_to_have_skills, education, desired_salary,
      schedule, contacts, relocation, languages, employment_type, work_format,
      extra_information, login, password
    """
    try:
        (position, field, region,
         min_age, max_age, min_exp, max_exp,
         seniority, must_have, nice_to_have, education, salary,
         schedule, contacts, relocation, languages, employment_type, work_format,
         extra_information, login, password) = args

        con = connect_to_db(dbname); cur = con.cursor()
        cur.execute("""
            INSERT INTO vacancies (
                login, password, position, field, region,
                min_age, max_age, min_experience, max_experience,
                seniority, must_have_skills, nice_to_have_skills, education, desired_salary,
                schedule, contacts, relocation, languages, employment_type, work_format, extra_information
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            login, password,
            (position or None), (field or None), (region or None),
            (int(min_age) if str(min_age).strip() else None),
            (int(max_age) if str(max_age).strip() else None),
            (int(min_exp) if str(min_exp).strip() else None),
            (int(max_exp) if str(max_exp).strip() else None),
            (seniority or None),
            (must_have or None), (nice_to_have or None),
            (education or None),
            (int(salary) if str(salary).strip() else None),
            (schedule or None), (contacts or None),
            (None if str(relocation).strip()=="" else (str(relocation).lower() in ("true","1","t","yes","y"))),
            (languages or None), (employment_type or None), (work_format or None),
            (extra_information or None)
        ))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Вакансия создана")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def delete_vacancy(dbname, *args):
    """Удаление вакансий по OR-условиям."""
    try:
        (position, field, region,
         min_age, max_age, min_exp, max_exp,
         seniority, must_have, nice_to_have, education, salary,
         schedule, contacts, relocation, languages, employment_type, work_format,
         extra_information, login, password) = args

        con = connect_to_db(dbname); cur = con.cursor()
        conds, params = [], []

        def add(cond, val, cast=int):
            if val is not None and str(val).strip() != "":
                params.append(cast(val) if cast else val); conds.append(cond)

        add("login = %s", login, cast=None)
        add("password = %s", password, cast=None)
        add("position ILIKE %s", f"%{position}%" if position else None, cast=None)
        add("field = %s", field, cast=None)
        add("region = %s", region, cast=None)
        add("education = %s", education, cast=None)
        add("min_age = %s", min_age); add("max_age = %s", max_age)
        add("min_experience = %s", min_exp); add("max_experience = %s", max_exp)

        if relocation is not None and str(relocation).strip() != "":
            params.append(str(relocation).lower() in ("true","1","t","yes","y"))
            conds.append("relocation = %s")

        if not conds:
            messagebox.showwarning("Нет фильтра", "Укажите условия для удаления"); return

        cur.execute("DELETE FROM vacancies WHERE " + " OR ".join(conds), tuple(params))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Удалено")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def select_vacancy(dbname, *, position=None, field=None, region=None,
                   min_age=None, max_age=None,
                   min_experience=None, max_experience=None,
                   min_salary=None, education=None, schedule=None,
                   seniority=None, relocation=None, login=None):
    """
    Поиск вакансий с учётом min/max возраста и опыта, хранящихся в вакансиях.
    Фильтрация понятна так:
      - если передан min_age -> вакансии, где min_age_vac >= min_age
      - если передан max_age -> вакансии, где max_age_vac <= max_age
      - аналогично для min_experience / max_experience
    """
    try:
        con = connect_to_db(dbname); cur = con.cursor()
        query = """SELECT id, position, field, region, desired_salary,
                          min_age, max_age, min_experience, max_experience, seniority
                   FROM vacancies"""
        conds, params = [], []

        def add(cond, val, cast=int):
            if val is not None and str(val).strip() != "":
                params.append(cast(val) if cast else val); conds.append(cond)

        add("position ILIKE %s", f"%{position}%" if position else None, cast=None)
        add("field = %s", field, cast=None)
        add("region = %s", region, cast=None)
        add("education = %s", education, cast=None)
        add("schedule = %s", schedule, cast=None)
        add("seniority = %s", seniority, cast=None)
        add("desired_salary >= %s", min_salary)

        add("min_age >= %s", min_age)
        add("max_age <= %s", max_age)
        add("min_experience >= %s", min_experience)
        add("max_experience <= %s", max_experience)

        add("login = %s", login, cast=None)

        if relocation is not None and str(relocation).strip() != "":
            params.append(str(relocation).lower() in ("true","1","t","yes","y"))
            conds.append("relocation = %s")

        if conds: query += " WHERE " + " AND ".join(conds)

        cur.execute(query, tuple(params))
        rows = cur.fetchall(); cur.close(); con.close()

        if not rows:
            messagebox.showinfo("Результат", "Ничего не найдено.")
        else:
            text = "\n".join([
                f"#{r[0]} | {r[1] or ''} | {r[2] or ''} | {r[3] or ''} | З/п≥{r[4] or '—'} | "
                f"Возраст: {r[5] or '—'}–{r[6] or '—'} | Опыт: {r[7] or '—'}–{r[8] or '—'} | {r[9] or ''}"
                for r in rows
            ])
            messagebox.showinfo("Вакансии", text)
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))


def edit_vacancy(dbname, *args):
    """UPDATE вакансии по фильтру (по login/password и/или position)."""
    try:
        (position, field, region,
         min_age, max_age, min_exp, max_exp,
         seniority, must_have, nice_to_have, education, salary,
         schedule, contacts, relocation, languages, employment_type, work_format,
         extra_information, login, password) = args

        where_conds, where_params = [], []
        if str(login).strip():    where_conds.append("login = %s");    where_params.append(login)
        if str(password).strip(): where_conds.append("password = %s"); where_params.append(password)
        if str(position).strip(): where_conds.append("position ILIKE %s"); where_params.append(f"%{position}%")
        if not where_conds:
            messagebox.showwarning("Фильтр", "Задайте хотя бы login/password или position"); return

        set_cols, set_params = [], []
        def put(col, val, cast=None):
            if val is not None and str(val).strip() != "":
                set_cols.append(f"{col} = %s"); set_params.append(cast(val) if cast else val)

        put("field", field); put("region", region)
        put("min_age", min_age, cast=int); put("max_age", max_age, cast=int)
        put("min_experience", min_exp, cast=int); put("max_experience", max_exp, cast=int)
        put("seniority", seniority)
        put("must_have_skills", must_have); put("nice_to_have_skills", nice_to_have)
        put("education", education); put("desired_salary", salary, cast=int)
        put("schedule", schedule); put("contacts", contacts)
        if relocation is not None and str(relocation).strip() != "":
            set_cols.append("relocation = %s")
            set_params.append(str(relocation).lower() in ("true","1","t","yes","y"))
        put("languages", languages); put("employment_type", employment_type)
        put("work_format", work_format); put("extra_information", extra_information)

        if not set_cols:
            messagebox.showwarning("Нет изменений", "Заполните поля для обновления"); return

        con = connect_to_db(dbname); cur = con.cursor()
        q = "UPDATE vacancies SET " + ", ".join(set_cols) + " WHERE " + " AND ".join(where_conds)
        cur.execute(q, tuple(set_params + where_params))
        con.commit(); cur.close(); con.close()
        messagebox.showinfo("OK", "Обновлено")
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))
