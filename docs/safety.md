# BrisartAI Safety and Policy

## Local Data

BrisartAI does not upload local files. It reads and indexes local files into SQLite.

## Internet Mode

Internet mode is optional. It should be disabled in air-gapped deployments.

Rules:

- Respect `robots.txt` where available
- Do not bypass login pages
- Do not bypass paywalls
- Do not aggressively crawl websites
- Prefer user-approved URLs and search terms

## Answering

BrisartAI should cite sources and say when the index does not contain enough evidence.
