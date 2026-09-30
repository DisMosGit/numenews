# Spec Delta

## MODIFIED Requirements

### Requirement: `forecast` reads a day without fetching news

`forecast` SHALL print the reading for a day without fetching anything, running a model only when that
day has no stored reading. It MUST accept a `--date` in three forms: an absolute date, one of the named
days relative to the pipeline clock, or a whole-day offset from it. Any other value MUST be a usage
error. The reading MUST be built from the window that ends on the requested day, so a past or future
day is read from its own evidence rather than from the current day's, and that reading MUST be the one
stored under the requested day.

#### Scenario: A named day

- **WHEN** `--date` is one of the named relative days
- **THEN** the reading for that day, resolved against the pipeline clock, is printed

#### Scenario: A whole-day offset

- **WHEN** `--date` is a signed day offset
- **THEN** the offset is applied to the pipeline clock, crossing month and year boundaries correctly

#### Scenario: A day other than today

- **WHEN** `--date` names a day before the current one and that day has no stored reading
- **THEN** the printed reading is built from the window ending on that day, and no item published after
  it contributes

#### Scenario: An unparseable date

- **WHEN** `--date` matches none of the accepted forms
- **THEN** the run fails with exit code 2 and nothing on standard output
