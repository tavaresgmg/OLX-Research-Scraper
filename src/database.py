import sqlite3

class Database:
    def __init__(self, db_name="olx_precos.db"):
        self.db_name = db_name
        self.conn = None

    def connect(self):
        """Conecta ao banco de dados."""
        self.conn = sqlite3.connect(self.db_name)
        return self

    def close(self):
        """Fecha a conexão com o banco de dados."""
        if self.conn:
            self.conn.close()

    def create_table(self):
        """Cria a tabela 'produtos' se ela não existir."""
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT,
            preco REAL,
            url TEXT,
            titulo TEXT,
            data_extracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def insert_data(self, produto, preco, url, titulo):
        """Insere dados na tabela 'produtos'."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO produtos (produto, preco, url, titulo) VALUES (?, ?, ?, ?)",
                       (produto, preco, url, titulo))
        self.conn.commit()