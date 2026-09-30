# Spec Delta

## Purpose

Exposes the project's news, numerology, pattern and memory operations to MCP hosts as a fixed set of
typed tools, so an agent can ask a numerology question about the news without touching Qdrant, the
news APIs or an LLM itself.

## ADDED Requirements

### Requirement: The server publishes exactly nine tools over stdio

The server SHALL identify itself as `numenews` and SHALL expose exactly nine tools:
`fetch_news`, `extract_numbers`, `compute_numerology`, `find_patterns`, `check_master_numbers`,
`build_forecast`, `query_qdrant`, `save_pattern` and `get_history`. It MUST speak JSON-RPC over the
process's standard input and output, and MUST write logs and progress to standard error so the wire is
never polluted.

#### Scenario: A client lists the tools

- **WHEN** a client completes the MCP handshake and lists the tools
- **THEN** it receives exactly the nine tools named above, and the server identifies itself as `numenews`

#### Scenario: The server starts with nothing configured

- **WHEN** the server is launched with no Qdrant running, no news API keys and no LLM endpoint
- **THEN** it starts and completes the handshake successfully rather than exiting

### Requirement: Every tool returns a typed structured result

Every tool MUST return a Pydantic model or a list of them, so each call carries typed
`structuredContent` alongside the text a model reads. A tool MUST NOT return a bare dictionary. A
single model MUST be returned unwrapped; a list of models MUST be wrapped as `{"result": [...]}`.

#### Scenario: A single-model tool

- **WHEN** a client calls `compute_numerology`
- **THEN** the structured result is the model's own fields at the top level, not nested under a key

#### Scenario: A list-returning tool

- **WHEN** a client calls `get_history`
- **THEN** the structured result is an object with a single `result` key holding the list of activations

### Requirement: Prerequisites are resolved lazily and reported as actionable errors

The server MUST NOT require any dependency at startup. Each tool MUST build what it needs on its first
call and reuse it afterwards. When a prerequisite is missing, the tool MUST fail as a tool error whose
message names the missing thing and the action that supplies it, rather than raising an untranslated
exception.

#### Scenario: Qdrant is not running

- **WHEN** a client calls `query_qdrant` while Qdrant is unreachable
- **THEN** the call returns an error result whose message says Qdrant is not reachable and names the command that starts it

#### Scenario: No LLM endpoint is configured

- **WHEN** a client calls `extract_numbers` with no LLM endpoint configured
- **THEN** the call returns an error result naming the environment variables that would configure one

#### Scenario: The context-free tools still answer

- **WHEN** a client calls `compute_numerology` or `check_master_numbers` on a server with nothing configured at all
- **THEN** both answer successfully

### Requirement: `fetch_news` aggregates sources with graceful degradation

`fetch_news` SHALL take a `topic` and an inclusive `date_range` and return `list[NewsItem]`. It MUST
query the configured sources concurrently, MUST skip a source that fails while keeping the results of
the others, MUST de-duplicate the combined result, and MUST filter it to the requested range. A range
whose start falls after its end MUST be refused before any source is queried.

#### Scenario: One source is down

- **WHEN** one of the configured sources returns an error and the others answer
- **THEN** the call succeeds and returns the items from the sources that answered

#### Scenario: A reversed range

- **WHEN** `date_range` has a start later than its end
- **THEN** the call is rejected with the offending field named, and no source is queried

### Requirement: `extract_numbers` merges a model reading with a deterministic pass

`extract_numbers` SHALL take one text and return `ExtractedNumbers`. It MUST combine the extraction
agent's reading with the deterministic pattern pass so that a number written as a word is still found,
and it MUST report in `sources` which strategies contributed. If the model cannot answer at all, the
tool MUST degrade to the deterministic reading instead of failing.

#### Scenario: The model cannot answer

- **WHEN** the extraction agent raises because the provider is unavailable
- **THEN** the tool returns the deterministic reading and marks it as such in `sources`

### Requirement: `find_patterns` saves what it finds

`find_patterns` SHALL take a list of stored news ids, find the connections among those items, save
them, and return `list[Pattern]`. An id that is not in the store MUST be skipped rather than failing
the call. Each returned pattern MUST carry the discovery timestamp that was persisted with it.

#### Scenario: An unknown id is mixed in

- **WHEN** `news_ids` contains an id that is not in the store alongside ids that are
- **THEN** the call succeeds, the known ids are analysed, and the unknown id is ignored

#### Scenario: No ids at all

- **WHEN** `news_ids` is empty
- **THEN** the tool answers an empty list without running a model

### Requirement: `build_forecast` is idempotent per day

`build_forecast` SHALL take a calendar day, return the `Forecast` for it and persist it. A day that
already has a stored reading MUST be answered from storage without running a model. A day without one
MUST be assembled from the stored news window plus the recent activations of the numbers involved, and
the result MUST be saved under that day so a later call is free.

#### Scenario: The same day is read twice

- **WHEN** `build_forecast` is called twice for the same day
- **THEN** the second call returns the same reading and runs no model

### Requirement: `query_qdrant` searches stored news and saved patterns by meaning

`query_qdrant` SHALL take a `collection` of `news` or `patterns`, a query string and a `limit` between
1 and 50, and SHALL return `CollectionQueryResult`. Optional filters MUST narrow the news collection by
publication window, source, reduced value or master number, and MUST be applied inside the search
rather than after it. Filters supplied for the `patterns` collection MUST be refused rather than
silently ignored. A missing collection MUST produce an error naming the operation that creates it.

#### Scenario: Filters are sent for patterns

- **WHEN** a client passes filters together with `collection: "patterns"`
- **THEN** the call is rejected with an error saying filters apply to the news collection only

#### Scenario: Filtered news search

- **WHEN** a client searches the news collection with a date window and a reduced value
- **THEN** every returned item matches both filters

### Requirement: `save_pattern` is idempotent on the pattern id

`save_pattern` SHALL store one pattern and return it as written. Re-saving the same pattern id MUST
overwrite the stored point rather than creating a second one. When `discovered_at` is omitted it MUST
be filled in with the current time; when it is supplied it MUST be preserved and never rewritten. A
`strength` outside the range 0 to 1, or a `type` outside the known set, MUST be rejected.

#### Scenario: The same pattern is saved twice

- **WHEN** the same pattern id is saved twice
- **THEN** one point exists for it and the original `discovered_at` is unchanged

#### Scenario: An out-of-range strength

- **WHEN** a pattern is submitted with a strength above 1
- **THEN** the call is rejected with the offending field named

### Requirement: `get_history` answers activations newest first

`get_history` SHALL take a number and a `days` window between 1 and 365 (default 30) and return
`list[NumberActivation]`, newest first. The window MUST end today and include it, so a window of 1 day
means today. Each entry MUST correspond to one stored `(news item, number)` pair and MUST carry the
snippet the number was read in and the item's own reduced value when it has one.

#### Scenario: A one-day window

- **WHEN** `get_history` is called with `days` of 1
- **THEN** only activations dated today are returned

#### Scenario: A window outside the allowed range

- **WHEN** `days` is 0 or greater than 365
- **THEN** the call is rejected with the offending field named

### Requirement: Expected failures are distinguishable from defects

An expected condition MUST be reported as a tool error with `is_error` true and no
`structuredContent`, carrying a message the model can act on. An argument that violates the published
schema MUST be rejected before the tool body runs, naming the offending field. Any other exception MUST
NOT be translated: it MUST surface as a generic execution error with the traceback logged to standard
error, so a defect is never disguised as a normal answer.

#### Scenario: An argument violates the schema

- **WHEN** a client sends a malformed identifier or an unknown collection name
- **THEN** the call is rejected with the offending field named and the tool body never runs

#### Scenario: An unexpected defect

- **WHEN** a tool raises an exception that is not an expected domain failure
- **THEN** the client receives a generic execution error and the traceback is written to standard error
