# 🗺 numenews Roadmap

> Каждая задача — **атомарная**: один осмысленный коммит, чёткое Definition of Done, минимум зависимостей от незавершённых задач.

---

## 📖 Как читать этот документ

- **Фазы** выполняются последовательно. Внутри фазы задачи можно брать в любом порядке, если не указано `depends on`.
- **Атомарность** = задача завершается за один рабочий подход (30 мин – 4 часа) и оставляет репозиторий в рабочем состоянии.
- **DoD** (Definition of Done) — обязательные критерии завершения.
- **Оценка** — грубая: `S` (< 1ч), `M` (1–3ч), `L` (3–8ч). `XL` — признак, что задачу надо дробить.
- **Метка 🧪** — задача сопровождается тестами.
- **Метка 📝** — задача сопровождается документацией (README, ADR, docstring).
- **Метка 🔌** — задача требует внешнего сервиса (Docker, API).
- **Метка 🤖** — задача связана с LLM-агентом или промптом.

Статусы: `[ ]` — не начато, `[~]` — в работе, `[x]` — готово, `[-]` — отменено.

---

## 🎯 Целевое состояние (Definition of Done проекта)

- ✅ MCP-сервер с 9 кастомными инструментами, подключается к Claude Desktop / Cursor.
- ✅ One-shot CLI с JSON-выводом (`numenews today`, `numenews forecast`, ...).
- ✅ RAG-пайплайн: fetch → extract → compute → embed → search → forecast → save.
- ✅ Qdrant с 5 коллекциями, гибридный поиск, payload-индексы.
- ✅ Локальные эмбеддинги через `fastembed` (384d + 768d), без API-ключей.
- ✅ `pydantic-ai` для LLM-агентов со structured output.
- ✅ 5 новостных API за единым Protocol-интерфейсом с кэшем `hishel`.
- ✅ Долговременная память активаций чисел в `number_history`.
- ✅ `mypy --strict` + `pydantic v2` на всех границах модулей.
- ✅ Тесты: unit + property-based (`hypothesis`) + integration (Qdrant in-memory, `respx`) + eval (`ragas`).
- ✅ Покрытие: numerology ≥ 95%, application ≥ 80%, infrastructure ≥ 70%.
- ✅ `make lint && make test` проходят локально.
- ✅ `make mcp` поднимает MCP-сервер, `make dev` — Qdrant.

---

## Phase 0 — Skeleton 🦴

> **Цель:** пустой репозиторий превращается в проект, где всё линтится, тестируется и поднимается.
> **Результат фазы:** `make dev` поднимает Qdrant, `make lint && make test` зелёные.

### 0.1. Инициализация репозитория
- [x] `git init`, `.gitignore` (Python, uv, IDE, `.env`, `*.pyc`, `.qdrant/`, `*.hishel/`) · `S`
- [x] `LICENSE.md` (MIT) · `S` 📝
- [x] `README.md` (обзор + быстрый старт + скриншот JSON) · `S` 📝
- [x] `CONTRIBUTING.md` · `S` 📝
- [x] `CHANGELOG.md` (Keep a Changelog) · `S` 📝
- [x] `AGENTS.md` — единый файл для агентных IDE · `M` 📝
- [x] Первый коммит: `chore: initial skeleton` · `S`

**DoD:** репозиторий создан, `.md` файлы на месте, `AGENTS.md` ссылается на `ROADMAP.md`.

### 0.2. uv + src-layout
- [x] Корневой `pyproject.toml` с `[project]` и dev-зависимостями · `S` 📝
- [x] Директория `src/numenews/` с пустым `__init__.py` · `S`
- [x] Подпакеты: `models/`, `numerology/`, `news/`, `embeddings/`, `vector/`, `agents/`, `mcp/`, `cli/` · `S`
- [x] Директории `tests/unit`, `tests/integration`, `tests/eval`, `docs/`, `docs/adr/`, `docs/agentic/` · `S`
- [x] `uv sync` работает без ошибок · `S`
- [x] Коммит: `chore: uv + src-layout skeleton` · `S`

**DoD:** `uv sync` проходит, структура директорий на месте.

### 0.3. Инфраструктура (Docker Compose + Qdrant)
- [x] `docker-compose.yml` с Qdrant · `S` 🔌
- [x] Volume `qdrant_storage` для персистентности · `S` 🔌
- [x] Healthcheck через HTTP API Qdrant · `S` 🔌
      *В образе `qdrant/qdrant` нет `curl`, поэтому проверка — TCP-проба HTTP-порта через `bash /dev/tcp`; сам HTTP API (`/readyz`, `/collections`) проверен с хоста.*
- [x] Порт `:6333` (HTTP) и `:6334` (gRPC) · `S`
- [x] `docker compose up -d` поднимает Qdrant · `S` 🔌
- [x] Коммит: `chore(infra): qdrant via docker compose` · `S`

**DoD:** `docker compose up -d` — контейнер `healthy`, Web UI на `:6333/dashboard`.

### 0.4. Тулинг (ruff, mypy, pytest, pre-commit)
- [x] Конфиг `ruff` (line-length=100, target=py314, select = all) · `S`
      *`target=py312` в черновике устарел — проект на Python 3.14. Вместо буквального `select = all` — курируемый набор (`E, W, F, I, N, UP, B, A, C4, SIM, ANN, RUF, PTH`) с `ignore = ["ANN401"]`; обоснование в комментарии `pyproject.toml`.*
- [x] Конфиг `mypy --strict` с плагином `pydantic.mypy` · `S`
- [x] Конфиг `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) · `S`
- [x] Конфиг `coverage` (branch, fail_under=80) · `S`
      *В phase 0 `fail_under = 0`: на скелете покрывать нечего, пороги слоёв (95/80/70%) включаются вместе со слоями и в phase 10.*
- [x] `.pre-commit-config.yaml`: ruff, ruff-format, mypy, check-yaml, end-of-file-fixer · `M`
- [x] `uv run pre-commit install` работает · `S`
- [x] `uv run pre-commit run --all-files` проходит · `S`
- [x] Коммит: `chore: ruff + mypy strict + pytest + pre-commit` · `M`

**DoD:** `pre-commit run --all-files` — все хуки passed.

### 0.5. Makefile
- [x] `make install` — `uv sync --all-extras` · `S`
- [x] `make lint` — ruff + mypy --strict · `S`
- [x] `make format` — ruff format + ruff check --fix · `S`
- [x] `make test` / `test-unit` / `test-integration` / `test-eval` · `M`
- [x] `make dev` — `docker compose up -d` · `S` 🔌
- [x] `make dev-down` — `docker compose down` · `S`
- [x] `make mcp` — запуск MCP-сервера (заглушка) · `S`
- [x] `make clean` — stop + rm volumes + rm caches · `S`
- [x] Коммит: `chore: Makefile with dev/lint/test/mcp/clean` · `M`

**DoD:** `make lint && make test` проходят на пустом проекте.

> *В этот же коммит добавлены минимальные `tests/conftest.py` (флаг `--run-eval`) и smoke-тесты
> юнита/интеграции/eval, иначе `make test`, `make test-integration` и `make test-eval` падают
> с «no tests ran»; тесты не заглушки-пустышки, а проверки контрактов (JSON в stdout у CLI,
> пустой stdout у MCP, in-memory Qdrant). Фикстуры добавляет 0.8.*

### 0.6. Конфиг через pydantic-settings
- [x] `src/numenews/config.py` — `Settings(BaseSettings)` · `M` 🧪
- [x] Поля: `qdrant_url`, `qdrant_api_key`, `openai_api_key`, `openai_base_url`, `llm_model`, `log_level`, `cache_dir` · `M`
      *Плюс `environment: Literal["dev", "prod"] = "dev"` — им переключается рендерер логов (0.7), отдельного `log_json` не заводим.*
- [x] `.env.example` со всеми переменными · `S` 📝
- [x] Загрузка через `model_config = SettingsConfigDict(env_file=".env")` · `S`
- [x] Тест: невалидный конфиг кидает `ValidationError` · `S` 🧪
- [x] Коммит: `feat(config): pydantic-settings` · `M` 🧪

**DoD:** `Settings()` читает `.env`, тест на невалидные значения зелёный.

### 0.7. Логирование (structlog)
- [ ] `src/numenews/logging.py` — настройка `structlog` · `M`
- [ ] JSON-вывод в production, human-readable в dev (`log_level`) · `S`
- [ ] Корреляция через `contextvars` (request_id, news_id) · `M`
- [ ] Интеграция с `pydantic-settings` · `S`
- [ ] Коммит: `feat(logging): structlog setup` · `M` 📝

**DoD:** `structlog.get_logger().info("test")` пишет JSON.

### 0.8. Первые тесты
- [ ] `tests/conftest.py` с фикстурами (`event_loop`, `anyio_backend`, `tmp_cache_dir`) · `S`
- [ ] `tests/unit/test_smoke.py` — `assert True` · `S` 🧪
- [ ] `tests/integration/__init__.py` + фикстура Qdrant in-memory · `M` 🧪
- [ ] `tests/eval/__init__.py` · `S`
- [ ] Коммит: `test: pytest scaffolding` · `M` 🧪

**DoD:** `make test` зелёный, фикстура `qdrant_in_memory` доступна.

### 0.9. Документация фазы 0
- [ ] `docs/ARCHITECTURE.md` — шаблон с заголовками · `S` 📝
- [ ] `docs/NUMEROLOGY.md` — шаблон · `S` 📝
- [ ] `docs/adr/0001-record-architecture-decisions.md` · `S` 📝
- [ ] `docs/adr/template.md` · `S` 📝
- [ ] `docs/agentic/AGENT_WORKFLOW.md` — как работаем с агентами · `M` 📝
- [ ] `ROADMAP.md` (этот документ) · `M` 📝
- [ ] Коммит: `docs: architecture, numerology, ADR templates, roadmap` · `M`

**✅ Phase 0 завершена, когда:** `make dev` поднимает Qdrant, `make lint && make test` зелёные, `Settings()` работает.

---

## Phase 1 — Numerology (чистая логика) 🧮

> **Цель:** чистый модуль нумерологии без зависимостей от LLM и Qdrant.
> **Результат фазы:** покрытие `numerology/` ≥ 95%, все инварианты покрыты property-based тестами.

### 1.1. Доменные модели (Pydantic)
- [ ] `NewsId`, `PatternId`, `ForecastId` (UUID-обёртки) · `S` 🧪
- [ ] `NewsItem` (id, title, text, source, date, url, numbers, numerology_value) · `M` 🧪
- [ ] `ExtractedNumbers` (numbers: list[int], sources: list[str], symbols: list[str]) · `S` 🧪
- [ ] `NumerologyResult` (value, is_master, breakdown) · `S` 🧪
- [ ] `Pattern` (id, type, numbers, news_ids, strength, interpretation) · `M` 🧪
- [ ] `Forecast` (date, dominant_number, master_active, patterns, forecast, advice, warnings) · `M` 🧪
- [ ] `NumberActivation` (number, date, news_id, context) · `S` 🧪
- [ ] Коммит: `feat(models): domain pydantic models` · `M` 🧪

**DoD:** все модели проходят `mypy --strict`, `model_config = ConfigDict(frozen=True, strict=True)`.

### 1.2. Редукция
- [ ] `reduce_number(n: int) -> int` — свёртка до 1–9 · `S` 🧪
- [ ] Исключения: 11, 22, 33 не редуцируются (мастер-числа) · `S` 🧪
- [ ] `reduce_date(d: date) -> int` — сумма цифр даты · `S` 🧪
- [ ] Property-based тесты: результат всегда ∈ {1..9, 11, 22, 33} · `M` 🧪
- [ ] Коммит: `feat(numerology): reduction` · `M` 🧪

**DoD:** `hypothesis` генерирует 1000 случайных чисел, инвариант держится.

### 1.3. Мастер-числа
- [ ] `is_master(n: int) -> bool` · `S` 🧪
- [ ] `MASTER_NUMBERS = frozenset({11, 22, 33})` · `S`
- [ ] `check_master_numbers(numbers: Sequence[int]) -> MasterCheckResult` · `S` 🧪
- [ ] Тесты: границы, пустой список, дубликаты · `S` 🧪
- [ ] Коммит: `feat(numerology): master numbers` · `S` 🧪

**DoD:** функция возвращает `MasterCheckResult(has_master, master_numbers, count)`.

### 1.4. Гематрия
- [ ] `gematria_simple(text: str) -> int` — A=1..Z=26 + кириллица · `M` 🧪
- [ ] `gematria_reduce(text: str) -> int` — гематрия + редукция · `S` 🧪
- [ ] Нормализация: lowercase, удаление пробелов и пунктуации · `S` 🧪
- [ ] Property-based: гематрия неотрицательна, редукция в допустимом множестве · `M` 🧪
- [ ] Тесты на известные значения (например, `"sun" -> 54`) · `S` 🧪
- [ ] Коммит: `feat(numerology): gematria` · `M` 🧪

**DoD:** поддержка латиницы и кириллицы, тесты на граничные случаи.

### 1.5. Резонанс дат
- [ ] `date_resonance(d1: date, d2: date) -> int` — совпадение редуцированных значений · `S` 🧪
- [ ] `find_date_resonances(dates: Sequence[date]) -> list[tuple[date, date, int]]` · `M` 🧪
- [ ] Тесты: одинаковые даты, разные, диапазон · `S` 🧪
- [ ] Коммит: `feat(numerology): date resonance` · `M` 🧪

**DoD:** возвращает пары с одинаковым редуцированным значением.

### 1.6. Извлечение чисел (regex-фолбэк)
- [ ] `extract_numbers_regex(text: str) -> list[int]` — числа из текста · `S` 🧪
- [ ] `extract_dates_regex(text: str) -> list[date]` — даты в форматах ISO, DD.MM.YYYY, «15 марта» · `M` 🧪
- [ ] `extract_symbols(text: str, symbols: Sequence[str]) -> list[str]` — повторяющиеся символы · `S` 🧪
- [ ] Коммит: `feat(numerology): regex extraction fallback` · `M` 🧪

**DoD:** работает без LLM, используется как fallback при ошибке агента.

### 1.7. Публичный API модуля
- [ ] `src/numenews/numerology/__init__.py` с `__all__` · `S`
- [ ] `compute_numerology(text: str) -> NumerologyResult` — объединяет всё · `M` 🧪
- [ ] Docstrings на публичных функциях · `S` 📝
- [ ] Коммит: `feat(numerology): public api` · `M` 🧪

**DoD:** модуль импортируется, `compute_numerology("Sun rises")` возвращает результат.

### 1.8. Документация нумерологии
- [ ] `docs/NUMEROLOGY.md` — редукция, мастер-числа, гематрия с примерами · `M` 📝
- [ ] `docs/adr/0002-numerology-scope.md` — почему только редукция + мастер + гематрия · `M` 📝
- [ ] Коммит: `docs: numerology rules and scope` · `M` 📝

**✅ Phase 1 завершена, когда:** покрытие `numerology/` ≥ 95%, `mypy --strict` зелёный, property-based тесты проходят.

---

## Phase 2 — News Sources 🌐

> **Цель:** 5 новостных API за единым Protocol-интерфейсом с кэшем.
> **Результат фазы:** `fetch_news(topic, date_range)` возвращает объединённый список из всех 5 API.

### 2.1. Protocol-интерфейс
- [ ] `NewsSource(Protocol)` с `async def fetch(topic, date_range) -> list[NewsItem]` · `S` 🧪
- [ ] `NewsSourceError` — базовое исключение · `S`
- [ ] `Topic`, `DateRange` — Pydantic-модели · `S` 🧪
- [ ] Коммит: `feat(news): source protocol` · `S` 🧪

**DoD:** `mypy --strict` проверяет структурную типизацию.

### 2.2. HTTP-клиент с кэшем (hishel)
- [ ] `httpx.AsyncClient` + `hishel.AsyncCacheClient` · `M` 🧪
- [ ] Кэш-директория из `Settings.cache_dir` · `S`
- [ ] TTL 15 минут для новостей · `S` 🧪
- [ ] Обёртка с `tenacity` для retry на 5xx · `M` 🧪
- [ ] Тест: повторный запрос идёт из кэша (`respx`) · `M` 🧪
- [ ] Коммит: `feat(news): http client with hishel cache` · `M` 🧪

**DoD:** тест через `respx` подтверждает, что второй запрос не бьёт по сети.

### 2.3. GDELT adapter
- [ ] `GDELTSource(NewsSource)` · `M` 🧪
- [ ] Парсинг ответа GDELT Doc API · `M` 🧪
- [ ] Маппинг в `NewsItem` · `S` 🧪
- [ ] Тест через `respx` с фикстурой ответа · `M` 🧪
- [ ] Коммит: `feat(news): gdelt adapter` · `M` 🧪

**DoD:** реальный запрос к GDELT возвращает новости, тест изолирован через `respx`.

### 2.4. NewsAPI.org adapter
- [ ] `NewsAPISource(NewsSource)` · `M` 🧪
- [ ] Чтение `NEWSAPI_KEY` из `Settings` · `S`
- [ ] Обработка 429 (rate limit) через `tenacity` · `M` 🧪
- [ ] Тест через `respx` · `M` 🧪
- [ ] Коммит: `feat(news): newsapi adapter` · `M` 🧪

**DoD:** тест на 429 покрыт, retry срабатывает.

### 2.5. GNews adapter
- [ ] `GNewsSource(NewsSource)` · `M` 🧪
- [ ] Чтение `GNEWS_KEY` · `S`
- [ ] Маппинг в `NewsItem` · `S` 🧪
- [ ] Коммит: `feat(news): gnews adapter` · `M` 🧪

### 2.6. Mediastack adapter
- [ ] `MediastackSource(NewsSource)` · `M` 🧪
- [ ] Чтение `MEDIASTACK_KEY` · `S`
- [ ] Коммит: `feat(news): mediastack adapter` · `M` 🧪

### 2.7. Currents API adapter
- [ ] `CurrentsSource(NewsSource)` · `M` 🧪
- [ ] Чтение `CURRENTS_KEY` · `S`
- [ ] Коммит: `feat(news): currents adapter` · `M` 🧪

### 2.8. Агрегатор
- [ ] `NewsAggregator` — параллельный опрос через `asyncio.gather` · `M` 🧪
- [ ] Дедупликация по `(title, source, date)` · `M` 🧪
- [ ] Graceful degradation: если один API упал — возвращаем остальные · `M` 🧪
- [ ] Тест: 2 из 5 падают — возвращаются 3 · `M` 🧪
- [ ] Коммит: `feat(news): aggregator with graceful degradation` · `M` 🧪

**DoD:** агрегатор возвращает объединённый список, не падает при падении одного источника.

### 2.9. Документация источников
- [ ] `docs/NEWS_SOURCES.md` — лимиты, ключи, примеры запросов · `M` 📝
- [ ] Обновить `.env.example` · `S`
- [ ] Коммит: `docs: news sources` · `M`

**✅ Phase 2 завершена, когда:** `fetch_news("politics", last_7d)` возвращает новости из ≥ 3 источников.

---

## Phase 3 — Embeddings + Qdrant 🧠

> **Цель:** векторный слой с 5 коллекциями и гибридным поиском.
> **Результат фазы:** новости индексируются, семантический поиск работает.

### 3.1. Embeddings (fastembed)
- [ ] `Embedder` Protocol с `embed(texts) -> list[list[float]]` · `S` 🧪
- [ ] `FastEmbedSmall` (384d, `bge-small-en-v1.5`) · `M` 🧪
- [ ] `FastEmbedBase` (768d, `bge-base-en-v1.5`) · `M` 🧪
- [ ] Lazy-инициализация модели (не грузить при импорте) · `M` 🧪
- [ ] Тест: эмбеддинг детерминирован, размерность корректна · `M` 🧪
- [ ] Коммит: `feat(embeddings): fastembed wrapper` · `M` 🧪

**DoD:** `FastEmbedBase().embed(["hello"])` возвращает `list[float]` длиной 768.

### 3.2. Qdrant-клиент
- [ ] `QdrantClient` обёртка в `vector/client.py` · `M` 🧪
- [ ] Подключение к Docker Qdrant из `Settings.qdrant_url` · `S`
- [ ] Health-check при старте · `S` 🧪
- [ ] Фикстура `qdrant_in_memory` для тестов · `M` 🧪
- [ ] Коммит: `feat(vector): qdrant client` · `M` 🧪

**DoD:** тест использует `QdrantClient(":memory:")`, интеграционный тест — Docker.

### 3.3. Коллекция `news`
- [ ] `create_news_collection()` с 768d COSINE · `M` 🧪
- [ ] Payload-индексы: `date`, `source`, `numerology_value`, `master_number` · `M` 🧪
- [ ] `upsert_news(items: Sequence[NewsItem])` · `M` 🧪
- [ ] `search_news(query, filters, limit)` · `M` 🧪
- [ ] Тест: upsert + search по семантике · `M` 🧪
- [ ] Коммит: `feat(vector): news collection` · `M` 🧪

**DoD:** payload-индексы созданы **до** ингеста, поиск с фильтром работает.

### 3.4. Коллекция `numbers`
- [ ] `create_numbers_collection()` с 384d COSINE · `M` 🧪
- [ ] Payload-индексы: `number`, `context` · `M` 🧪
- [ ] `upsert_number_patterns(patterns)` · `M` 🧪
- [ ] Коммит: `feat(vector): numbers collection` · `M` 🧪

### 3.5. Коллекция `patterns`
- [ ] `create_patterns_collection()` с 768d · `M` 🧪
- [ ] Payload-индексы: `type`, `strength`, `discovered_at` · `M` 🧪
- [ ] `save_pattern(pattern)`, `find_similar_patterns(query)` · `M` 🧪
- [ ] Коммит: `feat(vector): patterns collection` · `M` 🧪

### 3.6. Коллекция `forecasts`
- [ ] `create_forecasts_collection()` с 768d · `M` 🧪
- [ ] Payload-индексы: `date`, `dominant_number` · `M` 🧪
- [ ] `save_forecast`, `get_forecast(date)` · `M` 🧪
- [ ] Коммит: `feat(vector): forecasts collection` · `M` 🧪

### 3.7. Коллекция `number_history`
- [ ] Создание без вектора (payload-only) · `M` 🧪
- [ ] Payload-индексы: `number`, `date` · `M` 🧪
- [ ] `record_activation(number, date, news_id, context)` · `M` 🧪
- [ ] `get_history(number, days)` · `M` 🧪
- [ ] Коммит: `feat(vector): number history` · `M` 🧪

### 3.8. Гибридный поиск
- [ ] `hybrid_search_news(query, filter_, limit)` — dense + filter · `M` 🧪
- [ ] Фильтр внутри `Prefetch` при multi-stage запросе · `M` 🧪
- [ ] Тест: фильтр по `numerology_value=7` + семантический запрос · `M` 🧪
- [ ] Коммит: `feat(vector): hybrid search` · `M` 🧪

**DoD:** pre-filtering работает, тест с комбинацией dense + payload зелёный.

### 3.9. Документация Qdrant
- [ ] `docs/QDRANT_COLLECTIONS.md` — 5 коллекций, payload-схемы, примеры · `M` 📝
- [ ] `docs/EMBEDDINGS.md` — почему 384d и 768d, fastembed · `M` 📝
- [ ] ADR `0003-local-embeddings.md` · `M` 📝
- [ ] Коммит: `docs: qdrant + embeddings` · `M` 📝

**✅ Phase 3 завершена, когда:** новости индексируются, гибридный поиск возвращает релевантные результаты.

---

## Phase 4 — LLM Agents (pydantic-ai) 🤖

> **Цель:** 3 агента для извлечения чисел, поиска паттернов и прогноза.
> **Результат фазы:** каждый агент возвращает валидированную Pydantic-модель.

### 4.1. LLM-клиент
- [ ] `build_llm_model()` — OpenAI-совместимый клиент из `Settings` · `M` 🧪
- [ ] Поддержка OpenRouter / локального Ollama через `base_url` · `S`
- [ ] Тест: модель инициализируется, конфиг валиден · `S` 🧪
- [ ] Коммит: `feat(agents): llm client` · `S` 🧪

**DoD:** `build_llm_model()` работает с любым OpenAI-совместимым эндпоинтом.

### 4.2. ExtractNumbersAgent
- [ ] `ExtractNumbersAgent` на `pydantic_ai.Agent` · `M` 🤖 🧪
- [ ] `output_type=ExtractedNumbers` · `S`
- [ ] Промпт: извлечь числа, даты, имена, символы · `M` 📝
- [ ] Fallback на regex при ошибке LLM · `M` 🧪
- [ ] Тест: мок LLM возвращает валидный JSON · `M` 🧪
- [ ] Коммит: `feat(agents): extract numbers agent` · `M` 🤖 🧪

**DoD:** при ошибке LLM используется `extract_numbers_regex`.

### 4.3. PatternAgent
- [ ] `PatternAgent` с `output_type=list[Pattern]` · `M` 🤖 🧪
- [ ] Промпт: найти повторения, мастер-числа, резонансы, скрытые связи · `M` 📝
- [ ] Валидация `strength ∈ [0, 1]` через Pydantic · `S` 🧪
- [ ] Тест: мок LLM возвращает паттерн · `M` 🧪
- [ ] Коммит: `feat(agents): pattern agent` · `M` 🤖 🧪

**DoD:** агент возвращает `list[Pattern]`, Pydantic отбрасывает невалидные.

### 4.4. ForecastAgent
- [ ] `ForecastAgent` с `output_type=Forecast` · `M` 🤖 🧪
- [ ] Промпт: учесть мастер-числа, историю, семантику · `M` 📝
- [ ] Инъекция `number_history` в контекст промпта · `M` 🧪
- [ ] Тест: агент получает историю и возвращает прогноз · `M` 🧪
- [ ] Коммит: `feat(agents): forecast agent` · `M` 🤖 🧪

**DoD:** прогноз содержит все поля `Forecast` (date, dominant_number, forecast, advice, warnings).

### 4.5. Промпты в отдельном модуле
- [ ] `agents/prompts.py` с константами · `S` 📝
- [ ] Few-shot примеры для каждого агента · `M` 📝
- [ ] Тесты на формат промпта (snapshot) · `M` 🧪
- [ ] Коммит: `feat(agents): prompts module` · `M` 📝

### 4.6. Документация агентов
- [ ] `docs/PROMPTS.md` — все промпты с обоснованием · `M` 📝
- [ ] ADR `0004-pydantic-ai-choice.md` — почему `pydantic-ai` · `M` 📝
- [ ] Коммит: `docs: prompts + ADR` · `M` 📝

**✅ Phase 4 завершена, когда:** каждый агент возвращает валидную Pydantic-модель, тесты изолированы от реального LLM.

---

## Phase 5 — RAG Pipeline 🔄

> **Цель:** полный пайплайн от новостей до прогноза.
> **Результат фазы:** `build_forecast(date)` проходит всю цепочку и сохраняет результат.

### 5.1. Pipeline orchestrator
- [ ] `Pipeline` класс с методами `ingest`, `analyze`, `forecast` · `M` 🧪
- [ ] Логирование каждого шага через `structlog` · `S`
- [ ] Тайминги шагов (для профилирования) · `S` 🧪
- [ ] Коммит: `feat(pipeline): orchestrator` · `M` 🧪

### 5.2. Ingest
- [ ] `Pipeline.ingest(topic, date_range)` · `M` 🧪
- [ ] fetch → extract → compute → embed → upsert · `M` 🧪
- [ ] Идемпотентность по `news_id` · `M` 🧪
- [ ] Тест: повторный ingest не дублирует · `M` 🧪
- [ ] Коммит: `feat(pipeline): ingest step` · `M` 🧪

### 5.3. Analyze
- [ ] `Pipeline.analyze(news_ids)` — поиск паттернов · `M` 🧪
- [ ] `find_patterns` → `PatternAgent` → `save_pattern` · `M` 🧪
- [ ] Тест: 3 новости с числом 11 → паттерн `resonance` · `M` 🧪
- [ ] Коммит: `feat(pipeline): analyze step` · `M` 🧪

### 5.4. Forecast
- [ ] `Pipeline.forecast(date)` — прогноз · `M` 🧪
- [ ] Чтение истории из `number_history` · `M` 🧪
- [ ] `ForecastAgent` + сохранение в Qdrant · `M` 🧪
- [ ] Тест: прогноз сохраняется, повторный вызов возвращает из кэша · `M` 🧪
- [ ] Коммит: `feat(pipeline): forecast step` · `M` 🧪

### 5.5. Управление контекстом
- [ ] Скользящее окно 7 дней в `Pipeline` · `M` 🧪
- [ ] `summarize_old_news()` — суммаризация через LLM · `M` 🧪
- [ ] Сохранение дайджеста в Qdrant · `M` 🧪
- [ ] Коммит: `feat(pipeline): context management` · `M` 🧪

### 5.6. E2E integration-тест
- [ ] Тест: `ingest → analyze → forecast` на фикстурах · `M` 🧪
- [ ] Qdrant in-memory + мок LLM + `respx` для API · `M` 🧪
- [ ] Коммит: `test(integration): full pipeline` · `M` 🧪

### 5.7. Документация пайплайна
- [ ] `docs/RAG_PIPELINE.md` — диаграмма + описание шагов · `M` 📝
- [ ] `docs/CONTEXT_MANAGEMENT.md` — окно, суммаризация, память · `M` 📝
- [ ] Коммит: `docs: rag pipeline + context` · `M` 📝

**✅ Phase 5 завершена, когда:** `Pipeline().forecast(today)` возвращает `Forecast` и сохраняет его.

---

## Phase 6 — MCP Server 🔌

> **Цель:** MCP-сервер с 9 инструментами, подключается к Claude Desktop и Cursor.
> **Результат фазы:** `make mcp` запускает сервер, инструменты вызываются из клиента.

### 6.1. Каркас MCP-сервера
- [ ] `mcp/server.py` — `FastMCP("numenews")` · `S` 🧪
- [ ] Dependency injection через `AppContext` · `M` 🧪
- [ ] Точка входа `mcp/main.py` со `stdio` transport · `S`
- [ ] Тест: сервер стартует, `list_tools` возвращает пустой список · `M` 🧪
- [ ] Коммит: `feat(mcp): server skeleton` · `M` 🧪

**DoD:** `make mcp` запускает сервер, не падает при подключении.

### 6.2. Инструмент `fetch_news`
- [ ] `@mcp.tool() def fetch_news(topic, date_range) -> list[NewsItem]` · `M` 🧪
- [ ] Вызов `NewsAggregator` · `S`
- [ ] Structured output через Pydantic · `S`
- [ ] Коммит: `feat(mcp): fetch_news tool` · `M` 🧪

### 6.3. Инструмент `extract_numbers`
- [ ] `@mcp.tool() def extract_numbers(text) -> ExtractedNumbers` · `S` 🧪
- [ ] Вызов `ExtractNumbersAgent` · `S`
- [ ] Коммит: `feat(mcp): extract_numbers tool` · `S` 🧪

### 6.4. Инструмент `compute_numerology`
- [ ] `@mcp.tool() def compute_numerology(text) -> NumerologyResult` · `S` 🧪
- [ ] Чистая функция из `numerology/` · `S`
- [ ] Коммит: `feat(mcp): compute_numerology tool` · `S` 🧪

### 6.5. Инструмент `find_patterns`
- [ ] `@mcp.tool() def find_patterns(news_ids) -> list[Pattern]` · `M` 🧪
- [ ] Вызов `Pipeline.analyze` · `S`
- [ ] Коммит: `feat(mcp): find_patterns tool` · `M` 🧪

### 6.6. Инструмент `check_master_numbers`
- [ ] `@mcp.tool() def check_master_numbers(numbers) -> MasterCheckResult` · `S` 🧪
- [ ] Коммит: `feat(mcp): check_master_numbers tool` · `S` 🧪

### 6.7. Инструмент `build_forecast`
- [ ] `@mcp.tool() def build_forecast(date) -> Forecast` · `M` 🧪
- [ ] Вызов `Pipeline.forecast` · `S`
- [ ] Коммит: `feat(mcp): build_forecast tool` · `M` 🧪

### 6.8. Инструмент `query_qdrant`
- [ ] `@mcp.tool() def query_qdrant(collection, query, filters) -> list[dict]` · `M` 🧪
- [ ] Валидация `collection` через Literal · `S` 🧪
- [ ] Коммит: `feat(mcp): query_qdrant tool` · `M` 🧪

### 6.9. Инструмент `save_pattern`
- [ ] `@mcp.tool() def save_pattern(pattern) -> SavedPattern` · `S` 🧪
- [ ] Upsert в коллекцию `patterns` · `S`
- [ ] Коммит: `feat(mcp): save_pattern tool` · `S` 🧪

### 6.10. Инструмент `get_history`
- [ ] `@mcp.tool() def get_history(number) -> list[NumberActivation]` · `S` 🧪
- [ ] Чтение из `number_history` · `S`
- [ ] Коммит: `feat(mcp): get_history tool` · `S` 🧪

### 6.11. Интеграция с клиентами
- [ ] Конфиг для Claude Desktop (`claude_desktop_config.json`) · `S` 📝
- [ ] Конфиг для Cursor (`.cursor/mcp.json`) · `S` 📝
- [ ] Ручной smoke-тест из Claude Desktop · `M`
- [ ] Коммит: `docs(mcp): client configs` · `M` 📝

### 6.12. Документация MCP
- [ ] `docs/MCP_TOOLS.md` — 9 инструментов, сигнатуры, примеры · `L` 📝
- [ ] ADR `0001-use-mcp-server.md` · `M` 📝
- [ ] Коммит: `docs: mcp tools + ADR` · `M` 📝

**✅ Phase 6 завершена, когда:** Claude Desktop видит 9 инструментов, `fetch_news` возвращает новости.

---

## Phase 7 — CLI (one-shot, JSON) 💻

> **Цель:** one-shot CLI с JSON-выводом.
> **Результат фазы:** `numenews today` возвращает валидный JSON в stdout.

### 7.1. Каркас CLI (Typer)
- [ ] `cli/main.py` — `Typer` app с командой-заглушкой · `S` 🧪
- [ ] Точка входа в `pyproject.toml` (`[project.scripts] numenews = ...`) · `S`
- [ ] `numenews --version` работает · `S` 🧪
- [ ] Коммит: `feat(cli): typer skeleton` · `S` 🧪

### 7.2. JSON-вывод
- [ ] `cli/output.py` — `print_json(model)` через `model_dump_json(indent=2)` · `S` 🧪
- [ ] Все команды пишут **только** JSON в stdout · `S`
- [ ] Логи в stderr через `structlog` · `S` 🧪
- [ ] `--pretty` флаг (по умолчанию True) · `S`
- [ ] Тест: вывод парсится `json.loads` · `M` 🧪
- [ ] Коммит: `feat(cli): json output` · `M` 🧪

**DoD:** stdout — валидный JSON, можно пайпить в `jq`.

### 7.3. Команда `today`
- [ ] `numenews today --topic politics` · `M` 🧪
- [ ] Pipeline: ingest + analyze + forecast на сегодня · `M` 🧪
- [ ] Коммит: `feat(cli): today command` · `M` 🧪

### 7.4. Команда `forecast`
- [ ] `numenews forecast --date 2026-09-22` · `M` 🧪
- [ ] Поддержка `--date tomorrow` и `--date +3d` · `M` 🧪
- [ ] Коммит: `feat(cli): forecast command` · `M` 🧪

### 7.5. Команда `history`
- [ ] `numenews history --number 11 --days 30` · `S` 🧪
- [ ] Коммит: `feat(cli): history command` · `S` 🧪

### 7.6. Команда `search`
- [ ] `numenews search --query "число 7 и финансы"` · `M` 🧪
- [ ] Гибридный поиск через `query_qdrant` · `S`
- [ ] Коммит: `feat(cli): search command` · `M` 🧪

### 7.7. Команда `patterns`
- [ ] `numenews patterns --type resonance --min-strength 0.7` · `S` 🧪
- [ ] Коммит: `feat(cli): patterns command` · `S` 🧪

### 7.8. Команда `mcp`
- [ ] `numenews mcp --transport stdio` · `S` 🧪
- [ ] Проксирует в `mcp/main.py` · `S`
- [ ] Коммит: `feat(cli): mcp command` · `S` 🧪

### 7.9. Smoke-тесты CLI
- [ ] `typer.testing.CliRunner` для всех команд · `M` 🧪
- [ ] Тест: `numenews today` возвращает exit code 0 + JSON · `M` 🧪
- [ ] Коммит: `test(cli): smoke tests` · `M` 🧪

### 7.10. Документация CLI
- [ ] `docs/USER_FLOW.md` — все команды + примеры JSON · `M` 📝
- [ ] ADR `0005-json-only-output.md` · `M` 📝
- [ ] ADR `0006-one-shot-vs-repl.md` · `M` 📝
- [ ] Коммит: `docs: user flow + ADRs` · `M` 📝

**✅ Phase 7 завершена, когда:** `numenews today | jq .dominant_number` работает.

---

## Phase 8 — Long-term Memory 🧠

> **Цель:** долговременная память активаций чисел между сессиями.
> **Результат фазы:** `get_history(11, days=30)` возвращает все активации из `number_history`.

### 8.1. Запись активаций
- [ ] `record_activation` вызывается при ingest каждой новости · `M` 🧪
- [ ] Сохранение: `number, date, news_id, context, numerology_value` · `S` 🧪
- [ ] Идемпотентность по `(number, news_id)` · `M` 🧪
- [ ] Коммит: `feat(memory): record activations` · `M` 🧪

### 8.2. Чтение истории
- [ ] `get_history(number, days)` с payload-фильтром · `M` 🧪
- [ ] Агрегация: частота по дням · `M` 🧪
- [ ] Коммит: `feat(memory): read history` · `M` 🧪

### 8.3. Инъекция в промпт прогноза
- [ ] `ForecastAgent` получает историю последних 30 дней · `M` 🧪
- [ ] Форматирование истории в промпт · `M` 📝
- [ ] Тест: прогноз учитывает историю (snapshot промпта) · `M` 🧪
- [ ] Коммит: `feat(memory): inject history into forecast` · `M` 🧪

### 8.4. Документация памяти
- [ ] `docs/CONTEXT_MANAGEMENT.md` — расширить разделом про `number_history` · `M` 📝
- [ ] Коммит: `docs: number history` · `S` 📝

**✅ Phase 8 завершена, когда:** после двух запусков `numenews today` история активаций растёт.

---

## Phase 9 — Eval (ragas) 📊

> **Цель:** измеримое качество RAG.
> **Результат фазы:** `make test-eval` выдаёт отчёт по метрикам `ragas`.

### 9.1. Фикстуры новостей
- [ ] `tests/eval/fixtures/news.jsonl` — 50 новостей с известными числами · `M` 📝
- [ ] `tests/eval/fixtures/questions.jsonl` — 20 Q&A пар · `M` 📝
- [ ] Загрузчики фикстур · `S` 🧪
- [ ] Коммит: `test(eval): fixtures` · `M`

### 9.2. Скрипт eval
- [ ] `tests/eval/test_rag.py` с `ragas.evaluate` · `M` 🧪
- [ ] Метрики: `faithfulness`, `context_precision`, `context_recall`, `answer_relevancy` · `M` 🧪
- [ ] Пороги: `faithfulness ≥ 0.7`, `context_precision ≥ 0.6` · `S` 🧪
- [ ] Makefile таргет `test-eval` · `S`
- [ ] Коммит: `test(eval): ragas metrics` · `M` 🧪

### 9.3. Отчёт eval
- [ ] Сохранение отчёта в `docs/eval_report.md` · `S` 📝
- [ ] `docs/EVAL.md` — как запускать, как читать · `M` 📝
- [ ] Коммит: `docs: eval report` · `M` 📝

**✅ Phase 9 завершена, когда:** `make test-eval` зелёный, отчёт сохранён.

---

## Phase 10 — Polish ✨

> **Цель:** репозиторий готов к показу.
> **Результат фазы:** README с диаграммой, все ADR, покрытие, тег `v0.1.0`.

### 10.1. Документация
- [ ] `docs/ARCHITECTURE.md` — полная диаграмма (Mermaid) · `L` 📝
- [ ] `docs/STACK.md` — обоснование выбора каждого инструмента · `M` 📝
- [ ] `docs/TESTING.md` — стратегия тестов · `M` 📝
- [ ] `docs/TOOL_USE.md` — логика выбора инструментов агентом · `M` 📝
- [ ] `docs/GLOSSARY.md` — MCP, RAG, гематрия, мастер-число · `M` 📝
- [ ] `docs/FAQ.md` — «почему нумерология?», «как подключить к Cursor?» · `M` 📝
- [ ] Коммит: `docs: full documentation` · `L` 📝

### 10.2. Agentic-документация
- [ ] `docs/agentic/CONVENTIONS.md` — стиль кода, нейминг · `M` 📝
- [ ] `docs/agentic/GUARDRAILS.md` — что агенту запрещено · `M` 📝
- [ ] `docs/agentic/PROMPTING_PLAYBOOK.md` — переиспользуемые промпты · `M` 📝
- [ ] `docs/agentic/EVAL_OF_AGENT.md` — как ревьюим агентскую генерацию · `M` 📝
- [ ] `docs/agentic/TOOLING.md` — какие IDE используем · `M` 📝
- [ ] Коммит: `docs(agentic): workflow and guardrails` · `L` 📝

### 10.3. ADR
- [ ] ADR `0007-qdrant-hybrid-search.md` · `M` 📝
- [ ] ADR `0008-fastembed-vs-openai.md` · `M` 📝
- [ ] ADR `0009-hishel-caching.md` · `M` 📝
- [ ] Коммит: `docs(adr): vector, embeddings, cache` · `M` 📝

### 10.4. Покрытие тестами
- [ ] Coverage: `numerology/` ≥ 95% · `M` 🧪
- [ ] Coverage: `pipeline/` + `agents/` ≥ 80% · `M` 🧪
- [ ] Coverage: `vector/` + `news/` ≥ 70% · `M` 🧪
- [ ] Бейдж покрытия в README · `S`
- [ ] Коммит: `test: coverage report` · `M`

### 10.5. Финальная вычитка
- [ ] Пройтись по `TODO` в коде · `M`
- [ ] Убрать `print()`, `pdb.set_trace()`, закомментированный код · `S`
- [ ] `make lint && make test && make test-eval` — зелёные · `S`
- [ ] Обновить `CHANGELOG.md` релизом `v0.1.0` · `S`
- [ ] Тег `v0.1.0` · `S`
- [ ] Коммит: `chore: release v0.1.0` · `S`

**✅ Phase 10 завершена, когда:** README рендерит диаграмму, все ADR на месте, `v0.1.0` тегирован.

---

## 📊 Сводка по фазам

| Фаза | Тема | Задач (примерно) | Оценка |
|------|------|------------------|--------|
| 0 | Skeleton | 35 | 1–2 дня |
| 1 | Numerology (чистая логика) | 25 | 2 дня |
| 2 | News Sources (5 API) | 30 | 3 дня |
| 3 | Embeddings + Qdrant | 30 | 3–4 дня |
| 4 | LLM Agents | 20 | 2–3 дня |
| 5 | RAG Pipeline | 20 | 2–3 дня |
| 6 | MCP Server (9 tools) | 30 | 3–4 дня |
| 7 | CLI (one-shot, JSON) | 20 | 2 дня |
| 8 | Long-term Memory | 10 | 1 день |
| 9 | Eval (ragas) | 10 | 1–2 дня |
| 10 | Polish | 25 | 2–3 дня |
| **Всего** | | **~255** | **~22–30 дней** |

---

## 🎯 Milestones (для GitHub Milestones)

| Milestone | Фазы | Что демонстрирует |
|-----------|------|-------------------|
| **M0 — Foundation** | 0 | Репо, tooling, Qdrant, config, logs |
| **M1 — Numerology** | 1 | Чистая доменная логика, property-based тесты |
| **M2 — Data** | 2 | 5 новостных API за Protocol + кэш |
| **M3 — Vector** | 3 | Qdrant 5 коллекций + гибридный поиск |
| **M4 — Agents** | 4 | `pydantic-ai` + structured output |
| **M5 — RAG** | 5 | Полный пайплайн ingest → forecast |
| **M6 — MCP** | 6 | 9 инструментов, подключение к клиентам |
| **M7 — CLI** | 7 | One-shot JSON-интерфейс |
| **M8 — Memory** | 8 | Долговременная память активаций |
| **M9 — Eval** | 9 | Измеримое качество RAG |
| **M10 — v0.1.0** | 10 | Портфолио-ready |

---

## 📌 Правила работы с роадмапом

1. **Атомарность важнее скорости.** Если задача кажется `XL` — дели на подзадачи прямо в этом файле.
2. **Каждая задача — коммит.** Имя = тип + scope + subject (см. `CONTRIBUTING.md`).
3. **DoD обязателен.** Не закрывай задачу, если DoD не выполнен полностью.
4. **Метки 🧪, 📝, 🤖, 🔌 — не опциональны.** Тесты, документация, промпты и инфра идут вместе с кодом.
5. **Фазы последовательны, задачи внутри фазы — параллельны.** Зависимости указаны явно.
6. **Обновляй этот файл по ходу.** Новая задача — в нужную фазу, не в бэклог.
7. **Отменённые задачи** помечай `[-]` с комментарием «почему».
8. **Прогресс виден в GitHub Projects.** Board: `Backlog` / `In Progress` / `Review` / `Done`.
