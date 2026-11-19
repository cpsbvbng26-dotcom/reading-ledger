# reading-ledger

[日本語](./README.md)

A ledger, per work, of how far each cited item was read, which version was read, and when.
Citing an item and reading it are different things; the ledger writes the difference down, item by item.

## Ledgers

The ledgers are TOML files in `ledger/`, one per work.
There are 4 ledgers with 93 items in all.
They cover the paper of golden-window-resolution, its continuity paper (`continuity/paper/joint-continuity.tex`, with `continuity/REFEREE.md`), the literature check in `games/README.md` of trinity-operator, and the record of the literature check of 2026-11-18, kept as `sources/lit-check-2026-11-18.md`.
The last is a search record, not a work: its items need not be cited anywhere.

The reading of an item is one of `read` (with the sections read), `abstract only`, `record only` and `not read; cited as quoted in` (with the item that quoted it).
It can also be `recalled, not read`, `own work`, or `not stated`, where the source says nothing about the reading.
`record only` means that the bibliographic record was seen, and nothing more.
The fields are listed in the Japanese README.

## Checks

Every DOI is resolved at Crossref, or at DataCite where Crossref has no record, and every arXiv id at the arXiv API, version by version.
The title and the first author must match the ledger.
Every `\bibitem` of a paper must have an entry and every entry must be a `\bibitem`; the DOI, the arXiv id, the version read and the class of reading must agree with what the paper prints.
For the search record, the DOIs it names and the DOIs of the ledger must be the same set.

```
python3 verification/check.py            # offline, against verification/cache/
python3 verification/check.py --online   # fetch the registry records and the works again
python3 verification/check.py --record   # fetch again and write verification/cache/
python3 verification/check.py --break    # break each check once and see it fail
```

CI runs the offline check on every push and pull request, and the online check as a separate job then and once a week.

## The Raith example

In the proof of its `Corollary 7.2`, the paper of golden-window-resolution names Raith's 1989 paper as the source of `Lemma 6.2` of Allaart and Kong, who cite Raith's 1994 paper.
Neither was read.
The discrepancy was found on 2026-11-19, in the referee pass of the continuity paper, and is recorded as GW-001 in self-correction.
The published PDF is frozen and was not changed.
The ledger records which Raith paper each work relied on: `Raith89` in `golden-window-resolution.toml` is `recalled, not read`; `Raith94` in `joint-continuity.toml` is `not read; cited as quoted in` the papers of Kalle, Kong, Langeveld and Li and of Allaart and Kong.
Both name GW-001 in `see`, and the check looks at the pair.

## What was found

Matching the ledger with the registries showed that the item of Barnsley, Steiner and Vince prints the title of the journal version, while the arXiv version read has another title.
The journal DOI is not printed; the one Crossref returned is kept in `doi_found`.
For Sun and Li, the titles on arXiv and in the journal end differently.

## Searched for and not entered

`verification/references.toml` of autonomy-and-self-cultivation lists the sources of the philosophy papers and, by design, has no field for whether a source was read; there is no record of reading to copy.
E8 in `ERRATA.md` of trinity-infinity says the original of Friedkin and Johnsen was not consulted; the Trinity-Infinity papers do not cite it, so E8 appears only in the note of `FJ90`.

## Operator

Takuya Nemoto. ORCID iD [0009-0000-1406-0547](https://orcid.org/0009-0000-1406-0547).
[Report an error](https://github.com/cpsbvbng26-dotcom/reading-ledger/issues/new?template=error-report.yml). Security issues go through [SECURITY.md](./SECURITY.md).

## Use of a language model

The ledgers and the checks were written by Claude Code (Anthropic) at the operator's request.
The readings are copied from what the works and the record say; no item was read again to make the ledger.
Claude is not an author.

## Licence

Ledgers and text are [CC BY 4.0](./LICENSE); code is [MIT](./LICENSE-CODE).
The titles and names in the cached registry records are the records of each registry.
