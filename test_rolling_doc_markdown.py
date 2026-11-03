import os
import argparse
from src.ingestion.rolling_doc_markdown import process_pdf_rolling_markdown, process_docx_rolling_markdown
from src.ingestion.chunking import process_markdown_for_parent_child

def test_chunking(md_path: str):
    print(f"\n--- Running Parent-Child Chunking on {md_path} ---")
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            
        parent_dict, all_children = process_markdown_for_parent_child(
            md_content=md_text, 
            source_file=os.path.basename(md_path), 
            branch_name="test_branch", 
            doc_type="document_markdown"
        )
        
        print(f"Found {len(parent_dict)} Parent Sections and {len(all_children)} Child Chunks.")
        print("\nParent Sections Detected:")
        for idx, (p_id, p_section) in enumerate(list(parent_dict.items())[:10]):
            children_count = sum(1 for c in all_children if c.get("parent_id") == p_id)
            topic = p_section.get("topic_title", "Unknown Topic")
            print(f"  {idx+1}. {topic} (Children: {children_count})")
            
        if len(parent_dict) > 10:
            print(f"  ... and {len(parent_dict) - 10} more.")
            
    except Exception as e:
        print(f"Error testing chunking: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Rolling LLM Markdown Restructuring")
    parser.add_argument("--file", type=str, default="CIS-DF.docx", help="Path to PDF or DOCX file to test")
    parser.add_argument("--pages", type=int, default=None, help="Max pages/blocks to process (for quick testing)")
    args = parser.parse_args()
    
    file_path = args.file
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        exit(1)
        
    ext = os.path.splitext(file_path)[1].lower()
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_md = f"output_{base_name}_rolling.md"
    
    if ext == ".pdf":
        print(f"Starting PDF Rolling Markdown for {file_path}...")
        process_pdf_rolling_markdown(file_path, output_md, max_pages=args.pages)
        print(f"Finished. Saved to {output_md}")
        test_chunking(output_md)
        
    elif ext == ".docx":
        print(f"Starting DOCX Rolling Markdown for {file_path}...")
        process_docx_rolling_markdown(file_path, output_md, max_blocks=args.pages)
        print(f"Finished. Saved to {output_md}")
        test_chunking(output_md)
        
    else:
        print(f"Unsupported extension: {ext}. Please provide a .pdf or .docx file.")
