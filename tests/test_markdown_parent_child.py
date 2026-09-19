import pytest
from src.ingestion.chunking import parse_timestamp_seconds, process_markdown_for_parent_child

def test_parse_timestamp_seconds():
    # Test valid timestamps
    assert parse_timestamp_seconds("[05:30] My Topic") == ("05:30", 330, "My Topic")
    assert parse_timestamp_seconds("[1:05:30] Long Topic") == ("1:05:30", 3930, "Long Topic")
    
    # Test no timestamp
    assert parse_timestamp_seconds("General Overview") == ("N/A", 0, "General Overview")

def test_process_markdown_for_parent_child():
    md_content = """
## [01:20] First Topic
This is the first topic.
It has some lines.

### Subtopic 1
This is a child chunk for the first topic. It should be long enough to not be filtered out. Let's make it a bit longer.

## [02:30] Second Topic
This is the second topic. It has enough content to be considered a child chunk too. Let's make it longer than 30 characters.
"""
    parent_dict, child_chunks = process_markdown_for_parent_child(md_content, "dummy.md", "main")
    
    # Check parent_dict
    assert len(parent_dict) == 2
    titles = [p["topic_title"] for p in parent_dict.values()]
    assert "First Topic" in titles
    assert "Second Topic" in titles
    
    # Check timestamps
    first_parent = [p for p in parent_dict.values() if p["topic_title"] == "First Topic"][0]
    second_parent = [p for p in parent_dict.values() if p["topic_title"] == "Second Topic"][0]
    
    # Check children
    assert len(child_chunks) >= 2
    
    first_topic_children = [c for c in child_chunks if c["metadata"]["section_heading"] == "First Topic"]
    assert len(first_topic_children) >= 1
    assert first_topic_children[0]["metadata"]["timestamp"] == "01:20"
    assert first_topic_children[0]["metadata"]["timestamp_seconds"] == 80

def test_edge_case_no_headers():
    md_content = "This is just a regular paragraph with no headers. It should still be chunked properly without crashing, and it's long enough to pass."
    parent_dict, child_chunks = process_markdown_for_parent_child(md_content, "test.md", "main")
    assert len(parent_dict) == 1
    p_id = list(parent_dict.keys())[0]
    assert parent_dict[p_id]["topic_title"] == "General Overview"
    assert len(child_chunks) >= 1

def test_short_chunk_filtering():
    md_content = "## Topic\n\nShort\n\n### Child\nThis child chunk is long enough to be included in the final output."
    _, child_chunks = process_markdown_for_parent_child(md_content, "test.md", "main")
    
    # "Short" should be filtered out
    texts = [c["chunk_text"] for c in child_chunks]
    assert "Short" not in texts
    assert any("This child chunk is long enough" in t for t in texts)
