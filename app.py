import streamlit as st
import sqlite3
import pandas as pd

from datetime import date, datetime, time, timedelta
from pathlib import Path

import hashlib
import hmac
import os
import uuid
import html
from textwrap import dedent


# ============================================================
# FILE LOCATIONS
# ============================================================
#This section tells Python where to find the files it needs

BASE_DIR = Path(__file__).resolve().parent   #finds the location of the file, turns it into a Path object, makes it an absolute path and find the parent file of app.py

DATABASE = BASE_DIR / "science_practicals.db" #tells python where the database is

ATTACHMENTS_FOLDER = BASE_DIR / "attachments"

ATTACHMENTS_FOLDER.mkdir(parents=True,exist_ok=True) #this lets pythom make the attachements folder if it doesnt already exist.


# ============================================================
# DEFAULT SETTINGS
# ============================================================

# These are only defaults.
# Later the actual values come from the database.

DEFAULT_PERIODS = ["P1","P2","P3","P4","P5"]

DEFAULT_YEARGROUPS = ["Year 7","Year 8","Year 9","Year 10","Year 11","Year 12","Year 13"]

DEFAULT_ROOMS = ["Lab 1","Lab 2","Lab 3","Lab 4","Lab 5","Lab 6","Lab 7","Lab 8","Lab 9","E1"]


# Default requisition deadline:
# Thursday = 3 because Monday = 0

DEFAULT_DEADLINE_WEEKDAY = 3
DEFAULT_DEADLINE_TIME = "10:40"


# Default attachment retention

DEFAULT_ATTACHMENT_RETENTION_WEEKS = 6


# Staff colours

STAFF_COLOURS = {"Grey": "#D9D9D9","Red": "#F4CCCC","Orange": "#FCE5CD","Yellow": "#FFF2CC","Green": "#D9EAD3","Blue": "#CFE2F3","Purple": "#D9D2E9","Pink": "#EAD1DC",}

def connect():

    conn = sqlite3.connect(DATABASE,timeout=10) #opens a connection to the database

    conn.execute("PRAGMA foreign_keys = ON") #foreign key is a relationship between 2 db tables so to prevent dicontinuities

    return conn

def column_exists(table_name,column_name): #checks whether a particular column already exixts

    conn = connect()

    cursor = conn.cursor() #an object used to execute SQL commands and retrieve their results

    cursor.execute(f"PRAGMA table_info({table_name})")

    columns = [row[1]for row in cursor.fetchall()]

    conn.close()

    return column_name in columns


def add_column_if_missing(table_name,column_name,column_definition): #updates the db is the column is missing

    if not column_exists(table_name,column_name):

        conn = connect()

        conn.execute(f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}""")

        conn.commit()
        conn.close()

def hash_password(password,salt=None): #this is the one way transformation of the original password

    if salt is None: #a salt is a random value added to a password hashing process

        salt = os.urandom(16) #This generates 16 random bytes

    password_hash = hashlib.pbkdf2_hmac("sha256",password.encode(),salt,100000) #sha256 is the underlying algorithm, encode turns it into bytes salt adds the random bytes and it performs 100000 iterations of the derivaton process

    return (salt.hex()+ ":"+ password_hash.hex()) #hex turns from bytes to hexidecimal text then it combines them

def check_password(password,stored_password): #this checks if the hash entered matches the one stored

    try:

        salt_hex, hash_hex = (stored_password.split(":"))

        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac("sha256",password.encode(),salt,100000)

        return hmac.compare_digest(new_hash.hex(),hash_hex) #securely matches two hash strings apparently designed to reeduce timing based information leakage

    except (ValueError,AttributeError): #handles potential errors that may arise to prevent a full crash

        return False



def create_database(): #welp guess what this does

    conn = connect()

    cursor = conn.cursor()


    # ========================================================
    # USERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            calendar_colour TEXT NOT NULL
                DEFAULT '#D9D9D9',
            must_change_password INTEGER NOT NULL
                DEFAULT 0,
            active INTEGER NOT NULL
                DEFAULT 1
        )
    """)


    # ========================================================
    # PRACTICAL LIBRARY
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            practical_name TEXT NOT NULL,
            year_group TEXT NOT NULL,
            equipment TEXT NOT NULL,
            technician_notes TEXT,
            code TEXT NOT NULL,
            active INTEGER NOT NULL
                DEFAULT 1
        )
    """)


    # ========================================================
    # REQUISITIONS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            teacher_id INTEGER NOT NULL,

            class_name TEXT NOT NULL,
            year_group TEXT NOT NULL,
            code TEXT,
            room TEXT NOT NULL,

            practical_name TEXT NOT NULL,
            practical_date TEXT NOT NULL,
            period TEXT NOT NULL,

            number INTEGER NOT NULL,

            equipment TEXT NOT NULL,
            notes TEXT,

            risk_assessment_confirmed
                INTEGER NOT NULL DEFAULT 0,

            submitted_at TEXT,

            is_late
                INTEGER NOT NULL DEFAULT 0,

            approval_status TEXT NOT NULL
                DEFAULT 'Approved',

            approved_by INTEGER,
            approved_at TEXT,

            technician_response TEXT,

            FOREIGN KEY (teacher_id)
                REFERENCES users(id),

            FOREIGN KEY (approved_by)
                REFERENCES users(id)
        )
    """)


    # ========================================================
    # ATTACHMENTS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS
        requisition_attachments (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            requisition_id INTEGER NOT NULL,

            original_filename TEXT NOT NULL,

            stored_filename TEXT NOT NULL,

            file_path TEXT NOT NULL,

            uploaded_at TEXT NOT NULL,

            FOREIGN KEY (requisition_id)
                REFERENCES requisitions(id)
                ON DELETE CASCADE
        )
    """)


    # ========================================================
    # SCHOOL SETTINGS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS school_settings (

            id INTEGER PRIMARY KEY
                CHECK (id = 1),

            school_name TEXT NOT NULL
                DEFAULT 'School',

            department_name TEXT NOT NULL
                DEFAULT 'Science',

            deadline_weekday INTEGER NOT NULL
                DEFAULT 3,

            deadline_time TEXT NOT NULL
                DEFAULT '10:40',

            allow_late_requisitions INTEGER NOT NULL
                DEFAULT 1,

            attachment_retention_weeks INTEGER NOT NULL
                DEFAULT 6
        )
    """)


    # ========================================================
    # ROOMS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            room_name TEXT UNIQUE NOT NULL,

            sort_order INTEGER NOT NULL
                DEFAULT 0,

            active INTEGER NOT NULL
                DEFAULT 1
        )
    """)


    # ========================================================
    # YEAR GROUPS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS year_groups (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            year_name TEXT UNIQUE NOT NULL,

            sort_order INTEGER NOT NULL
                DEFAULT 0,

            active INTEGER NOT NULL
                DEFAULT 1
        )
    """)


    # ========================================================
    # PERIODS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS periods (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            period_name TEXT UNIQUE NOT NULL,

            sort_order INTEGER NOT NULL
                DEFAULT 0,

            active INTEGER NOT NULL
                DEFAULT 1
        )
    """)


    # ========================================================
    # LESSON TIMES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lesson_times (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            day_name TEXT NOT NULL,

            year_group TEXT NOT NULL,

            period TEXT NOT NULL,

            start_time TEXT NOT NULL,

            end_time TEXT NOT NULL,

            UNIQUE (
                day_name,
                year_group,
                period
            )
        )
    """)


    conn.commit()
    conn.close()




def migrate_database():

    # ========================================================
    # USERS
    # ========================================================

    add_column_if_missing(
        "users",
        "calendar_colour",
        "TEXT NOT NULL DEFAULT '#D9D9D9'"
    )

    add_column_if_missing(
        "users",
        "must_change_password",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        "users",
        "active",
        "INTEGER NOT NULL DEFAULT 1"
    )


    # ========================================================
    # PRACTICALS
    # ========================================================

    add_column_if_missing(
        "practicals",
        "technician_notes",
        "TEXT"
    )

    add_column_if_missing(
        "practicals",
        "active",
        "INTEGER NOT NULL DEFAULT 1"
    )


    # ========================================================
    # REQUISITIONS
    # ========================================================

    add_column_if_missing(
        "requisitions",
        "risk_assessment_confirmed",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        "requisitions",
        "submitted_at",
        "TEXT"
    )

    add_column_if_missing(
        "requisitions",
        "is_late",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        "requisitions",
        "approval_status",
        "TEXT NOT NULL DEFAULT 'Approved'"
    )

    add_column_if_missing(
        "requisitions",
        "approved_by",
        "INTEGER"
    )

    add_column_if_missing(
        "requisitions",
        "approved_at",
        "TEXT"
    )

    add_column_if_missing(
        "requisitions",
        "technician_response",
        "TEXT"
    )


def initialise_default_settings():

    conn = connect()

    cursor = conn.cursor()


    # School settings

    cursor.execute(
        """
        INSERT OR IGNORE INTO school_settings
        (
            id,
            school_name,
            department_name,
            deadline_weekday,
            deadline_time,
            allow_late_requisitions,
            attachment_retention_weeks
        )
        VALUES
        (
            1,
            'School',
            'Science',
            3,
            '10:40',
            1,
            6
        )
        """
    )


    # Rooms

    for index, room in enumerate(
        DEFAULT_ROOMS
    ):

        cursor.execute(
            """
            INSERT OR IGNORE INTO rooms
            (
                room_name,
                sort_order
            )
            VALUES (?, ?)
            """,
            (
                room,
                index
            )
        )


    # Year groups

    for index, year_group in enumerate(
        DEFAULT_YEARGROUPS
    ):

        cursor.execute(
            """
            INSERT OR IGNORE INTO year_groups
            (
                year_name,
                sort_order
            )
            VALUES (?, ?)
            """,
            (
                year_group,
                index
            )
        )


    # Periods

    for index, period in enumerate(
        DEFAULT_PERIODS
    ):

        cursor.execute(
            """
            INSERT OR IGNORE INTO periods
            (
                period_name,
                sort_order
            )
            VALUES (?, ?)
            """,
            (
                period,
                index
            )
        )


    conn.commit()
    conn.close()


create_database()
migrate_database()

initialise_default_settings()

def get_school_settings():

    conn = connect()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            school_name,
            department_name,
            deadline_weekday,
            deadline_time,
            allow_late_requisitions,
            attachment_retention_weeks
        FROM school_settings
        WHERE id = 1
    """)

    result = cursor.fetchone()

    conn.close()

    return {
        "school_name": result[0],
        "department_name": result[1],
        "deadline_weekday": result[2],
        "deadline_time": result[3],
        "allow_late_requisitions": bool(
            result[4]
        ),
        "attachment_retention_weeks":
            result[5]
    }


def update_school_settings(
    school_name=None,
    department_name=None,
    deadline_weekday=None,
    deadline_time=None,
    allow_late_requisitions=None,
    attachment_retention_weeks=None
):

    current = get_school_settings()

    if school_name is None:
        school_name = current["school_name"]
    if department_name is None:
        department_name = current["department_name"]
    if deadline_weekday is None:
        deadline_weekday = current["deadline_weekday"]
    if deadline_time is None:
        deadline_time = current["deadline_time"]
    if allow_late_requisitions is None:
        allow_late_requisitions = current["allow_late_requisitions"]
    if attachment_retention_weeks is None:
        attachment_retention_weeks = current["attachment_retention_weeks"]

    conn = connect()

    conn.execute("""
        UPDATE school_settings
        SET
            school_name = ?,
            department_name = ?,
            deadline_weekday = ?,
            deadline_time = ?,
            allow_late_requisitions = ?,
            attachment_retention_weeks = ?
        WHERE id = 1
    """, (
        school_name.strip(),
        department_name.strip(),
        int(deadline_weekday),
        deadline_time,
        int(allow_late_requisitions),
        int(attachment_retention_weeks)
    ))

    conn.commit()
    conn.close()


def get_rooms(include_inactive=False):

    conn = connect()

    where_clause = "" if include_inactive else "WHERE active = 1"

    df = pd.read_sql_query(f"""
        SELECT
            id,
            room_name,
            sort_order,
            active
        FROM rooms
        {where_clause}
        ORDER BY
            sort_order,
            room_name
    """, conn)

    conn.close()

    return df

def get_room_names():

    rooms = get_rooms()

    return rooms[
        "room_name"
    ].tolist()


def get_year_groups(include_inactive=False):

    conn = connect()

    where_clause = "" if include_inactive else "WHERE active = 1"

    df = pd.read_sql_query(f"""
        SELECT
            id,
            year_name,
            sort_order,
            active
        FROM year_groups
        {where_clause}
        ORDER BY
            sort_order,
            year_name
    """, conn)

    conn.close()

    return df

def get_year_group_names():

    year_groups = get_year_groups()

    return year_groups[
        "year_name"
    ].tolist()


def get_periods(include_inactive=False):

    conn = connect()

    where_clause = "" if include_inactive else "WHERE active = 1"

    df = pd.read_sql_query(f"""
        SELECT
            id,
            period_name,
            sort_order,
            active
        FROM periods
        {where_clause}
        ORDER BY
            sort_order,
            period_name
    """, conn)

    conn.close()

    return df


def get_period_names():

    periods = get_periods()

    return periods[
        "period_name"
    ].tolist()


def add_room(room_name):

    conn = connect()

    try:

        conn.execute(
            """
            INSERT INTO rooms
            (room_name, sort_order)
            VALUES (
                ?,
                (
                    SELECT
                        COALESCE(MAX(sort_order), -1) + 1
                    FROM rooms
                )
            )
            """,
            (
                room_name.strip(),
            )
        )

        conn.commit()

        return True, "Room added."

    except sqlite3.IntegrityError:

        return False, "That room already exists."

    finally:

        conn.close()


def add_year_group(year_name):

    conn = connect()

    try:

        conn.execute(
            """
            INSERT INTO year_groups
            (year_name, sort_order)
            VALUES (
                ?,
                (
                    SELECT
                        COALESCE(MAX(sort_order), -1) + 1
                    FROM year_groups
                )
            )
            """,
            (
                year_name.strip(),
            )
        )

        conn.commit()

        return True, "Year group added."

    except sqlite3.IntegrityError:

        return False, (
            "That year group already exists."
        )

    finally:

        conn.close()


def add_period(period_name):

    conn = connect()

    try:

        conn.execute(
            """
            INSERT INTO periods
            (period_name, sort_order)
            VALUES (
                ?,
                (
                    SELECT
                        COALESCE(MAX(sort_order), -1) + 1
                    FROM periods
                )
            )
            """,
            (
                period_name.strip(),
            )
        )

        conn.commit()

        return True, "Period added."

    except sqlite3.IntegrityError:

        return False, (
            "That period already exists."
        )

    finally:

        conn.close()



def save_lesson_time(
    day_name,
    year_group,
    period,
    start_time,
    end_time
):

    conn = connect()

    conn.execute("""
        INSERT INTO lesson_times
        (
            day_name,
            year_group,
            period,
            start_time,
            end_time
        )

        VALUES (?, ?, ?, ?, ?)

        ON CONFLICT(
            day_name,
            year_group,
            period
        )

        DO UPDATE SET
            start_time = excluded.start_time,
            end_time = excluded.end_time
    """, (
        day_name,
        year_group,
        period,
        start_time,
        end_time
    ))

    conn.commit()
    conn.close()


def get_lesson_time(
    practical_date,
    year_group,
    period
):

    day_name = practical_date.strftime(
        "%A"
    )

    conn = connect()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            start_time,
            end_time

        FROM lesson_times

        WHERE
            day_name = ?
            AND year_group = ?
            AND period = ?
    """, (
        day_name,
        year_group,
        period
    ))

    result = cursor.fetchone()

    conn.close()

    if result is None:

        return None

    return (
        f"{result[0]}–{result[1]}"
    )


def create_user(
    username,
    password,
    display_name,
    role,
    calendar_colour="#D9D9D9",
    must_change_password=True
):

    conn = connect()

    password_hash = hash_password(
        password
    )

    try:

        conn.execute("""
            INSERT INTO users
            (
                username,
                password_hash,
                display_name,
                role,
                calendar_colour,
                must_change_password,
                active
            )

            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            username.strip().lower(),
            password_hash,
            display_name.strip(),
            role,
            calendar_colour,
            int(must_change_password)
        ))

        conn.commit()

        success = True
        message = (
            "User created successfully."
        )

    except sqlite3.IntegrityError:

        success = False
        message = (
            "That username already exists."
        )

    finally:

        conn.close()

    return success, message



def authenticate_user(
    username,
    password
):

    conn = connect()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            username,
            password_hash,
            display_name,
            role,
            calendar_colour,
            must_change_password,
            active

        FROM users

        WHERE username = ?
    """, (
        username.strip().lower(),
    ))

    result = cursor.fetchone()

    conn.close()

    if result is None:

        return None

    if not result[7]:

        return None

    if not check_password(
        password,
        result[2]
    ):

        return None

    return {
        "id": result[0],
        "username": result[1],
        "display_name": result[3],
        "role": result[4],
        "calendar_colour": result[5],
        "must_change_password": bool(
            result[6]
        )
    }


def get_users():

    conn = connect()

    df = pd.read_sql_query("""
        SELECT
            id,
            username,
            display_name,
            role,
            calendar_colour,
            must_change_password,
            active

        FROM users

        ORDER BY display_name
    """, conn)

    conn.close()

    return df


def users_exist():

    conn = connect()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def change_password(
    user_id,
    new_password
):

    password_hash = hash_password(
        new_password
    )

    conn = connect()

    conn.execute("""
        UPDATE users

        SET
            password_hash = ?,
            must_change_password = 0

        WHERE id = ?
    """, (
        password_hash,
        user_id
    ))

    conn.commit()
    conn.close()


def reset_user_password(
    user_id,
    temporary_password
):

    password_hash = hash_password(
        temporary_password
    )

    conn = connect()

    conn.execute("""
        UPDATE users

        SET
            password_hash = ?,
            must_change_password = 1

        WHERE id = ?
    """, (
        password_hash,
        user_id
    ))

    conn.commit()
    conn.close()


def update_user(
    user_id,
    display_name,
    role,
    calendar_colour,
    active
):

    conn = connect()

    conn.execute("""
        UPDATE users

        SET
            display_name = ?,
            role = ?,
            calendar_colour = ?,
            active = ?

        WHERE id = ?
    """, (
        display_name.strip(),
        role,
        calendar_colour,
        int(active),
        user_id
    ))

    conn.commit()
    conn.close()


def save_practical(
    name,
    code,
    year_group,
    equipment,
    technician_notes=""
):

    conn = connect()

    conn.execute("""
        INSERT INTO practicals
        (
            practical_name,
            code,
            year_group,
            equipment,
            technician_notes,
            active
        )

        VALUES (?, ?, ?, ?, ?, 1)
    """, (
        name.strip(),
        code.strip(),
        year_group,
        equipment.strip(),
        technician_notes.strip()
    ))

    conn.commit()
    conn.close()



def navigate_to_page(page_name):
    st.session_state["current_page"] = page_name


def get_practicals(
    include_inactive=False
):

    conn = connect()

    if include_inactive:

        query = """
            SELECT *
            FROM practicals
            ORDER BY
                code,
                year_group,
                practical_name
        """

    else:

        query = """
            SELECT *
            FROM practicals
            WHERE active = 1
            ORDER BY
                code,
                year_group,
                practical_name
        """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


def update_practical(
    practical_id,
    name,
    code,
    year_group,
    equipment,
    technician_notes,
    active=True
):

    conn = connect()

    conn.execute("""
        UPDATE practicals

        SET
            practical_name = ?,
            code = ?,
            year_group = ?,
            equipment = ?,
            technician_notes = ?,
            active = ?

        WHERE id = ?
    """, (
        name.strip(),
        code.strip(),
        year_group,
        equipment.strip(),
        technician_notes.strip(),
        int(active),
        practical_id
    ))

    conn.commit()
    conn.close()


def get_requisition_deadline(
    practical_date
):

    settings = get_school_settings()

    practical_monday = (
        practical_date
        - timedelta(
            days=practical_date.weekday()
        )
    )

    deadline_weekday = (
        settings["deadline_weekday"]
    )

    # Deadline is in the previous week

    days_before_monday = (
        7 - deadline_weekday
    )

    deadline_date = (
        practical_monday
        - timedelta(
            days=days_before_monday
        )
    )

    deadline_hour, deadline_minute = (
        settings["deadline_time"]
        .split(":")
    )

    return datetime.combine(
        deadline_date,
        time(
            hour=int(deadline_hour),
            minute=int(deadline_minute)
        )
    )


def is_requisition_late(
    practical_date
):

    deadline = get_requisition_deadline(
        practical_date
    )

    return datetime.now() > deadline


def save_requisition(
    teacher_id,
    class_name,
    year_group,
    code,
    room,
    practical_name,
    practical_date,
    period,
    number,
    equipment,
    notes,
    risk_assessment_confirmed
):

    submitted_at = datetime.now()

    late = is_requisition_late(
        practical_date
    )

    if late:

        approval_status = "Pending"

    else:

        approval_status = "Approved"


    conn = connect()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO requisitions
        (
            teacher_id,
            class_name,
            year_group,
            code,
            room,
            practical_name,
            practical_date,
            period,
            number,
            equipment,
            notes,
            risk_assessment_confirmed,
            submitted_at,
            is_late,
            approval_status
        )

        VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
    """, (
        teacher_id,
        class_name.strip(),
        year_group,
        code.strip(),
        room,
        practical_name.strip(),
        str(practical_date),
        period,
        int(number),
        equipment.strip(),
        notes.strip(),
        int(risk_assessment_confirmed),
        submitted_at.isoformat(),
        int(late),
        approval_status
    ))

    requisition_id = (
        cursor.lastrowid
    )

    conn.commit()
    conn.close()

    return requisition_id


def update_requisition(
    requisition_id,
    teacher_id,
    class_name,
    year_group,
    code,
    room,
    practical_name,
    practical_date,
    period,
    number,
    equipment,
    notes
):

    conn = connect()

    conn.execute("""
        UPDATE requisitions

        SET
            teacher_id = ?,
            class_name = ?,
            year_group = ?,
            code = ?,
            room = ?,
            practical_name = ?,
            practical_date = ?,
            period = ?,
            number = ?,
            equipment = ?,
            notes = ?

        WHERE id = ?
    """, (
        teacher_id,
        class_name.strip(),
        year_group,
        code.strip(),
        room,
        practical_name.strip(),
        str(practical_date),
        period,
        int(number),
        equipment.strip(),
        notes.strip(),
        requisition_id
    ))

    conn.commit()
    conn.close()


def delete_requisition(
    requisition_id
):

    # Delete physical attachment files first

    attachments = (
        get_requisition_attachments(
            requisition_id
        )
    )

    for _, attachment in (
        attachments.iterrows()
    ):

        file_path = Path(
            attachment["file_path"]
        )

        if file_path.exists():

            file_path.unlink()


    conn = connect()

    conn.execute(
        """
        DELETE FROM requisitions
        WHERE id = ?
        """,
        (
            requisition_id,
        )
    )

    conn.commit()
    conn.close()



def approve_requisition(
    requisition_id,
    technician_id,
    response=""
):

    conn = connect()

    try:
        cursor = conn.execute("""
            UPDATE requisitions

            SET
                approval_status = 'Approved',
                approved_by = ?,
                approved_at = ?,
                technician_response = ?

            WHERE id = ?
              AND approval_status = 'Pending'
        """, (
            technician_id,
            datetime.now().isoformat(),
            response.strip(),
            requisition_id
        ))

        # How many requisitions were actually updated?
        updated = cursor.rowcount

        conn.commit()

        return updated == 1

    finally:
        conn.close()




def decline_requisition(
    requisition_id,
    technician_id,
    response=""
):

    conn = connect()

    try:
        cursor = conn.execute("""
            UPDATE requisitions

            SET
                approval_status = 'Declined',
                approved_by = ?,
                approved_at = ?,
                technician_response = ?

            WHERE id = ?
              AND approval_status = 'Pending'
        """, (
            technician_id,
            datetime.now().isoformat(),
            response.strip(),
            requisition_id
        ))

        updated = cursor.rowcount

        conn.commit()

        return updated == 1

    finally:
        conn.close()



def get_all_requisitions(
    include_pending=True,
    include_declined=True
):

    conn = connect()

    conditions = []

    if not include_pending:

        conditions.append(
            """
            requisitions.approval_status
            != 'Pending'
            """
        )

    if not include_declined:

        conditions.append(
            """
            requisitions.approval_status
            != 'Declined'
            """
        )


    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )


    query = f"""
        SELECT
            requisitions.id,
            requisitions.teacher_id,

            users.display_name
                AS teacher,

            users.calendar_colour
                AS teacher_colour,

            requisitions.class_name,
            requisitions.year_group,
            requisitions.code,
            requisitions.room,

            requisitions.practical_name,
            requisitions.practical_date,
            requisitions.period,

            requisitions.number,
            requisitions.equipment,
            requisitions.notes,

            requisitions.risk_assessment_confirmed,
            requisitions.submitted_at,
            requisitions.is_late,
            requisitions.approval_status,
            requisitions.approved_by,
            requisitions.approved_at,
            requisitions.technician_response

        FROM requisitions

        JOIN users
            ON requisitions.teacher_id
            = users.id

        {where_clause}

        ORDER BY
            requisitions.practical_date,
            requisitions.period
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


def get_my_requisitions(
    teacher_id
):

    conn = connect()

    df = pd.read_sql_query("""
        SELECT
            requisitions.id,
            requisitions.teacher_id,

            users.display_name
                AS teacher,

            users.calendar_colour
                AS teacher_colour,

            requisitions.class_name,
            requisitions.year_group,
            requisitions.code,
            requisitions.room,

            requisitions.practical_name,
            requisitions.practical_date,
            requisitions.period,

            requisitions.number,
            requisitions.equipment,
            requisitions.notes,

            requisitions.risk_assessment_confirmed,
            requisitions.submitted_at,
            requisitions.is_late,
            requisitions.approval_status,
            requisitions.approved_at,
            requisitions.technician_response

        FROM requisitions

        JOIN users
            ON requisitions.teacher_id
            = users.id

        WHERE requisitions.teacher_id = ?

        ORDER BY
            requisitions.practical_date,
            requisitions.period
    """,
        conn,
        params=(
            teacher_id,
        )
    )

    conn.close()

    return df


def get_pending_requisitions():

    conn = connect()

    df = pd.read_sql_query("""
        SELECT
            requisitions.id,
            requisitions.teacher_id,

            users.display_name
                AS teacher,

            users.calendar_colour
                AS teacher_colour,

            requisitions.class_name,
            requisitions.year_group,
            requisitions.code,
            requisitions.room,

            requisitions.practical_name,
            requisitions.practical_date,
            requisitions.period,

            requisitions.number,
            requisitions.equipment,
            requisitions.notes,

            requisitions.submitted_at,
            requisitions.is_late

        FROM requisitions

        JOIN users
            ON requisitions.teacher_id
            = users.id

        WHERE
            requisitions.approval_status
            = 'Pending'

        ORDER BY
            requisitions.practical_date,
            requisitions.period
    """, conn)

    conn.close()

    return df


def delete_practical(practical_id):

    conn = connect()

    conn.execute(
        """
        DELETE FROM practicals
        WHERE id = ?
        """,
        (
            practical_id,
        )
    )

    conn.commit()
    conn.close()

def save_attachments(
    requisition_id,
    uploaded_files
):

    if not uploaded_files:

        return


    requisition_folder = (
        ATTACHMENTS_FOLDER
        / f"requisition_{requisition_id}"
    )

    requisition_folder.mkdir(
        parents=True,
        exist_ok=True
    )


    conn = connect()

    for uploaded_file in uploaded_files:

        original_filename = (
            uploaded_file.name
        )

        extension = Path(
            original_filename
        ).suffix.lower()


        stored_filename = (
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )


        file_path = (
            requisition_folder
            / stored_filename
        )


        with open(
            file_path,
            "wb"
        ) as file:

            file.write(
                uploaded_file.getbuffer()
            )


        conn.execute("""
            INSERT INTO requisition_attachments
            (
                requisition_id,
                original_filename,
                stored_filename,
                file_path,
                uploaded_at
            )

            VALUES (?, ?, ?, ?, ?)
        """, (
            requisition_id,
            original_filename,
            stored_filename,
            str(file_path),
            datetime.now().isoformat()
        ))


    conn.commit()
    conn.close()


def get_requisition_attachments(
    requisition_id
):

    conn = connect()

    df = pd.read_sql_query("""
        SELECT
            id,
            requisition_id,
            original_filename,
            stored_filename,
            file_path,
            uploaded_at

        FROM requisition_attachments

        WHERE requisition_id = ?

        ORDER BY uploaded_at
    """,
        conn,
        params=(
            requisition_id,
        )
    )

    conn.close()

    return df


def delete_attachment(
    attachment_id
):

    conn = connect()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT file_path
        FROM requisition_attachments
        WHERE id = ?
    """, (
        attachment_id,
    ))

    result = cursor.fetchone()

    if result is not None:

        file_path = Path(
            result[0]
        )

        if file_path.exists():

            file_path.unlink()


    conn.execute("""
        DELETE FROM requisition_attachments
        WHERE id = ?
    """, (
        attachment_id,
    ))

    conn.commit()
    conn.close()


def cleanup_old_attachments():

    settings = get_school_settings()

    retention_weeks = (
        settings[
            "attachment_retention_weeks"
        ]
    )

    cutoff_date = (
        date.today()
        - timedelta(
            weeks=retention_weeks
        )
    )


    conn = connect()

    old_attachments = pd.read_sql_query("""
        SELECT
            requisition_attachments.id,
            requisition_attachments.file_path

        FROM requisition_attachments

        JOIN requisitions

            ON requisition_attachments.requisition_id
            = requisitions.id

        WHERE requisitions.practical_date < ?
    """,
        conn,
        params=(
            str(cutoff_date),
        )
    )


    deleted_count = 0


    for _, attachment in (
        old_attachments.iterrows()
    ):

        file_path = Path(
            attachment["file_path"]
        )

        if file_path.exists():

            file_path.unlink()


        conn.execute("""
            DELETE FROM requisition_attachments
            WHERE id = ?
        """, (
            int(attachment["id"]),
        ))

        deleted_count += 1


    conn.commit()
    conn.close()


    # Remove empty requisition folders

    if ATTACHMENTS_FOLDER.exists():

        for folder in (
            ATTACHMENTS_FOLDER.iterdir()
        ):

            if (
                folder.is_dir()
                and not any(
                    folder.iterdir()
                )
            ):

                folder.rmdir()


    return deleted_count


def open_calendar_practical(current_date, period):

    # Remember which calendar slot was selected.
    st.session_state[
        "calendar_request_date"
    ] = current_date

    st.session_state[
        "calendar_request_period"
    ] = period

    # Navigate to the request page.
    st.session_state[
        "current_page"
    ] = "Request Practical"



# ============================================================
# SETTINGS - ADDITIONAL DATABASE FUNCTIONS
# ============================================================


def set_room_active(
    room_id,
    active
):

    conn = connect()

    conn.execute(
        """
        UPDATE rooms
        SET active = ?
        WHERE id = ?
        """,
        (
            int(active),
            room_id
        )
    )

    conn.commit()
    conn.close()


def set_year_group_active(
    year_group_id,
    active
):

    conn = connect()

    conn.execute(
        """
        UPDATE year_groups
        SET active = ?
        WHERE id = ?
        """,
        (
            int(active),
            year_group_id
        )
    )

    conn.commit()
    conn.close()


def set_period_active(
    period_id,
    active
):

    conn = connect()

    conn.execute(
        """
        UPDATE periods
        SET active = ?
        WHERE id = ?
        """,
        (
            int(active),
            period_id
        )
    )

    conn.commit()
    conn.close()


def get_lesson_time_values(
    day_name,
    year_group,
    period
):

    conn = connect()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            start_time,
            end_time

        FROM lesson_times

        WHERE day_name = ?
        AND year_group = ?
        AND period = ?
        """,
        (
            day_name,
            year_group,
            period
        )
    )

    row = cursor.fetchone()

    conn.close()


    if row is None:

        return None


    return {
        "start_time": row[0],
        "end_time": row[1]
    }




# ============================================================
# CALENDAR DISPLAY
# ============================================================

def show_week_calendar(
    requisitions,
    selected_date,
    show_teacher=False,
    show_status=False,
    calendar_key="calendar"
):

    monday = (
        selected_date
        - timedelta(days=selected_date.weekday())
    )

    st.caption(
        "Week beginning "
        + monday.strftime("%d %B %Y")
    )

    # Use the school's configured periods,
    # rather than hard-coding P1, P2, etc.
    periods = get_period_names()

    if not periods:
        st.warning(
            "No school periods have been configured."
        )
        return

    # Work on a copy of the requisition data.
    requisitions = requisitions.copy()

    if not requisitions.empty:

        requisitions["practical_date"] = (
            pd.to_datetime(
                requisitions["practical_date"]
            ).dt.date
        )

        # The normal calendar shows approved
        # requisitions only.
        if "approval_status" in requisitions.columns:

            requisitions = requisitions[
                requisitions["approval_status"]
                == "Approved"
            ]

    # Six columns:
    # one for period labels and five weekdays.
    column_widths = [0.65, 1, 1, 1, 1, 1]

    header_columns = st.columns(
        column_widths,
        gap="small"
    )

    header_columns[0].markdown("**Period**")

    for day_index in range(5):

        current_date = (
            monday + timedelta(days=day_index)
        )

        with header_columns[day_index + 1]:

            st.markdown(
                "**"
                + current_date.strftime("%A")
                + "**"
            )

            st.caption(
                current_date.strftime("%d %b")
            )

    st.divider()

    # Each period gets a full row across the week.
    for period in periods:

        row_columns = st.columns(
            column_widths,
            gap="small"
        )

        with row_columns[0]:

            st.markdown(f"**{period}**")

        for day_index in range(5):

            current_date = (
                monday + timedelta(days=day_index)
            )

            with row_columns[day_index + 1]:

                # A bordered container makes the
                # timetable slot visible even when
                # there are no practicals.
                with st.container(border=True):

                    if requisitions.empty:

                        slot_requisitions = (
                            requisitions
                        )

                    else:

                        slot_requisitions = (
                            requisitions[
                                (
                                    requisitions[
                                        "practical_date"
                                    ] == current_date
                                )
                                &
                                (
                                    requisitions[
                                        "period"
                                    ] == period
                                )
                            ]
                        )

                    # Show all practicals in this
                    # day/period, not just the first.
                    for _, practical in (
                        slot_requisitions.iterrows()
                    ):

                        teacher_colour = (
                            practical.get(
                                "teacher_colour",
                                "#D9D9D9"
                            )
                        )

                        if (
                            pd.isna(teacher_colour)
                            or not str(
                                teacher_colour
                            ).strip()
                        ):

                            teacher_colour = (
                                "#D9D9D9"
                            )

                        # Escape database text before
                        # displaying it inside HTML.
                        safe_colour = (
                            str(teacher_colour)
                            if str(teacher_colour)
                            in STAFF_COLOURS.values()
                            else "#D9D9D9"
                        )

                        practical_name = html.escape(
                            str(
                                practical[
                                    "practical_name"
                                ]
                            )
                        )

                        class_name = html.escape(
                            str(
                                practical[
                                    "class_name"
                                ]
                            )
                        )

                        room = html.escape(
                            str(practical["room"])
                        )

                        teacher_line = ""

                        if show_teacher:

                            teacher_line = (
                                "<strong>"
                                + html.escape(
                                    str(
                                        practical.get(
                                            "teacher", ""
                                        )
                                    )
                                )
                                + "</strong><br>"
                            )

                        lesson_time = get_lesson_time(
                            current_date,
                            practical["year_group"],
                            period
                        )

                        lesson_time_line = ""

                        if lesson_time:

                            lesson_time_line = (
                                "🕐 "
                                + html.escape(
                                    str(lesson_time)
                                )
                                + "<br>"
                            )

                        late_line = ""

                        if bool(
                            practical.get(
                                "is_late", False
                            )
                        ):

                            late_line = (
                                "⚠ Approved late<br>"
                            )

                        status_line = ""

                        if show_status:

                            status_line = (
                                html.escape(
                                    str(
                                        practical.get(
                                            "approval_status",
                                            ""
                                        )
                                    )
                                )
                                + "<br>"
                            )

                        card_html = f"""
                        <div style="
                            background-color:
                                {safe_colour};
                            color: black;
                            padding: 8px;
                            border-radius: 7px;
                            margin-bottom: 8px;
                            overflow-wrap: anywhere;
                            font-size: 0.85rem;
                        ">
                            <strong>
                                {practical_name}
                            </strong>
                            <br>
                            {teacher_line}
                            Class: {class_name}<br>
                            Room: {room}<br>
                            Sets: {practical["number"]}<br>
                            {lesson_time_line}
                            {late_line}
                            {status_line}
                        </div>
                        """

                        st.html(card_html)

                    # Add button at the bottom of
                    # EVERY timetable slot.
                    #
                    # We disable it for past dates,
                    # because the request form only
                    # permits today or future dates.

                    add_disabled = (
                        current_date < date.today()
                    )

                    
                    st.button(
                        "➕ Add Practical",
                        key=(
                            f"{calendar_key}_"
                            f"{current_date.isoformat()}_"
                            f"{period}"
                        ),
                        use_container_width=True,
                        disabled=add_disabled,
                        on_click=open_calendar_practical,
                        args=(current_date, period)
                    )




# ============================================================
# PAGE SETTINGS
# ============================================================

st.set_page_config(
    page_title="Science Practical Requisition",
    page_icon="🧪",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

if "user" not in st.session_state:
    st.session_state["user"] = None

if "editing_requisition" not in st.session_state:
    st.session_state["editing_requisition"] = None

if "selected_requisition" not in st.session_state:
    st.session_state["selected_requisition"] = None

if "editing_practical" not in st.session_state:
    st.session_state[
        "editing_practical"
    ] = None

if "delete_requisition" not in st.session_state:
    st.session_state[
        "delete_requisition"
    ] = None


# ============================================================
# FIRST-TIME SETUP
# ============================================================

if not users_exist():

    st.title("🧪 Science Practical Requisitions")

    st.subheader("First-Time Setup")

    st.info(
        "No users exist yet. "
        "Create the first technician account."
    )

    with st.form("first_user_form"):

        first_name = st.text_input(
            "Your Name"
        )

        first_username = st.text_input(
            "Username"
        )

        first_password = st.text_input(
            "Password",
            type="password"
        )

        first_password_again = st.text_input(
            "Confirm Password",
            type="password"
        )

        create_first_user = (
            st.form_submit_button(
                "Create Technician Account",
                type="primary"
            )
        )


    if create_first_user:

        if not first_name.strip():

            st.error(
                "Please enter your name."
            )

        elif not first_username.strip():

            st.error(
                "Please enter a username."
            )

        elif not first_password:

            st.error(
                "Please enter a password."
            )

        elif len(first_password) < 8:

            st.error(
                "Your password must contain "
                "at least 8 characters."
            )

        elif first_password != first_password_again:

            st.error(
                "The passwords do not match."
            )

        else:

            success, message = create_user(
                first_username,
                first_password,
                first_name,
                "technician",
                calendar_colour="#D9D9D9",
                must_change_password=False
            )

            if success:

                st.success(
                    "Technician account created. "
                    "You can now log in."
                )

                st.rerun()

            else:

                st.error(message)


    st.stop()


# ============================================================
# GET SCHOOL INFORMATION
# ============================================================

school_settings = get_school_settings()

school_name = school_settings[
    "school_name"
]

department_name = school_settings[
    "department_name"
]


# ============================================================
# LOGIN
# ============================================================

if st.session_state["user"] is None:

    st.title(
        f"🧪 {school_name} "
        f"{department_name} Practical Requisitions"
    )

    st.subheader("Login")

    with st.form("login_form"):

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        login_button = (
            st.form_submit_button(
                "Login",
                type="primary"
            )
        )


    if login_button:

        if not username.strip():

            st.error(
                "Please enter your username."
            )

        elif not password:

            st.error(
                "Please enter your password."
            )

        else:

            user = authenticate_user(
                username,
                password
            )

            if user is not None:

                st.session_state["user"] = user

                st.rerun()

            else:

                st.error(
                    "Incorrect username or password, "
                    "or this account has been deactivated."
                )


    st.stop()


# ============================================================
# CURRENT LOGGED-IN USER
# ============================================================

user = st.session_state["user"]


# ============================================================
# FORCED PASSWORD CHANGE
# ============================================================

if user.get(
    "must_change_password",
    False
):

    st.title("🔐 Change Your Password")

    st.info(
        "You are currently using a temporary password. "
        "Please create your own password before continuing."
    )

    st.write(
        f"Logged in as **{user['display_name']}**"
    )


    with st.form(
        "forced_password_change_form"
    ):

        new_password = st.text_input(
            "New Password",
            type="password"
        )

        new_password_again = st.text_input(
            "Confirm New Password",
            type="password"
        )

        change_password_button = (
            st.form_submit_button(
                "Change Password",
                type="primary"
            )
        )


    if change_password_button:

        if not new_password:

            st.error(
                "Please enter a new password."
            )

        elif len(new_password) < 8:

            st.error(
                "Your password must contain "
                "at least 8 characters."
            )

        elif new_password != new_password_again:

            st.error(
                "The passwords do not match."
            )

        else:

            change_password(
                user["id"],
                new_password
            )

            # Update the copy of the user stored
            # in Streamlit's session.

            st.session_state[
                "user"
            ][
                "must_change_password"
            ] = False

            st.success(
                "Password changed successfully."
            )

            st.rerun()


    # Prevent the user from reaching any other
    # part of the app until the password is changed.

    st.stop()


# ============================================================
# SIDEBAR / ROLE ACCESS
# ============================================================

st.sidebar.title("🧪 Science Practicals")

st.sidebar.write(
    f"Logged in as **{user['display_name']}**"
)

st.sidebar.caption(
    f"Role: {user['role'].title()}"
)


# Show the user's assigned colour

st.sidebar.markdown(
    f"""
    <div style="
        background-color: {user.get('calendar_colour', '#D9D9D9')};
        padding: 6px;
        border-radius: 6px;
        text-align: center;
        color: black;
        margin-bottom: 10px;
    ">
        Staff Colour
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# AVAILABLE PAGES
# ============================================================

if user["role"] == "teacher":

    pages = [
        "Request Practical",
        "My Requisitions",
        "Calendar",
        "My Account"
    ]


elif user["role"] == "technician":

    pages = [
        "Dashboard",
        "Request Practical",
        "Calendar",
        "All Requisitions",
        "Late Approvals",
        "Practical Library",
        "Print Requisitions",
        "Manage Users",
        "Settings",
        "My Account"
    ]


else:

    st.error(
        "Your account has an invalid role."
    )

    st.stop()


# Remember which page the user is viewing.
if (
    "current_page" not in st.session_state
    or st.session_state["current_page"] not in pages
):

    st.session_state["current_page"] = pages[0]


page = st.sidebar.radio(
    "Menu",
    pages,
    key="current_page"
)

# ============================================================
# LOGOUT
# ============================================================

st.sidebar.divider()


if st.sidebar.button(
    "Logout",
    use_container_width=True
):

    st.session_state["user"] = None

    st.session_state[
        "editing_requisition"
    ] = None

    st.session_state[
        "selected_requisition"
    ] = None

    st.rerun()


# ============================================================
# TEACHER - REQUEST PRACTICAL
# ============================================================

if page == "Request Practical":

    if user["role"] not in ("teacher","technician"):

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()

    st.title("➕ Request Practical")

    is_technician = user["role"] == "technician"

    if is_technician:

        st.info(
            "You are creating a requisition on behalf "
            "of a teacher. Select the teacher who "
            "will be using the practical."
        )

        users_df = get_users()

        teachers_df = users_df[
            (users_df["role"] == "teacher")
            & (users_df["active"] == 1)
        ].copy()

        if teachers_df.empty:

            st.error(
                "There are no active teacher accounts. "
                "Please create or activate a teacher "
                "account in Manage Users."
            )

            st.stop()

        teacher_options = {
            f"{row['display_name']} ({row['username']})": int(row["id"])
            for _, row in teachers_df.iterrows()
        }

        selected_teacher = st.selectbox(
            "Request on Behalf Of",
            options=list(teacher_options.keys()),
            key="request_on_behalf_of"
        )

        requisition_teacher_id = teacher_options[
            selected_teacher
        ]

        st.caption(
            "This practical will appear under the "
            "selected teacher's name and calendar colour."
        )

    else:

        requisition_teacher_id = user["id"]

        st.write(
            f"**Teacher:** {user['display_name']}"
        )

    # ========================================================
    # GET CURRENT SCHOOL OPTIONS
    # ========================================================

    year_groups = get_year_group_names()

    periods = get_period_names()

    rooms = get_room_names()


    if not year_groups:

        st.error(
            "No year groups have been configured. "
            "Please ask a technician to add them "
            "in Settings."
        )

        st.stop()


    if not periods:

        st.error(
            "No periods have been configured. "
            "Please ask a technician to add them "
            "in Settings."
        )

        st.stop()


    if not rooms:

        st.error(
            "No rooms have been configured. "
            "Please ask a technician to add them "
            "in Settings."
        )

        st.stop()


    # ========================================================
    # BASIC LESSON INFORMATION
    #
    # These are outside the form deliberately.
    #
    # Changing them reruns the page immediately, allowing
    # lesson times, deadlines and practical choices to update.
    # ========================================================

    st.subheader("Lesson Information")


    info_col1, info_col2 = st.columns(2)


    with info_col1:

        class_name = st.text_input(
            "Class",
            placeholder="e.g. 10X1"
        )


        year_group = st.selectbox(
            "Year Group",
            year_groups
        )


        # Apply a date selected from the calendar,
        # if there is one waiting.
        if "calendar_request_date" in st.session_state:

            st.session_state["request_practical_date"] = (
                st.session_state.pop(
                    "calendar_request_date"
                )
            )

        if "request_practical_date" not in st.session_state:

            st.session_state["request_practical_date"] = (
                date.today()
            )

        practical_date = st.date_input(
            "Date Required",
            min_value=date.today(),
            key="request_practical_date"
        )


    with info_col2:

        # Apply a period selected from the calendar.
        if "calendar_request_period" in st.session_state:

            selected_calendar_period = (
                st.session_state.pop(
                    "calendar_request_period"
                )
            )

            if selected_calendar_period in periods:

                st.session_state[
                        "request_practical_period"
                    ] = selected_calendar_period


        # Ensure the selected period is still valid
        # if school settings have changed.
        if (
            "request_practical_period"
            not in st.session_state
            or st.session_state[
                "request_practical_period"
            ] not in periods
        ):

            st.session_state[
                "request_practical_period"
            ] = periods[0]


        period = st.selectbox(
            "Period",
            periods,
            key="request_practical_period"
        )


        room = st.selectbox(
            "Room",
            rooms
        )


        number = st.number_input(
            "Number of Sets",
            min_value=1,
            max_value=50,
            value=1,
            step=1
        )


    # ========================================================
    # LESSON TIME
    # ========================================================

    lesson_time = get_lesson_time(
        practical_date,
        year_group,
        period
    )


    if lesson_time:

        st.info(
            f"🕐 **{period}: {lesson_time}**"
        )

    else:

        st.caption(
            f"🕐 No lesson time has been configured "
            f"for {year_group}, "
            f"{practical_date.strftime('%A')}, "
            f"{period}."
        )


    # ========================================================
    # DEADLINE INFORMATION
    # ========================================================

    deadline = get_requisition_deadline(
        practical_date
    )


    late = is_requisition_late(
        practical_date
    )


    if late:

        st.warning(
            "⚠️ **This requisition is being submitted "
            "after the normal deadline.**\n\n"
            f"The deadline for this practical was "
            f"**{deadline.strftime('%A %d %B at %H:%M')}**.\n\n"
            "The request will be sent to the technicians "
            "for approval. Preparation cannot be guaranteed."
        )

    else:

        st.caption(
            "Requisition deadline: "
            f"{deadline.strftime('%A %d %B at %H:%M')}"
        )


    st.divider()


    # ========================================================
    # PRACTICAL TYPE
    # ========================================================

    st.subheader("Practical")


    practical_type = st.radio(
        "Practical Type",
        [
            "Pre-set Practical",
            "Custom Practical"
        ],
        horizontal=True
    )


    practical_name = ""

    description = ""

    code = ""

    technician_notes = ""


    # ========================================================
    # PRE-SET PRACTICAL
    # ========================================================

    if practical_type == "Pre-set Practical":

        practicals = get_practicals()


        # Only show practicals for the selected year group

        matching_practicals = practicals[
            practicals["year_group"]
            == year_group
        ].copy()


        if matching_practicals.empty:

            st.warning(
                "There are currently no stored practicals "
                f"for {year_group}."
            )


        else:

            # ------------------------------------------------
            # OPTIONAL SEARCH
            # ------------------------------------------------

            practical_search = st.text_input(
                "Search Practical Library",
                placeholder=(
                    "Search by practical name or code"
                )
            )


            if practical_search.strip():

                search_text = (
                    practical_search.strip()
                )


                matching_practicals = (
                    matching_practicals[
                        matching_practicals[
                            "practical_name"
                        ].str.contains(
                            search_text,
                            case=False,
                            na=False
                        )
                        |
                        matching_practicals[
                            "code"
                        ].astype(str).str.contains(
                            search_text,
                            case=False,
                            na=False
                        )
                    ]
                )


            if matching_practicals.empty:

                st.info(
                    "No practicals match that search."
                )


            else:

                # Make a friendly label:
                #
                # 0.2 — Specific Heat Capacity

                practical_options = {}

                for _, practical in (
                    matching_practicals.iterrows()
                ):

                    label = (
                        f"{practical['code']} — "
                        f"{practical['practical_name']}"
                    )

                    practical_options[
                        label
                    ] = practical["id"]


                selected_label = st.selectbox(
                    "Select Practical",
                    list(
                        practical_options.keys()
                    )
                )


                selected_id = (
                    practical_options[
                        selected_label
                    ]
                )


                selected = (
                    matching_practicals[
                        matching_practicals[
                            "id"
                        ] == selected_id
                    ].iloc[0]
                )


                practical_name = str(
                    selected[
                        "practical_name"
                    ]
                )


                code = str(
                    selected["code"]
                )


                description = str(
                    selected[
                        "equipment"
                    ]
                )


                if pd.notna(
                    selected[
                        "technician_notes"
                    ]
                ):

                    technician_notes = str(
                        selected[
                            "technician_notes"
                        ]
                    )


                st.write(
                    f"**Code:** {code}"
                )


                st.write(
                    "**Standard Requirements:**"
                )


                st.text_area(
                    "Requirements",
                    value=description,
                    height=250,
                    disabled=True,
                    label_visibility="collapsed"
                )


                # Technician notes are deliberately NOT
                # shown to the teacher.
                #
                # They are for the technician team.


    # ========================================================
    # CUSTOM PRACTICAL
    # ========================================================

    else:

        code = st.text_input(
            "Code",
            placeholder=(
                "e.g. 0.2 (optional)"
            )
        )


        practical_name = st.text_input(
            "Practical Name",
            placeholder=(
                "e.g. Specific Heat Capacity"
            )
        )


        description = st.text_area(
            "Requirements",
            height=250,
            placeholder=(
                "Describe the equipment, chemicals, "
                "materials and quantities required."
            )
        )


    # ========================================================
    # ADDITIONAL INFORMATION
    # ========================================================

    st.divider()

    st.subheader(
        "Additional Information"
    )


    notes = st.text_area(
        "Additional Notes",
        height=120,
        placeholder=(
            "Any additional requirements or "
            "information the technicians need to know."
        )
    )


    # ========================================================
    # ATTACHMENTS
    # ========================================================

    uploaded_files = st.file_uploader(
        "Attachments (optional)",
        type=[
            "pdf",
            "docx",
            "xlsx",
            "png",
            "jpg",
            "jpeg"
        ],
        accept_multiple_files=True,
        help=(
            "Attach practical sheets, CPAC instructions, "
            "diagrams, photographs or other supporting "
            "information."
        )
    )


    if uploaded_files:

        st.caption(
            f"{len(uploaded_files)} "
            "attachment(s) selected."
        )


    # ========================================================
    # RISK ASSESSMENT CONFIRMATION
    # ========================================================

    st.divider()


    risk_assessment_confirmed = (
        st.checkbox(
            "I confirm that I have considered the "
            "relevant risk assessment(s) for this practical."
        )
    )


    # ========================================================
    # LATE REQUISITION ACKNOWLEDGEMENT
    # ========================================================

    late_acknowledged = True


    if late:

        late_acknowledged = (
            st.checkbox(
                "I understand that this request is late, "
                "requires technician approval, and that "
                "preparation cannot be guaranteed."
            )
        )


    # ========================================================
    # SUBMIT
    # ========================================================

    submit_requisition = st.button(
        "Submit Requisition",
        type="primary"
    )


    # ========================================================
    # PROCESS SUBMISSION
    # ========================================================

    if submit_requisition:

        if not class_name.strip():

            st.error(
                "Please enter a class."
            )


        elif not practical_name.strip():

            st.error(
                "Please enter or select a practical."
            )


        elif not room:

            st.error(
                "Please select a room."
            )


        elif not description.strip():

            st.error(
                "The practical must have requirements."
            )


        elif not risk_assessment_confirmed:

            st.error(
                "You must confirm that you have considered "
                "the relevant risk assessment(s) before "
                "submitting the requisition."
            )


        elif late and not late_acknowledged:

            st.error(
                "Please confirm that you understand "
                "the late-requisition conditions."
            )


        else:

            requisition_id = save_requisition(
                requisition_teacher_id,
                class_name,
                year_group,
                code,
                room,
                practical_name,
                practical_date,
                period,
                int(number),
                description,
                notes,
                risk_assessment_confirmed
            )


            # ================================================
            # SAVE ATTACHMENTS
            # ================================================

            if uploaded_files:

                save_attachments(
                    requisition_id,
                    uploaded_files
                )


            # ================================================
            # SUCCESS MESSAGE
            # ================================================

            if is_technician:

                if late:

                    st.warning(
                        "Requisition created on behalf of "
                        f"{selected_teacher}. "
                        "It is awaiting technician approval "
                        "because it was submitted late."
                    )

                else:

                    st.success(
                        "Requisition created successfully "
                        f"on behalf of {selected_teacher}."
                    )

            else:

                if late:

                    st.warning(
                        "Requisition submitted successfully, "
                        "but it is awaiting technician approval."
                    )

                else:

                    st.success(
                        "Requisition submitted successfully."
                    )


# ============================================================
# TEACHER - MY REQUISITIONS
# ============================================================

elif page == "My Requisitions":

    if user["role"] != "teacher":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("📋 My Requisitions")


    requisitions = get_my_requisitions(
        user["id"]
    )


    if requisitions.empty:

        st.info(
            "You have not submitted any requisitions."
        )


    else:

        requisitions[
            "practical_date"
        ] = pd.to_datetime(
            requisitions[
                "practical_date"
            ]
        )


        # Most recent/upcoming dates first

        requisitions = (
            requisitions.sort_values(
                [
                    "practical_date",
                    "period"
                ]
            )
        )


        for _, row in requisitions.iterrows():

            # =================================================
            # STATUS
            # =================================================

            status = row[
                "approval_status"
            ]


            is_late = bool(
                row["is_late"]
            )


            if status == "Pending":

                status_icon = "🟠"

                status_text = (
                    "Awaiting Technician Approval"
                )


            elif status == "Declined":

                status_icon = "🔴"

                status_text = "Declined"


            else:

                status_icon = "🟢"

                status_text = "Approved"


            # =================================================
            # EXPANDER TITLE
            # =================================================

            title = (
                f"{status_icon} "
                f"{row['practical_date'].strftime('%A %d %B')} "
                f"— {row['period']} "
                f"— {row['practical_name']}"
            )


            with st.expander(title):

                # =============================================
                # STATUS INFORMATION
                # =============================================

                st.write(
                    f"**Status:** {status_text}"
                )


                if is_late:

                    st.warning(
                        "⚠️ This requisition was submitted "
                        "after the normal deadline."
                    )


                if (
                    status == "Pending"
                    and is_late
                ):

                    st.info(
                        "This request is awaiting technician "
                        "approval. Preparation is not "
                        "guaranteed until it has been approved."
                    )


                elif (
                    status == "Approved"
                    and is_late
                ):

                    st.success(
                        "This late request has been "
                        "approved by a technician."
                    )


                elif status == "Declined":

                    st.error(
                        "This requisition has been "
                        "declined by a technician."
                    )


                # =============================================
                # TECHNICIAN RESPONSE
                # =============================================

                technician_response = row[
                    "technician_response"
                ]


                if (
                    pd.notna(
                        technician_response
                    )
                    and str(
                        technician_response
                    ).strip()
                ):

                    st.write(
                        "**Technician Response:**"
                    )

                    st.write(
                        technician_response
                    )


                st.divider()


                # =============================================
                # LESSON INFORMATION
                # =============================================

                info_col1, info_col2 = (
                    st.columns(2)
                )


                with info_col1:

                    st.write(
                        f"**Class:** "
                        f"{row['class_name']}"
                    )

                    st.write(
                        f"**Year Group:** "
                        f"{row['year_group']}"
                    )

                    st.write(
                        f"**Room:** "
                        f"{row['room']}"
                    )


                with info_col2:

                    st.write(
                        f"**Period:** "
                        f"{row['period']}"
                    )

                    st.write(
                        f"**Number of Sets:** "
                        f"{row['number']}"
                    )


                    if (
                        pd.notna(row["code"])
                        and str(
                            row["code"]
                        ).strip()
                    ):

                        st.write(
                            f"**Code:** "
                            f"{row['code']}"
                        )


                # =============================================
                # LESSON TIME
                # =============================================

                lesson_time = get_lesson_time(
                    row[
                        "practical_date"
                    ].date(),
                    row[
                        "year_group"
                    ],
                    row[
                        "period"
                    ]
                )


                if lesson_time:

                    st.write(
                        f"**Lesson Time:** "
                        f"{lesson_time}"
                    )


                st.divider()


                # =============================================
                # REQUIREMENTS
                # =============================================

                st.write(
                    "**Requirements:**"
                )

                st.text(
                    row["equipment"]
                )


                # =============================================
                # ADDITIONAL NOTES
                # =============================================

                if (
                    pd.notna(row["notes"])
                    and str(
                        row["notes"]
                    ).strip()
                ):

                    st.write(
                        "**Additional Notes:**"
                    )

                    st.write(
                        row["notes"]
                    )


                # =============================================
                # RISK ASSESSMENT
                # =============================================

                if row[
                    "risk_assessment_confirmed"
                ]:

                    st.caption(
                        "✓ Relevant risk assessment(s) "
                        "were confirmed as considered "
                        "when this request was submitted."
                    )


                # =============================================
                # ATTACHMENTS
                # =============================================

                attachments = (
                    get_requisition_attachments(
                        int(row["id"])
                    )
                )


                if not attachments.empty:

                    st.divider()

                    st.write(
                        "**Attachments:**"
                    )


                    for _, attachment in (
                        attachments.iterrows()
                    ):

                        file_path = Path(
                            attachment[
                                "file_path"
                            ]
                        )


                        if file_path.exists():

                            with open(
                                file_path,
                                "rb"
                            ) as file:

                                file_data = (
                                    file.read()
                                )


                            st.download_button(
                                label=(
                                    "📎 "
                                    + attachment[
                                        "original_filename"
                                    ]
                                ),
                                data=file_data,
                                file_name=(
                                    attachment[
                                        "original_filename"
                                    ]
                                ),
                                key=(
                                    f"teacher_attachment_"
                                    f"{attachment['id']}"
                                )
                            )


                        else:

                            st.caption(
                                f"📎 "
                                f"{attachment['original_filename']} "
                                f"— attachment no longer available"
                            )


# ============================================================
# CALENDAR
# ============================================================

elif page == "Calendar":

    st.title(
        "📅 Weekly Practical Calendar"
    )


    # ========================================================
    # TEACHER CALENDAR
    # ========================================================

    if user["role"] == "teacher":

        my_tab, all_tab = st.tabs(
            [
                "👤 My Practicals",
                "👥 All Practicals"
            ]
        )


        # ----------------------------------------------------
        # MY PRACTICALS
        # ----------------------------------------------------

        with my_tab:

            my_selected_date = (
                st.date_input(
                    "Choose a week",
                    value=date.today(),
                    key="my_calendar_week"
                )
            )


            my_requisitions = (
                get_my_requisitions(
                    user["id"]
                )
            )


            show_week_calendar(
                my_requisitions,
                my_selected_date,
                show_teacher=False,
                calendar_key=(
                    "teacher_my"
                )
            )


        # ----------------------------------------------------
        # ALL PRACTICALS
        # ----------------------------------------------------

        with all_tab:

            st.caption(
                "This calendar is read-only. "
                "It allows you to see practicals "
                "already requested across the department."
            )


            all_selected_date = (
                st.date_input(
                    "Choose a week",
                    value=date.today(),
                    key="all_teacher_calendar_week"
                )
            )


            # Exclude pending and declined requests.
            #
            # Teachers should only see confirmed
            # departmental practicals here.

            all_requisitions = (
                get_all_requisitions(
                    include_pending=False,
                    include_declined=False
                )
            )


            show_week_calendar(
                all_requisitions,
                all_selected_date,
                show_teacher=True,
                calendar_key=(
                    "teacher_all"
                )
            )


    # ========================================================
    # TECHNICIAN CALENDAR
    # ========================================================

    elif user["role"] == "technician":

        selected_date = (
            st.date_input(
                "Choose a week",
                value=date.today(),
                key="technician_calendar_week"
            )
        )


        requisitions = (
            get_all_requisitions(
                include_pending=False,
                include_declined=False
            )
        )


        show_week_calendar(
            requisitions,
            selected_date,
            show_teacher=True,
            calendar_key=(
                "technician_calendar"
            )
        )


    else:

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


# ============================================================
# TECHNICIAN DASHBOARD
# ============================================================

elif page == "Dashboard":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("🏠 Technician Dashboard")

    st.write(
        f"Welcome, **{user['display_name']}**."
    )


    # ========================================================
    # GET DATA
    # ========================================================

    requisitions = get_all_requisitions()

    pending_requisitions = (
        get_pending_requisitions()
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    today = date.today()


    if requisitions.empty:

        todays_count = 0
        upcoming_count = 0

    else:

        dashboard_requisitions = (
            requisitions.copy()
        )

        dashboard_requisitions[
            "practical_date"
        ] = pd.to_datetime(
            dashboard_requisitions[
                "practical_date"
            ]
        )


        todays_count = len(
            dashboard_requisitions[
                (
                    dashboard_requisitions[
                        "practical_date"
                    ].dt.date
                    == today
                )
                &
                (
                    dashboard_requisitions[
                        "approval_status"
                    ]
                    == "Approved"
                )
            ]
        )


        end_of_week = (
            today
            + timedelta(days=7)
        )


        upcoming_count = len(
            dashboard_requisitions[
                (
                    dashboard_requisitions[
                        "practical_date"
                    ].dt.date
                    >= today
                )
                &
                (
                    dashboard_requisitions[
                        "practical_date"
                    ].dt.date
                    <= end_of_week
                )
                &
                (
                    dashboard_requisitions[
                        "approval_status"
                    ]
                    == "Approved"
                )
            ]
        )


    pending_count = len(
        pending_requisitions
    )


    metric1, metric2, metric3 = (
        st.columns(3)
    )


    with metric1:

        st.metric(
            "Today's Practicals",
            todays_count
        )


    with metric2:

        st.metric(
            "Next 7 Days",
            upcoming_count
        )


    with metric3:

        st.metric(
            "Late Requests Awaiting Approval",
            pending_count
        )


    st.divider()


    # ========================================================
    # PENDING LATE REQUEST WARNING
    # ========================================================

    if pending_count > 0:

        st.warning(
            f"⚠️ There "
            f"{'is' if pending_count == 1 else 'are'} "
            f"**{pending_count}** late "
            f"{'request' if pending_count == 1 else 'requests'} "
            "waiting for technician approval.\n\n"
            "Open **Late Approvals** from the sidebar "
            "to review them."
        )


    # ========================================================
    # TODAY'S PRACTICALS
    # ========================================================

    st.subheader("Today's Practicals")


    if requisitions.empty:

        st.info(
            "No requisitions have been submitted."
        )


    else:

        todays_requisitions = (
            dashboard_requisitions[
                (
                    dashboard_requisitions[
                        "practical_date"
                    ].dt.date
                    == today
                )
                &
                (
                    dashboard_requisitions[
                        "approval_status"
                    ]
                    == "Approved"
                )
            ]
        )


        todays_requisitions = (
            todays_requisitions.sort_values(
                "period"
            )
        )


        if todays_requisitions.empty:

            st.info(
                "No approved practicals today."
            )


        else:

            for _, row in (
                todays_requisitions.iterrows()
            ):

                teacher_colour = row.get(
                    "teacher_colour",
                    "#D9D9D9"
                )


                if (
                    pd.isna(teacher_colour)
                    or not str(
                        teacher_colour
                    ).strip()
                ):

                    teacher_colour = (
                        "#D9D9D9"
                    )


                lesson_time = (
                    get_lesson_time(
                        row[
                            "practical_date"
                        ].date(),
                        row["year_group"],
                        row["period"]
                    )
                )


                time_text = ""

                if lesson_time:

                    time_text = (
                        f" • {lesson_time}"
                    )


                st.markdown(
                    f"""
                    <div style="
                        border-left:
                            8px solid {teacher_colour};
                        padding:
                            10px 14px;
                        margin-bottom:
                            10px;
                        background-color:
                            rgba(128,128,128,0.08);
                        border-radius:
                            6px;
                    ">

                    <strong>
                        {row['period']}
                        {time_text}
                        —
                        {row['practical_name']}
                    </strong>

                    <br>

                    {row['teacher']}
                    •
                    {row['class_name']}
                    •
                    {row['room']}
                    •
                    {row['number']} set(s)

                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ============================================================
# TECHNICIAN - ALL REQUISITIONS
# ============================================================

elif page == "All Requisitions":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("📋 All Requisitions")


    requisitions = get_all_requisitions()


    if requisitions.empty:

        st.info(
            "No requisitions have been submitted."
        )


    else:

        requisitions[
            "practical_date"
        ] = pd.to_datetime(
            requisitions[
                "practical_date"
            ]
        )


        # ====================================================
        # FILTERS
        # ====================================================

        st.subheader("Filters")


        filter_col1, filter_col2 = (
            st.columns(2)
        )


        filter_col3, filter_col4 = (
            st.columns(2)
        )


        # ----------------------------------------------------
        # ROOM
        # ----------------------------------------------------

        with filter_col1:

            room_filter = st.selectbox(
                "Room",
                ["All"]
                + get_room_names(),
                key="all_req_room_filter"
            )


        # ----------------------------------------------------
        # TEACHER
        # ----------------------------------------------------

        teacher_names = sorted(
            requisitions[
                "teacher"
            ].dropna().unique().tolist()
        )


        with filter_col2:

            teacher_filter = st.selectbox(
                "Teacher",
                ["All"]
                + teacher_names,
                key="all_req_teacher_filter"
            )


        # ----------------------------------------------------
        # YEAR GROUP
        # ----------------------------------------------------

        with filter_col3:

            year_filter = st.selectbox(
                "Year Group",
                ["All"]
                + get_year_group_names(),
                key="all_req_year_filter"
            )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        with filter_col4:

            status_filter = st.selectbox(
                "Status",
                [
                    "All",
                    "Approved",
                    "Pending",
                    "Declined"
                ],
                key="all_req_status_filter"
            )


        # ====================================================
        # DATE FILTER
        # ====================================================

        use_date_filter = st.checkbox(
            "Filter by date range"
        )


        if use_date_filter:

            date_col1, date_col2 = (
                st.columns(2)
            )


            with date_col1:

                start_date = st.date_input(
                    "From",
                    value=date.today(),
                    key="all_req_start_date"
                )


            with date_col2:

                end_date = st.date_input(
                    "To",
                    value=(
                        date.today()
                        + timedelta(days=7)
                    ),
                    key="all_req_end_date"
                )


        # ====================================================
        # APPLY FILTERS
        # ====================================================

        filtered = requisitions.copy()


        if room_filter != "All":

            filtered = filtered[
                filtered["room"]
                == room_filter
            ]


        if teacher_filter != "All":

            filtered = filtered[
                filtered["teacher"]
                == teacher_filter
            ]


        if year_filter != "All":

            filtered = filtered[
                filtered["year_group"]
                == year_filter
            ]


        if status_filter != "All":

            filtered = filtered[
                filtered[
                    "approval_status"
                ]
                == status_filter
            ]


        if use_date_filter:

            filtered = filtered[
                (
                    filtered[
                        "practical_date"
                    ].dt.date
                    >= start_date
                )
                &
                (
                    filtered[
                        "practical_date"
                    ].dt.date
                    <= end_date
                )
            ]


        # ====================================================
        # RESULTS
        # ====================================================

        st.divider()


        st.caption(
            f"{len(filtered)} "
            f"{'requisition' if len(filtered) == 1 else 'requisitions'}"
        )


        if filtered.empty:

            st.info(
                "No requisitions match those filters."
            )


        else:

            filtered = filtered.sort_values(
                [
                    "practical_date",
                    "period"
                ]
            )


            for _, row in (
                filtered.iterrows()
            ):

                # =============================================
                # STATUS
                # =============================================

                status = row[
                    "approval_status"
                ]


                if status == "Pending":

                    status_icon = "🟠"

                elif status == "Declined":

                    status_icon = "🔴"

                else:

                    status_icon = "🟢"


                late_marker = ""

                if bool(
                    row["is_late"]
                ):

                    late_marker = " ⚠️"


                # =============================================
                # TITLE
                # =============================================

                title = (
                    f"{status_icon} "
                    f"{row['practical_date'].strftime('%A %d %B')} "
                    f"— {row['period']} "
                    f"— {row['practical_name']} "
                    f"— {row['teacher']}"
                    f"{late_marker}"
                )


                with st.expander(title):

                    # =========================================
                    # TEACHER COLOUR
                    # =========================================

                    teacher_colour = row.get(
                        "teacher_colour",
                        "#D9D9D9"
                    )


                    st.markdown(
                        f"""
                        <div style="
                            background-color:
                                {teacher_colour};
                            color: black;
                            padding: 7px 10px;
                            border-radius: 6px;
                            display: inline-block;
                            margin-bottom: 10px;
                        ">
                            <strong>
                                {row['teacher']}
                            </strong>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                    # =========================================
                    # STATUS
                    # =========================================

                    st.write(
                        f"**Status:** "
                        f"{status}"
                    )


                    if bool(
                        row["is_late"]
                    ):

                        st.warning(
                            "⚠️ This requisition was "
                            "submitted after the normal "
                            "deadline."
                        )


                    # =========================================
                    # INFORMATION
                    # =========================================

                    info1, info2 = (
                        st.columns(2)
                    )


                    with info1:

                        st.write(
                            f"**Class:** "
                            f"{row['class_name']}"
                        )

                        st.write(
                            f"**Year Group:** "
                            f"{row['year_group']}"
                        )

                        st.write(
                            f"**Room:** "
                            f"{row['room']}"
                        )


                    with info2:

                        st.write(
                            f"**Period:** "
                            f"{row['period']}"
                        )

                        st.write(
                            f"**Number of Sets:** "
                            f"{row['number']}"
                        )


                        if (
                            pd.notna(row["code"])
                            and str(
                                row["code"]
                            ).strip()
                        ):

                            st.write(
                                f"**Code:** "
                                f"{row['code']}"
                            )


                    lesson_time = (
                        get_lesson_time(
                            row[
                                "practical_date"
                            ].date(),
                            row["year_group"],
                            row["period"]
                        )
                    )


                    if lesson_time:

                        st.write(
                            f"**Lesson Time:** "
                            f"{lesson_time}"
                        )


                    # =========================================
                    # REQUIREMENTS
                    # =========================================

                    st.divider()

                    st.write(
                        "**Requirements:**"
                    )

                    st.text(
                        row["equipment"]
                    )


                    # =========================================
                    # ADDITIONAL NOTES
                    # =========================================

                    if (
                        pd.notna(row["notes"])
                        and str(
                            row["notes"]
                        ).strip()
                    ):

                        st.write(
                            "**Teacher Additional Notes:**"
                        )

                        st.write(
                            row["notes"]
                        )


                    # =========================================
                    # RISK ASSESSMENT
                    # =========================================

                    if row[
                        "risk_assessment_confirmed"
                    ]:

                        st.caption(
                            "✓ Teacher confirmed that "
                            "the relevant risk assessment(s) "
                            "were considered."
                        )

                    else:

                        st.warning(
                            "No risk-assessment confirmation "
                            "is recorded for this requisition."
                        )


                    # =========================================
                    # ATTACHMENTS
                    # =========================================

                    attachments = (
                        get_requisition_attachments(
                            int(row["id"])
                        )
                    )


                    if not attachments.empty:

                        st.divider()

                        st.write(
                            "**Attachments:**"
                        )


                        for _, attachment in (
                            attachments.iterrows()
                        ):

                            file_path = Path(
                                attachment[
                                    "file_path"
                                ]
                            )


                            if file_path.exists():

                                with open(
                                    file_path,
                                    "rb"
                                ) as file:

                                    file_data = (
                                        file.read()
                                    )


                                st.download_button(
                                    label=(
                                        "📎 "
                                        + attachment[
                                            "original_filename"
                                        ]
                                    ),
                                    data=file_data,
                                    file_name=(
                                        attachment[
                                            "original_filename"
                                        ]
                                    ),
                                    key=(
                                        f"tech_attachment_"
                                        f"{attachment['id']}"
                                    )
                                )


                            else:

                                st.caption(
                                    f"📎 "
                                    f"{attachment['original_filename']} "
                                    "— file no longer available"
                                )


                    # =========================================
                    # TECHNICIAN RESPONSE
                    # =========================================

                    if (
                        pd.notna(
                            row[
                                "technician_response"
                            ]
                        )
                        and str(
                            row[
                                "technician_response"
                            ]
                        ).strip()
                    ):

                        st.divider()

                        st.write(
                            "**Technician Response:**"
                        )

                        st.write(
                            row[
                                "technician_response"
                            ]
                        )


                    # =========================================
                    # ACTION BUTTONS
                    # =========================================

                    st.divider()


                    action_col1, action_col2 = (
                        st.columns(2)
                    )


                    with action_col1:

                        if st.button(
                            "✏️ Edit / Move",
                            key=(
                                f"edit_req_"
                                f"{row['id']}"
                            ),
                            use_container_width=True
                        ):

                            st.session_state[
                                "editing_requisition"
                            ] = int(
                                row["id"]
                            )

                            st.rerun()


                    with action_col2:

                        if st.button(
                            "🗑️ Delete",
                            key=(
                                f"delete_req_"
                                f"{row['id']}"
                            ),
                            use_container_width=True
                        ):

                            st.session_state[
                                "delete_requisition"
                            ] = int(
                                row["id"]
                            )

                            st.rerun()


        # ====================================================
        # EDIT / MOVE REQUISITION
        # ====================================================

        editing_id = st.session_state.get(
            "editing_requisition"
        )


        if editing_id is not None:

            edit_rows = requisitions[
                requisitions["id"]
                == editing_id
            ]


            if not edit_rows.empty:

                edit_row = (
                    edit_rows.iloc[0]
                )


                st.divider()

                st.subheader(
                    "✏️ Edit / Move Requisition"
                )


                st.info(
                    f"Editing: "
                    f"**{edit_row['practical_name']}** "
                    f"for "
                    f"**{edit_row['teacher']}**"
                )


                # =============================================
                # GET TEACHERS
                # =============================================

                users_df = get_users()


                teachers_df = users_df[
                    (
                        users_df["role"]
                        == "teacher"
                    )
                    &
                    (
                        users_df["active"]
                        == 1
                    )
                ]


                teacher_options = {
                    row[
                        "display_name"
                    ]: int(row["id"])

                    for _, row
                    in teachers_df.iterrows()
                }


                teacher_names = list(
                    teacher_options.keys()
                )


                current_teacher = (
                    edit_row["teacher"]
                )


                if (
                    current_teacher
                    in teacher_names
                ):

                    teacher_index = (
                        teacher_names.index(
                            current_teacher
                        )
                    )

                else:

                    teacher_index = 0


                # =============================================
                # EDIT FORM
                # =============================================

                with st.form(
                    f"edit_requisition_form_"
                    f"{editing_id}"
                ):

                    edit_teacher_name = (
                        st.selectbox(
                            "Teacher",
                            teacher_names,
                            index=teacher_index
                        )
                    )


                    edit_class = st.text_input(
                        "Class",
                        value=str(
                            edit_row[
                                "class_name"
                            ]
                        )
                    )


                    year_options = (
                        get_year_group_names()
                    )


                    current_year = str(
                        edit_row[
                            "year_group"
                        ]
                    )


                    year_index = (
                        year_options.index(
                            current_year
                        )
                        if current_year
                        in year_options
                        else 0
                    )


                    edit_year = st.selectbox(
                        "Year Group",
                        year_options,
                        index=year_index
                    )


                    edit_code = st.text_input(
                        "Code",
                        value=(
                            ""
                            if pd.isna(
                                edit_row["code"]
                            )
                            else str(
                                edit_row[
                                    "code"
                                ]
                            )
                        )
                    )


                    room_options = (
                        get_room_names()
                    )


                    current_room = str(
                        edit_row["room"]
                    )


                    room_index = (
                        room_options.index(
                            current_room
                        )
                        if current_room
                        in room_options
                        else 0
                    )


                    edit_room = st.selectbox(
                        "Room",
                        room_options,
                        index=room_index
                    )


                    edit_name = st.text_input(
                        "Practical Name",
                        value=str(
                            edit_row[
                                "practical_name"
                            ]
                        )
                    )


                    edit_date = st.date_input(
                        "Date Required",
                        value=edit_row[
                            "practical_date"
                        ].date()
                    )


                    period_options = (
                        get_period_names()
                    )


                    current_period = str(
                        edit_row["period"]
                    )


                    period_index = (
                        period_options.index(
                            current_period
                        )
                        if current_period
                        in period_options
                        else 0
                    )


                    edit_period = st.selectbox(
                        "Period",
                        period_options,
                        index=period_index
                    )


                    edit_number = (
                        st.number_input(
                            "Number of Sets",
                            min_value=1,
                            max_value=50,
                            value=int(
                                edit_row[
                                    "number"
                                ]
                            ),
                            step=1
                        )
                    )


                    edit_equipment = (
                        st.text_area(
                            "Requirements",
                            value=str(
                                edit_row[
                                    "equipment"
                                ]
                            ),
                            height=250
                        )
                    )


                    edit_notes = (
                        st.text_area(
                            "Additional Notes",
                            value=(
                                ""
                                if pd.isna(
                                    edit_row[
                                        "notes"
                                    ]
                                )
                                else str(
                                    edit_row[
                                        "notes"
                                    ]
                                )
                            ),
                            height=120
                        )
                    )


                    save_edit = (
                        st.form_submit_button(
                            "Save Changes",
                            type="primary"
                        )
                    )


                cancel_edit = st.button(
                    "Cancel Editing",
                    key="cancel_req_edit"
                )


                if save_edit:

                    selected_teacher_id = (
                        teacher_options[
                            edit_teacher_name
                        ]
                    )


                    if not edit_class.strip():

                        st.error(
                            "Please enter a class."
                        )


                    elif not edit_name.strip():

                        st.error(
                            "Please enter a practical name."
                        )


                    elif not edit_equipment.strip():

                        st.error(
                            "Please enter the requirements."
                        )


                    else:

                        update_requisition(
                            editing_id,
                            selected_teacher_id,
                            edit_class,
                            edit_year,
                            edit_code,
                            edit_room,
                            edit_name,
                            edit_date,
                            edit_period,
                            int(edit_number),
                            edit_equipment,
                            edit_notes
                        )


                        st.session_state[
                            "editing_requisition"
                        ] = None


                        st.success(
                            "Requisition updated."
                        )

                        st.rerun()


                if cancel_edit:

                    st.session_state[
                        "editing_requisition"
                    ] = None

                    st.rerun()


        # ====================================================
        # DELETE CONFIRMATION
        # ====================================================

        delete_id = st.session_state.get(
            "delete_requisition"
        )


        if delete_id is not None:

            delete_rows = requisitions[
                requisitions["id"]
                == delete_id
            ]


            if not delete_rows.empty:

                delete_row = (
                    delete_rows.iloc[0]
                )


                st.divider()

                st.error(
                    "⚠️ Delete Requisition"
                )


                st.write(
                    "Are you sure you want to delete:"
                )


                st.write(
                    f"**{delete_row['practical_name']}** "
                    f"— {delete_row['teacher']} "
                    f"— "
                    f"{delete_row['practical_date'].strftime('%A %d %B')} "
                    f"— {delete_row['period']}?"
                )


                st.caption(
                    "Any attachments belonging to this "
                    "requisition will also be deleted."
                )


                delete_col1, delete_col2 = (
                    st.columns(2)
                )


                with delete_col1:

                    confirm_delete = (
                        st.button(
                            "Yes, Delete",
                            type="primary",
                            key=(
                                f"confirm_delete_"
                                f"{delete_id}"
                            ),
                            use_container_width=True
                        )
                    )


                with delete_col2:

                    cancel_delete = (
                        st.button(
                            "Cancel",
                            key=(
                                f"cancel_delete_"
                                f"{delete_id}"
                            ),
                            use_container_width=True
                        )
                    )


                if confirm_delete:

                    delete_requisition(
                        delete_id
                    )


                    st.session_state[
                        "delete_requisition"
                    ] = None


                    st.success(
                        "Requisition deleted."
                    )

                    st.rerun()


                if cancel_delete:

                    st.session_state[
                        "delete_requisition"
                    ] = None

                    st.rerun()


# ============================================================
# TECHNICIAN - PRACTICAL LIBRARY
# ============================================================

elif page == "Practical Library":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("📚 Practical Library")


    # ========================================================
    # SUCCESS MESSAGES
    # ========================================================

    practical_message = st.session_state.pop(
        "practical_library_message",
        None
    )

    if practical_message:

        st.success(
            practical_message,
            icon="✅"
        )


    view_tab, add_tab = st.tabs(
        [
            "View / Edit / Delete Practicals",
            "Add Practical"
        ]
    )


    # ========================================================
    # VIEW / EDIT / DELETE PRACTICALS
    # ========================================================

    with view_tab:

        practicals = get_practicals(
            include_inactive=True
        )


        if practicals.empty:

            st.info(
                "No stored practicals yet."
            )


        else:

            # ------------------------------------------------
            # FILTERS
            # ------------------------------------------------

            filter_col1, filter_col2 = st.columns(2)


            with filter_col1:

                search = st.text_input(
                    "Search Practical Library",
                    placeholder=(
                        "Search by practical name "
                        "or code"
                    ),
                    key="library_search"
                )


            with filter_col2:

                library_year = st.selectbox(
                    "Year Group",
                    ["All"]
                    + get_year_group_names(),
                    key="library_filter_year"
                )


            show_inactive = st.checkbox(
                "Show inactive practicals",
                value=False,
                key="library_show_inactive"
            )


            filtered_practicals = practicals.copy()


            if not show_inactive:

                filtered_practicals = (
                    filtered_practicals[
                        filtered_practicals[
                            "active"
                        ] == 1
                    ]
                )


            if search.strip():

                search_text = search.strip()

                filtered_practicals = (
                    filtered_practicals[
                        filtered_practicals[
                            "practical_name"
                        ].str.contains(
                            search_text,
                            case=False,
                            na=False
                        )
                        |
                        filtered_practicals[
                            "code"
                        ].astype(str).str.contains(
                            search_text,
                            case=False,
                            na=False
                        )
                    ]
                )


            if library_year != "All":

                filtered_practicals = (
                    filtered_practicals[
                        filtered_practicals[
                            "year_group"
                        ] == library_year
                    ]
                )


            # ------------------------------------------------
            # DISPLAY PRACTICALS
            # ------------------------------------------------

            if filtered_practicals.empty:

                st.info(
                    "No practicals match your filters."
                )


            else:

                for _, practical in (
                    filtered_practicals.iterrows()
                ):

                    practical_id = int(
                        practical["id"]
                    )

                    inactive_text = ""

                    if not bool(
                        practical["active"]
                    ):

                        inactive_text = (
                            " — INACTIVE"
                        )


                    title = (
                        f"{practical['code']} "
                        f"— {practical['year_group']} "
                        f"— {practical['practical_name']}"
                        f"{inactive_text}"
                    )


                    with st.expander(title):

                        st.write(
                            "**Standard Requirements:**"
                        )

                        st.text(
                            str(
                                practical["equipment"]
                            )
                        )


                        if (
                            pd.notna(
                                practical[
                                    "technician_notes"
                                ]
                            )
                            and str(
                                practical[
                                    "technician_notes"
                                ]
                            ).strip()
                        ):

                            st.write(
                                "**Technician Notes:**"
                            )

                            st.text(
                                str(
                                    practical[
                                        "technician_notes"
                                    ]
                                )
                            )


                        st.divider()


                        action_col1, action_col2 = (
                            st.columns(2)
                        )


                        with action_col1:

                            edit_button = st.button(
                                "✏️ Edit Practical",
                                key=(
                                    f"edit_practical_"
                                    f"{practical_id}"
                                ),
                                use_container_width=True
                            )


                        with action_col2:

                            delete_button = st.button(
                                "🗑️ Delete Practical",
                                key=(
                                    f"delete_practical_"
                                    f"{practical_id}"
                                ),
                                use_container_width=True
                            )


                        if edit_button:

                            st.session_state[
                                "editing_practical"
                            ] = practical_id

                            st.session_state[
                                "deleting_practical"
                            ] = None

                            st.rerun()


                        if delete_button:

                            st.session_state[
                                "deleting_practical"
                            ] = practical_id

                            st.session_state[
                                "editing_practical"
                            ] = None

                            st.rerun()


            # =================================================
            # EDIT PRACTICAL
            # =================================================

            editing_practical_id = (
                st.session_state.get(
                    "editing_practical"
                )
            )


            if editing_practical_id is not None:

                editing_rows = practicals[
                    practicals["id"]
                    == editing_practical_id
                ]


                if not editing_rows.empty:

                    practical = (
                        editing_rows.iloc[0]
                    )


                    st.divider()

                    st.subheader(
                        "✏️ Edit Stored Practical"
                    )


                    year_options = (
                        get_year_group_names()
                    )


                    current_year = str(
                        practical["year_group"]
                    )


                    if (
                        current_year
                        not in year_options
                    ):

                        year_options = (
                            [current_year]
                            + year_options
                        )


                    current_year_index = (
                        year_options.index(
                            current_year
                        )
                    )


                    current_tech_notes = ""

                    if pd.notna(
                        practical[
                            "technician_notes"
                        ]
                    ):

                        current_tech_notes = str(
                            practical[
                                "technician_notes"
                            ]
                        )


                    with st.form(
                        "edit_practical_form"
                    ):

                        edit_code = st.text_input(
                            "Code",
                            value=str(
                                practical["code"]
                            )
                        )


                        edit_year = st.selectbox(
                            "Year Group",
                            year_options,
                            index=current_year_index
                        )


                        edit_name = st.text_input(
                            "Practical Name",
                            value=str(
                                practical[
                                    "practical_name"
                                ]
                            )
                        )


                        edit_requirements = (
                            st.text_area(
                                "Standard Requirements",
                                value=str(
                                    practical[
                                        "equipment"
                                    ]
                                ),
                                height=300
                            )
                        )


                        edit_tech_notes = (
                            st.text_area(
                                "Technician Notes",
                                value=(
                                    current_tech_notes
                                ),
                                height=150,
                                help=(
                                    "These notes are for "
                                    "technicians and are not "
                                    "shown to teachers."
                                )
                            )
                        )


                        edit_active = st.checkbox(
                            "Active",
                            value=bool(
                                practical["active"]
                            ),
                            help=(
                                "Inactive practicals are "
                                "kept in the library but "
                                "cannot be selected by "
                                "teachers."
                            )
                        )


                        save_practical_changes = (
                            st.form_submit_button(
                                "Save Changes",
                                type="primary",
                                use_container_width=True
                            )
                        )


                    cancel_practical_edit = (
                        st.button(
                            "Cancel Editing",
                            key=(
                                "cancel_practical_edit"
                            )
                        )
                    )


                    if save_practical_changes:

                        if not edit_name.strip():

                            st.error(
                                "Please enter a "
                                "practical name."
                            )


                        elif not (
                            edit_requirements.strip()
                        ):

                            st.error(
                                "Please enter the "
                                "standard requirements."
                            )


                        else:

                            update_practical(
                                editing_practical_id,
                                edit_name,
                                edit_code,
                                edit_year,
                                edit_requirements,
                                edit_tech_notes,
                                edit_active
                            )


                            st.session_state[
                                "editing_practical"
                            ] = None

                            st.session_state[
                                "practical_library_message"
                            ] = (
                                "Practical successfully "
                                "updated."
                            )

                            st.rerun()


                    if cancel_practical_edit:

                        st.session_state[
                            "editing_practical"
                        ] = None

                        st.rerun()


            # =================================================
            # DELETE PRACTICAL
            # =================================================

            deleting_practical_id = (
                st.session_state.get(
                    "deleting_practical"
                )
            )


            if deleting_practical_id is not None:

                deleting_rows = practicals[
                    practicals["id"]
                    == deleting_practical_id
                ]


                if not deleting_rows.empty:

                    practical = (
                        deleting_rows.iloc[0]
                    )


                    st.divider()

                    st.error(
                        "⚠️ Delete Stored Practical"
                    )


                    st.write(
                        "Are you sure you want to "
                        "permanently delete:"
                    )


                    st.write(
                        f"**{practical['code']} — "
                        f"{practical['year_group']} — "
                        f"{practical['practical_name']}**"
                    )


                    st.warning(
                        "This removes the practical from "
                        "the stored practical library. "
                        "Existing requisitions that have "
                        "already used this practical will "
                        "not be deleted."
                    )


                    delete_col1, delete_col2 = (
                        st.columns(2)
                    )


                    with delete_col1:

                        confirm_delete = st.button(
                            "🗑️ Yes, Permanently Delete",
                            type="primary",
                            key=(
                                "confirm_delete_practical_"
                                f"{deleting_practical_id}"
                            ),
                            use_container_width=True
                        )


                    with delete_col2:

                        cancel_delete = st.button(
                            "Cancel",
                            key=(
                                "cancel_delete_practical_"
                                f"{deleting_practical_id}"
                            ),
                            use_container_width=True
                        )


                    if confirm_delete:

                        deleted_name = str(
                            practical[
                                "practical_name"
                            ]
                        )

                        delete_practical(
                            deleting_practical_id
                        )

                        st.session_state[
                            "deleting_practical"
                        ] = None

                        st.session_state[
                            "practical_library_message"
                        ] = (
                            f'"{deleted_name}" was '
                            f"successfully deleted."
                        )

                        st.rerun()


                    if cancel_delete:

                        st.session_state[
                            "deleting_practical"
                        ] = None

                        st.rerun()


    # ========================================================
    # ADD PRACTICAL
    # ========================================================

    with add_tab:

        st.subheader(
            "➕ Add a Stored Practical"
        )


        st.caption(
            "Stored practicals will be available "
            "for teachers to select when making "
            "a requisition."
        )


        year_options = (
            get_year_group_names()
        )


        if not year_options:

            st.warning(
                "No year groups have been configured. "
                "Add them in Settings first."
            )


        else:

            with st.form(
                "add_practical_form",
                clear_on_submit=True
            ):

                new_code = st.text_input(
                    "Code",
                    placeholder="e.g. 4.2"
                )


                new_year_group = st.selectbox(
                    "Year Group",
                    year_options
                )


                new_name = st.text_input(
                    "Practical Name"
                )


                new_description = (
                    st.text_area(
                        "Standard Requirements",
                        height=300,
                        placeholder=(
                            "Enter equipment, chemicals, "
                            "quantities and any other "
                            "standard requirements."
                        )
                    )
                )


                new_technician_notes = (
                    st.text_area(
                        "Technician Notes",
                        height=150,
                        placeholder=(
                            "Optional internal notes "
                            "for technicians."
                        ),
                        help=(
                            "Teachers will not see "
                            "these notes."
                        )
                    )
                )


                add_practical_button = (
                    st.form_submit_button(
                        "Add Practical",
                        type="primary",
                        use_container_width=True
                    )
                )


            if add_practical_button:

                if not new_name.strip():

                    st.error(
                        "Please enter a "
                        "practical name."
                    )


                elif not (
                    new_description.strip()
                ):

                    st.error(
                        "Please enter the "
                        "standard requirements."
                    )


                else:

                    save_practical(
                        new_name,
                        new_code,
                        new_year_group,
                        new_description,
                        new_technician_notes
                    )


                    st.session_state[
                        "practical_library_message"
                    ] = (
                        f'Practical "{new_name}" '
                        f"successfully added to "
                        f"the library."
                    )

                    st.rerun()


# ============================================================
# TECHNICIAN - MANAGE USERS
# ============================================================

elif page == "Manage Users":

    if user["role"] != "technician":
        st.error(
            "You do not have permission "
            "to access this page."
        )
        st.stop()

    st.title("👥 Manage Users")

    st.caption(
        "Create and manage teacher and technician accounts."
    )

    current_users_tab, add_user_tab = st.tabs(
        [
            "Current Users",
            "Add User"
        ]
    )

    # ========================================================
    # CURRENT USERS
    # ========================================================

    with current_users_tab:

        users = get_users()

        if users.empty:

            st.info("No users found.")

        else:

            # ------------------------------------------------
            # FILTERS
            # ------------------------------------------------

            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:

                user_search = st.text_input(
                    "Search Users",
                    placeholder="Search by name or username",
                    key="manage_users_search"
                )

            with filter_col2:

                role_filter = st.selectbox(
                    "Role",
                    [
                        "All",
                        "teacher",
                        "technician"
                    ],
                    key="manage_users_role_filter"
                )

            show_inactive = st.checkbox(
                "Show inactive users",
                value=False,
                key="manage_users_show_inactive"
            )

            filtered_users = users.copy()

            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            if user_search.strip():

                search_text = (
                    user_search
                    .strip()
                    .lower()
                )

                filtered_users = filtered_users[
                    filtered_users[
                        "display_name"
                    ].str.lower().str.contains(
                        search_text,
                        na=False
                    )
                    |
                    filtered_users[
                        "username"
                    ].str.lower().str.contains(
                        search_text,
                        na=False
                    )
                ]

            # ------------------------------------------------
            # ROLE FILTER
            # ------------------------------------------------

            if role_filter != "All":

                filtered_users = filtered_users[
                    filtered_users["role"]
                    == role_filter
                ]

            # ------------------------------------------------
            # ACTIVE FILTER
            # ------------------------------------------------

            if not show_inactive:

                filtered_users = filtered_users[
                    filtered_users["active"]
                    == 1
                ]

            # ------------------------------------------------
            # DISPLAY USERS
            # ------------------------------------------------

            if filtered_users.empty:

                st.info(
                    "No users match the selected filters."
                )

            else:

                for _, user_row in filtered_users.iterrows():

                    user_id = int(
                        user_row["id"]
                    )

                    is_current_user = (
                        user_id
                        == int(user["id"])
                    )

                    active = bool(
                        user_row["active"]
                    )

                    status_icon = (
                        "🟢"
                        if active
                        else "⚫"
                    )

                    role_text = str(
                        user_row["role"]
                    ).title()

                    expander_title = (
                        f"{status_icon} "
                        f"{user_row['display_name']} "
                        f"— {role_text}"
                    )

                    if is_current_user:

                        expander_title += " (You)"

                    with st.expander(
                        expander_title
                    ):

                        # ====================================
                        # ACCOUNT INFORMATION
                        # ====================================

                        info_col1, info_col2 = (
                            st.columns(2)
                        )

                        with info_col1:

                            st.write(
                                f"**Username:** "
                                f"{user_row['username']}"
                            )

                            st.write(
                                f"**Role:** "
                                f"{role_text}"
                            )

                        with info_col2:

                            if active:

                                st.write(
                                    "**Status:** Active"
                                )

                            else:

                                st.write(
                                    "**Status:** Inactive"
                                )

                            if bool(
                                user_row[
                                    "must_change_password"
                                ]
                            ):

                                st.warning(
                                    "Temporary password — "
                                    "user must change it "
                                    "at next login."
                                )

                        # ====================================
                        # STAFF COLOUR
                        # ====================================

                        colour = user_row[
                            "calendar_colour"
                        ]

                        if (
                            pd.isna(colour)
                            or not str(colour).strip()
                        ):

                            colour = "#D9D9D9"

                        st.markdown(
                            f"""
                            <div style="
                                background-color: {colour};
                                color: black;
                                padding: 6px 10px;
                                border-radius: 6px;
                                display: inline-block;
                                margin-bottom: 10px;
                            ">
                                Staff Colour
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        st.divider()

                        # ====================================
                        # EDIT USER
                        # ====================================

                        st.write(
                            "**Edit Account**"
                        )

                        

                        with st.form(
                            f"edit_user_form_{user_id}"
                        ):

                            edit_display_name = (
                                st.text_input(
                                    "Display Name",
                                    value=str(
                                        user_row[
                                            "display_name"
                                        ]
                                    )
                                )
                            )

                            # Current user cannot change
                            # their own role.

                            if is_current_user:

                                edit_role = st.selectbox(
                                    "Role",
                                    [
                                        str(
                                            user_row[
                                                "role"
                                            ]
                                        )
                                    ],
                                    disabled=True
                                )

                            else:

                                role_options = [
                                    "teacher",
                                    "technician"
                                ]

                                current_role = str(
                                    user_row["role"]
                                )

                                edit_role = st.selectbox(
                                    "Role",
                                    role_options,
                                    index=(
                                        role_options.index(
                                            current_role
                                        )
                                        if current_role
                                        in role_options
                                        else 0
                                    )
                                )

                            edit_colour = st.color_picker(
                                 "Staff Colour",
                                 value=str(colour)
                                )

                            if is_current_user:

                                edit_active = True

                                st.checkbox(
                                    "Account Active",
                                    value=True,
                                    disabled=True,
                                    help=(
                                        "You cannot deactivate "
                                        "your own account."
                                    )
                                )

                            else:

                                edit_active = st.checkbox(
                                    "Account Active",
                                    value=active
                                )

                            save_user_button = (
                                st.form_submit_button(
                                    "Save Changes",
                                    type="primary"
                                )
                            )

                        if save_user_button:

                            if not (
                                edit_display_name.strip()
                            ):

                                st.error(
                                    "Display name cannot "
                                    "be empty."
                                )

                            else:

                                update_user(
                                    user_id,
                                    edit_display_name,
                                    edit_role,
                                    edit_colour,
                                    edit_active
                                )

                                # If editing our own account,
                                # update the session copy too.

                                if is_current_user:

                                    st.session_state[
                                        "user"
                                    ][
                                        "display_name"
                                    ] = (
                                        edit_display_name
                                        .strip()
                                    )

                                    st.session_state[
                                        "user"
                                    ][
                                        "calendar_colour"
                                    ] = edit_colour

                                st.success(
                                    "User updated."
                                )

                                st.rerun()

                        # ====================================
                        # PASSWORD RESET
                        # ====================================

                        if not is_current_user:

                            st.divider()

                            st.write(
                                "**Reset Password**"
                            )

                            st.caption(
                                "Give the user a temporary "
                                "password. They will be forced "
                                "to choose a new password when "
                                "they next log in."
                            )

                            with st.form(
                                f"reset_password_form_"
                                f"{user_id}"
                            ):

                                temporary_password = (
                                    st.text_input(
                                        "Temporary Password",
                                        type="password"
                                    )
                                )

                                confirm_temporary = (
                                    st.text_input(
                                        "Confirm Temporary "
                                        "Password",
                                        type="password"
                                    )
                                )

                                reset_password_button = (
                                    st.form_submit_button(
                                        "Reset Password"
                                    )
                                )

                            if reset_password_button:

                                if (
                                    len(
                                        temporary_password
                                    )
                                    < 8
                                ):

                                    st.error(
                                        "Temporary password "
                                        "must contain at least "
                                        "8 characters."
                                    )

                                elif (
                                    temporary_password
                                    != confirm_temporary
                                ):

                                    st.error(
                                        "The passwords "
                                        "do not match."
                                    )

                                else:

                                    reset_user_password(
                                        user_id,
                                        temporary_password
                                    )

                                    st.success(
                                        "Password reset. "
                                        "The user must change "
                                        "it at next login."
                                    )

                                    st.rerun()

    # ========================================================
    # ADD USER
    # ========================================================

    with add_user_tab:

        st.subheader("Add User")

        st.caption(
            "Create a teacher or technician account. "
            "The new user will be required to change "
            "their temporary password when they first log in."
        )

        

        with st.form(
            "add_user_form"
        ):

            new_display_name = (
                st.text_input(
                    "Display Name",
                    placeholder="e.g. Mrs Smith"
                )
            )

            new_username = (
                st.text_input(
                    "Username",
                    placeholder="e.g. smithj"
                )
            )

            new_password = (
                st.text_input(
                    "Temporary Password",
                    type="password"
                )
            )

            new_password_again = (
                st.text_input(
                    "Confirm Temporary Password",
                    type="password"
                )
            )

            new_role = st.selectbox(
                "Role",
                [
                    "teacher",
                    "technician"
                ]
            )

            new_colour = st.color_picker(
                    "Staff Colour",
                    value="#D9D9D9"
                )

            create_user_button = (
                st.form_submit_button(
                    "Create User",
                    type="primary"
                )
            )

        if create_user_button:

            if not new_display_name.strip():

                st.error(
                    "Please enter a display name."
                )

            elif not new_username.strip():

                st.error(
                    "Please enter a username."
                )

            elif len(new_password) < 8:

                st.error(
                    "Temporary password must "
                    "contain at least 8 characters."
                )

            elif (
                new_password
                != new_password_again
            ):

                st.error(
                    "The passwords do not match."
                )

            else:


                success, message = create_user(
                    new_username,
                    new_password,
                    new_display_name,
                    new_role,
                    calendar_colour=new_colour,
                    must_change_password=True
                )

                if success:

                    st.success(
                        "User created successfully. "
                        "They will be asked to change "
                        "their password when they "
                        "first log in."
                    )

                    st.rerun()

                else:

                    st.error(message)

# ============================================================
# TECHNICIAN - SETTINGS
# ============================================================

elif page == "Settings":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("⚙️ Settings")

    st.caption(
        "Configure the school, rooms, year groups, periods, "
        "lesson times and requisition rules."
    )


    # ========================================================
    # SETTINGS TABS
    # ========================================================

    (
        general_tab,
        rooms_tab,
        years_tab,
        periods_tab,
        lesson_times_tab,
        requisition_tab
    ) = st.tabs(
        [
            "General",
            "Rooms",
            "Year Groups",
            "Periods",
            "Lesson Times",
            "Requisitions"
        ]
    )


    # ========================================================
    # GENERAL SETTINGS
    # ========================================================

    with general_tab:

        st.subheader("General Settings")

        settings = get_school_settings()


        with st.form("general_settings_form"):

            school_name = st.text_input(
                "School Name",
                value=settings[
                    "school_name"
                ]
            )


            department_name = st.text_input(
                "Department Name",
                value=settings[
                    "department_name"
                ]
            )


            save_general = (
                st.form_submit_button(
                    "Save General Settings",
                    type="primary"
                )
            )


        if save_general:

            if not school_name.strip():

                st.error(
                    "Please enter a school name."
                )


            elif not department_name.strip():

                st.error(
                    "Please enter a department name."
                )


            else:

                update_school_settings(
                    school_name=school_name.strip(),
                    department_name=(
                        department_name.strip()
                    )
                )


                st.success(
                    "General settings saved."
                )

                st.rerun()


    # ========================================================
    # ROOMS
    # ========================================================

    with rooms_tab:

        st.subheader("Rooms")

        st.caption(
            "These rooms will appear when teachers "
            "submit practical requisitions."
        )


        rooms = get_rooms(include_inactive=True)


        # ----------------------------------------------------
        # EXISTING ROOMS
        # ----------------------------------------------------

        if rooms.empty:

            st.info(
                "No rooms have been configured."
            )


        else:

            st.write("**Current Rooms**")


            for _, room_row in rooms.iterrows():

                room_name = room_row[
                    "room_name"
                ]


                active_text = (
                    "🟢 Active"
                    if room_row["active"]
                    else "⚫ Inactive"
                )


                col1, col2 = st.columns(
                    [3, 1]
                )


                with col1:

                    st.write(
                        f"**{room_name}**"
                    )

                    st.caption(
                        active_text
                    )


                with col2:

                    if room_row["active"]:

                        if st.button(
                            "Deactivate",
                            key=(
                                f"deactivate_room_"
                                f"{room_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_room_active(
                                int(
                                    room_row["id"]
                                ),
                                False
                            )

                            st.rerun()


                    else:

                        if st.button(
                            "Reactivate",
                            key=(
                                f"reactivate_room_"
                                f"{room_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_room_active(
                                int(
                                    room_row["id"]
                                ),
                                True
                            )

                            st.rerun()


                st.divider()


        # ----------------------------------------------------
        # ADD ROOM
        # ----------------------------------------------------

        st.write("**Add Room**")


        with st.form("add_room_form"):

            new_room = st.text_input(
                "Room Name",
                placeholder="e.g. Lab 10"
            )


            add_room_button = (
                st.form_submit_button(
                    "Add Room",
                    type="primary"
                )
            )


        if add_room_button:

            if not new_room.strip():

                st.error(
                    "Please enter a room name."
                )


            else:

                success, message = add_room(
                    new_room.strip()
                )


                if success:

                    st.success(
                        "Room added."
                    )

                    st.rerun()


                else:

                    st.error(
                        message
                    )


    # ========================================================
    # YEAR GROUPS
    # ========================================================

    with years_tab:

        st.subheader("Year Groups")

        st.caption(
            "These year groups will be available "
            "throughout the requisition system."
        )


        year_groups = get_year_groups(include_inactive=True)


        if year_groups.empty:

            st.info(
                "No year groups have been configured."
            )


        else:

            st.write(
                "**Current Year Groups**"
            )


            for _, year_row in (
                year_groups.iterrows()
            ):

                year_name = year_row[
                    "year_name"
                ]


                active_text = (
                    "🟢 Active"
                    if year_row["active"]
                    else "⚫ Inactive"
                )


                col1, col2 = st.columns(
                    [3, 1]
                )


                with col1:

                    st.write(
                        f"**{year_name}**"
                    )

                    st.caption(
                        active_text
                    )


                with col2:

                    if year_row["active"]:

                        if st.button(
                            "Deactivate",
                            key=(
                                f"deactivate_year_"
                                f"{year_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_year_group_active(
                                int(
                                    year_row["id"]
                                ),
                                False
                            )

                            st.rerun()


                    else:

                        if st.button(
                            "Reactivate",
                            key=(
                                f"reactivate_year_"
                                f"{year_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_year_group_active(
                                int(
                                    year_row["id"]
                                ),
                                True
                            )

                            st.rerun()


                st.divider()


        # ----------------------------------------------------
        # ADD YEAR GROUP
        # ----------------------------------------------------

        st.write(
            "**Add Year Group**"
        )


        with st.form(
            "add_year_group_form"
        ):

            new_year_group = (
                st.text_input(
                    "Year Group",
                    placeholder="e.g. Year 14"
                )
            )


            add_year_button = (
                st.form_submit_button(
                    "Add Year Group",
                    type="primary"
                )
            )


        if add_year_button:

            if not new_year_group.strip():

                st.error(
                    "Please enter a year group."
                )


            else:

                success, message = (
                    add_year_group(
                        new_year_group.strip()
                    )
                )


                if success:

                    st.success(
                        "Year group added."
                    )

                    st.rerun()


                else:

                    st.error(
                        message
                    )


    # ========================================================
    # PERIODS
    # ========================================================

    with periods_tab:

        st.subheader("Periods")

        st.caption(
            "Configure the lesson periods used "
            "by the school."
        )


        periods = get_periods(include_inactive=True)


        if periods.empty:

            st.info(
                "No periods have been configured."
            )


        else:

            st.write(
                "**Current Periods**"
            )


            for _, period_row in (
                periods.iterrows()
            ):

                period_name = period_row[
                    "period_name"
                ]


                active_text = (
                    "🟢 Active"
                    if period_row["active"]
                    else "⚫ Inactive"
                )


                col1, col2 = st.columns(
                    [3, 1]
                )


                with col1:

                    st.write(
                        f"**{period_name}**"
                    )

                    st.caption(
                        active_text
                    )


                with col2:

                    if period_row["active"]:

                        if st.button(
                            "Deactivate",
                            key=(
                                f"deactivate_period_"
                                f"{period_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_period_active(
                                int(
                                    period_row["id"]
                                ),
                                False
                            )

                            st.rerun()


                    else:

                        if st.button(
                            "Reactivate",
                            key=(
                                f"reactivate_period_"
                                f"{period_row['id']}"
                            ),
                            use_container_width=True
                        ):

                            set_period_active(
                                int(
                                    period_row["id"]
                                ),
                                True
                            )

                            st.rerun()


                st.divider()


        # ----------------------------------------------------
        # ADD PERIOD
        # ----------------------------------------------------

        st.write(
            "**Add Period**"
        )


        with st.form(
            "add_period_form"
        ):

            new_period = st.text_input(
                "Period Name",
                placeholder="e.g. P6"
            )


            add_period_button = (
                st.form_submit_button(
                    "Add Period",
                    type="primary"
                )
            )


        if add_period_button:

            if not new_period.strip():

                st.error(
                    "Please enter a period name."
                )


            else:

                success, message = add_period(
                    new_period.strip()
                )


                if success:

                    st.success(
                        "Period added."
                    )

                    st.rerun()


                else:

                    st.error(
                        message
                    )


    # ========================================================
    # LESSON TIMES
    # ========================================================

    with lesson_times_tab:

        st.subheader("Lesson Times")

        st.caption(
            "Set lesson times for each day, year group "
            "and period. This allows different year groups "
            "to have different lunch and lesson times."
        )


        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday"
        ]


        active_year_groups = (
            get_year_group_names()
        )


        active_periods = (
            get_period_names()
        )


        if (
            not active_year_groups
            or not active_periods
        ):

            st.warning(
                "You need at least one active year group "
                "and one active period before lesson times "
                "can be configured."
            )


        else:

            # ------------------------------------------------
            # CHOOSE LESSON
            # ------------------------------------------------

            lesson_col1, lesson_col2 = (
                st.columns(2)
            )


            with lesson_col1:

                lesson_day = st.selectbox(
                    "Day",
                    day_names,
                    key="settings_lesson_day"
                )


                lesson_year = st.selectbox(
                    "Year Group",
                    active_year_groups,
                    key="settings_lesson_year"
                )


            with lesson_col2:

                lesson_period = st.selectbox(
                    "Period",
                    active_periods,
                    key="settings_lesson_period"
                )


            # ------------------------------------------------
            # CURRENT TIME
            # ------------------------------------------------

            existing_lesson_time = (
                get_lesson_time_values(
                    lesson_day,
                    lesson_year,
                    lesson_period
                )
            )


            default_start = time(
                hour=9,
                minute=0
            )

            default_end = time(
                hour=10,
                minute=0
            )


            if existing_lesson_time:

                try:

                    default_start = (
                        datetime.strptime(
                            existing_lesson_time[
                                "start_time"
                            ],
                            "%H:%M"
                        ).time()
                    )


                    default_end = (
                        datetime.strptime(
                            existing_lesson_time[
                                "end_time"
                            ],
                            "%H:%M"
                        ).time()
                    )

                except ValueError:

                    pass


            with st.form(
                "lesson_time_form"
            ):

                time_col1, time_col2 = (
                    st.columns(2)
                )


                with time_col1:

                    start_time_value = (
                        st.time_input(
                            "Start Time",
                            value=default_start
                        )
                    )


                with time_col2:

                    end_time_value = (
                        st.time_input(
                            "End Time",
                            value=default_end
                        )
                    )


                save_lesson_button = (
                    st.form_submit_button(
                        "Save Lesson Time",
                        type="primary"
                    )
                )


            if save_lesson_button:

                if (
                    end_time_value
                    <= start_time_value
                ):

                    st.error(
                        "The lesson end time must "
                        "be after the start time."
                    )


                else:

                    save_lesson_time(
                        lesson_day,
                        lesson_year,
                        lesson_period,
                        start_time_value.strftime(
                            "%H:%M"
                        ),
                        end_time_value.strftime(
                            "%H:%M"
                        )
                    )


                    st.success(
                        f"Lesson time saved for "
                        f"{lesson_year}, "
                        f"{lesson_day}, "
                        f"{lesson_period}."
                    )

                    st.rerun()


    # ========================================================
    # REQUISITION SETTINGS
    # ========================================================

    with requisition_tab:

        st.subheader(
            "Requisition Settings"
        )


        settings = (
            get_school_settings()
        )


        st.write(
            "**Weekly Requisition Deadline**"
        )

        st.caption(
            "This is the deadline for submitting "
            "requisitions for the following week."
        )


        weekday_options = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday"
        ]


        current_weekday = int(
            settings[
                "deadline_weekday"
            ]
        )


        try:

            current_deadline_time = (
                datetime.strptime(
                    settings[
                        "deadline_time"
                    ],
                    "%H:%M"
                ).time()
            )

        except ValueError:

            current_deadline_time = (
                time(
                    hour=10,
                    minute=40
                )
            )


        with st.form(
            "requisition_settings_form"
        ):

            deadline_day = (
                st.selectbox(
                    "Deadline Day",
                    weekday_options,
                    index=current_weekday
                )
            )


            deadline_time_value = (
                st.time_input(
                    "Deadline Time",
                    value=(
                        current_deadline_time
                    )
                )
            )


            allow_late = (
                st.checkbox(
                    "Allow late requisitions",
                    value=bool(
                        settings[
                            "allow_late_requisitions"
                        ]
                    ),
                    help=(
                        "When enabled, late requests "
                        "can be submitted but require "
                        "technician approval."
                    )
                )
            )


            retention_weeks = (
                st.number_input(
                    "Attachment Retention (weeks)",
                    min_value=1,
                    max_value=52,
                    value=int(
                        settings[
                            "attachment_retention_weeks"
                        ]
                    ),
                    step=1,
                    help=(
                        "Temporary requisition attachments "
                        "can be removed after this many weeks."
                    )
                )
            )


            save_requisition_settings = (
                st.form_submit_button(
                    "Save Requisition Settings",
                    type="primary"
                )
            )


        if save_requisition_settings:

            deadline_weekday = (
                weekday_options.index(
                    deadline_day
                )
            )


            update_school_settings(
                deadline_weekday=(
                    deadline_weekday
                ),
                deadline_time=(
                    deadline_time_value.strftime(
                        "%H:%M"
                    )
                ),
                allow_late_requisitions=(
                    allow_late
                ),
                attachment_retention_weeks=(
                    int(
                        retention_weeks
                    )
                )
            )


            st.success(
                "Requisition settings saved."
            )

            st.rerun()



# ============================================================
# TECHNICIAN - LATE APPROVALS
# ============================================================

elif page == "Late Approvals":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("⚠️ Late Requisition Approvals")


    pending = get_pending_requisitions()


    if pending.empty:

        st.success(
            "There are no late requisitions "
            "waiting for approval."
        )


    else:

        pending[
            "practical_date"
        ] = pd.to_datetime(
            pending[
                "practical_date"
            ]
        )


        st.warning(
            f"{len(pending)} late "
            f"{'request is' if len(pending) == 1 else 'requests are'} "
            "waiting for approval."
        )


        for _, row in pending.iterrows():

            title = (
                f"🟠 "
                f"{row['practical_date'].strftime('%A %d %B')} "
                f"— {row['period']} "
                f"— {row['practical_name']} "
                f"— {row['teacher']}"
            )


            with st.expander(
                title,
                expanded=True
            ):

                st.write(
                    f"**Teacher:** {row['teacher']}"
                )

                st.write(
                    f"**Class:** {row['class_name']}"
                )

                st.write(
                    f"**Year Group:** {row['year_group']}"
                )

                st.write(
                    f"**Room:** {row['room']}"
                )

                st.write(
                    f"**Number of Sets:** {row['number']}"
                )


                if (
                    pd.notna(row["code"])
                    and str(row["code"]).strip()
                ):

                    st.write(
                        f"**Code:** {row['code']}"
                    )


                lesson_time = get_lesson_time(
                    row[
                        "practical_date"
                    ].date(),
                    row["year_group"],
                    row["period"]
                )


                if lesson_time:

                    st.write(
                        f"**Lesson Time:** "
                        f"{lesson_time}"
                    )


                st.write(
                    "**Requirements:**"
                )

                st.text(
                    row["equipment"]
                )


                if (
                    pd.notna(row["notes"])
                    and str(
                        row["notes"]
                    ).strip()
                ):

                    st.write(
                        "**Teacher Additional Notes:**"
                    )

                    st.write(
                        row["notes"]
                    )


                # =============================================
                # ATTACHMENTS
                # =============================================

                attachments = (
                    get_requisition_attachments(
                        int(row["id"])
                    )
                )


                if not attachments.empty:

                    st.write(
                        "**Attachments:**"
                    )


                    for _, attachment in (
                        attachments.iterrows()
                    ):

                        file_path = Path(
                            attachment[
                                "file_path"
                            ]
                        )


                        if file_path.exists():

                            with open(
                                file_path,
                                "rb"
                            ) as file:

                                file_data = file.read()


                            st.download_button(
                                label=(
                                    "📎 "
                                    + attachment[
                                        "original_filename"
                                    ]
                                ),
                                data=file_data,
                                file_name=(
                                    attachment[
                                        "original_filename"
                                    ]
                                ),
                                key=(
                                    f"approval_attachment_"
                                    f"{attachment['id']}"
                                )
                            )


                st.divider()


                technician_response = (
                    st.text_area(
                        "Response to Teacher",
                        placeholder=(
                            "Optional message explaining "
                            "the approval or reason for "
                            "declining."
                        ),
                        key=(
                            f"approval_response_"
                            f"{row['id']}"
                        )
                    )
                )


                approve_col, decline_col = (
                    st.columns(2)
                )


                with approve_col:

                    approve_button = (
                        st.button(
                            "✅ Approve",
                            key=(
                                f"approve_"
                                f"{row['id']}"
                            ),
                            type="primary",
                            use_container_width=True
                        )
                    )


                with decline_col:

                    decline_button = (
                        st.button(
                            "❌ Decline",
                            key=(
                                f"decline_"
                                f"{row['id']}"
                            ),
                            use_container_width=True
                        )
                    )


                
                if approve_button:

                    success = approve_requisition(
                        int(row["id"]),
                        user["id"],
                        technician_response
                    )

                    if success:
                        st.success(
                            "Late requisition approved."
                        )
                    else:
                        st.warning(
                            "This requisition has already "
                            "been dealt with by another "
                            "technician. Your decision "
                            "was not saved."
                        )

                    st.rerun()



                
                if decline_button:

                    decline_reason = (
                        technician_response.strip()
                    )

                    if not decline_reason:

                        st.error(
                            "Please give the teacher a "
                            "reason before declining the "
                            "requisition."
                        )

                    else:

                        success = decline_requisition(
                            int(row["id"]),
                            user["id"],
                            decline_reason
                        )

                        if success:
                            st.success(
                                "Requisition declined."
                            )
                        else:
                            st.warning(
                                "This requisition has already "
                                "been dealt with by another "
                                "technician. Your decision "
                                "was not saved."
                            )

                        st.rerun()



# ============================================================
# MY ACCOUNT
# ============================================================

elif page == "My Account":

    st.title("👤 My Account")

    st.write(
        f"Signed in as **{user['display_name']}**"
    )

    st.caption(
        f"Role: {user['role'].title()}"
    )


    # ========================================================
    # ACCOUNT INFORMATION
    # ========================================================

    st.subheader("Account Information")


    info_col1, info_col2 = st.columns(2)


    with info_col1:

        st.write(
            f"**Display Name:** "
            f"{user['display_name']}"
        )


        st.write(
            f"**Username:** "
            f"{user['username']}"
        )


    with info_col2:

        st.write(
            f"**Role:** "
            f"{user['role'].title()}"
        )


        # ----------------------------------------------------
        # STAFF COLOUR
        # ----------------------------------------------------

        staff_colour = user.get(
            "calendar_colour",
            "#D9D9D9"
        )


        st.write(
            "**Staff Colour:**"
        )


        st.markdown(
            f"""
            <div style="
                background-color: {staff_colour};
                color: black;
                padding: 7px 12px;
                border-radius: 6px;
                display: inline-block;
                min-width: 100px;
                text-align: center;
            ">
                {user['display_name']}
            </div>
            """,
            unsafe_allow_html=True
        )


    st.caption(
        "Display names, roles and staff colours are "
        "managed by technicians."
    )


    st.divider()


    # ========================================================
    # CHANGE PASSWORD
    # ========================================================

    st.subheader("🔐 Change Password")


    st.caption(
        "You can change your password here at any time."
    )


    with st.form(
        "change_own_password_form"
    ):

        current_password = st.text_input(
            "Current Password",
            type="password"
        )


        new_password = st.text_input(
            "New Password",
            type="password"
        )


        confirm_new_password = st.text_input(
            "Confirm New Password",
            type="password"
        )


        change_password_button = (
            st.form_submit_button(
                "Change Password",
                type="primary"
            )
        )


    # ========================================================
    # PROCESS PASSWORD CHANGE
    # ========================================================

    if change_password_button:

        # ----------------------------------------------------
        # CHECK CURRENT PASSWORD
        # ----------------------------------------------------

        authenticated_user = (
            authenticate_user(
                user["username"],
                current_password
            )
        )


        if not current_password:

            st.error(
                "Please enter your current password."
            )


        elif authenticated_user is None:

            st.error(
                "Your current password is incorrect."
            )


        elif not new_password:

            st.error(
                "Please enter a new password."
            )


        elif len(new_password) < 8:

            st.error(
                "Your new password must contain "
                "at least 8 characters."
            )


        elif new_password != confirm_new_password:

            st.error(
                "The new passwords do not match."
            )


        elif new_password == current_password:

            st.error(
                "Your new password must be different "
                "from your current password."
            )


        else:

            change_password(
                user["id"],
                new_password
            )


            st.success(
                "✅ Your password has been changed "
                "successfully."
            )

# ============================================================
# TECHNICICAN - PRINT REQUISITIONS
# ============================================================

elif page == "Print Requisitions":

    if user["role"] != "technician":

        st.error(
            "You do not have permission "
            "to access this page."
        )

        st.stop()


    st.title("🖨️ Print Requisitions")

    st.caption(
        "Select a week to create printable requisition slips. "
        "Only approved requisitions are included."
    )


    # ========================================================
    # CHOOSE WEEK
    # ========================================================

    selected_date = st.date_input(
        "Choose a week",
        value=date.today(),
        key="print_requisition_week"
    )


    monday = (
        selected_date
        - timedelta(
            days=selected_date.weekday()
        )
    )

    friday = (
        monday
        + timedelta(days=4)
    )


    st.write(
        f"**Week:** "
        f"{monday.strftime('%d %B %Y')} "
        f"— "
        f"{friday.strftime('%d %B %Y')}"
    )


    # ========================================================
    # GET REQUISITIONS
    # ========================================================

    requisitions = get_all_requisitions(
        include_pending=False,
        include_declined=False
    )


    if requisitions.empty:

        st.info(
            "There are no approved requisitions "
            "to print."
        )


    else:

        requisitions = requisitions.copy()


        requisitions[
            "practical_date"
        ] = pd.to_datetime(
            requisitions[
                "practical_date"
            ]
        )


        # ====================================================
        # FILTER TO SELECTED WEEK
        # ====================================================

        week_requisitions = (
            requisitions[
                (
                    requisitions[
                        "practical_date"
                    ].dt.date
                    >= monday
                )
                &
                (
                    requisitions[
                        "practical_date"
                    ].dt.date
                    <= friday
                )
                &
                (
                    requisitions[
                        "approval_status"
                    ]
                    == "Approved"
                )
            ].copy()
        )


        # ====================================================
        # SORT
        # ====================================================

        if not week_requisitions.empty:

            # Convert period into a useful sort order.
            #
            # This uses the order configured in Settings
            # rather than alphabetically sorting P1, P2 etc.

            configured_periods = (
                get_period_names()
            )


            period_order = {
                period_name: index

                for index, period_name
                in enumerate(
                    configured_periods
                )
            }


            week_requisitions[
                "_period_order"
            ] = (
                week_requisitions[
                    "period"
                ].map(
                    period_order
                ).fillna(999)
            )


            week_requisitions = (
                week_requisitions.sort_values(
                    [
                        "practical_date",
                        "_period_order",
                        "room",
                        "teacher"
                    ]
                )
            )


        # ====================================================
        # NO PRACTICALS
        # ====================================================

        if week_requisitions.empty:

            st.info(
                "There are no approved requisitions "
                "for this week."
            )


        else:

            # =================================================
            # SUMMARY
            # =================================================

            st.success(
                f"{len(week_requisitions)} "
                f"{'requisition' if len(week_requisitions) == 1 else 'requisitions'} "
                "ready to print."
            )


            # =================================================
            # PRINT INSTRUCTIONS
            # =================================================

            st.info(
                "When you are ready, use your browser's "
                "**Print** command (Ctrl+P). "
                "The menus and controls will be hidden "
                "from the printed page."
            )


            st.divider()


            # =================================================
            # PRINT CSS
            # =================================================

            st.markdown(
                """
                <style>

                /* ------------------------------------------
                   PRINT SLIP
                   ------------------------------------------ */

                .requisition-slip {
                    border: 1px solid #333;
                    border-left: 8px solid var(--teacher-colour);
                    border-radius: 4px;
                    padding: 10px 12px;
                    margin-bottom: 12px;
                    background: white;
                    color: black;
                    page-break-inside: avoid;
                    break-inside: avoid;
                }


                .requisition-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    border-bottom: 1px solid #999;
                    padding-bottom: 6px;
                    margin-bottom: 7px;
                }


                .requisition-teacher {
                    font-size: 1.1rem;
                    font-weight: bold;
                }


                .requisition-date {
                    text-align: right;
                    font-weight: bold;
                }


                .requisition-practical {
                    font-size: 1.05rem;
                    font-weight: bold;
                    margin-top: 5px;
                    margin-bottom: 5px;
                }


                .requisition-details {
                    margin-bottom: 7px;
                }


                .requisition-section-title {
                    font-weight: bold;
                    margin-top: 5px;
                }


                .requisition-text {
                    white-space: pre-wrap;
                    overflow-wrap: anywhere;
                }


                .late-approved {
                    font-weight: bold;
                    margin-top: 5px;
                }


                /* ------------------------------------------
                   PRINTING
                   ------------------------------------------ */

                @media print {

                    /* Hide Streamlit interface */

                    [data-testid="stSidebar"] {
                        display: none !important;
                    }


                    [data-testid="stHeader"] {
                        display: none !important;
                    }


                    [data-testid="stToolbar"] {
                        display: none !important;
                    }


                    [data-testid="stDecoration"] {
                        display: none !important;
                    }


                    [data-testid="stStatusWidget"] {
                        display: none !important;
                    }


                    footer {
                        display: none !important;
                    }


                    button {
                        display: none !important;
                    }


                    /* Hide ordinary Streamlit elements
                       specifically marked no-print */

                    .no-print {
                        display: none !important;
                    }


                    /* Make page wider */

                    .block-container {
                        max-width: 100% !important;
                        padding: 0 !important;
                        margin: 0 !important;
                    }


                    /* Keep slips compact */

                    .requisition-slip {
                        margin: 0 0 8px 0;
                        padding: 7px 9px;
                        font-size: 10pt;
                    }


                    @page {
                        size: A4;
                        margin: 10mm;
                    }

                }

                </style>
                """,
                unsafe_allow_html=True
            )


            # =================================================
            # DISPLAY BY DAY
            # =================================================

            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday"
            ]


            for day_number in range(5):

                current_date = (
                    monday
                    + timedelta(
                        days=day_number
                    )
                )


                day_requisitions = (
                    week_requisitions[
                        week_requisitions[
                            "practical_date"
                        ].dt.date
                        == current_date
                    ]
                )


                if day_requisitions.empty:

                    continue


                # =============================================
                # DAY HEADING
                # =============================================

                st.markdown(
                    f"""
                    <div class="print-day-heading">
                        <h3>
                            {day_names[day_number]}
                            —
                            {current_date.strftime('%d %B %Y')}
                        </h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # =============================================
                # REQUISITION SLIPS
                # =============================================

                for _, row in (
                    day_requisitions.iterrows()
                ):

                    # -----------------------------------------
                    # TEACHER COLOUR
                    # -----------------------------------------

                    teacher_colour = row.get(
                        "teacher_colour",
                        "#D9D9D9"
                    )


                    if (
                        pd.isna(
                            teacher_colour
                        )
                        or not str(
                            teacher_colour
                        ).strip()
                    ):

                        teacher_colour = (
                            "#D9D9D9"
                        )


                    # -----------------------------------------
                    # LESSON TIME
                    # -----------------------------------------

                    lesson_time = (
                        get_lesson_time(
                            current_date,
                            row["year_group"],
                            row["period"]
                        )
                    )


                    if lesson_time:

                        time_text = (
                            f"{row['period']} "
                            f"({lesson_time})"
                        )

                    else:

                        time_text = str(
                            row["period"]
                        )


                    # -----------------------------------------
                    # CODE
                    # -----------------------------------------

                    code_text = ""


                    if (
                        pd.notna(row["code"])
                        and str(
                            row["code"]
                        ).strip()
                    ):

                        code_text = (
                            f" | Code: "
                            f"{row['code']}"
                        )


                    # -----------------------------------------
                    # NOTES
                    # -----------------------------------------

                    notes_html = ""


                    if (
                        pd.notna(row["notes"])
                        and str(
                            row["notes"]
                        ).strip()
                    ):

                        notes_html = f"""
                            <div class="requisition-section-title">
                                Additional Notes:
                            </div>

                            <div class="requisition-text">
                                {row['notes']}
                            </div>
                        """


                    # -----------------------------------------
                    # LATE
                    # -----------------------------------------

                    late_html = ""


                    if bool(
                        row["is_late"]
                    ):

                        late_html = """
                            <div class="late-approved">
                                ⚠ Late request — approved
                            </div>
                        """


                    # -----------------------------------------
                    # REQUIREMENTS
                    # -----------------------------------------

                    equipment = ""

                    if pd.notna(
                        row["equipment"]
                    ):

                        equipment = str(
                            row["equipment"]
                        )


                    # -----------------------------------------
                    # PRINT SLIP
                    # -----------------------------------------

                    requisition_slip = f"""
                    <div
                        class="requisition-slip"
                        style="--teacher-colour: {teacher_colour};"
                    >

                        <div class="requisition-header">

                            <div class="requisition-teacher">
                                {row['teacher']}
                            </div>

                            <div class="requisition-date">
                                {current_date.strftime('%A %d %B')}
                                <br>
                                {time_text}
                            </div>

                        </div>

                        <div class="requisition-practical">
                            {row['practical_name']}
                        </div>

                        <div class="requisition-details">

                            <strong>Class:</strong>
                            {row['class_name']}

                            &nbsp;&nbsp; | &nbsp;&nbsp;

                            <strong>Year:</strong>
                            {row['year_group']}

                            <br>

                            <strong>Room:</strong>
                            {row['room']}

                            &nbsp;&nbsp; | &nbsp;&nbsp;

                            <strong>Sets:</strong>
                            {row['number']}

                            {code_text}

                        </div>

                        <div class="requisition-section-title">
                        Requirements:
                        </div>

                        <div class="requisition-text">
                            {equipment}
                        </div>

                        {notes_html}

                        {late_html}

                    </div>
                    """

                    st.html(requisition_slip)








