
import sqlite3
import datetime


class JarStore:

    def __init__(self, dbfile):

        self._dbfile = dbfile
        self._conn = None

    def __del__(self):
        if self._conn:
            self._conn.close()

    def open_db(self):
        self.close_db()
        self._conn = sqlite3.connect(self._dbfile)
        self.create_db_tables()

    def close_db(self):
        if self._conn:
            self._conn.close()
        self._conn = None

    def create_db_tables(self):
        with self._conn:
            self._conn.execute('''
            CREATE TABLE IF NOT EXISTS swears
            (
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                when_swore TEXT NOT NULL,
                swear_word TEXT NOT NULL
            )''')

    def add_swear(self, user_id, user_name, swear_word):
        when_swore = datetime.datetime.now().isoformat()
        query = '''
            INSERT INTO swears (user_id, user_name, when_swore, swear_word) VALUES (?, ?, ?, ?)
        '''
        args = [user_id, user_name, when_swore, swear_word]
        with self._conn:
            self._conn.execute(query, args)

    def get_swear_total(self):
        with self._conn:
            sql = self._conn.execute("SELECT COUNT(*) as num_rows from swears")
            row = sql.fetchone()
            return row[0]


