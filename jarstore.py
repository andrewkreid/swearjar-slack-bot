
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
                swear_word TEXT NOT NULL,
                cents INT NOT NULL
            )''')
            self._conn.execute('''
            CREATE TABLE IF NOT EXISTS payments
            (
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                when_paid TEXT NOT NULL,
                cents INT NOT NULL
            )
           ''')

    def add_swear(self, user_id, user_name, swear_word, fine):
        when_swore = datetime.datetime.now().isoformat()
        query = '''
            INSERT INTO swears (user_id, user_name, when_swore, swear_word, cents) VALUES (?, ?, ?, ?, ?)
        '''
        args = [user_id, user_name, when_swore, swear_word, fine]
        with self._conn:
            self._conn.execute(query, args)

    def get_swear_total(self):
        with self._conn:
            sql = self._conn.execute("SELECT SUM(cents) as num_rows from swears")
            row = sql.fetchone()
            if row:
                return row[0]
            else:
                return 0

    def get_money_owed(self, user_id):
        with self._conn:
            # total the fines
            sql = self._conn.execute("SELECT SUM(cents) FROM swears WHERE user_id = ?", [user_id])
            row = sql.fetchone()
            if row:
                fines = int(row[0])
            else:
                fines = 0
        return fines

    def get_money_paid(self, user_id):
        with self._conn:
            # total the payments
            sql = self._conn.execute("SELECT SUM(cents) FROM payments WHERE user_id = ?", [user_id])
            row = sql.fetchone()
            if row and row[0]:
                payments = int(row[0])
            else:
                payments = 0
        return payments

    def get_swears(self, user_id, limit=20):
        with self._conn:
            sql = self._conn.execute(
                "SELECT when_swore, swear_word FROM swears WHERE user_id = ? ORDER BY when_swore DESC LIMIT ?",
                [user_id, limit])
            retval = []
            for row in sql:
                retval.append(row)
        return retval

    def get_leaders(self):
        with self._conn:
            sql = self._conn.execute(
                "SELECT SUM(cents) as total, user_name FROM swears GROUP BY user_name ORDER BY total DESC"
            )
            retval = []
            for row in sql:
                retval.append(row)
        return retval

    def add_payment(self, user_id, user_name, cents):
        with self._conn:
            args = [
                user_id,
                user_name,
                datetime.datetime.now().isoformat(),
                cents
                ]
            self._conn.execute("INSERT INTO payments (user_id, user_name, when_paid, cents) VALUES (?, ?, ?, ?)",
                               args)
