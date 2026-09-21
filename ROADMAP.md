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
- [x] `src/numenews/logging.py` — настройка `structlog` · `M`
- [x] JSON-вывод в production, human-readable в dev (`log_level`) · `S`
- [x] Корреляция через `contextvars` (request_id, news_id) · `M`
- [x] Интеграция с `pydantic-settings` · `S`
- [x] Коммит: `feat(logging): structlog setup` · `M` 📝

**DoD:** `structlog.get_logger().info("test")` пишет JSON.

> *Логи идут в stderr (stdout занят JSON-ом CLI); stdlib-записи (`httpx`, `qdrant-client`)
> проходят через тот же `ProcessorFormatter`, поэтому поток однородный. Заглушки
> `cli/__main__.py` и `mcp/__main__.py` переведены на `configure_logging()`/`get_logger()`.*

### 0.8. Первые тесты
- [x] `tests/conftest.py` с фикстурами (`event_loop`, `anyio_backend`, `tmp_cache_dir`) · `S`
      *`event_loop` удалён в `pytest-asyncio` ≥ 1.0, а плагин `anyio` не используется: вместо них
      `asyncio_mode = "auto"` + `asyncio_default_fixture_loop_scope`, а асинхронный smoke-тест
      доказывает, что корутины идут без маркера. Фикстуры: `settings` (герметичные настройки) и
      `tmp_cache_dir`.*
- [x] `tests/unit/test_smoke.py` — `assert True` · `S` 🧪
      *Вместо пустышки — контрактные проверки: версия пакета, JSON в stdout у CLI, пустой stdout
      у MCP, работа `asyncio_mode = "auto"`. Добавлены в 0.5 и расширены здесь.*
- [x] `tests/integration/__init__.py` + фикстура Qdrant in-memory · `M` 🧪
- [x] `tests/eval/__init__.py` · `S`
- [x] Коммит: `test: pytest scaffolding` · `M` 🧪

**DoD:** `make test` зелёный, фикстура `qdrant_in_memory` доступна.

### 0.9. Документация фазы 0
- [x] `docs/ARCHITECTURE.md` — шаблон с заголовками · `S` 📝
- [x] `docs/NUMEROLOGY.md` — шаблон · `S` 📝
- [x] `docs/adr/0001-record-architecture-decisions.md` · `S` 📝
- [x] `docs/adr/template.md` · `S` 📝
- [x] `docs/agentic/AGENT_WORKFLOW.md` — как работаем с агентами · `M` 📝
- [x] `ROADMAP.md` (этот документ) · `M` 📝
- [x] Коммит: `docs: architecture, numerology, ADR templates, roadmap` · `M`

**✅ Phase 0 завершена, когда:** `make dev` поднимает Qdrant, `make lint && make test` зелёные, `Settings()` работает.

> **Итог phase 0 (2026-09-21).** Все задачи 0.1–0.9 закрыты, `make lint`, `make test`,
> `make test-integration`, `make test-eval` и `pre-commit run --all-files` зелёные;
> `make dev` поднимает Qdrant 1.19.1 в статусе `healthy` (`/readyz` и `/dashboard` отвечают 200);
> `Settings()` читает `.env`, `structlog` пишет JSON в stderr при `ENVIRONMENT=prod`.
> Отклонения от черновика отмечены в задачах выше (ruff `select`, `fail_under`, фикстуры
> `event_loop`/`anyio_backend`, healthcheck без `curl`, ADR MCP → 0010).

---

## Phase 1 — Numerology (чистая логика) 🧮

> **Цель:** чистый модуль нумерологии без зависимостей от LLM и Qdrant.
> **Результат фазы:** покрытие `numerology/` ≥ 95%, все инварианты покрыты property-based тестами.

### 1.1. Доменные модели (Pydantic)
- [x] `NewsId`, `PatternId`, `ForecastId` (UUID-обёртки) · `S` 🧪
- [x] `NewsItem` (id, title, text, source, date, url, numbers, numerology_value) · `M` 🧪
- [x] `ExtractedNumbers` (numbers: list[int], sources: list[str], symbols: list[str]) · `S` 🧪
- [x] `NumerologyResult` (value, is_master, breakdown) · `S` 🧪
- [x] `Pattern` (id, type, numbers, news_ids, strength, interpretation) · `M` 🧪
- [x] `Forecast` (date, dominant_number, master_active, patterns, forecast, advice, warnings) · `M` 🧪
- [x] `NumberActivation` (number, date, news_id, context) · `S` 🧪
- [x] Коммит: `feat(models): domain pydantic models` · `M` 🧪

**DoD:** все модели проходят `mypy --strict`, `model_config = ConfigDict(frozen=True, strict=True)`.

> *Отклонения. `MasterCheckResult` добавлен в `models/` здесь, хотя roadmap упоминает его только в 1.3:
> он нужен и 1.3, и MCP-инструменту 6.6. `NumerologyResult` несёт `text` и `gematria` сверх
> `(value, is_master, breakdown)`, а `breakdown` — кортеж отрендеренных шагов (так модель остаётся
> hashable и JSON читаем). `NewsItem.numbers`/`numerology_value` получили значения по умолчанию
> (`()`/`None`): извлечение приходит только в 4.2/5.2, а `None` — явное «ещё не посчитано», потому что
> `0` не входит в множество редуцированных значений. `ExtractedNumbers.sources` — метки стратегий
> извлечения (`regex`, `llm`), а не параллельный список к `numbers`. `PatternType` — замкнутый
> `Literal["resonance", "repetition", "master", "symbol", "hidden"]`, `discovered_at` появится в 3.5
> вместе с payload-индексом. Поле прогноза названо `master_active` по этому файлу, а не
> `master_number_active` из `.docs/plan.md`. Модели делятся по модулям (`ids`, `news`, `results`,
> `patterns`, `forecasts`, `memory`) и переэкспортируются из `models/__init__.py`.*

### 1.2. Редукция
- [x] `reduce_number(n: int) -> int` — свёртка до 1–9 · `S` 🧪
- [x] Исключения: 11, 22, 33 не редуцируются (мастер-числа) · `S` 🧪
- [x] `reduce_date(d: date) -> int` — сумма цифр даты · `S` 🧪
- [x] Property-based тесты: результат всегда ∈ {1..9, 11, 22, 33} · `M` 🧪
- [x] Коммит: `feat(numerology): reduction` · `M` 🧪

**DoD:** `hypothesis` генерирует 1000 случайных чисел, инвариант держится.

> *Отклонения. `MASTER_NUMBERS`/`REDUCED_NUMBERS` вынесены в `numerology/constants.py` уже здесь:
> редукция обязана останавливаться на мастер-числах до того, как 1.3 добавит проверки, а два модуля
> должны ссылаться на одно определение, а не повторять `11/22/33`. Публичная `reduction_steps(n)`
> добавлена рядом с `reduce_number`, чтобы `compute_numerology` (1.7) рендерил шаги тем же циклом, а не
> второй копией; `_digit_sum`/`_digit_sum_chain` — приватные. `n < 1` (включая `0`) вне области
> определения и кидает `ValueError`: `0` не входит в `REDUCED_NUMBERS`, а дата всегда даёт хотя бы одну
> ненулевую цифру. Тестовый пример «`hypothesis` 1000 чисел» реализован как `max_examples=1000` на
> `st.integers(min_value=1, max_value=10**12)` плюс отдельные проверки идемпотентности и `st.dates()`.*

### 1.3. Мастер-числа
- [x] `is_master(n: int) -> bool` · `S` 🧪
- [x] `MASTER_NUMBERS = frozenset({11, 22, 33})` · `S`
- [x] `check_master_numbers(numbers: Sequence[int]) -> MasterCheckResult` · `S` 🧪
- [x] Тесты: границы, пустой список, дубликаты · `S` 🧪
- [x] Коммит: `feat(numerology): master numbers` · `S` 🧪

**DoD:** функция возвращает `MasterCheckResult(has_master, master_numbers, count)`.

> *`MASTER_NUMBERS` лежит в `numerology/constants.py` (заведён в 1.2, см. примечание там);
> `master.py` импортирует его и добавляет `is_master`/`check_master_numbers`, а `MasterCheckResult`
> определён в `models/results.py` (заведён в 1.1). Семантика полей: `master_numbers` — различные
> мастер-числа по возрастанию, `count` — все вхождения, поэтому `[11, 11]` даёт `(True, (11,), 2)`;
> пустая последовательность — валидный вход и даёт `(False, (), 0)`.*

### 1.4. Гематрия
- [x] `gematria_simple(text: str) -> int` — A=1..Z=26 + кириллица · `M` 🧪
- [x] `gematria_reduce(text: str) -> int` — гематрия + редукция · `S` 🧪
- [x] Нормализация: lowercase, удаление пробелов и пунктуации · `S` 🧪
- [x] Property-based: гематрия неотрицательна, редукция в допустимом множестве · `M` 🧪
- [x] Тесты на известные значения (например, `"sun" -> 54`) · `S` 🧪
- [x] Коммит: `feat(numerology): gematria` · `M` 🧪

**DoD:** поддержка латиницы и кириллицы, тесты на граничные случаи.

> *Открытый вопрос «кириллический offset» из шаблона `docs/NUMEROLOGY.md` закрыт: позиция в русском
> алфавите из 33 букв, `А=1 … Я=33`, `Ё=7` (выбор согласован; обоснование — в ADR 0002). Латиница —
> `A=1 … Z=26`. Прочие кириллические буквы (`Ї`, `Ґ`, `Ђ`) и другие письменности игнорируются, а не
> додумываются; `normalize_text` делает `casefold` и выбрасывает всё, кроме известных букв, поэтому
> текст без букв даёт сумму `0`. Так как `reduce_number` начинается с `1`, `gematria_reduce` возвращает
> `0` сам — это задокументированный сентинел, и инвариант 4 в `docs/NUMEROLOGY.md` переформулирован как
> `∈ {0} ∪ REDUCED_NUMBERS`. В `pyproject.toml` добавлены `per-file-ignores` для `RUF001/002/003` в
> `gematria.py` и его тестах: они намеренно называют кириллические буквы, и без исключения ruff считает
> смешанные фрагменты случайными конфузаблами; в остальных файлах правила остаются включёнными.*

### 1.5. Резонанс дат
- [x] `date_resonance(d1: date, d2: date) -> int` — совпадение редуцированных значений · `S` 🧪
- [x] `find_date_resonances(dates: Sequence[date]) -> list[tuple[date, date, int]]` · `M` 🧪
- [x] Тесты: одинаковые даты, разные, диапазон · `S` 🧪
- [x] Коммит: `feat(numerology): date resonance` · `M` 🧪

**DoD:** возвращает пары с одинаковым редуцированным значением.

> *`date_resonance` возвращает само общее редуцированное значение (а не `1`/`0`-флаг) — так третий
> элемент пары в `find_date_resonances` не приходится пересчитывать. Отсутствие резонанса — `0`:
> редуцированное значение даты всегда ≥ 1, поэтому сентинел однозначен. Пары неупорядоченные и идут в
> порядке входа (`i < j`), одинаковые даты резонируют по определению, `[]`/один элемент — пустой
> результат.*

### 1.6. Извлечение чисел (regex-фолбэк)
- [x] `extract_numbers_regex(text: str) -> list[int]` — числа из текста · `S` 🧪
- [x] `extract_dates_regex(text: str) -> list[date]` — даты в форматах ISO, DD.MM.YYYY, «15 марта» · `M` 🧪
- [x] `extract_symbols(text: str, symbols: Sequence[str]) -> list[str]` — повторяющиеся символы · `S` 🧪
- [x] Коммит: `feat(numerology): regex extraction fallback` · `M` 🧪

**DoD:** работает без LLM, используется как fallback при ошибке агента.

> *Отклонения и уточнения. `extract_dates_regex` получил keyword-only `today: date | None = None`:
> дата без года («15 марта») дополняется годом из `today`, по умолчанию — текущим, а тесты и повторный
> прогон старой партии передают его явно и не зависят от часов. Несуществующие даты (`31.02.2026`)
> пропускаются, а не кидают исключение: опечатка в новости не должна терять остальные даты. Месяцы —
> только русские, в родительном и именительном падежах; английские названия месяцев в 1.6 не входят.
> `extract_numbers_regex` формат-агностичен: цифры даты тоже возвращаются (`"2026-09-21"` → `[2026, 9, 21]`),
> а разделитель тысяч не понимается (`"1,000"` → `[1, 0]`) — оба поведения зафиксированы тестами.
> `extract_symbols` возвращает символы, **присутствующие** в тексте (без учёта регистра, подстрокой,
> в порядке аргумента, без дублей): частота — задача слоя паттернов, а не этой функции. Пустой текст и
> пустой список символов дают `[]`.*

### 1.7. Публичный API модуля
- [x] `src/numenews/numerology/__init__.py` с `__all__` · `S`
- [x] `compute_numerology(text: str) -> NumerologyResult` — объединяет всё · `M` 🧪
- [x] Docstrings на публичных функциях · `S` 📝
- [x] Коммит: `feat(numerology): public api` · `M` 🧪

**DoD:** модуль импортируется, `compute_numerology("Sun rises")` возвращает результат.

> *«Объединяет всё» прочитано как «собирает чтение текста»: `compute_numerology` = нормализация +
> гематрия + редукция + проверка мастер-числа, а извлечение чисел/дат сознательно не входит — это
> работа агента с `extract_*_regex` как фолбэком (4.2), и смешивать два разных вопроса в одном
> результате не нужно. Функция живёт в `numerology/api.py`, пакетный `__init__.py` только
> переэкспортирует поверхность через `__all__`. `breakdown` всегда начинается со строки
> `gematria_simple = <сумма>`, затем идут шаги редукции; текст без букв даёт `gematria = value = 0`,
> `is_master = False` и `breakdown = ("no letters to sum",)`. Тест `test_numerology_api.py`
> подпроцессом проверяет и правило AGENTS.md: импорт `numenews.numerology` не тянет `news`, `vector`,
> `agents`, `mcp`, `cli`, а `numenews.models` не импортирует ничего, кроме самого себя.*

### 1.8. Документация нумерологии
- [x] `docs/NUMEROLOGY.md` — редукция, мастер-числа, гематрия с примерами · `M` 📝
- [x] `docs/adr/0002-numerology-scope.md` — почему только редукция + мастер + гематрия · `M` 📝
- [x] Коммит: `docs: numerology rules and scope` · `M` 📝

**✅ Phase 1 завершена, когда:** покрытие `numerology/` ≥ 95%, `mypy --strict` зелёный, property-based тесты проходят.

> *В этот же коммит вошли: правка строки `numerology` в таблице слоёв `docs/ARCHITECTURE.md`
> («May import: nothing» → `models`, обоснование в ADR 0002), обновлённый раздел «Implemented so far»,
> docstring пакета `numenews/__init__.py` и запись в `CHANGELOG.md`. ADR 0002 фиксирует пять правил
> слоя, кириллический офсет `А=1 … Я=33` (`Ё=7`), семантику `MasterCheckResult`, сентинелы `0`/`None`,
> инъекцию `today` и то, что `compute_numerology` читает буквы, а не извлекает числа.*

> **Итог phase 1 (2026-09-21).** Задачи 1.1–1.8 закрыты. Покрытие `src/numenews/numerology/` — 100%
> инструкций и ветвей (130 инструкций, 26 ветвей), `src/numenews/models/` — 100%; всего `make test` —
> 177 тестов, включая property-based на hypothesis (`max_examples=1000` для редукции). `ruff check`,
> `ruff format --check`, `mypy --strict`, `pre-commit run --all-files` зелёные;
> `compute_numerology("Sun rises")` → `gematria=124`, `value=7`; `compute_numerology("солнце")` →
> `gematria=93`, `value=3`; `compute_numerology("k")` → `value=11`, `is_master=True`. Отклонения от
> черновика отмечены в задачах выше: модульная раскладка `models/`, `MasterCheckResult` и
> дополнительные поля `NumerologyResult` в 1.1, `constants.py` и публичная `reduction_steps` в 1.2,
> `per-file-ignores` для `RUF001/002/003` в 1.4, keyword-only `today` и «присутствие, а не частота»
> в `extract_symbols` в 1.6, `numerology/api.py` и границы слоя в 1.7, строка `numerology` в
> `docs/ARCHITECTURE.md` в 1.8.

---

## Phase 2 — News Sources 🌐

> **Цель:** 5 новостных API за единым Protocol-интерфейсом с кэшем.
> **Результат фазы:** `fetch_news(topic, date_range)` возвращает объединённый список из всех 5 API.

### 2.1. Protocol-интерфейс
- [x] `NewsSource(Protocol)` с `async def fetch(topic, date_range) -> list[NewsItem]` · `S` 🧪
- [x] `NewsSourceError` — базовое исключение · `S`
- [x] `Topic`, `DateRange` — Pydantic-модели · `S` 🧪
- [x] Коммит: `feat(news): source protocol` · `S` 🧪

**DoD:** `mypy --strict` проверяет структурную типизацию.

> *Отклонения. `Topic`/`DateRange` лежат в `models/query.py`, а не в `news/`: это словарь границ
> (те же модели примут MCP-инструмент 6.2 и CLI 7.3), а `models` — единственный слой, который
> разрешено импортировать всем. `NewsSourceError` — не одно исключение, а база с подклассами
> `HTTPError`/`AuthError`/`RateLimitError`/`TransportError`/`ParseError`: агрегатору нужен один
> `except`, а флаг `retryable` живёт на исключении, потому что «повторять ли» — свойство отказа, а
> не места вызова. `NewsSource` объявляет `name` read-only property, чтобы класс-атрибут адаптера
> структурно подходил под протокол. `test_news_protocol.py` доказывает, что обычный класс без
> наследования удовлетворяет протоколу — и это же проверяет `mypy --strict`.*

### 2.2. HTTP-клиент с кэшем (hishel)
- [x] `httpx.AsyncClient` + `hishel.AsyncCacheClient` · `M` 🧪
- [x] Кэш-директория из `Settings.cache_dir` · `S`
- [x] TTL 15 минут для новостей · `S` 🧪
- [x] Обёртка с `tenacity` для retry на 5xx · `M` 🧪
- [x] Тест: повторный запрос идёт из кэша (`respx`) · `M` 🧪
- [x] Коммит: `feat(news): http client with hishel cache` · `M` 🧪

**DoD:** тест через `respx` подтверждает, что второй запрос не бьёт по сети.

> *Отклонения. Кэш работает в режиме `hishel.FilterPolicy`, а не в режиме спецификации: ни один из
> пяти API не присылает заголовков свежести, которыми RFC 9111 мог бы пользоваться, поэтому
> `SpecificationPolicy` считал бы каждый сохранённый ответ протухшим и кэш не отвечал бы никогда
> (проверено: два одинаковых запроса → два сетевых вызова). Пятнадцать минут — это
> `AsyncSqliteStorage(default_ttl=...)`, расширение hishel, а не правило кэширования; TTL влияет на
> срок хранения записи. Второе следствие того, что hishel сохраняет всё: в `FilterPolicy` добавлен
> фильтр `_CacheOnlySuccesses`, иначе кэшированный 503 повторялся бы весь TTL вместо retry, а 429
> скрывал бы сброс квоты. `tenacity` 9.1 больше не содержит `wait_retry_after`, поэтому задержка —
> своя функция: она уважает числовой `Retry-After` (HTTP-дата игнорируется) и иначе отступает
> экспоненциально; флаг `retryable` берётся с исключения (2.1). В лог идёт URL без query-строки:
> Mediastack передаёт ключ именно в query. Зависимости `httpx`/`hishel[httpx]`/`tenacity` (и
> `respx` в dev-группу) добавлены в этом же коммите, комментарий фаз в `pyproject.toml` обновлён.*

### 2.3. GDELT adapter
- [x] `GDELTSource(NewsSource)` · `M` 🧪
- [x] Парсинг ответа GDELT Doc API · `M` 🧪
- [x] Маппинг в `NewsItem` · `S` 🧪
- [x] Тест через `respx` с фикстурой ответа · `M` 🧪
- [x] Коммит: `feat(news): gdelt adapter` · `M` 🧪

**DoD:** реальный запрос к GDELT возвращает новости, тест изолирован через `respx`.

> *Отклонения. Общие правила маппинга вынесены в `news/items.py` уже здесь: `news_id` (детерминированный
> `uuid5(NAMESPACE_URL, url)` — он же даст идемпотентность ingest в 5.2), `publisher_name`
> (издатель, а не фид: по нему агрегатор дедуплицирует), `item_text` и `utc_date`. Все пять адаптеров
> используют один и тот же набор, поэтому правило живёт в одном месте. `text` у GDELT — заголовок: в
> `artlist` вообще нет поля с описанием. Часть DoD «реальный запрос возвращает новости» в этой среде
> недостижима: GDELT троттлит общий IP до 429 с текстовым телом (проверено curl-ом), поэтому happy
> path закрыт фикстурой документированного формата, а сам 429 — отдельным тестом. Заголовки
> `startdatetime`/`enddatetime` — UTC `YYYYMMDDHHMMSS`, конец диапазона берётся как 23:59:59; пустое
> тело (нет совпадений) — это результат, а не ошибка, HTML/текст при 200 — `NewsSourceParseError`.*

### 2.4. NewsAPI.org adapter
- [x] `NewsAPISource(NewsSource)` · `M` 🧪
- [x] Чтение `NEWSAPI_KEY` из `Settings` · `S`
- [x] Обработка 429 (rate limit) через `tenacity` · `M` 🧪
- [x] Тест через `respx` · `M` 🧪
- [x] Коммит: `feat(news): newsapi adapter` · `M` 🧪

**DoD:** тест на 429 покрыт, retry срабатывает.

> *Уточнения. Ключ уходит в заголовке `X-Api-Key`, а не в query-параметре `apiKey`: так он не
> попадает ни в URL, ни в лог, ни в ключ кэша. Чтение `NEWSAPI_KEY` живёт в самом адаптере —
> классметод `from_settings(settings, client)` возвращает `None`, если ключа нет (2.8 соберёт из них
> список). NewsAPI умеет отдавать `{"status":"error", ...}` с HTTP 200 — это тоже `NewsSourceError`,
> а не пустая страница. `description` предпочтительнее `content`: последний обрезан маркером
> `[+N chars]`, который снимается, когда кроме него текста нет. camelCase-поля ответа проходят через
> `Field(alias=...)`, чтобы не отключать правило ruff N815. Тест 429 использует `Retry-After: 0`
> (заголовок уважается) и проверяет, что второй попытки достаточно.*

### 2.5. GNews adapter
- [x] `GNewsSource(NewsSource)` · `M` 🧪
- [x] Чтение `GNEWS_KEY` · `S`
- [x] Маппинг в `NewsItem` · `S` 🧪
- [x] Коммит: `feat(news): gnews adapter` · `M` 🧪

> *Отклонение. GNews отвечает на исчерпанную дневную квоту кодом **403**, который центральный
> маппер (2.2) по HTTP-семантике читает как «запрещено»; адаптер переводит 403 в
> `NewsSourceRateLimitError`, потому что это и есть отказ по лимиту, а 401 остаётся
> `NewsSourceAuthError`. `from`/`to` уходят как RFC 3339 (`2026-09-15T00:00:00Z`), а не голыми
> датами, `max=10` — потолок бесплатного плана. Ключ — в заголовке `X-Api-Key`.*

### 2.6. Mediastack adapter
- [x] `MediastackSource(NewsSource)` · `M` 🧪
- [x] Чтение `MEDIASTACK_KEY` · `S`
- [x] Коммит: `feat(news): mediastack adapter` · `M` 🧪

> *Отклонения. `access_key` — единственная форма авторизации по документации, поэтому ключ
> уезжает в query-строке; в лог он не попадает (`get_response` логирует эндпоинт без параметров),
> но оказывается внутри хешированного ключа кэша — это отмечено в модуле и в `docs`.
> Диапазон дат уходит как `date=YYYY-MM-DD,YYYY-MM-DD`, хотя исторические запросы документированы
> только со Standard-плана: реализуется документированный контракт, а `function_access_restricted`
> на free-плане деградирует как обычная ошибка источника (оговорено в `docs/NEWS_SOURCES.md`).
> `published_at` приходит с офсетом `+00:00` и разбирается `fromisoformat`; издатель — плоская
> строка `source`.*

### 2.7. Currents API adapter
- [x] `CurrentsSource(NewsSource)` · `M` 🧪
- [x] Чтение `CURRENTS_KEY` · `S`
- [x] Коммит: `feat(news): currents adapter` · `M` 🧪

> *Уточнения. У Currents нет поля издателя — только `author`, а это человек; `source` берётся из хоста
> URL, потому что агрегатор дедуплицирует по `(title, source, date)` и подпись автора издателем не
> является. Диапазон уходит строгим RFC 3339 (`2026-09-15T00:00:00Z`): голая дата у Currents — это
> 400. `published` приходит как `2026-03-24 12:05:00 +0000`, поэтому парсится явным форматом, а не
> `fromisoformat`. Ключ — в заголовке `Authorization: Bearer`; `keywords` используется вместо
> `query` (при обоих Currents отдаёт приоритет `keywords`). `page_size=20` — потолок бесплатного
> плана.*

### 2.8. Агрегатор
- [x] `NewsAggregator` — параллельный опрос через `asyncio.gather` · `M` 🧪
- [x] Дедупликация по `(title, source, date)` · `M` 🧪
- [x] Graceful degradation: если один API упал — возвращаем остальные · `M` 🧪
- [x] Тест: 2 из 5 падают — возвращаются 3 · `M` 🧪
- [x] Коммит: `feat(news): aggregator with graceful degradation` · `M` 🧪

**DoD:** агрегатор возвращает объединённый список, не падает при падении одного источника.

> *Уточнения. Деградация распространяется только на `NewsSourceError`; любое другое исключение
> (баг в нашем маппинге, отменённая задача) перевыбрасывается — прятать дефект за «тихо thinner»
> результатом хуже, чем упасть. Пустой список источников — это ошибка конфигурации, она кидает
> `NewsSourceError`; «все упали» — это `[]` и по warning'у на источник. Фильтр по диапазону живёт
> здесь, а не в адаптерах: каждый API фильтрует со своей точностью, а точная граница должна быть
> одна. Порядок результата детерминирован (источник за источником, внутри — порядок API), при
> дедупликации остаётся первое вхождение. `build_sources(settings, client)` собирает список из
> `from_settings` (GDELT всегда, остальные — только при наличии ключа), а `fetch_news(topic,
> date_range)` в `news/api.py` — фасад фазы: он создаёт и закрывает клиент, поэтому долгоживущий
> клиент для MCP остаётся за `NewsAggregator` (фаза 6).*

### 2.9. Документация источников
- [x] `docs/NEWS_SOURCES.md` — лимиты, ключи, примеры запросов · `M` 📝
- [x] Обновить `.env.example` · `S`
- [x] Коммит: `docs: news sources` · `M`

> *В этот же коммит вошли: запись фазы 2 в `CHANGELOG.md`, раздел «Implemented so far» в
> `docs/ARCHITECTURE.md`, актуальный баннер и ссылка на новые docs в `README.md` (баннер всё ещё
> говорил «Phase 0» после фазы 1) и docstring пакета `numenews/__init__.py`.*

**✅ Phase 2 завершена, когда:** `fetch_news("politics", last_7d)` возвращает новости из ≥ 3 источников.

> **Итог phase 2 (2026-09-21).** Задачи 2.1–2.9 закрыты. Пять источников за одним протоколом:
> `news/` — 100% инструкций и ветвей (501 инструкция, 84 ветви), весь `make test` — 266 тестов,
> включая новый `tests/unit/test_news_aggregator.py` с фейками и пять интеграционных файлов с
> фикстурами `respx`; `ruff check`, `ruff format --check`, `mypy --strict` и
> `pre-commit run --all-files` зелёные.
>
> Условие фазы проверено интеграционным тестом `test_five_sources_with_two_failures_still_produce_news`:
> пять замоканных источников, два падают с 500/503 — `fetch_news` возвращает новости трёх.
> **Отклонение:** живого прогона «≥ 3 источников» нет — `.env` с ключами в репозитории нет, а GDELT
> из этой сети отвечает 429 (общий IP, троттл «1 запрос / 5 секунд»). Живьём проверено только то,
> что ключей не требует: эндпоинты существуют, ошибки маппятся (NewsAPI 401 `apiKeyMissing`, GNews
> 400, Mediastack 401 `missing_access_key`, Currents 401), GDELT отдаёт 429 с текстовым телом.
> Решение пользователя — закрывать фазу на фикстурах `respx` и зафиксировать отклонение здесь.
>
> Прочие отклонения отмечены по задачам выше: `Topic`/`DateRange` в `models/query.py` (2.1), режим
> `hishel.FilterPolicy` вместе с фильтром «кэшируем только 2xx» и зависимости в 2.2, общие правила
> маппинга в `news/items.py` (2.3), 403 GNews как квота (2.5), `access_key` Mediastack в
> query-строке (2.6), `source` Currents из хоста URL (2.7), деградация только по `NewsSourceError`
> (2.8).

---

## Phase 3 — Embeddings + Qdrant 🧠

> **Цель:** векторный слой с 5 коллекциями и гибридным поиском.
> **Результат фазы:** новости индексируются, семантический поиск работает.

### 3.1. Embeddings (fastembed)
- [x] `Embedder` Protocol с `embed(texts) -> list[list[float]]` · `S` 🧪
- [x] `FastEmbedSmall` (384d, `bge-small-en-v1.5`) · `M` 🧪
- [x] `FastEmbedBase` (768d, `bge-base-en-v1.5`) · `M` 🧪
- [x] Lazy-инициализация модели (не грузить при импорте) · `M` 🧪
- [x] Тест: эмбеддинг детерминирован, размерность корректна · `M` 🧪
- [x] Коммит: `feat(embeddings): fastembed wrapper` · `M` 🧪

**DoD:** `FastEmbedBase().embed(["hello"])` возвращает `list[float]` длиной 768.

> *Уточнения. `Embedder` объявляет ещё и `dimension`: векторному слою нужен размер вектора, чтобы
> построить коллекцию той же ширины и поймать несоответствие при создании, а не на первом запросе.
> `embed([])` возвращает `[]` **не загружая модель** — пустая партия не повод скачивать веса.
> `cache_dir` у обёрток по умолчанию `None` (каталог fastembed в системном tmp), поэтому DoD
> `FastEmbedBase()` без аргументов работает буквально; боевая сборка — `build_embedders(settings)`,
> и она всегда передаёт `Settings.embedding_cache_dir` (`.cache/fastembed`, gitignored): модели
> весят ~286 МБ вместе и скачиваются один раз при первом `embed`, а не при импорте.
> Тест на детерминизм и размерность — интеграционный (`tests/integration/test_embeddings_fastembed.py`),
> потому что ему нужны реальные веса; поведение самой обёртки (ленивость, переиспользование сессии,
> конвертация в `float`) закрыто юнит-тестом с подменённым `TextEmbedding`. `mypy --strict` разобрал
> fastembed без override: пакет поставляет `py.typed`.*

### 3.2. Qdrant-клиент
- [x] `QdrantClient` обёртка в `vector/client.py` · `M` 🧪
- [x] Подключение к Docker Qdrant из `Settings.qdrant_url` · `S`
- [x] Health-check при старте · `S` 🧪
- [x] Фикстура `qdrant_in_memory` для тестов · `M` 🧪
- [x] Коммит: `feat(vector): qdrant client` · `M` 🧪

**DoD:** тест использует `QdrantClient(":memory:")`, интеграционный тест — Docker.

> *Отклонения. Обёртка названа `VectorStore`, а не `QdrantClient`: одноимённый класс есть в
> `qdrant_client`, и импорт обоих в один модуль читался бы как рекурсия. Она держит клиент **и оба
> эмбеддера** (768d + 384d), чтобы операция коллекции не могла получить не тот эмбеддер, а тест
> собирал тот же объект поверх `QdrantClient(":memory:")` через `VectorStore.in_memory(...)` — без
> Docker и без весов. `from_settings(settings)` строит клиент по `Settings.qdrant_url`/`qdrant_api_key`
> и сразу зовёт `health_check()`: недостижимый сервер превращается в `VectorStoreError` с подсказкой
> про `make dev`, а не в транспортное исключение на первом же upsert. Прежняя фикстура
> `qdrant_in_memory` (сырой `QdrantClient`) оставлена — она проверена с phase 0 и нужна тестам, которым
> эмбеддер не нужен; к ней добавлены `vector_store` (in-memory store с фейковыми эмбеддерами) и
> `docker_store` (пропускает тест, если контейнер не поднят). Docker-тест —
> `tests/integration/test_vector_docker.py`; в этой среде `make dev` поднимает Qdrant 1.19.1, но
> localhost проксируется через proxychains, поэтому прогон с Docker делается с `env -u LD_PRELOAD`.*

### 3.3. Коллекция `news`
- [x] `create_news_collection()` с 768d COSINE · `M` 🧪
- [x] Payload-индексы: `date`, `source`, `numerology_value`, `master_number` · `M` 🧪
- [x] `upsert_news(items: Sequence[NewsItem])` · `M` 🧪
- [x] `search_news(query, filters, limit)` · `M` 🧪
- [x] Тест: upsert + search по семантике · `M` 🧪
- [x] Коммит: `feat(vector): news collection` · `M` 🧪

**DoD:** payload-индексы созданы **до** ингеста, поиск с фильтром работает.

> *Отклонения. `filters` — не сырой `qdrant_client.models.Filter`, а pydantic-модель `NewsFilter`
> (`models/query.py`, frozen+strict: `date_from`, `date_to`, `source`, `numerology_value`,
> `master_number` + проверка порядка дат): так Qdrant-типы остаются внутри `vector/`, а MCP-инструмент
> 6.8 получает типизированный словарь фильтров. Перевод модели в `Filter` — чистая функция
> `build_news_filter` (`vector/filters.py`), поэтому покрыт юнит-тестами без сервера.
> Даты в payload — RFC 3339 (`2026-09-21T00:00:00Z`), потому что `DATETIME`-индекс индексирует
> именно timestamp, а строгий `date` модели `NewsItem` такой строки не принимает: `news_from_payload`
> срезает дату до `YYYY-MM-DD` перед `model_validate_json`. Верхняя граница диапазона — `< следующий
> день 00:00:00Z`, чтобы включительный `date_to` не терял новости своего же дня. `master_number` —
> производное поле payload (`item.numerology_value in {11,22,33}` через `numerology.is_master`), а не
> поле модели: это вопрос к `numerology_value`, и ответ нужен фильтру. `None`-поля в payload не
> пишутся вовсе (`exclude_none`), чтобы «ещё не посчитано» не стало индексируемым null.
> Индексы нельзя проверить в local mode (Qdrant предупреждает, что они там не действуют), поэтому DoD
> проверен на Docker-сервере: `tests/integration/test_vector_docker.py` сверяет `payload_schema` с
> `NEWS_PAYLOAD_INDEXES`. В том же коммите появились `vector/collections.py`, `vector/payloads.py` и
> `VectorStore.ensure_collections()`; `upsert_news` сам создаёт коллекцию до первой точки, а
> `search_news` зовёт `require_collection` и падает `CollectionNotFoundError` вместо `ValueError`
> local mode.*

### 3.4. Коллекция `numbers`
- [x] `create_numbers_collection()` с 384d COSINE · `M` 🧪
- [x] Payload-индексы: `number`, `context` · `M` 🧪
- [x] `upsert_number_patterns(patterns)` · `M` 🧪
- [x] Коммит: `feat(vector): numbers collection` · `M` 🧪

> *Уточнение. Аргумент `upsert_number_patterns` — `Sequence[NumberActivation]`, а не новый тип
> «паттерна числа»: payload этой коллекции и есть `NumberActivation` (`number` + `context` плюс
> `date`/`news_id` для трассируемости), а 3.7 переиспользует тот же payload для `number_history`.
> Вектор строится по `context` (короткая фраза — работа для 384d-модели), а при пустом контексте —
> по самому числу, иначе пустая строка дала бы всем таким активациям один и тот же вектор.
> Point id — `uuid5` от `(news_id, number)`, по одной точке на пару: `ExtractedNumbers.numbers`
> уже дедуплицирован, поэтому повторный ingest перезаписывает активации, а не копит их. Различие
> коллекций: `numbers` — семантический индекс по контекстам, `number_history` (3.7) — точный
> журнал активаций; этот коммит пишет только первую.*

### 3.5. Коллекция `patterns`
- [x] `create_patterns_collection()` с 768d · `M` 🧪
- [x] Payload-индексы: `type`, `strength`, `discovered_at` · `M` 🧪
- [x] `save_pattern(pattern)`, `find_similar_patterns(query)` · `M` 🧪
- [x] Коммит: `feat(vector): patterns collection` · `M` 🧪

> *Отклонения. `Pattern` получил поле `discovered_at: datetime | None = None` — так его анонсировал
> docstring модели в 1.1, и без него нечего индексировать. Проставляет его `save_pattern`, а не
> агент: «когда найден» — факт о записи в Qdrant, а не о связи между новостями, и уже
> проставленный timestamp не перезаписывается (повторный `save_pattern` не переписывает историю).
> `save_pattern` возвращает сохранённую версию модели — вызывающему (5.3) нужен именно объект с
> заполненным временем. Вектор строится по `interpretation`, а при пустой интерпретации — по типу и
> числам, чтобы пустая строка не сделала все паттерны одним и тем же вектором. Point id — `PatternId`.
> `find_similar_patterns` не принимает фильтров: 3.5 просит только семантику, а отбор по `type`/
> `strength` — задача CLI 7.x и может быть добавлена поверх индексов без изменения схемы.*

### 3.6. Коллекция `forecasts`
- [x] `create_forecasts_collection()` с 768d · `M` 🧪
- [x] Payload-индексы: `date`, `dominant_number` · `M` 🧪
- [x] `save_forecast`, `get_forecast(date)` · `M` 🧪
- [x] Коммит: `feat(vector): forecasts collection` · `M` 🧪

> *Уточнения. У `Forecast` нет собственного id, и он не заводится: у дня ровно одно чтение, поэтому
> point id — `uuid5` от даты, `save_forecast` перезаписывает день, а `get_forecast` делает точечное
> чтение по этому id (это и нужно 5.4 для «повторный вызов возвращает из кэша»). Заодно остаются
> индексы `date`/`dominant_number` для диапазонных запросов, которые понадобятся позже.
> «День ещё не читали» — это `None`, а «коллекции нет вовсе» — `CollectionNotFoundError`: разные
> ситуации с разными действиями. Вектор строится по `forecast` + `advice` (смысловая часть), а не по
> числам, которые и так фильтруются по индексу.*

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
- [ ] ADR `0010-use-mcp-server.md` · `M` 📝
      *Номер изменён с `0001` (он занят записью о ведении ADR из 0.9); нумерация ADR — в `docs/adr/0001-record-architecture-decisions.md`.*
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
