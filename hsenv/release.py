"""What a public protocol release may contain (V080-PLATFORM §1.2, §6): one list, defined here, imported by
HumanStudy-Bench (scripts/research/protocols.py) and mirrored by the desktop fork allowlist.

`*` stays inside one path segment; `dir/**` is everything below dir. NEVER wins over PUBLIC_PATHS."""
import fnmatch

PUBLIC_PATHS = (
    "study.json", "protocol.json", "effects.json", "program.json", "capabilities.json",
    "review/fidelity-review-*.md", "review/checks-latest.json",
    "sources/SOURCE.json", "sources/open/**", "sourcetext/*", "variants/*.json", "artifacts/**", "package/**",
)

# never public, whatever PUBLIC_PATHS says
NEVER = ("sources/researcher/**", "sources/private/**", "sources/quarantine/**", "runs/**", "paper/**",
         "bundle.json", "**/runs/**", "**/records.jsonl")


def match(name, pattern):
    """`*` inside one segment; `dir/**` = anything below dir; `**/x` = x at any depth."""
    if pattern.startswith("**/"):
        parts = name.split("/")
        return any(match("/".join(parts[i:]), pattern[3:]) for i in range(len(parts)))
    if pattern.endswith("/**"):
        return name.startswith(pattern[:-2])
    a, b = name.split("/"), pattern.split("/")
    return len(a) == len(b) and all(fnmatch.fnmatchcase(x, y) for x, y in zip(a, b))


def is_public(name):
    """True when a path (relative, '/'-separated) may be published in a release."""
    if not name or name.startswith("/") or ".." in name.split("/"):
        return False
    return not any(match(name, p) for p in NEVER) and any(match(name, p) for p in PUBLIC_PATHS)
