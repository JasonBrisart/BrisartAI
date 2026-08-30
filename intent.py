"""brisart_ai/intent.py

Question-intent detection, shared by public web ranking
(web/crawler.py) and offline document retrieval (knowledge/ranker.py).

Term-overlap ranking alone can only answer "does this source mention
the query's words?" -- it can't tell "the right words for the wrong
reason" apart from a real answer. That's how "who invented microsoft?"
used to surface PowerPoint help pages (they share the word "microsoft"),
and "who invented the transistor?" surfaced a Wikipedia disambiguation
page for the *album* "Invented" (it shares the word "invented"). This
module classifies a query into one of six coarse intents -- founder,
inventor, statistic, explanation, comparison, or general -- and scores a
candidate document against that intent's vocabulary, returning the
exact terms that fired so a debug replay can show *why* something
ranked where it did.

Intent is a ranking hint, never a hard filter. Nothing is ever dropped
for having the "wrong" intent -- only nudged -- so a ranking mistake
degrades to "slightly wrong order," never "correct answer silently
deleted." No embeddings, no models, no network: everything here is
regex and fixed vocabulary lists, pure stdlib.

**How founder vs. inventor gets decided.** Both intents share the same
creation-verb vocabulary ("invented," "founded," "created," ...); what
differs is the *object*. `_KNOWN_COMPANIES` is a small, hand-maintained
set of single-token company names -- if the creation question mentions
one, it's routed to founder scoring. An unrecognized company falls back
to inventor-style classification, which is a safe default (its boosts
like "history"/"developed" are still generally useful).

**Two signals stronger than ordinary vocabulary.** A person's name
("Bill Gates") answers a "who" question but carries no genre vocabulary
at all -- `looks_like_person_name()` is a narrow shape test (2-3
capitalized words, no digits, no org/genre words) that recognizes a
*name's shape*, not any specific person; no list of real people is
embedded anywhere. And a Wikipedia disambiguation qualifier like
"(album)" is much stronger evidence of the wrong genre than an ordinary
keyword hit -- `SIGNAL_WORK` is weighted at 3x an ordinary boost/penalty
for exactly that reason.

**The generic-concept trap.** For "who invented the transistor,"
`/wiki/Invention` matches the verb "invented" and even earns the
"invention" boost, yet it's a page about the *concept* of invention in
general -- it never names who invented anything specific.
`is_generic_concept_page()` demotes a title that is a single bare
concept word, unless that word is itself the query's actual subject (so
a genuine query about "invention history" is unaffected). This needed a
second, standalone variant, `is_bare_generic_concept_title()`, because
knowledge/ranker.py has to apply the same guard even for
`INTENT_GENERAL` queries, which never call `score_intent()` at all --
see that function's own docstring for the full reasoning.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Dict, FrozenSet, List, Sequence, Set, Tuple

# --------------------------------------------------------------------------
# Intent labels
# --------------------------------------------------------------------------

INTENT_FOUNDER = "founder"
INTENT_INVENTOR = "inventor"
INTENT_STATISTIC = "statistic"
INTENT_EXPLANATION = "explanation"
INTENT_COMPARISON = "comparison"
INTENT_GENERAL = "general"

ALL_INTENTS: Tuple[str, ...] = (
    INTENT_FOUNDER,
    INTENT_INVENTOR,
    INTENT_STATISTIC,
    INTENT_EXPLANATION,
    INTENT_COMPARISON,
    INTENT_GENERAL,
)

# --------------------------------------------------------------------------
# Detection vocabulary
# --------------------------------------------------------------------------

_CREATION_VERBS: FrozenSet[str] = frozenset(
    {
        "invented", "invent", "invents", "invention", "created",
        "create", "creates", "founded", "found", "founds", "made",
        "make", "makes", "started", "start", "starts", "built",
        "build", "builds", "developed", "develop", "develops",
        "designed", "design", "designs", "wrote", "write", "writes",
    }
)

# Companies whose name in a creation question means the asker wants
# FOUNDERS. Deliberately small: guessing "is this a company?" from
# surface form alone is unreliable, and a wrong guess just sends the
# query to the wrong (but still reasonable) intent.
#
# 1.0.0-beta.9: extended with more single-token brand names
# (streaming/gig/fintech/gaming/productivity) that were previously
# falling through to the inventor default.
_KNOWN_COMPANIES: FrozenSet[str] = frozenset(
    {
        "microsoft", "apple", "google", "amazon", "facebook", "meta",
        "netflix", "tesla", "twitter", "ibm", "intel", "nvidia",
        "oracle", "adobe", "spacex", "openai", "anthropic", "uber",
        "airbnb", "paypal", "ebay", "yahoo", "sony", "samsung",
        "nintendo", "sega", "valve", "spotify", "reddit", "linkedin",
        "youtube", "instagram", "tiktok", "snapchat", "discord",
        "dropbox", "salesforce", "cisco", "dell", "hp", "lenovo",
        "qualcomm", "amd", "boeing", "ford", "toyota", "honda",
        "walmart", "costco", "starbucks", "mcdonalds", "nike",
        "disney", "pixar", "wikipedia", "mozilla", "canonical",
        "redhat", "github", "gitlab", "atlassian", "shopify",
        "stripe", "square", "robinhood", "coinbase", "binance",
        "twitch", "doordash", "instacart", "peloton", "zillow",
        "yelp", "grubhub", "chegg", "asana", "notion", "figma",
        "canva", "palantir", "snowflake", "databricks", "block",
        "blizzard", "activision", "ubisoft", "riot", "epic",
        "slack", "zoom", "airtable", "twilio", "okta", "datadog",
        "roblox", "unity", "epicgames",
    }
)

# Products/works that are NOT companies even when a company name sits
# beside them -- "who invented microsoft powerpoint" is product history,
# closer to inventor intent than founder intent.
_PRODUCT_WORDS: FrozenSet[str] = frozenset(
    {
        "powerpoint", "excel", "word", "outlook", "office", "windows",
        "teams", "azure", "onedrive", "sharepoint", "iphone", "ipad",
        "macbook", "android", "chrome", "gmail", "photoshop",
    }
)

_STATISTIC_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "many"), ("how", "much"), ("number", "of"),
    ("count", "of"), ("amount", "of"), ("total", "of"),
    ("population", "of"),
)
_STATISTIC_WORDS: FrozenSet[str] = frozenset(
    {"population", "estimate", "estimated", "statistics", "census"}
)

_EXPLANATION_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "does"), ("how", "do"), ("how", "did"), ("how", "is"),
    ("how", "are"), ("how", "can"), ("what", "causes"),
    ("what", "cause"), ("why", "do"), ("why", "does"),
    ("why", "is"), ("why", "are"),
)
_EXPLANATION_LEAD_WORDS: FrozenSet[str] = frozenset({"why", "explain"})

# "when was X invented" asks for a date, so date vocabulary is boosted.
_WHEN_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("when", "was"), ("when", "did"), ("when", "were"), ("what", "year"),
)

_COMPARISON_QUERY_RE = re.compile(
    r"\b("
    r"vs\.?|versus|compare|comparison|compared|"
    r"outlive[sd]?|outlast[sd]?|"
    r"better|worse|longer|shorter|faster|slower|"
    r"bigger|smaller|cheaper|more\s+expensive|"
    r"higher|lower|stronger|weaker|"
    r"difference|different|which\s+is"
    r")\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(str(text or "").casefold())


def _has_phrase(words: Sequence[str], phrase: Sequence[str]) -> bool:
    span = len(phrase)
    if span == 0 or len(words) < span:
        return False
    target = tuple(phrase)
    for start in range(len(words) - span + 1):
        if tuple(words[start:start + span]) == target:
            return True
    return False


# --------------------------------------------------------------------------
# Per-intent scoring vocabulary. Multi-word entries match as phrases;
# single words match as whole tokens (so "history" never fires inside
# "prehistory").
# --------------------------------------------------------------------------

INTENT_BOOSTS: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: (
        "founder", "founders", "founded", "founding", "co-founder",
        "cofounder", "co-founders", "cofounders", "history", "origin",
        "origins", "company", "corporation", "established",
        "founded by", "created by", "started by", "early history",
        "biography", "entrepreneur",
    ),
    INTENT_INVENTOR: (
        "inventor", "inventors", "invented", "invention", "history",
        "developed", "discovered", "origin", "origins", "pioneer",
        "bell labs", "laboratories", "patent", "first", "timeline",
        "invented by", "developed by", "discovery",
    ),
    INTENT_STATISTIC: (
        "population", "statistics", "stats", "estimate", "estimated",
        "census", "demographics", "number", "numbers", "count",
        "million", "billion", "thousand", "percent", "percentage",
        "households", "survey", "data", "total", "figures",
    ),
    INTENT_EXPLANATION: (
        "explanation", "explained", "cause", "causes", "mechanism",
        "science", "guide", "behavior", "behaviour", "process",
        "works", "working", "reason", "reasons", "how", "why",
        "because", "theory", "principle", "principles",
    ),
    INTENT_COMPARISON: (
        "comparison", "compare", "compares", "compared", "versus", "vs",
        "difference", "differences", "study", "research", "data",
        "statistics", "analysis", "report",
    ),
    INTENT_GENERAL: (),
}

# Genre markers that are predictably wrong for an intent -- penalties,
# never filters.
INTENT_PENALTIES: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: (
        "powerpoint", "excel", "outlook", "office", "microsoft-365",
        "microsoft365", "download", "pricing", "buy", "subscription",
        "sign-in", "signin", "sign in", "log-in", "login", "account",
        "support", "help", "troubleshoot", "install", "product",
        "products", "store", "app", "apps", "template", "templates",
        "tutorial", "album", "song", "film", "movie", "invention",
    ),
    INTENT_INVENTOR: (
        "album", "song", "single", "band", "lyrics", "discography",
        "movie", "film", "tv-series", "download", "buy", "pricing",
        "store", "support", "login", "account", "shop", "datasheet",
        "buy-now", "coupon",
    ),
    INTENT_STATISTIC: (
        "breed", "breeds", "adoption", "adopt", "shelter", "rescue",
        "album", "song", "movie", "film", "shop", "store", "buy",
        "pricing", "login", "account", "recipe", "toys", "names",
        "glossary", "dictionary", "definition", "meaning",
    ),
    INTENT_EXPLANATION: (
        "buy", "shop", "store", "pricing", "coupon", "deal", "deals",
        "login", "account", "album", "song", "movie", "film",
        "glossary", "dictionary", "definition", "list-of",
        "best-", "top-10", "top-", "review", "reviews",
    ),
    INTENT_COMPARISON: (
        "buy", "shop", "store", "pricing", "coupon", "login", "account",
        "album", "song", "movie", "film", "glossary", "dictionary",
        "definition",
    ),
    INTENT_GENERAL: (),
}

DATE_BOOSTS: Tuple[str, ...] = (
    "timeline", "chronology", "history", "year", "date", "dates",
    "century", "anniversary",
)

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")

# Wikipedia-style disambiguation qualifiers identifying a creative work
# rather than a topic. "Invented (album)" is the canonical trap for an
# inventor question.
_WORK_QUALIFIER_RE = re.compile(
    r"\((?:album|song|single|ep|band|film|movie|tv series|television series"
    r"|novel|book|video game|game|magazine|comics|play|musical|opera"
    r"|soundtrack|mixtape)\)",
    re.IGNORECASE,
)

SIGNAL_PERSON = "<person>"
SIGNAL_YEAR = "<year>"
SIGNAL_WORK = "<work-of-art>"
SIGNAL_GENERIC = "<generic-concept>"

# Penalties outweigh boosts on purpose: a wrong-genre marker like
# "(album)" is far more conclusive evidence than a right-genre one like
# "history" merely appearing somewhere.
BOOST_WEIGHTS: Dict[str, float] = {SIGNAL_PERSON: 2.0, SIGNAL_YEAR: 1.5}
PENALTY_WEIGHTS: Dict[str, float] = {SIGNAL_WORK: 3.0, SIGNAL_GENERIC: 1.5}
DEFAULT_PENALTY_WEIGHT = 1.5

_NON_NAME_TOKENS: FrozenSet[str] = frozenset(
    {
        "the", "of", "and", "a", "an", "in", "on", "for", "inc",
        "corp", "corporation", "company", "ltd", "llc", "group",
        "history", "invention", "album", "song", "film", "movie",
        "list", "index", "category", "wikipedia", "news", "home",
        "login", "account", "support", "download", "university",
        "institute", "labs", "laboratories", "museum", "school",
    }
)
_NAME_PART_RE = re.compile(r"^[A-Z][a-z]{1,}$")
_NAME_INITIAL_RE = re.compile(r"^[A-Z]\.?$")

# Bare abstract-concept encyclopedia titles. "law"/"legislation"/
# "politics"/"government" were added after a live failure: for "what
# laws have been passed since trump became president," a bare /wiki/Law
# page surfaced as a top source purely for sharing the word "law."
_GENERIC_CONCEPT_TITLES: FrozenSet[str] = frozenset(
    {
        "invention", "inventions", "inventor", "inventors",
        "discovery", "innovation", "technology", "science",
        "engineering", "history", "company", "corporation",
        "business", "entrepreneur", "entrepreneurship", "founder",
        "founders", "creation", "design", "research", "development",
        "population", "statistics", "demographics", "estimation",
        "explanation", "causality", "behavior", "behaviour",
        "law", "laws", "legislation", "politics", "government",
    }
)


def is_generic_concept_page(text: str, topic_terms: Set[str]) -> bool:
    """True for an encyclopedia page about a bare concept, not the topic.

    Only fires when a candidate title is a SINGLE concept word not
    itself the subject being asked about -- "history of the transistor"
    is multi-word and never matches; a bare "/wiki/History" does, unless
    "history" is literally the subject. Intended for one already-isolated
    title/URL, not a large combined haystack -- see
    is_bare_generic_concept_title() for the ranker-facing variant that
    also strips " - Site Name" suffixes.
    """
    for candidate in name_candidates(text):
        title = re.sub(r"_", " ", str(candidate or "")).strip()
        title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().casefold()
        if not title or " " in title:
            continue
        if title not in _GENERIC_CONCEPT_TITLES:
            continue
        subject_terms = {term.casefold() for term in (topic_terms or set())}
        if title in subject_terms:
            return False
        return True
    return False


def is_bare_generic_concept_title(candidate: str) -> bool:
    """True when `candidate` is a bare generic-concept title/slug.

    Unlike is_generic_concept_page(), takes one already-isolated title
    or URL slug directly, and strips a trailing " - Wikipedia" / "|
    Site Name" suffix before comparing, so both "Law" and
    "Law - Wikipedia" match while "History of the Transistor" and "Law
    of South Africa" (which carry more than the bare concept) do not.

    >>> is_bare_generic_concept_title("Law")
    True
    >>> is_bare_generic_concept_title("Law - Wikipedia")
    True
    >>> is_bare_generic_concept_title("History of the Transistor")
    False
    """
    if not candidate:
        return False
    cleaned = re.sub(r"[_\-]+", " ", str(candidate)).strip()
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
    cleaned = re.split(r"\s+[-|:]\s+", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.casefold()
    if not cleaned or " " in cleaned:
        return False
    return cleaned in _GENERIC_CONCEPT_TITLES


def looks_like_person_name(text: str) -> bool:
    """True when `text` looks like a personal name, e.g. "Bill Gates".

    A narrow shape test only -- two or three capitalized words, optional
    middle initial, no digits, no org/genre words. Only consulted for
    the founder/inventor intents where "who" is the actual question. It
    recognizes a name *shape*, not any specific person -- no list of
    people is embedded.

    >>> looks_like_person_name("Bill Gates")
    True
    >>> looks_like_person_name("History of Microsoft")
    False
    """
    raw = str(text or "").replace("_", " ")
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    parts = raw.split()
    if not 2 <= len(parts) <= 3:
        return False
    if any(part.casefold() in _NON_NAME_TOKENS for part in parts):
        return False
    if not _NAME_PART_RE.match(parts[0]):
        return False
    if not _NAME_PART_RE.match(parts[-1]):
        return False
    if len(parts) == 3 and not (
        _NAME_PART_RE.match(parts[1]) or _NAME_INITIAL_RE.match(parts[1])
    ):
        return False
    return True


def wants_person(query: str) -> bool:
    """True when the query asks *who* did something."""
    return "who" in set(_words(query))


def name_candidates(text: str) -> List[str]:
    """Fragments of `text` that might be a person's name.

    A candidate arrives either as a bare title ("Bill Gates") or a full
    URL; in URL form the scheme/host/path prefix push the name past the
    2-3 word limit looks_like_person_name() needs, so the last path
    segment is offered as an extra candidate -- where encyclopedia and
    biography URLs put the subject.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    candidates = [raw]
    if "//" in raw or raw.count("/") >= 2:
        path = raw.split("?", 1)[0].split("#", 1)[0]
        segments = [seg for seg in path.split("/") if seg]
        if segments:
            last = urllib.parse.unquote(segments[-1])
            last = re.sub(r"\.(html?|php|aspx?|htm)$", "", last, flags=re.I)
            if last and last not in candidates:
                candidates.append(last)
    return candidates


def detect_intent(query: str) -> str:
    """Classify a query into one of ALL_INTENTS.

    Order matters: statistic and explanation are checked before the
    creation intents, since "how many X did Y invent" is primarily a
    counting question. Founder vs. inventor is decided purely by whether
    a known company name is present.

    >>> detect_intent("who invented microsoft?")
    'founder'
    >>> detect_intent("who invented the transistor and when?")
    'inventor'
    >>> detect_intent("how many cats are in america?")
    'statistic'
    >>> detect_intent("why do cats purr?")
    'explanation'
    """
    words = _words(query)
    if not words:
        return INTENT_GENERAL
    word_set = set(words)

    if any(_has_phrase(words, phrase) for phrase in _STATISTIC_PHRASES):
        return INTENT_STATISTIC
    if word_set & _STATISTIC_WORDS:
        return INTENT_STATISTIC

    if _COMPARISON_QUERY_RE.search(str(query or "")):
        return INTENT_COMPARISON

    has_creation = bool(word_set & _CREATION_VERBS)

    # An explanation question outranks the creation reading, but "who
    # invented X" must stay a creation question even though it starts
    # with a question word.
    if not has_creation or "who" not in word_set:
        if any(_has_phrase(words, phrase) for phrase in _EXPLANATION_PHRASES):
            return INTENT_EXPLANATION
        if words[0] in _EXPLANATION_LEAD_WORDS:
            return INTENT_EXPLANATION

    if has_creation:
        if word_set & _PRODUCT_WORDS:
            return INTENT_INVENTOR
        if word_set & _KNOWN_COMPANIES:
            return INTENT_FOUNDER
        return INTENT_INVENTOR

    return INTENT_GENERAL


def wants_date(query: str) -> bool:
    """True when the query explicitly asks *when* something happened."""
    words = _words(query)
    return any(_has_phrase(words, phrase) for phrase in _WHEN_PHRASES)


def boost_terms(intent: str, query: str = "") -> Tuple[str, ...]:
    """Boost vocabulary for an intent, plus date terms when relevant."""
    terms = INTENT_BOOSTS.get(intent, ())
    if query and wants_date(query):
        merged = list(terms)
        for term in DATE_BOOSTS:
            if term not in merged:
                merged.append(term)
        return tuple(merged)
    return terms


def penalty_terms(intent: str) -> Tuple[str, ...]:
    """Penalty vocabulary for an intent."""
    return INTENT_PENALTIES.get(intent, ())


def _normalize_haystack(text: str) -> Tuple[str, Set[str]]:
    """Space-normalized text plus its token set, for matching.

    Punctuation and URL separators collapse to spaces so
    "history-of-microsoft" and "History of Microsoft" tokenize alike.
    """
    lowered = str(text or "").casefold()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return (spaced, set(spaced.split()))


def _match_vocabulary(haystack: str, tokens: Set[str], vocabulary: Sequence[str]) -> List[str]:
    """Vocabulary entries present in the haystack.

    Multi-word/hyphenated entries match as phrases; single words match
    as whole tokens (so "history" doesn't fire inside "prehistory").
    """
    hits: List[str] = []
    for entry in vocabulary:
        normalized = re.sub(r"[^a-z0-9]+", " ", entry.casefold()).strip()
        if not normalized:
            continue
        if " " in normalized:
            if normalized in haystack:
                hits.append(entry)
        elif normalized in tokens:
            hits.append(entry)
    return hits


def score_intent(
    text: str,
    intent: str,
    query: str = "",
    boost_weight: float = 1.0,
    penalty_weight: float = DEFAULT_PENALTY_WEIGHT,
    max_boosts: int = 4,
    topic_terms: Set[str] | None = None,
) -> Tuple[float, List[str], List[str]]:
    """Score `text` for fit with `intent`.

    Returns `(delta, boosts_hit, penalties_hit)` -- a signed adjustment
    plus the exact terms that produced it, which is what makes ranking
    explainable in the replay scripts. Ordinary vocabulary credit is
    capped at `max_boosts` distinct terms so a page stuffed with genre
    words can't dominate on vocabulary alone; the four strong signals
    (person, year, work-of-art, generic concept) aren't subject to that
    cap, since each identifies a page's genre outright rather than just
    hinting at it.

    Only called by ranker.py for non-INTENT_GENERAL queries -- see
    knowledge/ranker.py's intent_adjust() for why the generic-concept
    guard embedded here (via is_generic_concept_page) had to be
    duplicated as a standalone check for the INTENT_GENERAL case, since
    this function is simply never reached for those queries.
    """
    haystack, tokens = _normalize_haystack(text)
    if not haystack:
        return (0.0, [], [])

    vocabulary_hits = _match_vocabulary(haystack, tokens, boost_terms(intent, query))
    penalties = _match_vocabulary(haystack, tokens, penalty_terms(intent))

    strong_boosts: List[str] = []

    if query and wants_date(query) and _YEAR_RE.search(haystack):
        strong_boosts.append(SIGNAL_YEAR)

    if (
        query
        and intent in (INTENT_FOUNDER, INTENT_INVENTOR)
        and wants_person(query)
        and any(looks_like_person_name(candidate) for candidate in name_candidates(text))
    ):
        strong_boosts.append(SIGNAL_PERSON)

    if _WORK_QUALIFIER_RE.search(str(text or "")):
        penalties = penalties + [SIGNAL_WORK]

    if topic_terms is not None and is_generic_concept_page(text, topic_terms):
        penalties = penalties + [SIGNAL_GENERIC]

    counted = vocabulary_hits[: max(0, max_boosts)]
    boost_total = sum(BOOST_WEIGHTS.get(term, 1.0) for term in counted) + sum(
        BOOST_WEIGHTS.get(term, 1.0) for term in strong_boosts
    )
    penalty_total = sum(PENALTY_WEIGHTS.get(term, 1.0) for term in penalties)

    delta = (boost_total * boost_weight) - (penalty_total * penalty_weight)
    return (delta, counted + strong_boosts, penalties)


def describe_intent(intent: str, query: str = "") -> str:
    """One-line human summary of an intent, for debug output."""
    if intent == INTENT_GENERAL:
        return "general (no specific intent detected; term overlap only)"
    date_note = " +dates" if query and wants_date(query) else ""
    return (
        f"{intent}{date_note} "
        f"(boosts={len(boost_terms(intent, query))}, "
        f"penalties={len(penalty_terms(intent))})"
    )


__all__ = [
    "ALL_INTENTS", "BOOST_WEIGHTS", "DATE_BOOSTS", "DEFAULT_PENALTY_WEIGHT",
    "INTENT_BOOSTS", "INTENT_COMPARISON", "INTENT_EXPLANATION",
    "INTENT_FOUNDER", "INTENT_GENERAL", "INTENT_INVENTOR",
    "INTENT_PENALTIES", "INTENT_STATISTIC", "PENALTY_WEIGHTS",
    "SIGNAL_GENERIC", "SIGNAL_PERSON", "SIGNAL_WORK", "SIGNAL_YEAR",
    "boost_terms", "describe_intent", "detect_intent",
    "is_bare_generic_concept_title", "is_generic_concept_page",
    "looks_like_person_name", "name_candidates", "penalty_terms",
    "score_intent", "wants_date", "wants_person",
]
