import pytest
import tempfile
import os
import sqlite3
from unittest.mock import patch, MagicMock
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.setup import init_db

@patch('db.setup.logging.info')
@patch('db.setup.logging.error')
def test_init_db_success(mock_error, mock_info):
    # Testa inicialização bem-sucedida
    with tempfile.NamedTemporaryFile(delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        init_db(temp_db_path)

        # Verificar se tabela foi criada
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'items'

        # Verificar estrutura da tabela
        cursor.execute("PRAGMA table_info(items)")
        columns = cursor.fetchall()
        assert len(columns) == 3
        assert columns[0][1] == 'id'
        assert columns[1][1] == 'name'
        assert columns[2][1] == 'value'

        conn.close()

        mock_info.assert_called_once_with("Banco de dados inicializado com sucesso.")
        assert not mock_error.called

    finally:
        # Pequena pausa para liberar locks no Windows
        import time
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except PermissionError:
            pass  # Ignorar se ainda está sendo usado

@patch('db.setup.logging.info')
@patch('db.setup.logging.error')
def test_init_db_sqlite_error(mock_error, mock_info):
    # Testa erro do SQLite
    with patch('sqlite3.connect') as mock_connect:
        mock_connect.side_effect = sqlite3.Error("Erro de conexão")

        init_db('invalid_path.db')

        mock_error.assert_called_once_with("Erro ao inicializar banco de dados: Erro de conexão")
        assert not mock_info.called

@patch('db.setup.logging.info')
@patch('db.setup.logging.error')
def test_init_db_table_already_exists(mock_error, mock_info):
    # Testa quando tabela já existe
    with tempfile.NamedTemporaryFile(delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        # Criar tabela manualmente primeiro
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value TEXT
            )
        ''')
        conn.commit()
        conn.close()

        # Chamar init_db novamente
        init_db(temp_db_path)

        # Verificar que ainda existe e não houve erro
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        result = cursor.fetchone()
        assert result is not None
        conn.close()

        mock_info.assert_called_once_with("Banco de dados inicializado com sucesso.")
        assert not mock_error.called

    finally:
        # Pequena pausa para liberar locks no Windows
        import time
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except PermissionError:
            pass  # Ignorar se ainda está sendo usado

@patch('db.setup.logging.info')
@patch('db.setup.logging.error')
def test_init_db_connection_closed(mock_error, mock_info):
    # Testa fechamento de conexão
    with tempfile.NamedTemporaryFile(delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        init_db(temp_db_path)

        # Tentar conectar novamente para verificar que foi fechada corretamente
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()

        mock_info.assert_called_once_with("Banco de dados inicializado com sucesso.")
        assert not mock_error.called

    finally:
        # Pequena pausa para liberar locks no Windows
        import time
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except PermissionError:
            pass  # Ignorar se ainda está sendo usado

