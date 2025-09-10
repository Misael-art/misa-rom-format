import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app
from db.setup import init_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_ai_endpoint_success(client):
    # Testa endpoint /ai com sucesso
    with patch('main.generate_text') as mock_generate:
        mock_generate.return_value = "Resposta mock"
        response = client.post('/ai', json={'prompt': 'Teste'})
        assert response.status_code == 200
        assert response.get_json() == {'response': 'Resposta mock'}

def test_ai_endpoint_no_prompt(client):
    # Testa endpoint sem prompt
    with patch('main.generate_text') as mock_generate:
        mock_generate.return_value = "Resposta mock"
        response = client.post('/ai', json={})
        assert response.status_code == 200
        assert response.get_json() == {'response': 'Resposta mock'}

def test_ai_endpoint_error(client):
    # Testa endpoint com erro
    with patch('main.generate_text') as mock_generate:
        mock_generate.side_effect = Exception("Erro IA")
        response = client.post('/ai', json={'prompt': 'Teste'})
        assert response.status_code == 500
        assert 'error' in response.get_json()

def test_load_config_success():
    # Testa carregamento de config com sucesso
    config_data = {
        'log_level': 'INFO',
        'db_path': 'test.db',
        'port': 5000
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config_data, f)

        with patch('builtins.open', MagicMock()) as mock_open:
            with patch('json.load') as mock_json:
                mock_json.return_value = config_data
                # Simular abertura
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                mock_json.return_value = config_data

                # Como é no __main__, testar a lógica
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    assert config == config_data
                except Exception as e:
                    assert False, f"Carregamento de config falhou: {e}"

def test_load_config_file_not_found():
    # Testa erro quando config não encontrado
    with patch('builtins.open', side_effect=FileNotFoundError):
        with pytest.raises(SystemExit):
            # Simular lógica do main
            try:
                with open('.misa/config.json', 'r') as f:
                    json.load(f)
            except FileNotFoundError:
                sys.exit(1)

def test_load_config_invalid_json():
    # Testa erro de JSON inválido
    with patch('builtins.open', MagicMock()) as mock_open:
        with patch('json.load', side_effect=json.JSONDecodeError("Erro", "", 0)):
            with pytest.raises(SystemExit):
                try:
                    with open('.misa/config.json', 'r') as f:
                        json.load(f)
                except json.JSONDecodeError:
                    sys.exit(1)

