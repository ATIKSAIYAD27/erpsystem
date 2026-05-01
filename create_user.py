import pymysql
from werkzeug.security import generate_password_hash

conn = pymysql.connect(
    host='localhost',
    port=3307,
    user='root',
    password='',
    database='erpsystem',
    cursorclass=pymysql.cursors.DictCursor
)

email = 'admin@erp.com'
password = 'admin123'
hashed = generate_password_hash(password)

with conn.cursor() as cursor:
    cursor.execute(
        "INSERT INTO users (email, password_hash, role_id) VALUES (%s, %s, %s)",
        (email, hashed, 1)
    )
conn.commit()
conn.close()

print(f"User created!\nEmail: {email}\nPassword: {password}")
