import json
import logging
import sys
import os

# Adicionar caminho para módulos
sys.path.append(os.path.dirname(__file__))

from flask import Flask, request, jsonify
from ia.ai import generate_text
from db.setup import init_db

app = Flask(__name__)

@app.route('/ai', methods=['POST'])
def ai_endpoint():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        response = generate_text(prompt)
        return jsonify({'response': response})
    except Exception as e:
        logging.error(f"Erro no endpoint AI: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Carregar config
    try:
        with open('.misa/config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Arquivo de configuração não encontrado.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Erro ao carregar config: {e}")
        sys.exit(1)

    # Configurar logging
    logging.basicConfig(level=getattr(logging, config['log_level']))

    # Inicializar DB
    init_db(config['db_path'])

    # Executar IA básica
    print("Executando IA básica...")
    resultado = generate_text("Olá, mundo!")
    print(f"Resultado: {resultado}")

    # Executar app Flask
    app.run(host='0.0.0.0', port=config['port'])