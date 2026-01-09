# Scripts Directory - Optimized Suite Architecture

This directory contains unified suite tools for comprehensive system management, testing, and deployment.

## 🚀 Optimized Architecture

The scripts directory has been **optimized from 38 files to 6 unified suites** (90% reduction) with enhanced functionality and better organization.

## 📦 Available Suites

### ⚡ Автоматический сброс и загрузка документов (`reset_and_ingest_documents.py`)
Один вызов очищает PostgreSQL, Redis и ChromaDB, затем загружает тестовые документы через умный чанкер.

```bash
python scripts/reset_and_ingest_documents.py --documents-path "файлы_для_теста"

# Опционально:
#   --skip-clear   пропустить очистку стораджей
#   --no-verify    пропустить финальную проверку
#   --verbose      подробные логи
```

> Полезно при локальной разработке и в Docker-контейнерах (`/app/файлы_для_теста`).

### 🧪 40-вопросный аудит точности (`run_40_question_evaluation.py`)
Конвейер, который при необходимости запускает очистку/загрузку, затем прогоняет 40 целевых вопросов и сохраняет отчёт.

```bash
# Первый запуск с очисткой и загрузкой
python scripts/run_40_question_evaluation.py --documents-path "файлы_для_теста"

# Повторный прогон без пересоздания данных
python scripts/run_40_question_evaluation.py --skip-ingest --api-base-url "http://localhost:8080"

# Использование кастомного файла с вопросами
python scripts/run_40_question_evaluation.py --skip-ingest --questions-file "вопросы_для_теста.txt"
```

> Отчёты и подробные логи сохраняются в каталоге `results/qa_40_questions` (переопределяется флагом `--results-dir`).

### 1. Production Management Suite (`production_suite.py`)
Unified tool for production system management and startup checks.

```bash
# Production startup checks
python -m scripts.production_suite --mode=startup

# Simplified system check  
python -m scripts.production_suite --mode=check

# Gemini-specific checks
python -m scripts.production_suite --mode=gemini

# Full production verification
python -m scripts.production_suite --mode=full
```

**Replaces:** `production_startup.py`, `production_startup_gemini.py`, `production_check_simplified.py`

### 2. Document Management Suite (`document_suite.py`)
Comprehensive document loading, testing, and management tool.

```bash
# Load PDF documents
python -m scripts.document_suite --mode=pdf --path="/path/to/pdfs"

# Generate test documents
python -m scripts.document_suite --mode=test --count=10

# Run document tests
python -m scripts.document_suite --mode=run-tests

# Full document workflow
python -m scripts.document_suite --mode=full --path="/path" --count=5
```

**Replaces:** `load_pdf_documents.py`, `load_test_documents.py`, `test_runner.py`

### 3. Testing & Debugging Suite (`testing_suite.py`)
Advanced testing, debugging, and performance analysis tool.

```bash
# Debug session
python -m scripts.testing_suite --mode=debug

# System diagnostics
python -m scripts.testing_suite --mode=diagnostics

# Performance testing
python -m scripts.testing_suite --mode=performance

# Full testing session
python -m scripts.testing_suite --mode=full
```

**Replaces:** `debug/`, `analysis/advanced_test.py`, `analysis/full_test.py`, performance testing utilities

### 4. Maintenance Suite (`maintenance_suite.py`)
Database and system maintenance operations.

```bash
# Fix database schema
python -m scripts.maintenance_suite --mode=fix-schema

# Fix database records
python -m scripts.maintenance_suite --mode=fix-records

# Reindex documents
python -m scripts.maintenance_suite --mode=reindex

# Full maintenance (requires --confirm for destructive operations)
python -m scripts.maintenance_suite --mode=full --confirm

# Clear databases (DESTRUCTIVE - requires confirmation)
python -m scripts.maintenance_suite --mode=clear-all --confirm
```

**Replaces:** entire `maintenance/` folder (8 files)

### 5. Analysis & Diagnostics Suite (`analysis_suite.py`)
System analysis, diagnostics, and health monitoring.

```bash
# Document analysis
python -m scripts.analysis_suite --mode=documents

# Database diagnostics
python -m scripts.analysis_suite --mode=database

# ChromaDB diagnostics
python -m scripts.analysis_suite --mode=chroma

# Search system diagnostics
python -m scripts.analysis_suite --mode=search

# Full system analysis
python -m scripts.analysis_suite --mode=full
```

**Replaces:** `analysis/` folder (3 files), `diagnostics/` folder (6 files)

### 6. Utilities Suite (`utilities_suite.py`)
Docker management, bot testing, and system utilities.

```bash
# Docker operations
python -m scripts.utilities_suite --mode=docker --action=build
python -m scripts.utilities_suite --mode=docker --action=start
python -m scripts.utilities_suite --mode=docker --action=status

# Bot testing
python -m scripts.utilities_suite --mode=bot-test

# System health check
python -m scripts.utilities_suite --mode=health-check
```

**Replaces:** `docker_manager.py`, `manual_bot_test.py`

## 🎯 Key Benefits

1. **90% Reduction in Files:** From 38 files to 6 unified suites
2. **Enhanced Functionality:** Each suite combines related operations with improved error handling
3. **Consistent Interface:** All suites use similar command-line arguments and output formats
4. **Better Reporting:** Comprehensive JSON reports with human-readable summaries
5. **Modular Design:** Each suite is self-contained but can work together
6. **Performance Optimized:** Reduced overhead and faster execution

## 📊 Common Options

All suites support these common options:
- `--output <file>` - Specify output file for reports (default: `{suite}_report.json`)
- `--mode <mode>` - Operation mode (varies per suite)

## 🔧 Environment Requirements

Ensure these environment variables are set:
- `TELEGRAM_BOT_TOKEN` - For bot-related operations
- `DATABASE_URL` - For database operations
- `GEMINI_API_KEY` - For AI-related features
- `CHROMA_URL` - For vector database operations (optional)

## 📈 Migration Guide

| Old File/Folder | New Suite | Migration Command |
|-----------------|-----------|-------------------|
| `production_startup.py` | `production_suite.py` | `--mode=startup` |
| `load_pdf_documents.py` | `document_suite.py` | `--mode=pdf` |
| `maintenance/` | `maintenance_suite.py` | Various modes |
| `analysis/` | `analysis_suite.py` | `--mode=documents` |
| `diagnostics/` | `analysis_suite.py` | Various modes |
| `debug/` | `testing_suite.py` | `--mode=debug` |

## 🚨 Important Notes

- **Backup Data:** Before using maintenance suite with `--confirm`
- **Environment:** Ensure all required environment variables are set
- **Dependencies:** Some features require optional dependencies (ChromaDB, Docker, etc.)
- **Permissions:** Some operations may require elevated permissions

## 📝 Example Workflows

### Complete System Check
```bash
# 1. Health check
python -m scripts.utilities_suite --mode=health-check

# 2. System analysis
python -m scripts.analysis_suite --mode=full

# 3. Production readiness
python -m scripts.production_suite --mode=full
```

### Development Workflow
```bash
# 1. Load test data
python -m scripts.document_suite --mode=test --count=20

# 2. Run tests
python -m scripts.testing_suite --mode=full

# 3. Analyze results
python -m scripts.analysis_suite --mode=documents
```

### Maintenance Workflow
```bash
# 1. System diagnostics
python -m scripts.analysis_suite --mode=database

# 2. Fix issues
python -m scripts.maintenance_suite --mode=fix-schema
python -m scripts.maintenance_suite --mode=fix-records

# 3. Reindex if needed
python -m scripts.maintenance_suite --mode=reindex
```
- **Информирование пользователей**: объясняют архитектурные решения и изменения.
- **Документирование истории**: сохраняют информацию о том, что было удалено и почему.

> **Использование:** Запустите любой из этих скриптов, чтобы получить информацию об изменениях в тестовой инфраструктуре проекта.
