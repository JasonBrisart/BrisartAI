"""Question-intent detection and intent-aware scoring for BrisartAI.

Why this exists
---------------
Term-overlap ranking answers "does this source mention the query words?"
It cannot answer "does this source mention them for the right reason?",
so it produced results that were topically adjacent but useless:

    who invented microsoft?           -> Invention, Microsoft PowerPoint,
                                         Outlook.com
    who invented the transistor ...?  -> Invention, Invented (album),
                                         Field-effect transistor ranked
                                         above History of the transistor

Every one of those matches a query word. "Invention" matches *invented*,
"PowerPoint" matches *microsoft*, "Invented (album)" matches *invented*
perfectly. Overlap alone cannot separate them, because the missing
signal is not vocabulary -- it is what KIND of page answers the
question. A founder question wants a company/history/people page; a
product page is the wrong genre no matter how many query words it
contains.

So a query is classified into a coarse intent, and each intent carries
two vocabularies:

  * BOOST terms   -- words whose presence suggests the right genre
                     ("founded", "co-founder", "history", "bell labs")
  * PENALTY terms -- words marking a predictably wrong genre for this
                     intent ("powerpoint", "download", "sign in",
                     "album", "breeds")

The result is deterministic, explainable, and dependency-free: scoring a
candidate returns the exact terms that fired, so
``scripts/debug_search_replay.py`` and
``scripts/debug_offline_replay.py`` can print *why* a source ranked
where it did.

Design constraints
------------------
* Pure standard library. No embeddings, no models, no network.
* Intent is a HINT, not a filter. Nothing is ever dropped for having the
  wrong intent -- scores are nudged, so a strong term-overlap match still
  wins when no genre signal is present. This keeps the failure mode
  "slightly wrong order" instead of "correct answer deleted".
* One vocabulary, two consumers. ``web/crawler.py`` scores URLs (short,
  no prose) and ``knowledge/ranker.py`` scores indexed documents (title
  plus body text). They share this module's detection and constants so
  the two paths cannot drift apart, which is exactly how the duplicated
  dictionary blocklists rotted before being consolidated.

Deliberate non-goals
--------------------
This does not attempt correct ranking in general, and it is not a
relevance framework. It removes a specific class of obviously-wrong
result. Anything subtler is left to term overlap.
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
INTENT_GENERAL = "general"

ALL_INTENTS: Tuple[str, ...] = (
    INTENT_FOUNDER,
    INTENT_INVENTOR,
    INTENT_STATISTIC,
    INTENT_EXPLANATION,
    INTENT_GENERAL,
)

# --------------------------------------------------------------------------
# Detection vocabulary
# --------------------------------------------------------------------------

# Verbs that mean "brought into existence". Shared by the founder and
# inventor intents -- the distinguishing factor is the OBJECT, not the
# verb, which is the whole reason "who invented microsoft" is a founder
# question while "who invented the transistor" is an inventor question.
_CREATION_VERBS: FrozenSet[str] = frozenset(
    {
        "invented", "invent", "invents", "invention", "created",
        "create", "creates", "founded", "found", "founds", "made",
        "make", "makes", "started", "start", "starts", "built",
        "build", "builds", "developed", "develop", "develops",
        "designed", "design", "designs", "wrote", "write", "writes",
    }
)

# Companies/organizations whose name in a creation question means the
# asker wants FOUNDERS, not an inventor of a device. Kept explicit and
# small on purpose: guessing "is this token a company?" from surface form
# is unreliable, and a wrong guess sends the query to the wrong intent.
# Unknown entities fall through to the inventor intent, whose boosts
# (history/origin/developed) are a safe default for creation questions.
#
# Projects rather than companies -- Linux, Python, Wikipedia's software --
# deliberately are NOT listed. "who created linux?" lands on inventor
# intent, which is correct in substance (Linux is a kernel, not a firm)
# and in effect: the two classes share the history/person boosts that
# decide this ranking, so both orderings are identical. Verified by
# forcing each intent over the same candidate list.
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
    }
)

# Products/works that are NOT companies even when a company name appears
# beside them. "who invented microsoft powerpoint" is a product-history
# question, closer to inventor intent than founder intent.
_PRODUCT_WORDS: FrozenSet[str] = frozenset(
    {
        "powerpoint", "excel", "word", "outlook", "office", "windows",
        "teams", "azure", "onedrive", "sharepoint", "iphone", "ipad",
        "macbook", "android", "chrome", "gmail", "photoshop",
    }
)

_STATISTIC_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "many"),
    ("how", "much"),
    ("number", "of"),
    ("count", "of"),
    ("amount", "of"),
    ("total", "of"),
    ("population", "of"),
)

_STATISTIC_WORDS: FrozenSet[str] = frozenset(
    {"population", "estimate", "estimated", "statistics", "census"}
)

_EXPLANATION_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "does"),
    ("how", "do"),
    ("how", "did"),
    ("how", "is"),
    ("how", "are"),
    ("how", "can"),
    ("what", "causes"),
    ("what", "cause"),
    ("why", "do"),
    ("why", "does"),
    ("why", "is"),
    ("why", "are"),
)

_EXPLANATION_LEAD_WORDS: FrozenSet[str] = frozenset({"why", "explain"})

# "when was X invented" asks for a date, so date vocabulary is boosted.
_WHEN_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("when", "was"),
    ("when", "did"),
    ("when", "were"),
    ("what", "year"),
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _words(text: str) -> List[str]:
    """Lowercase word tokens of a query."""
    return _WORD_RE.findall(str(text or "").casefold())


def _has_phrase(words: Sequence[str], phrase: Sequence[str]) -> bool:
    """True when ``phrase`` appears as consecutive tokens in ``words``."""
    span = len(phrase)
    if span == 0 or len(words) < span:
        return False
    target = tuple(phrase)
    for start in range(len(words) - span + 1):
        if tuple(words[start:start + span]) == target:
            return True
    return False


# --------------------------------------------------------------------------
# Per-intent scoring vocabulary
# --------------------------------------------------------------------------

# Multi-word entries are matched as substrings of the (space-normalized)
# haystack; single words are matched as whole tokens. That distinction
# matters: "bell labs" must match as a phrase, while "history" should not
# fire inside "prehistory".
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
    INTENT_GENERAL: (),
}

# Genre markers that are predictably wrong for an intent. These are
# penalties, never filters.
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
    INTENT_GENERAL: (),
}

# Extra boost vocabulary for "when was X invented".
DATE_BOOSTS: Tuple[str, ...] = (
    "timeline", "chronology", "history", "year", "date", "dates",
    "century", "anniversary",
)

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")

# Wikipedia-style disambiguation qualifiers that identify a *creative
# work* rather than a topic. "Invented (album)" is the canonical trap for
# an inventor question: it matches "invented" exactly and sits on a
# high-authority domain, so overlap scoring loves it. The qualifier is
# decisive evidence, so it is weighted far above an ordinary keyword.
_WORK_QUALIFIER_RE = re.compile(
    r"\((?:album|song|single|ep|band|film|movie|tv series|television series"
    r"|novel|book|video game|game|magazine|comics|play|musical|opera"
    r"|soundtrack|mixtape)\)",
    re.IGNORECASE,
)

# Signals that carry more weight than a plain vocabulary hit, because
# they identify the genre of a page rather than merely mentioning a word.
SIGNAL_PERSON = "<person>"
SIGNAL_YEAR = "<year>"
SIGNAL_WORK = "<work-of-art>"
SIGNAL_GENERIC = "<generic-concept>"

# Per-term weights. Anything unlisted counts 1.0.
#
# Penalties outweigh boosts on purpose. A wrong-genre marker is far more
# reliable evidence than a right-genre one: "(album)" in a title is
# conclusive, whereas "history" appearing somewhere is only suggestive.
BOOST_WEIGHTS: Dict[str, float] = {
    SIGNAL_PERSON: 2.0,
    SIGNAL_YEAR: 1.5,
}

PENALTY_WEIGHTS: Dict[str, float] = {
    SIGNAL_WORK: 3.0,
    SIGNAL_GENERIC: 1.5,
}

# Default multiplier applied to every penalty term.
DEFAULT_PENALTY_WEIGHT = 1.5

# Tokens that disqualify a title from looking like a person's name.
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

# Encyclopedia pages about a bare abstract concept. For an inventor
# question these are the classic near-miss: /wiki/Invention matches
# "invented" and even earns the "invention" boost, yet it explains the
# concept of invention in general and never names who invented the thing
# asked about. Demoted so an entity-specific page outranks them, but not
# blocked, since they are a reasonable last resort.
_GENERIC_CONCEPT_TITLES: FrozenSet[str] = frozenset(
    {
        "invention", "inventions", "inventor", "inventors",
        "discovery", "innovation", "technology", "science",
        "engineering", "history", "company", "corporation",
        "business", "entrepreneur", "entrepreneurship", "founder",
        "founders", "creation", "design", "research", "development",
        "population", "statistics", "demographics", "estimation",
        "explanation", "causality", "behavior", "behaviour",
    }
)


def is_generic_concept_page(text: str, topic_terms: Set[str]) -> bool:
    """True for an encyclopedia page about a bare concept, not the topic.

    ``/wiki/Invention`` for "who invented the transistor" is the case
    this exists for: the title is one abstract noun drawn from the
    question's verb, carrying none of the question's actual subject.

    A page is only generic when its title is a single concept word AND
    that word is not itself the subject being asked about, so a genuine
    query about invention as a topic is unaffected.
    """
    for candidate in name_candidates(text):
        title = re.sub(r"_", " ", str(candidate or "")).strip()
        title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().casefold()
        if not title or " " in title:
            continue
        if title not in _GENERIC_CONCEPT_TITLES:
            continue
        # "history of the transistor" is multi-word so never lands here;
        # a bare "/wiki/History" does, unless history IS the subject.
        # Matching is exact, not stemmed, which is what separates the two
        # readings: the question "who invented X" contributes the verb
        # "invented", never the noun "invention", so /wiki/Invention stays
        # generic there -- while a query literally about "invention
        # history" contributes "invention" and keeps the page.
        subject_terms = {
            term.casefold() for term in (topic_terms or set())
        }
        if title in subject_terms:
            return False
        return True
    return False



def looks_like_person_name(text: str) -> bool:
    """True when ``text`` looks like a personal name, e.g. "Bill Gates".

    A "who invented/founded X" question is answered in large part by
    pages about *people*, but a person's page carries no genre vocabulary
    at all: "Bill Gates" contains no boost term, and its URL shares no
    word with the query "who invented microsoft", so pure term overlap
    scores it zero and a penalized product page can edge above it.

    This is a deliberately narrow shape test -- two or three capitalized
    words, optional middle initial, no digits, no organizational or genre
    words -- and it is only consulted for the founder/inventor intents,
    where "who" is the actual question. It recognizes a name *shape*; it
    does not know who anyone is, and no list of people is embedded.

    >>> looks_like_person_name("Bill Gates")
    True
    >>> looks_like_person_name("John Bardeen")
    True
    >>> looks_like_person_name("History of Microsoft")
    False
    >>> looks_like_person_name("Microsoft")
    False
    """
    raw = str(text or "").replace("_", " ")
    # Drop a trailing parenthetical qualifier: "Walter Brattain
    # (physicist)" is still a person, but "Invented (album)" must not
    # benefit, which the token checks below already prevent.
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False

    parts = raw.split()
    if not 2 <= len(parts) <= 3:
        return False
    if any(part.casefold() in _NON_NAME_TOKENS for part in parts):
        return False

    # First and last must be proper capitalized words; a middle token may
    # additionally be an initial ("John F. Kennedy").
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
    """Fragments of ``text`` that might be a person's name.

    :func:`looks_like_person_name` needs capitalization and a short token
    run, but a candidate arrives either as a bare title ("Bill Gates") or
    as a full URL ("https://en.wikipedia.org/wiki/Bill_Gates"). In the
    URL form the scheme, host, and path prefix add tokens that push the
    name past the 2-3 word limit, so the name is never recognized.

    The last path segment is therefore offered as an extra candidate,
    which is where encyclopedia and biography URLs put the subject.
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
            # Drop a trailing file extension ("Bill_Gates.html").
            last = re.sub(r"\.(html?|php|aspx?|htm)$", "", last, flags=re.I)
            if last and last not in candidates:
                candidates.append(last)
    return candidates


def detect_intent(query: str) -> str:
    """Classify a query into one of :data:`ALL_INTENTS`.

    Order matters. Statistic and explanation intents are checked before
    the creation intents because "how many X did Y invent" is primarily a
    counting question. Founder is distinguished from inventor purely by
    whether a known company name is present.

    >>> detect_intent("who invented microsoft?")
    'founder'
    >>> detect_intent("who invented the transistor and when?")
    'inventor'
    >>> detect_intent("how many cats are in america?")
    'statistic'
    >>> detect_intent("why do cats purr?")
    'explanation'
    >>> detect_intent("transistor")
    'general'
    """
    words = _words(query)
    if not words:
        return INTENT_GENERAL
    word_set = set(words)

    if any(_has_phrase(words, phrase) for phrase in _STATISTIC_PHRASES):
        return INTENT_STATISTIC
    if word_set & _STATISTIC_WORDS:
        return INTENT_STATISTIC

    has_creation = bool(word_set & _CREATION_VERBS)

    # An explanation question ("how does a transistor work") outranks the
    # creation reading, but "who invented X" must stay a creation
    # question even though it starts with a question word.
    if not has_creation or "who" not in word_set:
        if any(
            _has_phrase(words, phrase) for phrase in _EXPLANATION_PHRASES
        ):
            return INTENT_EXPLANATION
        if words[0] in _EXPLANATION_LEAD_WORDS:
            return INTENT_EXPLANATION

    if has_creation:
        # A product name means the question is about a product's history,
        # not about who founded the company that ships it.
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
    """Return (space-normalized text, token set) for matching.

    Punctuation and URL separators collapse to spaces so that
    "history-of-microsoft" and "History of Microsoft" tokenize alike, and
    so multi-word boosts like "bell labs" match either form.
    """
    lowered = str(text or "").casefold()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return (spaced, set(spaced.split()))


def _match_vocabulary(
    haystack: str,
    tokens: Set[str],
    vocabulary: Sequence[str],
) -> List[str]:
    """Return vocabulary entries present in the haystack.

    Multi-word and hyphenated entries are matched as phrases; single
    words are matched as whole tokens so "history" does not fire inside
    "prehistory".
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
    """Score ``text`` for how well it fits ``intent``.

    Returns ``(delta, boosts_hit, penalties_hit)`` where ``delta`` is a
    signed adjustment to add to a base relevance score. Returning the
    matched terms is what makes ranking explainable in the replay
    scripts.

    Ordinary vocabulary credit is capped at ``max_boosts`` distinct terms
    so a page stuffed with genre words cannot dominate on vocabulary
    alone. The strong signals (person, year, work-of-art, generic
    concept) are weighted separately and are not subject to that cap,
    because each identifies a page's genre outright.
    """
    haystack, tokens = _normalize_haystack(text)
    if not haystack:
        return (0.0, [], [])

    vocabulary_hits = _match_vocabulary(
        haystack, tokens, boost_terms(intent, query)
    )
    penalties = _match_vocabulary(haystack, tokens, penalty_terms(intent))

    strong_boosts: List[str] = []

    # A year is concrete evidence for a "when was it invented" question.
    if query and wants_date(query) and _YEAR_RE.search(haystack):
        strong_boosts.append(SIGNAL_YEAR)

    # A person's page answers a "who" question despite carrying no genre
    # vocabulary. Only the raw text can show this, since the check needs
    # capitalization that the normalized haystack has discarded.
    if (
        query
        and intent in (INTENT_FOUNDER, INTENT_INVENTOR)
        and wants_person(query)
        and any(
            looks_like_person_name(candidate)
            for candidate in name_candidates(text)
        )
    ):
        strong_boosts.append(SIGNAL_PERSON)

    # A creative work sharing the query's wording is not an answer.
    if _WORK_QUALIFIER_RE.search(str(text or "")):
        penalties = penalties + [SIGNAL_WORK]

    # A bare concept page borrows the question's verb without its
    # subject; demote it so an entity-specific page wins.
    if topic_terms is not None and is_generic_concept_page(text, topic_terms):
        penalties = penalties + [SIGNAL_GENERIC]

    counted = vocabulary_hits[: max(0, max_boosts)]
    boost_total = sum(
        BOOST_WEIGHTS.get(term, 1.0) for term in counted
    ) + sum(BOOST_WEIGHTS.get(term, 1.0) for term in strong_boosts)
    penalty_total = sum(
        PENALTY_WEIGHTS.get(term, 1.0) for term in penalties
    )

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
    "ALL_INTENTS",
    "BOOST_WEIGHTS",
    "DATE_BOOSTS",
    "DEFAULT_PENALTY_WEIGHT",
    "INTENT_BOOSTS",
    "INTENT_EXPLANATION",
    "INTENT_FOUNDER",
    "INTENT_GENERAL",
    "INTENT_INVENTOR",
    "INTENT_PENALTIES",
    "INTENT_STATISTIC",
    "PENALTY_WEIGHTS",
    "SIGNAL_GENERIC",
    "SIGNAL_PERSON",
    "SIGNAL_WORK",
    "SIGNAL_YEAR",
    "boost_terms",
    "describe_intent",
    "detect_intent",
    "is_generic_concept_page",
    "looks_like_person_name",
    "name_candidates",
    "penalty_terms",
    "score_intent",
    "wants_date",
    "wants_person",
]
