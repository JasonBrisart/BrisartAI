# brisart_ai/native/ — The Brisart Native Stack

Pure-Python, from-spec reimplementations of the standard-library building blocks BrisartAI relies on — so the project's philosophy ("no external dependencies, fully inspectable, custom where it earns you something") extends past `brisart_ai/` itself and into the primitives it's built on.

Every module below is **independently verified against the real stdlib function it replaces** — decision-for-decision, byte-for-byte — not merely internally self-consistent, and every module is **wired into its real call sites** across the rest of the application.


