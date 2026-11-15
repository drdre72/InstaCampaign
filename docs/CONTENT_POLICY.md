# Content policy

This pipeline produces disclosed, synthetic, SFW persona content for
Instagram. The constraints below are enforced in code where possible and
are not negotiable options — they are what keeps accounts and payouts alive.

## Hard rules

- **SFW ceiling.** `content.rating` is capped at `sfw`/`pg13`. No nudity or
  explicit generation or posting — Meta removes AI-generated nudity
  entirely, and it would kill the funnel account anyway. The `sfw` QC gate
  fails closed when the classifier is absent.
- **Always disclosed.** Every persona spec requires a `disclosure` field
  stating it is AI/virtual/generated. The IG bio states it; Meta's "AI
  info" label is applied to realistic generated media where required.
  The highest-earning AI personas (e.g. Aitana López) are openly labeled —
  disclosure does not hurt conversion, and undisclosed accounts get payout
  holds and bans.
- **Synthetic faces only.** Never imitate or generate a real, identifiable
  person — no deepfake tooling, ever. Face consistency binds only the
  persona's own generated reference sheet. A persona spec that asks for a
  real person's likeness is rejected at design review, not by the
  validator.
- **No deceptive monetization tooling.** No automated DM/chat systems that
  pretend the persona is a real person to extract money — that's fraud and
  platform-banned. Paid conversion happens on platforms that permit
  disclosed AI (see MONETIZATION.md), not via deception.

## Enforced vs. attested

| Rule | Enforcement |
| --- | --- |
| rating cap, banned terms, disclosure present | `persona validate`, `plan validate` — fail closed |
| SFW output | `qc sfw` classifier; needs_manual => operator `--attested` |
| identity consistency | `qc face` embedding similarity; needs_manual => attested |
| profile-level disclosure | operator attestation at persona creation |

## Why the strictness

The earning pattern (tubes/IG as top-of-funnel → 80% fan platform) only
works with accounts that survive. Verified-account requirements, AI
labeling rules, and payment-processor rules underneath them are the
platform reality — the compliance ledger is inherited from the sibling
projects because this industry demands more of it, not less.
