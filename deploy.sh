# Wait for MySQL to be ready
echo "Waiting for database..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  python -c "
import pymysql, os

mysql_ssl_ca = os.environ.get('MYSQL_ROOT_CERT')
host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))

if mysql_ssl_ca:
    ssl_config = {'ca': mysql_ssl_ca}
elif host not in ('127.0.0.1', 'localhost'):
    ssl_config = {}
else:
    ssl_config = None

conn = pymysql.connect(
    host=host,
    port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
    user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
    password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
    connect_timeout=10,
    ssl=ssl_config
)
conn.close()
print('Database ready!')
" && break
  echo "Attempt $i: Database not ready, waiting 5s..."
  sleep 5
done
