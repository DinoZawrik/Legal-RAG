#!/usr/bin/env python3
"""
Скрипт правильного запуска админ панели с переменными окружения
"""

import os
import sys
import subprocess

def main():
    # Устанавливаем правильные переменные окружения
    env = os.environ.copy()
    env['API_GATEWAY_URL'] = 'http://localhost:8080'
    env['PYTHONPATH'] = os.getcwd()
    
    # Переходим в директорию админ панели
    admin_panel_dir = os.path.join(os.getcwd(), 'admin_panel')
    
    print("Starting AdminPanel with correct environment variables...")
    print(f"API_GATEWAY_URL: {env['API_GATEWAY_URL']}")
    print(f"Working directory: {admin_panel_dir}")
    
    # Запускаем streamlit с правильными переменными
    cmd = [sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.port', '8090']
    
    subprocess.run(cmd, cwd=admin_panel_dir, env=env)

if __name__ == "__main__":
    main()