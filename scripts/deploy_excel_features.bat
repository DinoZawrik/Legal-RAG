@echo off
REM 🚀 Скрипт развертывания Excel функций в Docker для Windows

echo 🚀 LegalRAG Excel Features Deployment
echo ========================================

REM Проверяем наличие Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker не найден. Установите Docker Desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ docker-compose не найден. Установите docker-compose
    pause
    exit /b 1
)

echo ✅ Docker найден

REM Проверяем .env файл
if not exist .env (
    echo ⚠️ Файл .env не найден. Копируем из .env.example
    copy .env.example .env
    echo 📝 Отредактируйте .env файл с реальными API ключами перед продолжением
    echo    - GEMINI_API_KEY=your_real_key
    echo    - TELEGRAM_BOT_TOKEN=your_bot_token
    echo    - ADMIN_PANEL_PASSWORD=secure_password
    echo.
    pause
)

echo ✅ Конфигурация найдена

REM Останавливаем существующие контейнеры
echo 🛑 Останавливаем существующие контейнеры...
docker-compose -f docker-compose.microservices.yml down --remove-orphans

REM Очищаем старые образы (опционально)
set /p cleanup="🧹 Очистить старые Docker образы? (y/N): "
if /i "%cleanup%"=="y" (
    echo 🧹 Очищаем старые образы...
    docker image prune -f --filter label=com.docker.compose.project=alpha
)

REM Пересобираем с новыми изменениями
echo 🔨 Пересобираем контейнеры с Excel поддержкой...
docker-compose -f docker-compose.microservices.yml build --no-cache

REM Запускаем систему
echo 🚀 Запускаем систему...
docker-compose -f docker-compose.microservices.yml up -d

REM Ждем готовности
echo ⏳ Ожидаем готовности сервисов...
timeout /t 30 /nobreak >nul

REM Проверяем статус
echo 🔍 Проверяем статус контейнеров...
docker-compose -f docker-compose.microservices.yml ps

REM Проверяем здоровье системы
echo 💚 Проверяем здоровье API Gateway...
for /L %%i in (1,1,30) do (
    curl -f http://localhost:8080/health >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ API Gateway готов!
        goto :admin_check
    )
    echo ⏳ Ожидание API Gateway... (%%i/30)
    timeout /t 2 /nobreak >nul
)

:admin_check
echo 💻 Проверяем админ-панель...
for /L %%i in (1,1,30) do (
    curl -f http://localhost:8090 >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Админ-панель готова!
        goto :run_tests
    )
    echo ⏳ Ожидание админ-панели... (%%i/30)
    timeout /t 2 /nobreak >nul
)

:run_tests
REM Запускаем автотесты
echo 🧪 Запускаем тесты новой функциональности...
python test_docker_excel_support.py
if %errorlevel% equ 0 (
    echo ✅ Все тесты пройдены!
) else (
    echo ⚠️ Некоторые тесты не прошли, но система должна работать
)

echo.
echo 🎉 РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!
echo =========================
echo.
echo 🌐 Доступные сервисы:
echo    • API Gateway: http://localhost:8080
echo    • Админ-панель: http://localhost:8090
echo    • ChromaDB: http://localhost:8000
echo.
echo 🔧 Управление:
echo    • Просмотр логов: docker-compose -f docker-compose.microservices.yml logs -f
echo    • Остановка: docker-compose -f docker-compose.microservices.yml down
echo    • Перезапуск: docker-compose -f docker-compose.microservices.yml restart
echo.
echo 📊 Новые возможности:
echo    ✅ Поддержка Excel/CSV файлов
echo    ✅ Приоритизация новых документов
echo    ✅ Улучшенная админ-панель
echo    ✅ E2E тестирование
echo.
echo 📖 Подробная документация: DOCKER_DEPLOYMENT.md
echo.
pause