import psycopg2 as pg
import os
import time

from defFunc import load_env_vars, logSave


# DB 연결
def get_db_connect():
    env_data = load_env_vars()
    db_host = env_data.get("PATH", "")
    db_name = env_data.get("BUILD_CATEGORY", "") + "_origin"
    db_id = env_data.get("DB_ID", "")
    db_pw = env_data.get("DB_PW", "")
    conn = pg.connect(
        dbname=db_name,
        user=db_id,
        password=db_pw,
        host=db_host,
        port='5432'
    )
    cur = conn.cursor()
    return conn, cur


# insert sql, 단건, 입력할 값을 넣으면 DB연결후 sql 실행하고 종료
def execute_insert_data(sql="", valuse=()):
    conn = None
    cur = None
    try:
        conn, cur = get_db_connect()
        cur.execute(sql, valuse)  # sql문과 튜플하나
        conn.commit()
    except Exception as e:
        logger1 = logSave("logs", "db_error")
        logger1.LogTextOut(f"[Postgres] insert data : {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# insert sql, 복수건, 입력할 값을 넣으면 DB연결후 sql 실행하고 종료
def execute_insert_many(sql="", values=[]):
    conn = None
    cur = None
    try:
        conn, cur = get_db_connect()
        cur.executemany(sql, values)
        conn.commit()
        logger_success = logSave("logs", "db_commit")
        logger_success.LogTextOut(f"commit success {len(values)}")
    except Exception as e:
        logger1 = logSave("logs", "db_error")
        logger1.LogTextOut(f"[Postgres] insert many : {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# power 테이블에 필요한 SQL, 단건, 입력값 준비해서 execute 함수 실행
def insert_global_power(data):
    sql = """
        INSERT INTO tbl_power
        ("date", floor, humi, "section", temp,active_electric_energy, total_active_power, total_reactive_power, total_apparent_power, total_power_factor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """  # power 테이블에 맞는 SQL 설정
    values = (
        data["date"], data["floor"], data["humi"],data["section"], data["temp"],
        data["active_electric_energy"],
        data["total_active_power"], data["total_reactive_power"],
        data["total_apparent_power"], data["total_power_factor"]
    )  # tbl_power 테이블에 맞게 딕셔너리를 튜플로 전처리
    execute_insert_data(sql, values)

# power 테이블에 필요한 SQL, 복수건, 입력값 준비해서 execute 함수 실행
def insert_global_power_many(data_list):
    sql = """
        INSERT INTO tbl_power
        ("date", floor, humi,"section", temp,active_electric_energy,
         total_active_power, total_reactive_power,
         total_apparent_power, total_power_factor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = []
    for data in data_list:
        values.append((
            data["date"], data["floor"], data["humi"], data["section"], data["temp"],
            data["active_electric_energy"],
            data["total_active_power"], data["total_reactive_power"],
            data["total_apparent_power"], data["total_power_factor"]
        ))

    execute_insert_many(sql, values)


# energy 테이블에 필요한 SQL, 단수 ,입력값 준비해서 execute 함수 실행
def insert_global_energy(data):
    sql = """
        INSERT INTO tbl_energy
        ("date", floor, "section", co2, temp, humi, pm1, pm2_5, pm10, voc, tempimage, errcode)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """  # tbl_energy 테이블에 맞는 SQL 설정
    values = (
        data["date"], data["floor"], data["section"],
        data["co2"], data["temperature"], data["humidity"],
        data["pm1_0"], data["pm2_5"], data["pm10"], data["voc"]
    )  # energy 테이블에 맞게 딕셔너리를 튜플로 전처리
    execute_insert_data(sql, values)

# energy 테이블에 필요한 SQL, 복수, 입력값 준비해서 execute 함수 실행
def insert_global_energy_many(data_list):
    sql = """
        INSERT INTO tbl_energy
        ("date", floor, "section", co2, temp, humi, pm1, pm2_5, pm10, voc, tempimage, errcode)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """  # tbl_energy 테이블에 맞는 SQL 설정
    values = []
    for data in data_list:
        values.append((
            data["date"], data["floor"], data["section"],
            data["co2"], data["temperature"], data["humidity"],
            data["pm1_0"], data["pm2_5"], data["pm10"], data["voc"]
        ))  # energy 테이블에 맞게 딕셔너리를 튜플로 전처리
    execute_insert_many(sql, values)



# water 테이블에 필요한 SQL, 단건, 입력값 준비해서 execute 함수 실행
def insert_global_water(data):
    sql = """
        INSERT INTO tbl_water
        ("date", floor, "section", inst_flow, neg_dec_data, neg_sum_data, pos_dec_data, pos_sum_data, plain_dec_data, plain_sum_data, today_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """  # power 테이블에 맞는 SQL 설정
    values = (
        data["date"], data["floor"], data["section"],
        data["inst_flow"], data["neg_dec_data"],
        data["neg_sum_data"], data["pos_dec_data"],
        data["pos_sum_data"], data["plain_dec_data"],
        data["plain_sum_data"], data["today_value"],
    )  # tbl_power 테이블에 맞게 딕셔너리를 튜플로 전처리
    execute_insert_data(sql, values)

# water 테이블에 필요한 SQL, 복수건, 입력값 준비해서 execute 함수 실행
def insert_global_water_many(data_list):
    sql = """
        INSERT INTO tbl_water
        ("date", floor, "section", inst_flow, neg_dec_data, neg_sum_data, pos_dec_data, pos_sum_data, plain_dec_data, plain_sum_data, today_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """  # water 테이블에 맞는 SQL 설정
    values = []
    for data in data_list:
        values.append((
            data["date"], data["floor"], data["section"],
            data["inst_flow"], data["neg_dec_data"],
            data["neg_sum_data"], data["pos_dec_data"],
            data["pos_sum_data"], data["plain_dec_data"],
            data["plain_sum_data"], data["today_value"],
        ))  # tbl_water 테이블에 맞게 딕셔너리를 튜플로 전처리
    execute_insert_many(sql, values)

#todo : mqtt로 수정
