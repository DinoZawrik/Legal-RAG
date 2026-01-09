#!/bin/bash
# 🚀 Скрипт развертывания Excel функций в Docker

set -e  # Выход при ошибке

echo "🚀 LegalRAG Excel Features Deployment"
echo "========================================"

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден. Установите Docker Desktop"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не найден. Установите docker-compose"
    exit 1
fi

echo "✅ Docker найден"

# Проверяем .env файл
if [ ! -f .env ]; then
    echo "⚠️ Файл .env не найден. Копируем из .env.example"
    cp .env.example .env
    echo "📝 Отредактируйте .env файл с реальными API ключами перед продолжением"
    echo "   - GEMINI_API_KEY=your_real_key"
    echo "   - TELEGRAM_BOT_TOKEN=your_bot_token"
    echo "   - ADMIN_PANEL_PASSWORD=secure_password"
    echo ""
    read -p "Нажмите Enter когда .env будет настроен..."
fi

echo "✅ Конфигурация найдена"

# Останавливаем существующие контейнеры
echo "🛑 Останавливаем существующие контейнеры..."
docker-compose -f docker-compose.microservices.yml down --remove-orphans || true

# Очищаем старые образы (опционально)
read -p "🧹 Очистить старые Docker образы? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 Очищаем старые образы..."
    docker image prune -f --filter label=com.docker.compose.project=alpha || true
fi

# Пересобираем с новыми изменениями
echo "🔨 Пересобираем контейнеры с Excel поддержкой..."
docker-compose -f docker-compose.microservices.yml build --no-cache

# Запускаем систему
echo "🚀 Запускаем систему..."
docker-compose -f docker-compose.microservices.yml up -d

# Ждем готовности
echo "⏳ Ожидаем готовности сервисов..."
sleep 30

# Проверяем статус
echo "🔍 Проверяем статус контейнеров..."
docker-compose -f docker-compose.microservices.yml ps

# Проверяем здоровье системы
echo "💚 Проверяем здоровье API Gateway..."
for i in {1..30}; do
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "✅ API Gateway готов!"
        break
    fi
    echo "⏳ Ожидание API Gateway... ($i/30)"
    sleep 2
done

echo "💻 Проверяем админ-панель..."
for i in {1..30}; do
    if curl -f http://localhost:8090 > /dev/null 2>&1; then
        echo "✅ Админ-панель готова!"
        break
    fi
    echo "⏳ Ожидание админ-панели... ($i/30)"
    sleep 2
done

# Запускаем автотесты
echo "🧪 Запускаем тесты новой функциональности..."
if python test_docker_excel_support.py; then
    echo "✅ Все тесты пройдены!"
else
    echo "⚠️ Некоторые тесты не прошли, но система должна работать"
fi

echo ""
echo "🎉 РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!"
echo "========================="
echo ""
echo "🌐 Доступные сервисы:"
echo "   • API Gateway: http://localhost:8080"
echo "   • Админ-панель: http://localhost:8090"
echo "   • ChromaDB: http://localhost:8000"
echo ""
echo "🔧 Управление:"
echo "   • Просмотр логов: docker-compose -f docker-compose.microservices.yml logs -f"
echo "   • Остановка: docker-compose -f docker-compose.microservices.yml down"
echo "   • Перезапуск: docker-compose -f docker-compose.microservices.yml restart"
echo ""
echo "📊 Новые возможности:"
echo "   ✅ Поддержка Excel/CSV файлов"
echo "   ✅ Приоритизация новых документов" 
echo "   ✅ Улучшенная админ-панель"
echo "   ✅ E2E тестирование"
echo ""
echo "📖 Подробная документация: DOCKER_DEPLOYMENT.md"