# LegalRAG Documentation Site

Красивая документация в стиле FastAPI, построенная на MkDocs Material.

## 🚀 Быстрый старт

### Linux/Mac

```bash
# Из корня проекта
./serve_docs.sh
```

### Windows

```bash
# Из корня проекта
serve_docs.bat
```

Откройте http://127.0.0.1:8000 в браузере.

---

## 📦 Установка вручную

```bash
# Создать virtual environment
python -m venv venv_docs
source venv_docs/bin/activate  # Linux/Mac
venv_docs\Scripts\activate  # Windows

# Установить зависимости
pip install -r docs_site/requirements.txt

# Запустить dev server
mkdocs serve
```

---

## 🏗️ Build для production

### Автоматически

```bash
./build_docs.sh  # Linux/Mac
```

### Вручную

```bash
mkdocs build
```

Результат в директории `site/`.

---

## 📁 Структура

```
docs_site/
├── mkdocs.yml              # Конфигурация MkDocs
├── requirements.txt        # Python зависимости
├── docs/                   # Markdown документация
│   ├── index.md           # Главная страница
│   ├── stylesheets/       # Кастомные стили
│   │   └── extra.css
│   ├── guides/            # Руководства
│   │   ├── quickstart.md
│   │   └── configuration.md
│   ├── migration/         # Миграция v2.0
│   │   ├── overview.md
│   │   ├── quickstart.md
│   │   └── troubleshooting.md
│   ├── architecture/      # Архитектура
│   │   └── overview.md
│   ├── api/               # API Reference
│   └── development/       # Development guides
└── site/                  # Сгенерированный HTML (после build)
```

---

## 🎨 Возможности

### Material Theme

- 🌓 **Dark/Light mode** - переключение тем
- 🔍 **Search** - полнотекстовый поиск
- 📱 **Responsive** - мобильная версия
- 🎨 **Syntax highlighting** - подсветка кода
- 📊 **Mermaid diagrams** - диаграммы в Markdown

### Markdown Extensions

- ✅ **Task lists** - чеклисты
- 💡 **Admonitions** - красивые info boxes
- 🔗 **Auto-linking** - автоматические ссылки
- 📝 **Code tabs** - вкладки с кодом
- 🔢 **Line numbers** - номера строк в коде
- 📋 **Copy button** - копирование кода

---

## 📝 Добавление новой страницы

1. Создайте `.md` файл в `docs/`:

```bash
touch docs/guides/new_guide.md
```

2. Добавьте в `mkdocs.yml`:

```yaml
nav:
  - Guides:
      - Quickstart: guides/quickstart.md
      - Configuration: guides/configuration.md
      - New Guide: guides/new_guide.md  # Добавить здесь
```

3. Напишите контент:

```markdown
# New Guide

Your content here...

## Code Example

```python
print("Hello, LegalRAG!")
```
```

4. Сохраните и обновите браузер (hot reload).

---

## 🎨 Кастомизация

### Изменить тему

```yaml
# mkdocs.yml
theme:
  palette:
    primary: indigo  # Изменить цвет
    accent: amber
```

### Добавить CSS

Добавьте стили в `docs/stylesheets/extra.css`.

### Добавить JavaScript

```yaml
# mkdocs.yml
extra_javascript:
  - javascripts/custom.js
```

---

## 🚀 Deployment

### GitHub Pages

```bash
mkdocs gh-deploy
```

### Netlify

1. Подключить GitHub репозиторий
2. Build command: `mkdocs build`
3. Publish directory: `site`

### Vercel

```json
{
  "buildCommand": "pip install -r docs_site/requirements.txt && mkdocs build",
  "outputDirectory": "site"
}
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY docs_site/ /app/docs_site/
COPY mkdocs.yml /app/

RUN pip install -r docs_site/requirements.txt
RUN mkdocs build

# Serve with nginx
FROM nginx:alpine
COPY --from=0 /app/site /usr/share/nginx/html
```

---

## 📚 Ресурсы

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Mermaid Diagrams](https://mermaid.js.org/)

---

## 🐛 Troubleshooting

### Ошибка "Module not found"

```bash
pip install --upgrade -r docs_site/requirements.txt
```

### Порт 8000 занят

```bash
mkdocs serve -a 127.0.0.1:8001
```

### CSS не применяется

Проверьте путь в `mkdocs.yml`:

```yaml
extra_css:
  - stylesheets/extra.css  # Должен совпадать с путем в docs/
```

---

**Готово!** 🎉 Создавайте красивую документацию для LegalRAG.
