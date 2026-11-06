"""
High School Management System API.

The application stores academic records and activity memberships in SQLite so
changes survive process restarts and can be related to real student records.
"""

from contextlib import closing
from pathlib import Path
import os
import sqlite3
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


app = FastAPI(
    title="Mergington High School API",
    description="API for school records and extracurricular activities",
)

current_dir = Path(__file__).parent
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(current_dir, "static")),
    name="static",
)

DATABASE_PATH = current_dir / "school.sqlite"

ACTIVITY_SEEDS = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


class StudentInput(BaseModel):
    email: str
    name: str
    study_level_id: Optional[int] = None
    department_id: Optional[int] = None


class ProfessorInput(BaseModel):
    name: str
    email: str
    department_id: Optional[int] = None


class NamedInput(BaseModel):
    name: str


class CourseInput(BaseModel):
    code: str
    name: str
    department_id: Optional[int] = None


class ClassSectionInput(BaseModel):
    course_id: int
    professor_id: int
    section: str
    semester: str


class ActivityInput(BaseModel):
    name: str
    description: str
    schedule: str
    max_participants: int = Field(gt=0)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    with closing(get_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS study_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS professors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                study_level_id INTEGER REFERENCES study_levels(id) ON DELETE SET NULL,
                department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS class_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                professor_id INTEGER NOT NULL REFERENCES professors(id) ON DELETE RESTRICT,
                section TEXT NOT NULL,
                semester TEXT NOT NULL,
                UNIQUE(course_id, section, semester)
            );
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK(max_participants > 0)
            );
            CREATE TABLE IF NOT EXISTS activity_memberships (
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                PRIMARY KEY(activity_id, student_id)
            );
            """
        )
        for activity_name, activity in ACTIVITY_SEEDS.items():
            connection.execute(
                """
                INSERT OR IGNORE INTO activities
                    (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (
                    activity_name,
                    activity["description"],
                    activity["schedule"],
                    activity["max_participants"],
                ),
            )
            for email in activity["participants"]:
                connection.execute(
                    "INSERT OR IGNORE INTO students (email, name) VALUES (?, ?)",
                    (email, email.split("@")[0].replace(".", " ").title()),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO activity_memberships (activity_id, student_id)
                    SELECT a.id, s.id FROM activities a, students s
                    WHERE a.name = ? AND s.email = ?
                    """,
                    (activity_name, email),
                )
        connection.commit()


initialize_database()


def rows(table: str) -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def create_record(table: str, values: dict[str, Any]) -> dict[str, Any]:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    try:
        with closing(get_connection()) as connection:
            cursor = connection.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            connection.commit()
            return dict(connection.execute(
                f"SELECT * FROM {table} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone())
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def delete_record(table: str, record_id: int) -> None:
    with closing(get_connection()) as connection:
        cursor = connection.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Record not found")


def update_record(table: str, record_id: int, values: dict[str, Any]) -> dict[str, Any]:
    assignments = ", ".join(f"{column} = ?" for column in values)
    try:
        with closing(get_connection()) as connection:
            cursor = connection.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Record not found")
            connection.commit()
            return dict(connection.execute(
                f"SELECT * FROM {table} WHERE id = ?", (record_id,)
            ).fetchone())
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with closing(get_connection()) as connection:
        activities = {}
        for activity in connection.execute("SELECT * FROM activities ORDER BY name"):
            participants = connection.execute(
                """
                SELECT s.email FROM students s
                JOIN activity_memberships m ON m.student_id = s.id
                WHERE m.activity_id = ? ORDER BY s.email
                """,
                (activity["id"],),
            ).fetchall()
            activities[activity["name"]] = {
                "description": activity["description"],
                "schedule": activity["schedule"],
                "max_participants": activity["max_participants"],
                "participants": [participant["email"] for participant in participants],
            }
        return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    with closing(get_connection()) as connection:
        activity = connection.execute(
            "SELECT * FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        student = connection.execute(
            "SELECT id FROM students WHERE email = ?", (email,)
        ).fetchone()
        if student is None:
            raise HTTPException(
                status_code=400,
                detail="Student must be created before joining an activity",
            )
        existing = connection.execute(
            """
            SELECT 1 FROM activity_memberships
            WHERE activity_id = ? AND student_id = ?
            """,
            (activity["id"], student["id"]),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Student is already signed up")
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM activity_memberships WHERE activity_id = ?",
            (activity["id"],),
        ).fetchone()["count"]
        if count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")
        connection.execute(
            "INSERT INTO activity_memberships (activity_id, student_id) VALUES (?, ?)",
            (activity["id"], student["id"]),
        )
        connection.commit()
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            DELETE FROM activity_memberships
            WHERE activity_id = (SELECT id FROM activities WHERE name = ?)
              AND student_id = (SELECT id FROM students WHERE email = ?)
            """,
            (activity_name, email),
        )
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=400, detail="Student is not signed up")
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.get("/students")
def list_students():
    return rows("students")


@app.post("/students")
def create_student(student: StudentInput):
    return create_record("students", student.model_dump())


@app.delete("/students/{student_id}")
def delete_student(student_id: int):
    delete_record("students", student_id)
    return {"message": "Student deleted"}


@app.put("/students/{student_id}")
def update_student(student_id: int, student: StudentInput):
    return update_record("students", student_id, student.model_dump())


@app.get("/professors")
def list_professors():
    return rows("professors")


@app.post("/professors")
def create_professor(professor: ProfessorInput):
    return create_record("professors", professor.model_dump())


@app.delete("/professors/{professor_id}")
def delete_professor(professor_id: int):
    delete_record("professors", professor_id)
    return {"message": "Professor deleted"}


@app.put("/professors/{professor_id}")
def update_professor(professor_id: int, professor: ProfessorInput):
    return update_record("professors", professor_id, professor.model_dump())


@app.get("/departments")
def list_departments():
    return rows("departments")


@app.post("/departments")
def create_department(department: NamedInput):
    return create_record("departments", department.model_dump())


@app.delete("/departments/{department_id}")
def delete_department(department_id: int):
    delete_record("departments", department_id)
    return {"message": "Department deleted"}


@app.put("/departments/{department_id}")
def update_department(department_id: int, department: NamedInput):
    return update_record("departments", department_id, department.model_dump())


@app.get("/study-levels")
def list_study_levels():
    return rows("study_levels")


@app.post("/study-levels")
def create_study_level(level: NamedInput):
    return create_record("study_levels", level.model_dump())


@app.delete("/study-levels/{level_id}")
def delete_study_level(level_id: int):
    delete_record("study_levels", level_id)
    return {"message": "Study level deleted"}


@app.put("/study-levels/{level_id}")
def update_study_level(level_id: int, level: NamedInput):
    return update_record("study_levels", level_id, level.model_dump())


@app.get("/courses")
def list_courses():
    return rows("courses")


@app.post("/courses")
def create_course(course: CourseInput):
    return create_record("courses", course.model_dump())


@app.delete("/courses/{course_id}")
def delete_course(course_id: int):
    delete_record("courses", course_id)
    return {"message": "Course deleted"}


@app.put("/courses/{course_id}")
def update_course(course_id: int, course: CourseInput):
    return update_record("courses", course_id, course.model_dump())


@app.get("/class-sections")
def list_class_sections():
    return rows("class_sections")


@app.post("/class-sections")
def create_class_section(section: ClassSectionInput):
    return create_record("class_sections", section.model_dump())


@app.delete("/class-sections/{section_id}")
def delete_class_section(section_id: int):
    delete_record("class_sections", section_id)
    return {"message": "Class section deleted"}


@app.put("/class-sections/{section_id}")
def update_class_section(section_id: int, section: ClassSectionInput):
    return update_record("class_sections", section_id, section.model_dump())


@app.get("/activities-admin")
def list_activity_records():
    return rows("activities")


@app.post("/activities-admin")
def create_activity(activity: ActivityInput):
    return create_record("activities", activity.model_dump())


@app.delete("/activities-admin/{activity_id}")
def delete_activity(activity_id: int):
    delete_record("activities", activity_id)
    return {"message": "Activity deleted"}


@app.put("/activities-admin/{activity_id}")
def update_activity(activity_id: int, activity: ActivityInput):
    return update_record("activities", activity_id, activity.model_dump())
