import random
from db.connections import connect_to_db, load_config

DB_NAME = load_config().get("database", "t1v7")

FIRST_NAMES = [
    "Иван", "Петр", "Алексей", "Сергей", "Михаил",
    "Дмитрий", "Николай", "Андрей", "Владимир", "Егор"
]
LAST_NAMES = [
    "Иванов", "Петров", "Сидоров", "Кузнецов", "Попов",
    "Смирнов", "Васильев", "Новиков", "Морозов", "Федоров"
]
POSITIONS = [
    "Python Developer", "Java Developer", "Data Analyst",
    "Frontend Developer", "Backend Developer", "DevOps Engineer",
    "QA Engineer", "Business Analyst", "ML Engineer", "Project Manager"
]
SENIORITY = ["Junior", "Middle", "Senior", "Lead"]
EDUCATION = ["Bachelor's", "Master's", "PhD", "College"]
SCHEDULE = ["Full-time", "Part-time", "Flexible", "Shift"]
EMPLOYMENT_TYPES = ["Official", "Contract", "Freelance", "Internship"]
WORK_FORMATS = ["Remote", "Office", "Hybrid"]
LANGUAGES = ["Русский", "Английский", "Немецкий", "Французский", "Испанский"]

def count_rows(table):
    con = connect_to_db(DB_NAME)
    cur = con.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    n = cur.fetchone()[0]
    cur.close(); con.close()
    return n

def seed_candidates(n=100):
    existing = count_rows("candidates")
    if existing >= n:
        return

    con = connect_to_db(DB_NAME)
    cur = con.cursor()

    for i in range(existing, n):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        login = f"user{i+1}"
        password = f"pass{i+1}"
        age = random.randint(20, 50)
        exp = random.randint(0, age - 18)
        region = "Москва"
        position = random.choice(POSITIONS)
        seniority = random.choice(SENIORITY)
        must_have_skills = "Python, SQL, Git"
        nice_to_have_skills = "Teamwork, Communication"
        education = random.choice(EDUCATION)
        desired_salary = random.randint(60000, 250000)
        field = "IT"
        schedule = random.choice(SCHEDULE)
        contacts = f"user{i+1}@example.com, @user{i+1}"
        relocation = random.choice([True, False])
        portfolio_links = "https://github.com/example"
        languages = random.choice(LANGUAGES)
        courses = "Stepik, Coursera"
        internships = "Yandex, Sber"
        projects = "CRM system, Analytics Dashboard"
        achievements = "Best employee 2022"
        employment_type = random.choice(EMPLOYMENT_TYPES)
        work_format = random.choice(WORK_FORMATS)
        extra_information = "Готов к новым вызовам"
        score = random.randint(50, 100)

        cur.execute("""
            INSERT INTO candidates (
                login, password, name, age, experience, region,
                position, seniority, must_have_skills, nice_to_have_skills,
                education, desired_salary, field, schedule, contacts,
                relocation, portfolio_links, languages, courses,
                internships, projects, achievements, employment_type,
                work_format, extra_information, score
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s)
        """, (
            login, password, name, age, exp, region,
            position, seniority, must_have_skills, nice_to_have_skills,
            education, desired_salary, field, schedule, contacts,
            relocation, portfolio_links, languages, courses,
            internships, projects, achievements, employment_type,
            work_format, extra_information, score
        ))

    con.commit()
    cur.close(); con.close()

def seed_vacancies(n=100):
    existing = count_rows("vacancies")
    if existing >= n:
        return

    con = connect_to_db(DB_NAME)
    cur = con.cursor()

    for i in range(existing, n):
        login = f"hr{i+1}"
        password = f"hrpass{i+1}"
        age = None
        exp = None
        region = "Москва"
        position = random.choice(POSITIONS)
        seniority = random.choice(SENIORITY)
        must_have_skills = "Python, SQL, Git"
        nice_to_have_skills = "Teamwork, Communication"
        education = random.choice(EDUCATION)
        desired_salary = random.randint(80000, 300000)
        field = "IT"
        schedule = random.choice(SCHEDULE)
        contacts = f"hr{i+1}@example.com, @hr{i+1}"
        relocation = random.choice([True, False])
        languages = random.choice(LANGUAGES)
        employment_type = random.choice(EMPLOYMENT_TYPES)
        work_format = random.choice(WORK_FORMATS)
        extra_information = "Ищем сильного кандидата"

        cur.execute("""
            INSERT INTO vacancies (
                login, password, age, experience, region,
                position, seniority, must_have_skills, nice_to_have_skills,
                education, desired_salary, field, schedule, contacts,
                relocation, languages, employment_type, work_format,
                extra_information
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            login, password, age, exp, region,
            position, seniority, must_have_skills, nice_to_have_skills,
            education, desired_salary, field, schedule, contacts,
            relocation, languages, employment_type, work_format,
            extra_information
        ))

    con.commit()
    cur.close(); con.close()

def seed_all():
    seed_candidates(100)
    seed_vacancies(100)
