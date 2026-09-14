# Security Policy

BrisartAI is a local-first research assistant. It indexes local files and, optionally, crawls the public web into a local SQLite database. It stores no credentials, uploads no local files, and runs no server. If you find a security issue anywhere in this repository, please report it **privately** rather than opening a public issue.

---

## Reporting a vulnerability

**Do not open a public issue for a security report.** Public issues are indexed and searchable immediately, giving an attacker a head start before a fix ships.

Instead:

1. **Preferred — GitHub Private Vulnerability Reporting.** Use this repository's **Security** tab → **Report a vulnerability**. This opens a private advisory thread visible only to the maintainer and you.
2. **Fallback — direct contact.** If private reporting is unavailable, contact the maintainer, **Jason Brisart**, through a private channel (for example, a direct message via the maintainer's listed GitHub profile contact) rather than a public one.

Please include, where possible:

- Which component is affected (`web/`, `io/`, `knowledge/`, `native/`, `ui/`, or the shared `util` / `intent` / `blocklist` layer).
- Steps to reproduce, or a minimal proof of concept.
- The impact you believe it has (e.g. local-file disclosure, SSRF via the crawler, code execution during file parsing, denial of service, a decompression-bomb-style resource exhaustion).

---

## Response expectations

This is a solo-maintained research project, not a company with a security team on call. On a best-effort basis:

- **Acknowledgement** of a private report: within a few days.
- **Initial assessment** (confirmed / not applicable / needs more information): within roughly two weeks.
- **Fix or mitigation timeline** once a report is confirmed, communicated in the private advisory thread.

There is no bug-bounty program at this time.

---

## Coordinated disclosure

Please allow a reasonable window to investigate and ship a fix before any public disclosure. Once a fix is released, the advisory can be made public and credit given to the reporter (by name, handle, or anonymously) unless you request otherwise.

---

## Scope

**In scope:**

- **`web/`** — the crawler, fetcher, search providers, and `policy.py`. Server-Side Request Forgery (SSRF), private-address access, and robots/redirect handling are the highest-value area here.
- **`io/`** — file and HTML/PDF/Office parsing. A crafted file that causes code execution, resource exhaustion, or path traversal during ingestion is in scope.
- **`knowledge/`** — the SQLite schema and query construction (e.g. any injection path into the index).
- **`native/`** — the from-spec stdlib-equivalent primitives (hashing, URL parsing, JSON, HTML tokenizing, DEFLATE decompression, robots.txt interpretation). A crafted input that makes one of these disagree with the stdlib function it replaces in a security-relevant way — e.g. a URL that `brisart_url` parses differently than `urllib.parse` in a way that could bypass `web/policy.py`'s private-host check — is of particular interest, since these modules sit at a trust boundary between untrusted external bytes and the rest of the application.
- **`ui/`** and the entry point — path handling and how untrusted input reaches the layers above.

**Out of scope, but still worth reporting if you find something:** reachability of a genuinely public page that a user explicitly asked to research.

---

## Standing caveats

- **The crawler talks to the public internet when enabled.** `web/policy.py` refuses local / private / loopback / link-local destinations before any fetch, and honors a successfully-parsed `robots.txt`. By design, an unreachable or malformed `robots.txt` is treated as "allowed," not "denied" — a retrieval failure must never be readable as a site-wide block. This is a deliberate availability trade-off, not an oversight.
- **File parsing is best-effort and runs on attacker-influenceable bytes.** Every reader in `io/binary_readers.py` returns empty text on failure rather than raising, but parsing untrusted input is inherently a risk surface. `native/brisart_inflate.py`'s DEFLATE decompressor is a from-scratch implementation operating on untrusted bytes (PDF content streams today) — it is verified byte-for-byte against `zlib.decompress()` on a range of inputs including pure random data, but has **not** been specifically fuzzed for decompression-bomb-style resource exhaustion the way a mature, widely-deployed zlib implementation has.
- **The native stack replaces stdlib primitives, not stdlib guarantees.** Each module under `native/` is verified for behavioral equivalence with the stdlib function it replaces (see [`native/README.md`](../brisart_ai/native/README.md)), not independently security-audited beyond that. Treat any disagreement between a native module and its stdlib equivalent as a bug to report.
- **No sandbox.** BrisartAI runs with the privileges of the user who launched it and reads whatever local files that user points it at.

---

## Air-gapped use

Internet research is optional and can be disabled entirely (`auto_web_research = false`, and never invoking "Research Web"). In that configuration BrisartAI makes **no outbound network requests** and operates purely over local files and notes.
