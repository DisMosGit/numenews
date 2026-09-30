# Spec Delta

## Purpose

Gives the project a scriptable, one-shot command surface: every invocation performs one operation,
writes exactly one JSON document to standard output and exits with a code a shell can branch on, so
the output pipes directly into tools such as `jq` without parsing logs.

## ADDED Requirements

### Requirement: One invocation writes exactly one JSON document to stdout

Each command MUST perform one operation, write exactly one JSON document to standard output and
terminate. Logs, progress and warnings MUST go to standard error, so standard output stays parseable
in every outcome. The one exception is the `mcp` command, whose standard output is the JSON-RPC wire.

#### Scenario: A successful run

- **WHEN** any command other than `mcp` completes successfully
- **THEN** standard output holds exactly one JSON document and all progress appears on standard error

#### Scenario: The output is parseable while logging is verbose

- **WHEN** a command runs with progress logging enabled
- **THEN** the standard output still parses as a single JSON document

### Requirement: The two entry points run the same application

The installed console script and the module invocation MUST offer the same commands, arguments and
output.

#### Scenario: Both entry points answer

- **WHEN** the same command is run through the installed script and through the module invocation
- **THEN** both produce the same JSON document

### Requirement: Global options behave as published

`--version` MUST print a JSON document naming the project and its version and then exit. `--pretty`
and `--no-pretty` MUST select indented or single-line JSON, and MUST default to indented. Global
options MUST be accepted before the command name. `--help` MUST list the available commands and is the
only writer to standard output that is not a command result.

#### Scenario: Version as JSON

- **WHEN** `--version` is passed
- **THEN** standard output is a JSON document with the project name and version

#### Scenario: Compact output

- **WHEN** a command runs with `--no-pretty`
- **THEN** the JSON document occupies a single line

### Requirement: The command surface is fixed and documented

The CLI SHALL provide exactly six commands — `today`, `forecast`, `history`, `search`, `patterns` and
`mcp` — each with the following arguments and defaults:

- `today` takes an optional `--topic`, defaulting to `politics`, and prints a `Forecast`.
- `forecast` takes an optional `--date`, defaulting to today, and prints a `Forecast`.
- `history` takes a required `--number` and an optional `--days` between 1 and 365 defaulting to 30,
  and prints the activations plus their per-day fold.
- `search` takes a required query, an optional `--collection` of `news` or `patterns` defaulting to
  `news`, and an optional `--limit` between 1 and 50 defaulting to 10.
- `patterns` takes an optional `--type`, an optional `--min-strength` between 0 and 1, and an optional
  `--limit` between 1 and 200 defaulting to 50.
- `mcp` takes an optional `--transport` defaulting to `stdio`.

#### Scenario: The command list

- **WHEN** the help text is requested
- **THEN** exactly the six commands above are listed

#### Scenario: A required argument is missing

- **WHEN** `history` is run without `--number`
- **THEN** the run fails as a usage error with nothing on standard output

### Requirement: Exit codes distinguish the four outcomes

The process MUST exit `0` when the command answered, `1` when an expected domain failure occurred, `1`
when a defect occurred, and `2` when the invocation itself was invalid. An expected domain failure
MUST write a JSON object carrying an `error` message and a `kind` field naming the failure class, so a
script can branch without parsing prose. A defect MUST leave standard output empty and write its
traceback to standard error. A usage error MUST write its message to standard error and leave standard
output empty.

#### Scenario: An expected domain failure

- **WHEN** a command fails because a dependency such as the vector store is unavailable
- **THEN** the exit code is 1 and standard output is a JSON object with `error` and `kind`

#### Scenario: An invalid invocation

- **WHEN** an unknown command or an unparseable option value is given
- **THEN** the exit code is 2 and standard output is empty

### Requirement: `today` is idempotent and cheap to repeat

`today` SHALL fetch the topic's news for the recent window, extract what it needs, store what it read
and print the day's reading. Running it twice MUST NOT duplicate stored work: an article already in the
store MUST be skipped before its extraction, and a day that already has a stored reading MUST be
answered from storage without running a model. The day and the window MUST come from the pipeline's
clock in UTC.

#### Scenario: A second run on the same day

- **WHEN** `today` is run twice in a row
- **THEN** the second run adds no duplicate articles and runs no model for the reading

#### Scenario: The topic can be chosen

- **WHEN** `today` is run with an explicit topic
- **THEN** the fetch covers that topic instead of the default one

### Requirement: `forecast` reads a day without fetching news

`forecast` SHALL print the reading for a day without fetching anything, running a model only when that
day has no stored reading. It MUST accept a `--date` in three forms: an absolute date, one of the named
days relative to the pipeline clock, or a whole-day offset from it. Any other value MUST be a usage
error.

#### Scenario: A named day

- **WHEN** `--date` is one of the named relative days
- **THEN** the reading for that day, resolved against the pipeline clock, is printed

#### Scenario: A whole-day offset

- **WHEN** `--date` is a signed day offset
- **THEN** the offset is applied to the pipeline clock, crossing month and year boundaries correctly

#### Scenario: An unparseable date

- **WHEN** `--date` matches none of the accepted forms
- **THEN** the run fails with exit code 2 and nothing on standard output

### Requirement: `history` folds activations by day

`history` SHALL print one entry per stored `(news item, number)` pair for the requested number, newest
first, each carrying the snippet the number was read in and the item's own reduced value when it has
one. It MUST also fold those entries into a per-day frequency, newest day first. The `--days` window
MUST end today and include it.

#### Scenario: A one-day window

- **WHEN** `--days` is 1
- **THEN** only today's activations and today's frequency are reported

#### Scenario: The per-day fold agrees with the entries

- **WHEN** the activations are folded by day
- **THEN** each day's count equals the number of activation entries carrying that date

### Requirement: `search` embeds locally and never needs a key

`search` SHALL look up stored entities by meaning. Searching the news collection MUST use the same
fused multi-stage retrieval as the MCP query tool; searching patterns MUST find saved pattern
interpretations. The query MUST be embedded locally, so the command MUST work with no LLM endpoint and
no API key configured. Filters are not part of this command's surface.

#### Scenario: Searching without any model endpoint

- **WHEN** `search` runs with no LLM endpoint configured
- **THEN** it answers successfully

#### Scenario: Choosing the patterns collection

- **WHEN** `search` is run against the patterns collection
- **THEN** it returns saved pattern interpretations rather than news items

### Requirement: `patterns` is an exact filtered read

`patterns` SHALL list already-stored patterns, strongest first, optionally narrowed by pattern type and
by a minimum strength, and limited to the requested count. It MUST be an exact query over the indexed
fields rather than a similarity search, and it MUST distinguish "no patterns stored" from "patterns
exist but none match the filter" by reporting the filter it applied alongside what it found.

#### Scenario: Filtering by strength

- **WHEN** `patterns` is run with a minimum strength
- **THEN** every returned pattern has a strength at or above it, ordered strongest first

#### Scenario: The filter is echoed

- **WHEN** `patterns` returns
- **THEN** the document reports the pattern type and minimum strength that were applied

### Requirement: `mcp` serves the tool surface instead of printing a result

`mcp` SHALL serve the MCP tools over the selected transport, matching the behaviour of the standalone
MCP entry points. Its standard output MUST be the protocol wire and MUST NOT be a JSON result document.

#### Scenario: Serving over stdio

- **WHEN** `mcp` is run with the default transport
- **THEN** the process speaks the protocol on standard input and output and writes no result document
