#!/usr/bin/env python3
"""The checks of reading-ledger.

  python3 verification/check.py            offline: the ledger against the cached registry records and the cached sources
  python3 verification/check.py --online   the same, but every DOI is resolved again at Crossref (then DataCite), every
                                           arXiv id at export.arxiv.org, and every source file is fetched again from GitHub
                                           at the recorded commit
  python3 verification/check.py --record   --online, and write what was fetched into verification/cache/
  python3 verification/check.py --break    every check fails when the thing it watches is broken (offline)

A title matches when the letters a-z agree after mathematics, Greek letters, digits, accents and punctuation are
taken out; registries drop or mangle the β of a title in different ways, and a word that differs still fails.
The first author matches when the family names agree without accents and case.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time
import tomllib
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules  # noqa: E402
from rules import add, jload, sub  # noqa: E402

PROSE = ["README.md", "README.en.md"]
FIELDS = {"key", "citation", "title", "first_author", "doi", "doi_found", "doi_found_title", "arxiv", "arxiv_version", "arxiv_title",
          "arxiv_from", "reading", "sections", "quoted_in", "date_read", "date_read_until", "cited_in", "evidence", "relied_on", "see", "note"}
READINGS = ("read", "abstract only", "record only", "not read; cited as quoted in", "recalled, not read", "own work", "not stated")
CACHE_REG = "verification/cache/registry.json"
CACHE_SRC = "verification/cache/sources.json"
UA = {"User-Agent": "reading-ledger-check/1.0 (+https://github.com/cpsbvbng26-dotcom/reading-ledger)"}


def today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def ledgers(F):
    out = {}
    for f in sorted(F):
        if re.fullmatch(r"ledger/[a-z0-9-]+\.toml", f):
            try:
                out[f] = tomllib.loads(F[f])
            except Exception as e:
                out[f] = {"error": str(e)}
    return out


# ------------------------------------------------------------------ matching

def letters(s):
    s = re.sub(r"\$[^$]*\$", "", str(s or ""))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.casefold())


def family(s):
    s = str(s or "").strip()
    if "," in s:
        s = s.split(",")[0]
    return letters(s.split()[-1] if s.split() else s)


# ------------------------------------------------------------------ the registries

def http(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def fetch_doi(doi):
    q = urllib.parse.quote(doi)
    try:
        m = json.loads(http("https://api.crossref.org/works/" + q))["message"]
        a = (m.get("author") or [{}])[0]
        return {"registry": "crossref", "title": (m.get("title") or [""])[0], "first_author": a.get("family") or a.get("name")}
    except Exception:
        a = json.loads(http("https://api.datacite.org/dois/" + q))["data"]["attributes"]
        c = (a.get("creators") or [{}])[0]
        return {"registry": "datacite", "title": a["titles"][0]["title"], "first_author": c.get("familyName") or c.get("name")}


def fetch_arxiv(aid):
    time.sleep(3)  # the arXiv API asks for a pause between calls
    x = http("https://export.arxiv.org/api/query?id_list=" + aid)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = ET.fromstring(x).find("a:entry", ns)
    if e is None or e.find("a:title", ns) is None:
        raise ValueError("arXiv has no record of " + aid)
    got = e.find("a:id", ns).text.rsplit("/", 1)[-1]
    if re.search(r"v\d+$", aid) and got != aid:
        raise ValueError("arXiv returned %s for %s" % (got, aid))
    return {"registry": "arxiv", "title": " ".join(e.find("a:title", ns).text.split()),
            "first_author": e.find("a:author/a:name", ns).text, "id": got}


def identifiers(item):
    """(cache key, the title the ledger gives for it) for every identifier of an item."""
    out = []
    if item.get("doi"):
        out.append(("doi:" + item["doi"].lower(), item.get("title")))
    if item.get("doi_found"):
        out.append(("doi:" + item["doi_found"].lower(), item.get("doi_found_title")))
    if item.get("arxiv"):
        out.append(("arxiv:" + item["arxiv"] + item.get("arxiv_version", ""), item.get("arxiv_title") or item.get("title")))
    return out


# ------------------------------------------------------------------ the sources: what each work prints

def extract_tex(text):
    bib = text[text.index(r"\begin{thebibliography}"):]
    items = {}
    for m in re.finditer(r"\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\})", bib, re.S):
        body = m.group(2)
        doi = re.search(r"\\doi\{([^}]*)\}", body)
        arx = re.search(r"arXiv:(\d{4}\.\d{4,5})", body) or re.search(r"arxiv\.(\d{4}\.\d{4,5})", body)
        ver = re.search(r"\((v\d+) read\)", body)
        items[m.group(1)] = {"doi": doi.group(1).lower() if doi else None, "arxiv": arx.group(1) if arx else None,
                             "version": ver.group(1) if ver else None}
    lit = text[text.index(r"\label{sec:lit}"):]
    lit = lit[:lit.index(r"\section*")]
    reading = {}
    labels = [("Read in", "read"), ("Abstract only", "abstract only"), ("Recalled, not read", "recalled, not read"),
              ("Not read, cited as listed by others", "not read; cited as quoted in")]
    body, _, after = lit.partition(r"\end{itemize}")
    for chunk in body.split(r"\item")[1:]:
        kind = next((k for p, k in labels if chunk.strip().startswith(p)), None)
        for c in re.finditer(r"\\cite(?:\[[^\]]*\])?\{([^}]*)\}", chunk):
            for key in c.group(1).split(","):
                if kind:
                    reading.setdefault(key.strip(), kind)
    for sentence in re.split(r"(?<=\.)\s+", after):
        if "recalled, not read" in sentence:
            for c in re.finditer(r"\\cite(?:\[[^\]]*\])?\{([^}]*)\}", sentence):
                for key in c.group(1).split(","):
                    reading.setdefault(key.strip(), "recalled, not read")
    return {"bibitems": items, "reading": reading}


def extract_markdown(text):
    sec = text[text.index("Sources of the check:"):]
    sec = sec[:sec.index("\n## ")]
    items, reading = {}, {}
    for chunk in re.split(r"\n- ", sec)[1:]:
        flat = " ".join(chunk.split())
        doi = re.search(r"doi:(10\.\S+?)\.?(?:\s|$)", flat)
        arx = re.search(r"arXiv (\d{4}\.\d{4,5})(v\d+)", flat)
        key = doi.group(1).lower()
        items[key] = {"doi": key, "arxiv": arx.group(1) if arx else None, "version": arx.group(2) if arx else None}
        reading[key] = ("read" if "Read in part:" in flat else "abstract only" if "Abstract read." in flat
                        else "recalled, not read" if "Recalled, not read." in flat else None)
    return {"bibitems": items, "reading": reading}


def extract_record(text):
    dois = sorted({d.lower().rstrip(".,;:)") for d in re.findall(r"10\.\d{4,5}/[^\s,;]+", text)})
    return {"dois": dois}


def raw_url(work):
    return "https://raw.githubusercontent.com/%s/%s/%s" % (work["repository"], work["commit"], work["file"])


# ------------------------------------------------------------------ checks

def schema(F):
    bad = []
    L = ledgers(F)
    if not L:
        return ["no ledger"]
    ids = set()
    for f, d in L.items():
        if "error" in d:
            bad.append(f + ": " + d["error"])
            continue
        w = d.get("work", {})
        if w.get("id") in ids or "ledger/" + w.get("id", "") + ".toml" != f:
            bad.append(f + ": the id of the work and the file name")
        ids.add(w.get("id"))
        if w.get("kind") not in ("tex", "markdown", "record"):
            bad.append(f + ": the kind")
        if w.get("kind") != "record" and not (re.fullmatch(r"[0-9a-f]{40}", w.get("commit", "")) and w.get("repository") and w.get("file")):
            bad.append(f + ": the repository, commit and file of the work")
        if not w.get("reading_source"):
            bad.append(f + ": reading_source")
        keys = [i.get("key") for i in d.get("item", [])]
        if len(keys) != len(set(keys)):
            bad.append(f + ": a key twice")
        for i in d.get("item", []):
            k = f + " " + str(i.get("key"))
            for field in ("key", "citation", "title", "first_author", "reading", "evidence"):
                if not i.get(field):
                    bad.append(k + ": no " + field)
            for field in sorted(set(i) - FIELDS):
                bad.append(k + ": an unknown field " + field)
            r = i.get("reading")
            if r not in READINGS:
                bad.append(k + ": the reading " + str(r))
            for field in ("date_read", "date_read_until"):
                v = i.get(field)
                if v is not None:
                    try:
                        ok = datetime.date.fromisoformat(v).isoformat() == v
                    except Exception:
                        ok = False
                    if not ok or v > today():
                        bad.append(k + ": " + field + " " + str(v))
            if i.get("date_read_until") and i.get("date_read_until", "") < i.get("date_read", "9"):
                bad.append(k + ": date_read_until before date_read")
            if r in ("read", "abstract only", "record only", "not read; cited as quoted in") and not i.get("date_read"):
                bad.append(k + ": no date_read")
            if r in ("recalled, not read", "own work") and (i.get("date_read") or i.get("sections")):
                bad.append(k + ": a date or sections for an item that was not read")
            if r == "read" and not i.get("sections"):
                bad.append(k + ": read, but no sections")
            if r == "read" and i.get("arxiv") and not i.get("arxiv_version") and "version" not in i.get("note", ""):
                bad.append(k + ": read on arXiv, but no version and no note on the version")
            if r == "not read; cited as quoted in" and not i.get("quoted_in"):
                bad.append(k + ": no quoted_in")
            if r != "not read; cited as quoted in" and i.get("quoted_in"):
                bad.append(k + ": quoted_in for an item that is not cited as quoted")
            if r == "own work" and family(i.get("first_author")) != "nemoto":
                bad.append(k + ": own work by another author")
            if r == "not stated" and not i.get("note"):
                bad.append(k + ": not stated, without a note")
            if i.get("arxiv") and not re.fullmatch(r"\d{4}\.\d{4,5}", i["arxiv"]):
                bad.append(k + ": the arXiv id")
            if i.get("arxiv_version") and not re.fullmatch(r"v\d+", i["arxiv_version"]):
                bad.append(k + ": the arXiv version")
            if i.get("doi") and not re.fullmatch(r"10\.\d{4,9}/\S+", i["doi"]):
                bad.append(k + ": the DOI")
            if w.get("kind") != "record" and i.get("cited_in") != w.get("file"):
                bad.append(k + ": cited_in is not the file of the work")
    return bad


def registry_against(F, records):
    bad = []
    for f, d in ledgers(F).items():
        for i in d.get("item", []):
            for key, title in identifiers(i):
                rec = records.get(key)
                if rec is None:
                    bad.append("%s %s: %s has no registry record" % (f, i.get("key"), key))
                    continue
                if "error" in rec:
                    bad.append("%s %s: %s: %s" % (f, i.get("key"), key, rec["error"]))
                    continue
                if letters(rec["title"]) != letters(title):
                    bad.append("%s %s: %s title: ledger %r, %s %r" % (f, i.get("key"), key, title, rec["registry"], rec["title"]))
                if family(rec["first_author"]) != family(i.get("first_author")):
                    bad.append("%s %s: %s first author: ledger %r, %s %r" % (f, i.get("key"), key, i.get("first_author"), rec["registry"], rec["first_author"]))
    return bad


def registry_cached(F):
    C = jload(F, CACHE_REG)
    if C is None:
        return [CACHE_REG + " cannot be read"]
    bad = registry_against(F, C["records"])
    for k, r in C["records"].items():
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("fetched", "")) or r.get("fetched", "") > today():
            bad.append(k + ": the date fetched")
    used = {key for d in ledgers(F).values() for i in d.get("item", []) for key, _ in identifiers(i)}
    for k in sorted(set(C["records"]) - used):
        bad.append(k + ": a cached record that no item uses")
    return bad


def sources_against(F, S):
    bad = []
    for f, d in ledgers(F).items():
        w = d.get("work", {})
        s = S.get(w.get("id"))
        if s is None:
            bad.append(f + ": no cached source")
            continue
        items = {i.get("key"): i for i in d.get("item", [])}
        if w.get("kind") == "record":
            have = set()
            for i in items.values():
                have |= {x.lower() for x in (i.get("doi"), i.get("doi_found")) if x}
                if i.get("arxiv"):
                    have.add("10.48550/arxiv." + i["arxiv"])
            for x in sorted(set(s["dois"]) - have):
                bad.append(f + ": the record names %s, the ledger does not" % x)
            for x in sorted(have - set(s["dois"]) - {"10.48550/arxiv." + i["arxiv"] for i in items.values() if i.get("arxiv")}):
                bad.append(f + ": the ledger names %s, the record does not" % x)
            continue
        if s.get("commit") != w.get("commit") or s.get("file") != w.get("file"):
            bad.append(f + ": the cached source is of another commit or file")
        bib = s["bibitems"]
        for k in sorted(set(bib) - set(items)):
            bad.append(f + ": %s is cited in the work and has no entry" % k)
        for k in sorted(set(items) - set(bib)):
            bad.append(f + ": %s has an entry and is not cited in the work" % k)
        for k in sorted(set(bib) & set(items)):
            b, i = bib[k], items[k]
            if b["doi"] and b["doi"] != (i.get("doi") or "").lower():
                bad.append(f + " %s: the DOI printed is %s, the ledger has %s" % (k, b["doi"], i.get("doi")))
            if not b["doi"] and i.get("doi"):
                bad.append(f + " %s: the ledger has a DOI that the work does not print" % k)
            if b["arxiv"] and b["arxiv"] != i.get("arxiv"):
                bad.append(f + " %s: the arXiv id printed is %s, the ledger has %s" % (k, b["arxiv"], i.get("arxiv")))
            if not b["arxiv"] and i.get("arxiv") and not i.get("arxiv_from"):
                bad.append(f + " %s: the work prints no arXiv id, and the ledger does not say where its id comes from" % k)
            if b["version"] and b["version"] != i.get("arxiv_version"):
                bad.append(f + " %s: the version printed as read is %s, the ledger has %s" % (k, b["version"], i.get("arxiv_version")))
            said = s["reading"].get(k)
            if said and said != i.get("reading"):
                bad.append(f + " %s: the work says %r, the ledger says %r" % (k, said, i.get("reading")))
            if not said and i.get("reading") not in ("own work", "not stated"):
                bad.append(f + " %s: the work's record of reading does not classify it, and the ledger says %r" % (k, i.get("reading")))
    return bad


def sources_cached(F):
    S = jload(F, CACHE_SRC)
    if S is None:
        return [CACHE_SRC + " cannot be read"]
    bad = sources_against(F, S)
    for d in ledgers(F).values():
        w = d.get("work", {})
        if w.get("kind") == "record":
            t = F.get(w.get("file"))
            if t is None or extract_record(t)["dois"] != S.get(w["id"], {}).get("dois"):
                bad.append(w.get("id") + ": the kept record differs from the cache")
    return bad


def see_pairs(F):
    """Items that name the same correction (see = ...) must be at least two, in at least two ledgers, with different
    identifiers or titles: the worked example of the Raith citation (self-correction GW-001)."""
    bad = []
    groups = {}
    for f, d in ledgers(F).items():
        for i in d.get("item", []):
            if i.get("see"):
                if not re.fullmatch(r"self-correction [A-Z]+-\d{3}", i["see"]):
                    bad.append(f + " " + i.get("key", "") + ": see")
                groups.setdefault(i["see"], []).append((f, i))
    for s, g in groups.items():
        if len({f for f, _ in g}) < 2 or len({letters(i.get("title")) for _, i in g}) < 2:
            bad.append(s + ": the items that name it are not two different works in two ledgers")
    gw = {i["key"]: i for i in ledgers(F).get("ledger/golden-window-resolution.toml", {}).get("item", [])}
    jc = {i["key"]: i for i in ledgers(F).get("ledger/joint-continuity.toml", {}).get("item", [])}
    r89, r94 = gw.get("Raith89", {}), jc.get("Raith94", {})
    if r89.get("see") != "self-correction GW-001" or r94.get("see") != "self-correction GW-001":
        bad.append("the Raith example: both items name GW-001")
    if "1994" not in r89.get("note", "") or "Lemma 6.2" not in r94.get("relied_on", "") or "Corollary 7.2" not in r89.get("relied_on", ""):
        bad.append("the Raith example: which paper each work relied on")
    if r89.get("reading") != "recalled, not read" or r94.get("reading") != "not read; cited as quoted in":
        bad.append("the Raith example: neither was read")
    return bad


def total_items(F):
    return sum(len(d.get("item", [])) for d in ledgers(F).values())


COUNTERS = {
    "ledgers": lambda F: len(ledgers(F)),
    "items": total_items,
    "read": lambda F: sum(1 for d in ledgers(F).values() for i in d.get("item", []) if i.get("reading") == "read"),
}


CHECKS = [
    ("Every entry has a citation, an identifier or none, a reading from the vocabulary, a date where read, and the file where it is cited", schema),
    ("Every DOI and arXiv id matches its registry record in title and first author (cached; --online fetches again)", registry_cached),
    ("Every bibitem has an entry, every entry is a bibitem, and the DOI, arXiv id, version and reading agree with what the work prints (cached; --online fetches again)", sources_cached),
    ("The Raith example: the two works name the same correction and say which Raith paper each relied on", see_pairs),
    ("Copies of the canonical files and the licences are byte-identical (sha256)", rules.copies),
    ("No university name, other place of creative work, self-title, item of rule 10 or single relative", rules.words_not_written),
    ("No e-mail address in any file", rules.no_email),
    ("Workflows: actions pinned to commits, permissions, timeouts; Dependabot", rules.workflows),
    ("labels.yml makes the labels of the canonical workflows", lambda F: rules.labels(F)),
    ("CLAUDE.md carries rules 16, 17 and 18 (10 times)", rules.claude_md),
    ("The writing rules: です/ます, no second person, no bold, one dash per paragraph, short sentences", lambda F: rules.prose(F, PROSE)),
    ("Every number in prose is in the ledger of numbers, and every count matches the ledgers", lambda F: rules.numbers(F, PROSE, COUNTERS)),
    ("README.md and README.en.md link each other, disclose the language model and name the licences", rules.readme_pair),
]


def online(F, record):
    records, sources, bad = {}, {}, []
    for f, d in ledgers(F).items():
        for i in d.get("item", []):
            for key, _ in identifiers(i):
                if key in records:
                    continue
                try:
                    kind, ident = key.split(":", 1)
                    rec = fetch_doi(ident) if kind == "doi" else fetch_arxiv(ident)
                except Exception as e:
                    rec = {"error": str(e)}
                rec["fetched"] = today()
                records[key] = rec
        w = d["work"]
        try:
            if w["kind"] == "record":
                sources[w["id"]] = extract_record(F[w["file"]])
            else:
                text = http(raw_url(w))
                ex = extract_tex(text) if w["kind"] == "tex" else extract_markdown(text)
                ex.update({"repository": w["repository"], "commit": w["commit"], "file": w["file"],
                           "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
                sources[w["id"]] = ex
        except Exception as e:
            bad.append(w["id"] + ": the source could not be fetched: " + str(e))
    bad += registry_against(F, records) + sources_against(F, sources)
    if record:
        with open(os.path.join(rules.ROOT, CACHE_REG), "w", encoding="utf-8") as fh:
            json.dump({"_": ["Records fetched by verification/check.py --record: Crossref first, DataCite when Crossref has no record, and the arXiv API. The offline check compares the ledger with these records."],
                       "records": dict(sorted(records.items()))}, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        with open(os.path.join(rules.ROOT, CACHE_SRC), "w", encoding="utf-8") as fh:
            json.dump({"_": ["What each work prints, extracted by verification/check.py --record from the file at the recorded commit (fetched from raw.githubusercontent.com), or from the kept record."],
                       **dict(sorted(sources.items()))}, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    for b in bad:
        print("  FAIL  " + b)
    print("\nonline: %d records, %d sources, %d problems." % (len(records), len(sources), len(bad)))
    return 1 if bad else 0


def _swap_reading(G):
    G["ledger/golden-window-resolution.toml"] = G["ledger/golden-window-resolution.toml"].replace(
        'doi = "10.4153/cmb-1992-013-x"\nreading = "abstract only"', 'doi = "10.4153/cmb-1992-013-x"\nreading = "record only"', 1)


C = [c[0] for c in CHECKS]
GWL = "ledger/golden-window-resolution.toml"
JCL = "ledger/joint-continuity.toml"
BREAKS = [
    (C[0], "a reading outside the vocabulary", sub(GWL, 'reading = "abstract only"', 'reading = "skimmed"')),
    (C[0], "an unknown field", sub(GWL, 'key = "HR92"', 'key = "HR92"\nread_fully = true')),
    (C[0], "a date read in the future", sub(GWL, 'date_read = "2026-11-18"', 'date_read = "2099-01-01"')),
    (C[0], "an item read on arXiv without a version", sub(GWL, 'arxiv_version = "v4"\n', '')),
    (C[0], "an item cited as quoted with no source of the quotation", sub(JCL, 'quoted_in = "LSZ ([35] in arXiv 2509.04227v2)"\n', '')),
    (C[0], "an item that was not read with a date", sub(GWL, 'doi = "10.1007/bf02020954"\nreading = "recalled, not read"', 'doi = "10.1007/bf02020954"\nreading = "recalled, not read"\ndate_read = "2026-11-18"')),
    (C[1], "a title that differs from Crossref by one word", sub(GWL, 'title = "Hausdorff dimension for piecewise monotonic maps"', 'title = "Hausdorff dimension for piecewise linear maps"')),
    (C[1], "a first author that differs from the record", sub(GWL, 'first_author = "Kuang"', 'first_author = "Li"')),
    (C[1], "an arXiv title that differs from the version read", sub(JCL, 'arxiv_title = "Entropy-continuity for interval maps with holes"', 'arxiv_title = "Entropy continuity for maps with holes"')),
    (C[1], "a DOI without a record", sub(GWL, 'doi = "10.1080/0022250x.1990.9990069"', 'doi = "10.1080/0022250x.1990.9990070"')),
    (C[2], "a bibitem without an entry", lambda G: G.__setitem__(GWL, re.sub(r'\n\[\[item\]\]\nkey = "HJ13"[\s\S]*$', "\n", G[GWL]))),
    (C[2], "an entry that is not a bibitem", add(JCL, '\n[[item]]\nkey = "Extra"\ncitation = "x"\ntitle = "x"\nfirst_author = "x"\nreading = "recalled, not read"\nevidence = "x"\ncited_in = "continuity/paper/joint-continuity.tex"\n')),
    (C[2], "a version that differs from the one the work says was read", sub(GWL, 'arxiv_version = "v3"\narxiv_title = "Entropy plateaus', 'arxiv_version = "v2"\narxiv_title = "Entropy plateaus')),
    (C[2], "a reading that differs from what the work says", _swap_reading),
    (C[2], "the kept record names a DOI the ledger lacks", add("sources/lit-check-2026-11-18.md", "\nAlso 10.1000/xyz123.\n")),
    (C[3], "the Raith example loses the correction it names", sub(JCL, 'see = "self-correction GW-001"\n', '')),
    (C[3], "the Raith example says the work relied on another paper", sub(GWL, 'AKgen cites Raith\'s 1994 paper', 'AKgen cites this paper')),
    (C[4], "one character of SECURITY.md", sub("SECURITY.md", "7 日以内", "8 日以内")),
    (C[5], "the university's name", add("README.md", "\n" + rules.dec("WkVO") + " " + rules.dec("VW5pdmVyc2l0eQ==") + "\n")),
    (C[5], "the other place of creative work", add("ledger/trinity-operator-games.toml", "# " + rules.OTHER_PLACE[2] + "\n")),
    (C[6], "an e-mail address", add("sources/lit-check-2026-11-18.md", "\nwriter" + "@" + "example.com\n")),
    (C[7], "an action named by its version", sub(".github/workflows/check.yml", "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1", "actions/checkout@v7")),
    (C[7], "the network job writes", sub(".github/workflows/check.yml", "contents: read", "contents: write")),
    (C[8], "labels.yml drops a label", sub(".github/workflows/labels.yml", 'gh label create "erratum"', 'gh label create "error"')),
    (C[9], "CLAUDE.md loses rule 17", sub("CLAUDE.md", "`list_issues` で一覧を取らない", "`list_issues` で一覧を取る")),
    (C[10], "a sentence not in です/ます", add("README.md", "\n台帳は論文ごとに置く。\n")),
    (C[10], "you in English", add("README.en.md", "\nYour ledger is here.\n")),
    (C[11], "a count that differs from the ledgers", sub("README.md", "台帳は 4 本です。", "台帳は 5 本です。")),
    (C[11], "a number not in the ledger of numbers", add("README.md", "\n文献は 7 件を読みました。\n")),
    (C[12], "README.md does not link the English page", sub("README.md", "[English](./README.en.md)", "English")),
]

if __name__ == "__main__":
    F = rules.load()
    if "--online" in sys.argv or "--record" in sys.argv:
        sys.exit(online(F, "--record" in sys.argv))
    sys.exit(rules.run(CHECKS, BREAKS, F, sys.argv))
