# Spec Delta

## MODIFIED Requirements

### Requirement: `fetch_news` aggregates sources with graceful degradation

`fetch_news` SHALL take a `topic` and an inclusive `date_range` and return `list[NewsItem]`. It MUST
query the configured sources concurrently, MUST skip a source that fails while keeping the results of
the others, MUST de-duplicate the combined result, and MUST filter it to the requested range. A range
whose start falls after its end MUST be refused before any source is queried. A source's response MUST
be treated as that source's failure whatever its headers contain: a rate-limit response whose
retry hint is absent, malformed or out of range MUST fall back to the client's own backoff rather than
aborting the whole call, so no single upstream header can turn one failing source into a failed fetch.

#### Scenario: One source is down

- **WHEN** one of the configured sources returns an error and the others answer
- **THEN** the call succeeds and returns the items from the sources that answered

#### Scenario: A response carries an unusable retry hint

- **WHEN** a source answers a rate limit with a retry hint that is not a whole number of seconds or a
  valid date
- **THEN** the call still returns the other sources' results rather than failing

#### Scenario: A reversed range

- **WHEN** `date_range` has a start later than its end
- **THEN** the call is rejected with the offending field named, and no source is queried

### Requirement: `build_forecast` is idempotent per day

`build_forecast` SHALL take a calendar day, return the `Forecast` for it and persist it. A day that
already has a stored reading MUST be answered from storage without running a model. A day without one
MUST be assembled from the stored news window plus the recent activations of the numbers involved, and
the result MUST be saved under that day so a later call is free. The news window MUST be derived from
the day being read: it MUST end on that day and MUST NOT extend past it, so a day other than the
current one is read from the evidence of its own window rather than from the current day's. A day the
window holds no news for MUST still be answered, falling back to the day's own date value.

#### Scenario: The same day is read twice

- **WHEN** `build_forecast` is called twice for the same day
- **THEN** the second call returns the same reading and runs no model

#### Scenario: A day other than the current one

- **WHEN** `build_forecast` is called for a day before the current one
- **THEN** the reading is built from the window ending on that day, and no item dated after it is used

#### Scenario: The window holds no news

- **WHEN** no stored item falls inside the requested day's window
- **THEN** the call still answers a reading, resting on the day's own date value
