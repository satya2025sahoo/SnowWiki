"""
Quick self-test for markdown_cleanup.py.
Run from anywhere:  python test_cleanup.py
No PDF or GPU required.
"""

import sys, os
sys.path.insert(0, r"D:\SnowWiki\src")
from ingestion.pdf_utils.markdown_cleanup import clean_marker_markdown

# ---------------------------------------------------------------------------
# Test case 1 – Asset vs CI section (punctuation-free boundary merge)
# ---------------------------------------------------------------------------
INPUT_1 = """\
## Asset:

 Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time Is part of the financial lifecycle

# Configuration Item (CI):

 Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process Is part of the technical operations
"""

EXPECTED_1_FRAGMENTS = [
    "- Often starts during the procurement process",
    "- Is part of the financial lifecycle",
    "- Often starts when a discovery tool finds the CI for the first time",
    "- Is part of the technical operations",
]

# ---------------------------------------------------------------------------
# Test case 2 – Key Concepts section (<sup>o</sup> + merged bullets)
# ---------------------------------------------------------------------------
INPUT_2 = """\
### Key Concepts:

 Application Service: Logical representation of a deployed system, application, or product stack. <sup>o</sup> Operational CI used in ITSM/ITOM practices. <sup>o</sup> Can be environment-specific (Dev, Test, QA, Prod) or region-specific (AMS, EMEA, APJ). <sup>o</sup> Stored in cmdb_ci_service_auto or sub-classes. Service Map: Shows which CIs support a service, including applications, servers, middleware, and networks. <sup>o</sup> Helps identify service impact when components fail.
"""

EXPECTED_2_FRAGMENTS = [
    "  - Operational CI used in ITSM/ITOM practices",
    "  - Can be environment-specific",
    "  - Stored in cmdb_ci_service_auto",
    "  - Helps identify service impact",
]

# ---------------------------------------------------------------------------
# Test case 3 – Top-Down Mapping nested sub-points
# ---------------------------------------------------------------------------
INPUT_3 = """\
## 1. Top-Down Mapping

 Pattern-Based: <sup>o</sup> Best for: Mission-critical apps. <sup>o</sup> Level: Surgical/Process-to-process. <sup>o</sup> Key: Most Granular. ML Connection Suggestions: <sup>o</sup> Best for: Homegrown & custom COTS. <sup>o</sup> Level: Traffic-based/Fingerprinting. <sup>o</sup> Key: Fastest Time-to-Value. Note: These two can be used together or individually.
"""

EXPECTED_3_FRAGMENTS = [
    "  - Best for: Mission-critical apps",
    "  - Level: Surgical/Process-to-process",
    "  - Key: Most Granular",
    "  - Best for: Homogrown" ,  # partial OK
    "  - Key: Fastest Time-to-Value",
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check(name: str, raw: str, expected_fragments: list[str]) -> bool:
    result = clean_marker_markdown(raw)
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(result)
    print(f"{'-'*60}")
    passed = True
    for frag in expected_fragments:
        found = frag.lower() in result.lower()
        status = "✅" if found else "❌"
        print(f"  {status}  Expected fragment: {frag!r}")
        if not found:
            passed = False
    return passed


if __name__ == "__main__":
    results = [
        check("Asset vs CI — no-punctuation boundary merge", INPUT_1, EXPECTED_1_FRAGMENTS),
        check("Key Concepts — <sup>o</sup> + merged bullets",  INPUT_2, EXPECTED_2_FRAGMENTS),
        check("Top-Down Mapping — nested sub-points",          INPUT_3, EXPECTED_3_FRAGMENTS),
    ]
    print(f"\n{'='*60}")
    total  = len(results)
    passed = sum(results)
    print(f"RESULT: {passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)
