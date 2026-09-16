"""
File: brisart_ai/intent.py

Purpose
-------
Question- and answer-intent classification plus intent-aware scoring for
the Brisart Relevance Engine. Classifies a query into one of eleven
intent types -- founder, inventor, statistic, explanation, comparison,
general, definition, procedure, evidence, validation, and
implementation -- each with its own boost/penalty vocabulary, and scores
how well a document matches the detected intent. Also provides
negation-span detection (used by synthesis to recognize when a sentence
negates rather than affirms a claim) and multi-intent detection (every
plausible intent for a query, not just the single best guess). Intent is
a HINT, not a filter: it only nudges scores.

Communication / relationships
------------------------------
- knowledge/ranker.py: detect_intent(), score_intent(), name_candidates(),
  is_bare_generic_concept_title().
- knowledge/synthesizer.py: detect_intent()/detect_intents() drive
  sentence-boost modes; term_is_negated() suppresses negated sentences.
- knowledge/query_decomposition.py, web/crawler.py: detect_intent(),
  describe_intent(), score_intent().
- knowledge/confidence.py: detect_negation_spans()/is_position_negated().
- Imports nothing from elsewhere in brisart_ai; only re and typing.

Settings / parameters
---------------------
- _KNOWN_COMPANIES / _PRODUCT_WORDS / _CREATION_VERBS: finite hand-
  maintained vocabularies steering classification (KI-004); an
  unrecognized company falls back to inventor intent.
- INTENT_BOOSTS / INTENT_PENALTIES: per-intent term lists score_intent()
  matches against a document.
- Scoring point values (score_intent): BOOST_WEIGHTS -- <person> = 2.0,
  <year> = 1.5, other boost terms = 1.0; PENALTY_WEIGHTS -- <work-of-art>
  = 3.0, <generic-concept> = 1.5; DEFAULT_PENALTY_WEIGHT = 1.5; max_boosts
  = 4. delta = boost_total*boost_weight - penalty_total*penalty_weight.
- MULTI_INTENT_CONFIDENCE_FLOOR = 0.15: a secondary intent below this is
  dropped. A single lead-phrase match scores 0.5, each extra +0.15, capped
  0.95 so the primary label at 1.0 always ranks first.
- NEGATION_SCOPE_WORDS = 6: words after a negation cue treated as in scope.

Edge cases
----------
- detect_intent()/detect_intents() on empty input return INTENT_GENERAL
  (detect_intents returns [(INTENT_GENERAL, 1.0)]).
- score_intent() on empty text returns (0.0, [], []).
- detect_intents() always lists the single label first at confidence 1.0.
- term_is_negated() checks only the FIRST occurrence of a term.
- detect_negation_spans() returns merged character-offset spans, never
  per-sentence booleans.

Known limitations
-----------------
- Classification is vocabulary/phrase-driven, not learned; unrecognized
  phrasings fall back to INTENT_GENERAL with no intent nudge.
- _KNOWN_COMPANIES and _GENERIC_CONCEPT_TITLES are finite lists (KI-004,
  KI-008); an unlisted item is not specially handled.
- looks_like_person_name() is a capitalization heuristic; it accepts
  non-name Title-Case phrases and rejects lowercase/single-token names.
- Negation detection is scope-window based, not syntactic.
- Multi-intent detection only adds the five extended intents via a fixed
  lead-phrase table; two co-occurring primary intents are not detected.

Examples
--------
    >>> detect_intent("who invented microsoft?")
    'founder'
    >>> detect_intent("how many cats are in america?")
    'statistic'
    >>> term_is_negated("Microsoft was not founded by Gates alone.", "founded")
    True
    >>> delta, _b, _p = score_intent(
    ...     "Microsoft was founded by Bill Gates and Paul Allen",
    ...     INTENT_FOUNDER, "who founded microsoft")
    >>> delta > 0
    True
"""
from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Intent labels
# ---------------------------------------------------------------------------

INTENT_FOUNDER = "founder"
INTENT_INVENTOR = "inventor"
INTENT_STATISTIC = "statistic"
INTENT_EXPLANATION = "explanation"
INTENT_COMPARISON = "comparison"
INTENT_GENERAL = "general"

# Extended intent classes
INTENT_DEFINITION = "definition"
INTENT_PROCEDURE = "procedure"
INTENT_EVIDENCE = "evidence"
INTENT_VALIDATION = "validation"
INTENT_IMPLEMENTATION = "implementation"

ALL_INTENTS: Tuple[str, ...] = (
    INTENT_FOUNDER, INTENT_INVENTOR, INTENT_STATISTIC,
    INTENT_EXPLANATION, INTENT_COMPARISON, INTENT_GENERAL,
)
EXTENDED_INTENTS: Tuple[str, ...] = ALL_INTENTS + (
    INTENT_DEFINITION, INTENT_PROCEDURE, INTENT_EVIDENCE,
    INTENT_VALIDATION, INTENT_IMPLEMENTATION,
)

# ---------------------------------------------------------------------------
# Classification vocabularies
# ---------------------------------------------------------------------------

_CREATION_VERBS: FrozenSet[str] = frozenset({
    "invented", "invent", "invents", "invention", "created", "create",
    "creates", "founded", "found", "founds", "made", "make", "makes",
    "started", "start", "starts", "built", "build", "builds", "developed",
    "develop", "develops", "designed", "design", "designs", "wrote", "write",
    "writes",
})
_KNOWN_COMPANIES: FrozenSet[str] = frozenset({
    "microsoft", "apple", "google", "amazon", "facebook", "meta", "netflix",
    "tesla", "twitter", "ibm", "intel", "nvidia", "oracle", "adobe", "spacex",
    "openai", "anthropic", "uber", "airbnb", "paypal", "ebay", "yahoo", "sony",
    "samsung", "nintendo", "sega", "valve", "spotify", "reddit", "linkedin",
    "youtube", "instagram", "tiktok", "snapchat", "discord", "dropbox",
    "salesforce", "cisco", "dell", "hp", "lenovo", "qualcomm", "amd", "boeing",
    "ford", "toyota", "honda", "walmart", "costco", "starbucks", "mcdonalds",
    "nike", "disney", "pixar", "wikipedia", "mozilla", "canonical", "redhat",
    "github", "gitlab", "atlassian", "shopify", "stripe", "square", "robinhood",
    "coinbase", "binance", "twitch", "doordash", "instacart", "peloton",
    "zillow", "yelp", "grubhub", "chegg", "asana", "notion", "figma", "canva",
    "palantir", "snowflake", "databricks", "block", "blizzard", "activision",
    "ubisoft", "riot", "epic", "slack", "zoom", "airtable", "twilio", "okta",
    "datadog", "roblox", "unity", "epicgames",
})
_PRODUCT_WORDS: FrozenSet[str] = frozenset({
    "powerpoint", "excel", "word", "outlook", "office", "windows", "teams",
    "azure", "onedrive", "sharepoint", "iphone", "ipad", "macbook", "android",
    "chrome", "gmail", "photoshop",
})
_STATISTIC_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "many"), ("how", "much"), ("number", "of"), ("count", "of"),
    ("amount", "of"), ("total", "of"), ("population", "of"),
)
_STATISTIC_WORDS: FrozenSet[str] = frozenset(
    {"population", "estimate", "estimated", "statistics", "census"}
)
_EXPLANATION_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "does"), ("how", "do"), ("how", "did"), ("how", "is"),
    ("how", "are"), ("how", "can"), ("what", "causes"), ("what", "cause"),
    ("why", "do"), ("why", "does"), ("why", "is"), ("why", "are"),
)
_EXPLANATION_LEAD_WORDS: FrozenSet[str] = frozenset({"why", "explain"})
_WHEN_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("when", "was"), ("when", "did"), ("when", "were"), ("what", "year"),
)
_COMPARISON_QUERY_RE = re.compile(
    r"\b(vs\.?|versus|compare|comparison|compared|outlive[sd]?|outlast[sd]?|"
    r"better|worse|longer|shorter|faster|slower|bigger|smaller|cheaper|"
    r"more\s+expensive|higher|lower|stronger|weaker|difference|different|"
    r"which\s+is)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(str(text or "").casefold())


def _has_phrase(words: Sequence[str], phrase: Sequence[str]) -> bool:
    if isinstance(phrase, str):
        phrase = (phrase,)
    span = len(phrase)
    if span == 0 or len(words) < span:
        return False
    target = tuple(phrase)
    for start in range(len(words) - span + 1):
        if tuple(words[start:start + span]) == target:
            return True
    return False


def detect_intent(query: str) -> str:
    """Single-label six-way classification (unchanged, load-bearing for the
    ranker's single-factor intent multiplier)."""
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
    words = _words(query)
    return any(_has_phrase(words, phrase) for phrase in _WHEN_PHRASES)


def wants_person(query: str) -> bool:
    return "who" in set(_words(query))


_INTENT_DESCRIPTIONS = {
    INTENT_FOUNDER: "a founder/company-history question",
    INTENT_INVENTOR: "an inventor/invention-history question",
    INTENT_STATISTIC: "a statistic/quantity question",
    INTENT_EXPLANATION: "an explanation/mechanism question",
    INTENT_COMPARISON: "a comparison question",
    INTENT_GENERAL: "a general question",
    INTENT_DEFINITION: "a definition question",
    INTENT_PROCEDURE: "a procedure/how-to question",
    INTENT_EVIDENCE: "an evidence/sourcing question",
    INTENT_VALIDATION: "a fact-check/validation question",
    INTENT_IMPLEMENTATION: "an implementation/code question",
}


def describe_intent(intent: str, query: str = "") -> str:
    base = _INTENT_DESCRIPTIONS.get(intent, f"a {intent} question")
    return f"{intent} ({base})"


# ---------------------------------------------------------------------------
# Extended (multi-)intent detection
# ---------------------------------------------------------------------------

_LEAD_PHRASE_INTENTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("what", "is", "a"), INTENT_DEFINITION),
    (("what", "is", "an"), INTENT_DEFINITION),
    (("what", "does"), INTENT_DEFINITION),
    (("what", "are"), INTENT_DEFINITION),
    (("define",), INTENT_DEFINITION),
    (("how", "do", "i"), INTENT_PROCEDURE),
    (("how", "to"), INTENT_PROCEDURE),
    (("how", "can", "i"), INTENT_PROCEDURE),
    (("what", "steps"), INTENT_PROCEDURE),
    (("is", "there", "evidence"), INTENT_EVIDENCE),
    (("what", "evidence"), INTENT_EVIDENCE),
    (("is", "it", "true"), INTENT_VALIDATION),
    (("is", "this", "true"), INTENT_VALIDATION),
    (("is", "that", "correct"), INTENT_VALIDATION),
    (("how", "do", "you", "implement"), INTENT_IMPLEMENTATION),
    (("write", "a", "function"), INTENT_IMPLEMENTATION),
    (("write", "code", "to"), INTENT_IMPLEMENTATION),
)
MULTI_INTENT_CONFIDENCE_FLOOR = 0.15


def detect_intents(query: str) -> List[Tuple[str, float]]:
    """Every plausible intent for `query` with a confidence in (0, 1],
    highest first. Always includes detect_intent()'s single label first at
    confidence 1.0."""
    primary = detect_intent(query)
    results: List[Tuple[str, float]] = [(primary, 1.0)]
    seen = {primary}
    words = _words(query)
    if not words:
        return results
    hit_counts: Dict[str, int] = {}
    for phrase, intent in _LEAD_PHRASE_INTENTS:
        if _has_phrase(words, phrase):
            hit_counts[intent] = hit_counts.get(intent, 0) + 1
    for intent, count in hit_counts.items():
        if intent in seen:
            continue
        confidence = min(0.95, 0.5 + 0.15 * (count - 1))
        if confidence >= MULTI_INTENT_CONFIDENCE_FLOOR:
            results.append((intent, confidence))
            seen.add(intent)
    results.sort(key=lambda item: item[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Negation awareness
# ---------------------------------------------------------------------------

NEGATION_WORDS: FrozenSet[str] = frozenset({
    "not", "no", "never", "without", "isn't", "isnt", "doesn't", "doesnt",
    "won't", "wont", "cannot", "can't", "cant", "neither", "nor", "n't",
    "didn't", "didnt", "wasn't", "wasnt", "weren't", "werent", "aren't",
    "arent", "hasn't", "hasnt", "haven't", "havent", "hadn't", "hadnt",
})
NEGATION_SCOPE_WORDS = 6
_TOKEN_SPAN_RE = re.compile(r"\S+")


def detect_negation_spans(text: str, scope_words: int = NEGATION_SCOPE_WORDS) -> List[Tuple[int, int]]:
    if not text:
        return []
    tokens = list(_TOKEN_SPAN_RE.finditer(text))
    if not tokens:
        return []
    raw_spans: List[Tuple[int, int]] = []
    for index, token in enumerate(tokens):
        cleaned = re.sub(r"[^\w']", "", token.group(0)).casefold()
        if cleaned in NEGATION_WORDS or cleaned.endswith("n't"):
            end_index = min(len(tokens) - 1, index + scope_words)
            raw_spans.append((token.start(), tokens[end_index].end()))
    if not raw_spans:
        return []
    raw_spans.sort()
    merged: List[Tuple[int, int]] = [raw_spans[0]]
    for start, end in raw_spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def is_position_negated(position: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def term_is_negated(text: str, term: str) -> bool:
    if not text or not term:
        return False
    match = re.search(re.escape(term), text, re.IGNORECASE)
    if not match:
        return False
    return is_position_negated(match.start(), detect_negation_spans(text))


# ---------------------------------------------------------------------------
# Name / concept-title heuristics
# ---------------------------------------------------------------------------

_NON_NAME_TOKENS = frozenset({
    "the", "of", "and", "a", "an", "in", "on", "for", "inc", "corp",
    "corporation", "company", "ltd", "llc", "group", "history", "invention",
    "album", "song", "film", "movie", "list", "index", "category",
    "wikipedia", "news", "home", "login", "account", "support", "download",
    "university", "institute", "labs", "laboratories", "museum", "school",
})
_NAME_PART_RE = re.compile(r"^[A-Z][a-z]{1,}$")
_NAME_INITIAL_RE = re.compile(r"^[A-Z]\.?$")
_GENERIC_CONCEPT_TITLES = frozenset({
    "invention", "inventions", "inventor", "inventors", "discovery",
    "innovation", "technology", "science", "engineering", "history",
    "company", "corporation", "business", "entrepreneur", "entrepreneurship",
    "founder", "founders", "creation", "design", "research", "development",
    "population", "statistics", "demographics", "estimation", "explanation",
    "causality", "behavior", "behaviour", "law", "laws", "legislation",
    "politics", "government",
})


def name_candidates(text: str) -> List[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    candidates = [raw]
    if "//" in raw or raw.count("/") >= 2:
        path = raw.split("?", 1)[0].split("#", 1)[0]
        segs = [s for s in path.split("/") if s]
        if segs:
            last = re.sub(r"\.(html?|php|aspx?|htm)$", "", segs[-1], flags=re.I)
            if last and last not in candidates:
                candidates.append(last)
    return candidates


def looks_like_person_name(text: str) -> bool:
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", str(text or "").replace("_", " ")).strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    parts = raw.split()
    if not 2 <= len(parts) <= 3:
        return False
    if any(p.casefold() in _NON_NAME_TOKENS for p in parts):
        return False
    if not _NAME_PART_RE.match(parts[0]) or not _NAME_PART_RE.match(parts[-1]):
        return False
    if len(parts) == 3 and not (_NAME_PART_RE.match(parts[1]) or _NAME_INITIAL_RE.match(parts[1])):
        return False
    return True


def is_bare_generic_concept_title(candidate: str) -> bool:
    if not candidate:
        return False
    c = re.sub(r"[_\-]+", " ", str(candidate)).strip()
    c = re.sub(r"\s*\([^)]*\)\s*$", "", c).strip()
    c = re.split(r"\s+[-|:]\s+", c, maxsplit=1)[0].strip().casefold()
    if not c or " " in c:
        return False
    return c in _GENERIC_CONCEPT_TITLES


def is_generic_concept_page(text: str, topic_terms: Set[str]) -> bool:
    for candidate in name_candidates(text):
        t = re.sub(r"_", " ", str(candidate or "")).strip()
        t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip().casefold()
        if not t or " " in t:
            continue
        if t not in _GENERIC_CONCEPT_TITLES:
            continue
        if t in {x.casefold() for x in (topic_terms or set())}:
            return False
        return True
    return False


# ---------------------------------------------------------------------------
# Intent-aware scoring
# ---------------------------------------------------------------------------

INTENT_BOOSTS: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: ("founder", "founders", "founded", "founding", "co-founder",
        "cofounder", "history", "origin", "origins", "company", "corporation",
        "established", "created by", "started by", "biography", "entrepreneur"),
    INTENT_INVENTOR: ("inventor", "inventors", "invented", "invention", "history",
        "developed", "discovered", "origin", "origins", "pioneer", "laboratories",
        "patent", "first", "timeline", "discovery"),
    INTENT_STATISTIC: ("population", "statistics", "stats", "estimate", "estimated",
        "census", "demographics", "number", "numbers", "count", "million",
        "billion", "thousand", "percent", "percentage", "households", "survey",
        "total", "figures"),
    INTENT_EXPLANATION: ("explanation", "explained", "cause", "causes", "mechanism",
        "science", "guide", "behavior", "process", "works", "working", "reason",
        "reasons", "because", "theory", "principle", "principles"),
    INTENT_COMPARISON: ("comparison", "compare", "compares", "compared", "versus",
        "difference", "differences", "study", "research", "analysis", "report"),
    INTENT_DEFINITION: ("definition", "defined", "means", "meaning", "refers",
        "term", "terminology", "glossary"),
    INTENT_PROCEDURE: ("steps", "step", "procedure", "instructions", "guide",
        "tutorial", "howto", "how-to", "process", "method", "install", "setup",
        "configure"),
    INTENT_EVIDENCE: ("evidence", "proof", "source", "sources", "citation",
        "cited", "reference", "study", "studies", "research", "data", "findings"),
    INTENT_VALIDATION: ("true", "false", "correct", "incorrect", "accurate",
        "myth", "fact", "verify", "verified", "confirm", "confirmed", "debunk",
        "debunked"),
    INTENT_IMPLEMENTATION: ("implement", "implementation", "code", "function",
        "class", "module", "algorithm", "sample", "example"),
    INTENT_GENERAL: (),
}
INTENT_PENALTIES: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: ("powerpoint", "excel", "outlook", "office", "download",
        "pricing", "buy", "subscription", "signin", "sign in", "login",
        "account", "support", "help", "install", "product", "products", "store",
        "app", "apps", "template", "templates", "tutorial", "album", "song",
        "film", "movie"),
    INTENT_INVENTOR: ("album", "song", "single", "band", "lyrics", "discography",
        "movie", "film", "download", "buy", "pricing", "store", "support",
        "login", "account", "shop", "datasheet", "coupon"),
    INTENT_STATISTIC: ("breed", "breeds", "adoption", "adopt", "shelter", "rescue",
        "album", "song", "movie", "film", "shop", "store", "buy", "pricing",
        "login", "account", "recipe", "toys", "names", "glossary", "dictionary",
        "definition", "meaning"),
    INTENT_EXPLANATION: ("buy", "shop", "store", "pricing", "coupon", "deal",
        "deals", "login", "account", "album", "song", "movie", "film", "glossary",
        "dictionary", "definition", "review", "reviews"),
    INTENT_COMPARISON: ("buy", "shop", "store", "pricing", "coupon", "login",
        "account", "album", "song", "movie", "film", "glossary", "dictionary",
        "definition"),
    INTENT_DEFINITION: ("buy", "shop", "pricing", "login", "account"),
    INTENT_PROCEDURE: ("history", "biography", "opinion", "review"),
    INTENT_EVIDENCE: ("rumor", "gossip", "opinion", "unverified"),
    INTENT_VALIDATION: ("tutorial", "howto", "recipe"),
    INTENT_IMPLEMENTATION: ("history", "biography"),
    INTENT_GENERAL: (),
}
DATE_BOOSTS = ("timeline", "chronology", "history", "year", "date", "dates",
               "century", "anniversary")
_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")
_WORK_QUALIFIER_RE = re.compile(
    r"\((?:album|song|single|ep|band|film|movie|tv series|television series|"
    r"novel|book|video game|game|magazine|comics|play|musical|opera|"
    r"soundtrack|mixtape)\)", re.IGNORECASE)

SIGNAL_PERSON = "<person>"
SIGNAL_YEAR = "<year>"
SIGNAL_WORK = "<work-of-art>"
SIGNAL_GENERIC = "<generic-concept>"
BOOST_WEIGHTS = {SIGNAL_PERSON: 2.0, SIGNAL_YEAR: 1.5}
PENALTY_WEIGHTS = {SIGNAL_WORK: 3.0, SIGNAL_GENERIC: 1.5}
DEFAULT_PENALTY_WEIGHT = 1.5


def boost_terms(intent: str, query: str = "") -> Tuple[str, ...]:
    terms = INTENT_BOOSTS.get(intent, ())
    if query and wants_date(query):
        merged = list(terms)
        for t in DATE_BOOSTS:
            if t not in merged:
                merged.append(t)
        return tuple(merged)
    return terms


def penalty_terms(intent: str) -> Tuple[str, ...]:
    return INTENT_PENALTIES.get(intent, ())


def _normalize_haystack(text: str) -> Tuple[str, Set[str]]:
    lowered = str(text or "").casefold()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return spaced, set(spaced.split())


def _match_vocabulary(haystack: str, tokens: Set[str], vocabulary) -> List[str]:
    hits = []
    for entry in vocabulary:
        n = re.sub(r"[^a-z0-9]+", " ", entry.casefold()).strip()
        if not n:
            continue
        if " " in n:
            if n in haystack:
                hits.append(entry)
        elif n in tokens:
            hits.append(entry)
    return hits


def score_intent(text, intent, query="", boost_weight=1.0,
                 penalty_weight=DEFAULT_PENALTY_WEIGHT, max_boosts=4,
                 topic_terms=None):
    """Return (delta, matched_boost_signals, matched_penalty_signals)."""
    haystack, tokens = _normalize_haystack(text)
    if not haystack:
        return (0.0, [], [])
    vocab_hits = _match_vocabulary(haystack, tokens, boost_terms(intent, query))
    penalties = _match_vocabulary(haystack, tokens, penalty_terms(intent))
    strong = []
    if query and wants_date(query) and _YEAR_RE.search(haystack):
        strong.append(SIGNAL_YEAR)
    if (query and intent in (INTENT_FOUNDER, INTENT_INVENTOR) and wants_person(query)
            and any(looks_like_person_name(c) for c in name_candidates(text))):
        strong.append(SIGNAL_PERSON)
    if _WORK_QUALIFIER_RE.search(str(text or "")):
        penalties = penalties + [SIGNAL_WORK]
    if topic_terms is not None and is_generic_concept_page(text, topic_terms):
        penalties = penalties + [SIGNAL_GENERIC]
    counted = vocab_hits[:max(0, max_boosts)]
    boost_total = (sum(BOOST_WEIGHTS.get(t, 1.0) for t in counted)
                   + sum(BOOST_WEIGHTS.get(t, 1.0) for t in strong))
    penalty_total = sum(PENALTY_WEIGHTS.get(t, 1.0) for t in penalties)
    delta = (boost_total * boost_weight) - (penalty_total * penalty_weight)
    return (delta, counted + strong, penalties)


__all__ = [
    "INTENT_FOUNDER", "INTENT_INVENTOR", "INTENT_STATISTIC", "INTENT_EXPLANATION",
    "INTENT_COMPARISON", "INTENT_GENERAL", "INTENT_DEFINITION", "INTENT_PROCEDURE",
    "INTENT_EVIDENCE", "INTENT_VALIDATION", "INTENT_IMPLEMENTATION",
    "ALL_INTENTS", "EXTENDED_INTENTS",
    "detect_intent", "detect_intents", "describe_intent", "wants_date",
    "wants_person", "MULTI_INTENT_CONFIDENCE_FLOOR",
    "NEGATION_WORDS", "NEGATION_SCOPE_WORDS", "detect_negation_spans",
    "is_position_negated", "term_is_negated",
    "name_candidates", "looks_like_person_name", "is_bare_generic_concept_title",
    "is_generic_concept_page", "INTENT_BOOSTS", "INTENT_PENALTIES",
    "boost_terms", "penalty_terms", "score_intent",
]


