# Spec Delta

## Purpose

Defines what the project's long-term memory must contain after news is ingested: the per-article
write set that makes a repeated ingest safe, the one-summary-per-period rule for stored digests, and
the evidence quality of a stored activation, so a reading built from memory can be trusted to rest on
what it claims.

## ADDED Requirements

### Requirement: A repeated ingest never skips an article whose memory is incomplete

Ingest writes three things derived from one article: the article itself, its number patterns, and one
activation per distinct number it carries. The skip rule for a repeated ingest MUST be based on that
whole set, not on the article alone. An article whose point exists but whose patterns or activations
were never written MUST be treated as not yet ingested and MUST be completed by the next ingest of the
same range. A run interrupted after any of the three writes but before the last MUST NOT leave an
article that no later ingest will ever complete.

The three things MUST be written in an order that leaves the article unskipped until its memory is
whole, so an interruption at any point leaves work the next run picks up rather than a silently
incomplete record.

#### Scenario: The run dies after the article is stored

- **WHEN** an ingest stores an article and then fails before its activations are written
- **THEN** a later ingest of the same range writes that article's activations instead of skipping it

#### Scenario: A completed article is not rewritten

- **WHEN** an ingest runs again over a range whose articles were fully ingested
- **THEN** no model runs for those articles, no article is duplicated, and no activation is written twice

#### Scenario: The interruption is invisible in the answer

- **WHEN** an ingest completes after a previous run was interrupted
- **THEN** the returned stored items and activation count describe the completed state, and the
  memory holds exactly one activation per `(article, number)` pair

### Requirement: One digest exists per period and covers the period it states

A digest MUST be saved exactly once per summarisation, under the period of the older items it covers.
That stored period and the digest's numbers MUST describe the whole older range. A limit on how many
items reach the prompt MUST bound the prompt only: it MUST NOT cause a second stored digest, and it
MUST NOT narrow the stored period to the items the model was shown. Re-summarising the same period
MUST overwrite that period's digest rather than adding a second one, and a period that was never
summarised MUST NOT answer with a digest stored for a different period.

#### Scenario: More older items than the prompt limit

- **WHEN** a range holds more items older than the window than the summary limit allows
- **THEN** exactly one digest is stored for that summarisation, and its stated period and numbers
  cover the whole older range rather than only the items the summary was built from

#### Scenario: A sub-period is asked for

- **WHEN** a caller asks for the digest of a period that was never stored
- **THEN** there is no digest to return rather than a digest stored for a different period

#### Scenario: The same range is summarised twice

- **WHEN** the same older range is summarised again
- **THEN** one digest exists for that period, holding the newer summary

### Requirement: A stored activation names the mention it was read in

The snippet kept with an activation MUST be anchored at an occurrence of the activation's own number
as a whole number, so the evidence shown for it does not point at a different, larger number that
merely contains those digits. When the text contains no such occurrence, the stored snippet MUST fall
back to the opening of the text rather than anchoring on a partial match.

#### Scenario: A larger number contains the digits

- **WHEN** an article mentions `30` and later `3`, and an activation is recorded for `3`
- **THEN** its snippet is anchored at the standalone `3`, not at `30`

#### Scenario: The number never appears alone

- **WHEN** an activation is recorded for a number the text only contains inside a larger number
- **THEN** the snippet falls back to the opening of the text and still names the number

### Requirement: The dominant number is read only from reduced values

The dominant-number rule MUST consider only reduced numbers — `1` to `9` and the master numbers `11`,
`22` and `33`. A value outside that set MUST be rejected as invalid input rather than counted, because
a raw sum or a partial reduction would otherwise be reported as a day's dominant number while not
being a number the reading can rest on. An empty set of values MUST remain a valid input and MUST
answer the `0` sentinel.

#### Scenario: A value that is not reduced

- **WHEN** the dominant number is asked for a set containing a value outside the reduced numbers
- **THEN** the request is rejected naming the offending value

#### Scenario: A day with no numbers at all

- **WHEN** the dominant number is asked for an empty set
- **THEN** the answer is the `0` sentinel with no votes and nothing counted
