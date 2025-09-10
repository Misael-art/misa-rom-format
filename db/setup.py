import sqlite3
import logging

def init_db(db_path):
    """
    Inicializa o banco de dados SQLite com tabela básica.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value TEXT
            )
        ''')
        conn.commit()
        logging.info("Banco de dados inicializado com sucesso.")
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar banco de dados: {e}")
    finally:
        if 'conn' in locals():
            conn.close()