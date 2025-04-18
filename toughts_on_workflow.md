## Tolerant vs. fail-fast code

Models tend to choose tolerant, defensive, forgiving coding style, which is not always right. You need to explain when to go tolerant vs. fail-fast code.

### Tolerant / Defensive / Forgiving**
This approach **tries to make sense of imperfect inputs**, avoid crashing, and preserve uptime and flow even if the data is messy or malformed.

**Traits:**
- Tolerates malformed or unexpected data
- Tries alternate paths or fallbacks
- Warns in logs but doesn’t raise exceptions unless it must
- Aims for resilience over strict correctness

**Pros:**
- Keeps systems running even when upstream components misbehave
- Reduces impact of flaky external systems or data feeds
- Can be better for user-facing systems where downtime is expensive

**Cons:**
- Might silently accept bad data
- Logs can become noisy and harder to act on
- Bugs or data issues might go undetected until much later
- Code paths can become harder to reason about due to hidden assumptions

**Possible labels:**
- *Defensive programming*
- *Forgiving mode*
- *Resilient parser*
- *Fail-soft*

---

### Assertive / Strict / Fail-fast**
This approach **expects well-formed input** and fails loudly and early when things don’t meet expectations.

**Traits:**
- Validates assumptions immediately
- Crashes or throws on unexpected input
- Prefers correctness and traceability over resilience
- Shorter, more explicit code paths

**Pros:**
- Bugs are caught closer to the root cause
- Data integrity is better preserved
- Simpler logic; fewer fallback paths to test
- Encourages upstream systems to be better-behaved

**Cons:**
- Can cause cascading failures if not handled carefully
- Might bring down systems over recoverable edge cases
- Often unsuitable for real-time systems where uptime is critical

**Possible labels:**
- *Fail-fast*
- *Strict mode*
- *Input contract enforcement*
- *Zero-tolerance parser*

---
