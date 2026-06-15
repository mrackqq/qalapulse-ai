# QalaPulse AI

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-maps-199900?logo=leaflet&logoColor=white)
![Status](https://img.shields.io/badge/status-MVP-06B6D4)

**QalaPulse AI** — web-MVP городской операционной платформы для Астаны.  
Проект помогает принимать обращения жителей, автоматически анализировать их, расставлять приоритеты, назначать ответственные службы, контролировать SLA и показывать проблемные зоны города на карте.

Проще: это не “сайт для жалоб”, а **мини-диспетчерская для smart city**.

## Зачем Это Нужно

В большом городе обращения жителей приходят по разным темам: транспорт, дороги, освещение, подтопления, снег, мусор, запахи, ЖКХ, безопасность. Проблема в том, что такие обращения сложно быстро:

- классифицировать;
- понять, что срочно;
- найти дубли рядом;
- назначить правильную службу;
- проконтролировать срок реакции;
- показать проблемные зоны на карте;
- подготовить понятный отчет для района или акимата.

**QalaPulse AI** решает эту задачу как MVP для городского пилота.

## Что Уже Работает

### Для жителей

- Отправка обращения через web-форму.
- Описание проблемы текстом.
- Выбор точки на карте.
- Локальный поиск ориентира по Астане.
- Загрузка фото “до”.
- Получение результата AI-анализа после отправки.

### Для городских служб

- Dashboard со списком заявок.
- Карта обращений по Астане.
- Маркеры, кластеры и heatmap.
- Автоназначение ответственной службы.
- SLA-контроль: `on_track`, `due_soon`, `overdue`, `closed`.
- Карточка заявки с деталями.
- Загрузка фото “после”.
- Закрытие задачи.
- История статусов.

### Для акимата / оператора

- Общий dashboard.
- Кабинет района.
- Кабинет службы.
- SLA-рейтинг служб и районов.
- Аналитика по категориям, районам и статусам.
- PDF / XLSX / CSV отчеты.
- Demo-сценарий для презентации.
- Swagger API.

## Главные Фичи MVP

- **Rule-based AI без внешних ключей**  
  Проект работает сразу, даже без OpenAI/DeepSeek API.

- **Optional LLM mode**  
  Можно включить OpenAI или DeepSeek через переменные окружения.

- **Priority score 0-100**  
  Система оценивает срочность обращения.

- **AI confidence**  
  Показывает уверенность анализа.

- **SLA**  
  Для заявок автоматически считается срок реакции.

- **Поиск дублей**  
  Система ищет похожие обращения рядом по координатам и ключевым словам.

- **Фото до/после**  
  Житель добавляет фото проблемы, служба добавляет фото результата.

- **Карта города**  
  Leaflet-карта с маркерами, кластерами и heatmap.

- **Отчеты**  
  Можно скачать PDF, XLSX или CSV.

## Стек

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- SQLite для локального запуска
- PostgreSQL через Docker Compose
- Jinja2 templates
- Tailwind CSS CDN
- Leaflet.js
- Leaflet.markercluster
- Leaflet.heat
- Chart.js
- ReportLab для PDF
- Docker / Docker Compose
- Alembic scaffold

## Быстрый Старт Через Docker

```bash
# (опционально) свои настройки и LLM-ключи
cp .env.example .env

docker compose up --build
```

После запуска открыть:

```text
http://localhost:8000
```

Создать демо-данные:

```bash
docker compose exec web python -m app.seed
```

## Локальный Запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

Открыть:

```text
http://127.0.0.1:8000
```

Если порт занят:

```bash
uvicorn app.main:app --reload --port 8001
```

Тогда открыть:

```text
http://127.0.0.1:8001
```

## Основные Страницы

| URL | Назначение |
| --- | --- |
| `/` | Главная страница |
| `/submit` | Форма обращения жителя |
| `/dashboard` | Общая карта и список обращений |
| `/issues/{id}` | Карточка одной заявки |
| `/analytics` | Аналитика и графики |
| `/reports` | Отчеты |
| `/service` | Кабинет службы |
| `/district` | Кабинет района |
| `/performance` | SLA-рейтинг служб и районов |
| `/demo` | Demo-сценарий для защиты |
| `/login` | Demo-вход в роли |
| `/docs` | Swagger / OpenAPI |

## Demo-Аккаунты

Пароль для всех:

```text
demo
```

| Логин | Роль |
| --- | --- |
| `resident` | Житель |
| `operator` | Городской оператор |
| `esil` | Районный админ Esil |
| `lighting` | Служба освещения |
| `roads` | Дорожная служба |
| `admin` | Super admin |

## Как Показать Проект Жюри

Лучший сценарий для Demo Day:

1. Открыть `/demo`.
2. Нажать **“Загрузить pitch dataset”**.
3. Показать набор реальных городских проблем Астаны:
   - тёмный участок на пешеходном маршруте;
   - подтопление перехода после дождя;
   - гололёд на тротуаре;
   - переполненная контейнерная площадка;
   - выбоина на тротуаре;
   - нет расписания на остановке;
   - запах канализации от коллектора.
4. Нажать **“Создать demo-обращение”**.
5. Открыть созданную заявку.
6. Показать, что система определила:
   - категорию;
   - район;
   - priority score;
   - risk level;
   - AI confidence;
   - ответственную службу;
   - SLA.
7. Открыть `/dashboard`.
8. Переключить карту: кластеры, маркеры, heatmap.
9. Открыть `/service` и показать кабинет службы.
10. В карточке заявки загрузить фото “после” и закрыть задачу.
11. Открыть `/performance` и показать рейтинг служб/районов.
12. Открыть `/reports` и скачать PDF или XLSX.

## Презентация / Pitch Deck

В репозитории есть генератор брендированной презентации (.pptx) для защиты:

```bash
pip install -r requirements-dev.txt
python build_deck.py
```

Создаст `QalaPulse_AI_Pitch.pptx` (13 слайдов, 16:9). Открывается в PowerPoint / Google Slides, экспортируется в PDF или видео. Сам файл `.pptx` не коммитится (генерируется из скрипта).

## Как Работает AI

По умолчанию используется локальный rule-based анализатор:

```text
app/services/ai_analyzer.py
```

Он:

- ищет ключевые слова;
- определяет категорию;
- определяет район;
- считает приоритет;
- добавляет теги;
- формирует объяснение;
- считает confidence.

Optional LLM wrapper:

```text
app/services/llm_analyzer.py
```

Чтобы включить OpenAI:

```env
ENABLE_LLM=true
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
```

Чтобы включить DeepSeek:

```env
ENABLE_LLM=true
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek-chat
```

Если ключа нет или LLM не отвечает, система автоматически возвращается к rule-based режиму.

## Структура Проекта

```text
app/
  main.py                 # routes, pages, API, reports, SLA logic
  models.py               # SQLAlchemy models
  schemas.py              # Pydantic schemas
  seed.py                 # demo data
  database.py             # DB connection
  config.py               # settings and paths
  services/
    ai_analyzer.py        # local rule-based AI
    llm_analyzer.py       # optional OpenAI/DeepSeek mode
    duplicate_detector.py # duplicate search
  templates/              # Jinja2 pages
  static/uploads/         # uploaded photos
alembic/                  # migration scaffold
Dockerfile
docker-compose.yml
requirements.txt
```

## Главные Модели

### Issue

Основная заявка.

Хранит:

- текст обращения;
- адрес;
- координаты;
- фото “до”;
- фото “после”;
- категорию;
- район;
- priority score;
- risk level;
- AI confidence;
- AI mode;
- ответственную службу;
- исполнителя;
- SLA;
- статус;
- дату создания;
- дату закрытия.

### StatusHistory

История изменения статусов.

### DuplicateLink

Связи между похожими обращениями.

## API

Основные endpoints:

| Method | URL | Что делает |
| --- | --- | --- |
| `POST` | `/api/issues` | Создать обращение |
| `GET` | `/api/issues` | Получить список обращений |
| `GET` | `/api/issues/{id}` | Получить одну заявку |
| `PATCH` | `/api/issues/{id}/status` | Изменить статус |
| `GET` | `/api/issues/{id}/duplicates` | Найти похожие обращения |
| `GET` | `/api/stats` | Общая статистика |
| `GET` | `/api/performance` | SLA-рейтинг |
| `GET` | `/api/geocode?q=Mega` | Локальный геокодинг |
| `GET` | `/api/analytics/categories` | Аналитика по категориям |
| `GET` | `/api/analytics/districts` | Аналитика по районам |

Swagger:

```text
/docs
```

## Отчеты

Страница:

```text
/reports
```

Файлы:

```text
/reports/district.xlsx
/reports/district.csv
/reports/district.pdf
/reports/print
```

Примеры фильтров:

```text
/reports?district=Esil
/reports?category=lighting
/reports?status=in_progress
```

## Полезные Команды

Пересоздать демо-данные:

```bash
python -m app.seed
```

Запустить сервер:

```bash
uvicorn app.main:app --reload
```

Проверить Python-синтаксис:

```bash
python -m compileall app
```

Проверить Docker Compose:

```bash
docker compose config --quiet
```

## Кто Что Может Делать В Команде

### Backend

- нормальная авторизация вместо demo-cookie;
- права доступа на уровне API;
- расширенный workflow статусов;
- audit log;
- интеграция с iKOMEK109 или CRM;
- улучшение отчетов;
- тесты.

### Frontend

- улучшить mobile UI;
- сделать timeline заявки;
- улучшить dashboard;
- сделать красивую pitch-страницу;
- улучшить UX кабинета службы;
- добавить manual override для оператора.

### AI / Data

- улучшить rule-based классификацию;
- добавить больше ключевых слов по Астане;
- улучшить поиск дублей;
- настроить LLM mode;
- добавить computer vision для фото “до/после”.

### Product / Pitch

- собрать реальные кейсы Астаны;
- подготовить pitch deck;
- записать demo video;
- сделать one-page PDF;
- описать B2G-модель;
- подготовить план пилота на 2 месяца.

## Что Важно Помнить

- Telegram-бота нет. Это только web-приложение.
- Проект работает без внешних AI-ключей.
- LLM — optional.
- Главная ценность проекта: не прием жалоб, а **приоритизация, карта, SLA, службы, дубли, фото до/после и отчетность для города**.

## Pitch-Формулировка

> QalaPulse AI помогает Астане превратить хаотичные обращения жителей в управляемую систему городских задач. Платформа автоматически классифицирует обращения, определяет приоритет и риск, назначает ответственную службу, контролирует SLA и показывает проблемные зоны города на карте.

## MVP-Ценность Для Акселератора

За 2 месяца акселерации проект можно довести до пилота:

- выбрать 1 район;
- подключить 2-3 категории проблем;
- собрать реальные обращения;
- показать карту проблемных зон;
- измерить SLA;
- показать работу служб;
- сформировать отчет для акимата.

Это делает QalaPulse AI понятным и реалистичным B2G-продуктом для smart city.
