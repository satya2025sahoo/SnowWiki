from src.ingestion.chunking import process_markdown_for_parent_child

md = """
## Topic 1: GlideAjax Example

This section explains how to use GlideAjax.

### 1. Client Script

```javascript
function onLoad() {
    var ga = new GlideAjax('CatalogDataEvaluator');
    ga.addParam('sysparm_name', 'getAvailableDevices');
    ga.getXML(callbackFn);
}
function callbackFn(response) {
    var answer = response.responseXML.documentElement.getAttribute('answer');
    g_form.setValue('device', answer);
}
```

## Topic 2: User Criteria

Use User Criteria to control catalog item visibility.
"""

parents, children = process_markdown_for_parent_child(md, "test.md", "main")
print(f"Parents: {len(parents)}")
print(f"Children: {len(children)}")
for c in children:
    print(f"  Child [{c['topic_title']}]: starts with: {repr(c['chunk_text'][:80])}")
