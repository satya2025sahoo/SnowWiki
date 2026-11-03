"""
Quick self-test for safe markdown_cleanup.py
Run from anywhere:  python test_cleanup.py
No PDF or GPU required.
"""

import sys, os
sys.path.insert(0, r"D:\SnowWiki\src")
from ingestion.pdf_utils.markdown_cleanup import clean_marker_markdown

# ---------------------------------------------------------------------------
# Test case 1 – Prose with proper nouns and technical terms
# (Ensure sentences with capitalized words are NOT split into bullets)
# ---------------------------------------------------------------------------
INPUT_1 = """\
### Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.

### Discovery Ranges:

Discovery ranges define which IP addresses ServiceNow Discovery scans.
"""

EXPECTED_1_FRAGMENTS = [
    "### Class",
    "Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.",
    "### Discovery Ranges:",
    "Discovery ranges define which IP addresses ServiceNow Discovery scans.",
]

UNWANTED_1_FRAGMENTS = [
    "- Windows.",
    "- Server, Linux.",
    "- ServiceNow.",
    "- Discovery scans.",
]

# ---------------------------------------------------------------------------
# Test case 2 – Safe sub-bullet normalization
# (Ensure <sup>o</sup> and - o convert to nested bullets "  - ")
# ---------------------------------------------------------------------------
INPUT_2 = """\
#### Limiting Discovery Data:

- Improves data accuracy
<sup>o</sup> Avoids populating the CMDB with low-priority or irrelevant data.
<sup>o</sup> Establishes a strong foundation with high-quality CIs.
- Prevents CMDB data overload
- o Reduces clutter caused by unnecessary Discovery results.
- o Keeps the CMDB clean and maintainable.
"""

EXPECTED_2_FRAGMENTS = [
    "#### Limiting Discovery Data:",
    "- Improves data accuracy",
    "  - Avoids populating the CMDB with low-priority or irrelevant data.",
    "  - Establishes a strong foundation with high-quality CIs.",
    "- Prevents CMDB data overload",
    "  - Reduces clutter caused by unnecessary Discovery results.",
    "  - Keeps the CMDB clean and maintainable.",
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check(name: str, raw: str, expected_fragments: list, unwanted_fragments: list = None) -> bool:
    result = clean_marker_markdown(raw)
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(result)
    print(f"{'-'*60}")
    passed = True
    for frag in expected_fragments:
        found = frag in result
        status = "PASS" if found else "FAIL"
        print(f"  [{status}]  Expected: {frag!r}")
        if not found:
            passed = False
    if unwanted_fragments:
        for frag in unwanted_fragments:
            found = frag in result
            status = "FAIL" if found else "PASS"
            print(f"  [{status}]  Must NOT contain: {frag!r}")
            if found:
                passed = False
    return passed


if __name__ == "__main__":
    results = [
        check("Prose block preservation (No unwanted bullets)", INPUT_1, EXPECTED_1_FRAGMENTS, UNWANTED_1_FRAGMENTS),
        check("Sub-bullet normalization (<sup>o</sup> and - o)", INPUT_2, EXPECTED_2_FRAGMENTS),
    ]
    print(f"\n{'='*60}")
    total = len(results)
    passed = sum(results)
    print(f"RESULT: {passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)

