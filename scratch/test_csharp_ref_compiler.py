import os
import pytest
from pathlib import Path
from csharp_ref_compiler import parse_toc, resolve_snippet, expand_markdown, compile_reference

def test_parse_toc(tmp_path):
    toc_content = """
items:
- name: Overview
  href: ./overview.md
- name: Keywords
  items:
  - name: abstract
    href: ./keywords/abstract.md
  - name: config
    href: ./config.yml
"""
    toc_path = tmp_path / "toc.yml"
    toc_path.write_text(toc_content, encoding="utf-8")
    
    result = parse_toc(str(toc_path))
    assert result == ["overview.md", os.path.normpath("keywords/abstract.md")]

def test_resolve_snippet(tmp_path):
    cs_content = """
using System;
namespace Test
{
    class Program
    {
        // <MySnippet>
        static void Hello()
        {
            Console.WriteLine("Hello");
        }
        // </MySnippet>
        
        // <AnotherSnippet>
        static int Add(int a, int b) => a + b;
        // </AnotherSnippet>
    }
}
"""
    cs_dir = tmp_path / "snippets"
    cs_dir.mkdir()
    cs_path = cs_dir / "test.cs"
    cs_path.write_text(cs_content, encoding="utf-8")
    
    md_path = tmp_path / "test.md"
    md_path.write_text("dummy", encoding="utf-8")
    
    # ID指定ありでスニペットを解決
    snippet = resolve_snippet(str(md_path), "snippets/test.cs", "MySnippet")
    assert "Console.WriteLine" in snippet
    assert "Hello()" in snippet
    assert "using System;" not in snippet
    assert "Add(int a" not in snippet
    
    # ID指定なしで全体を解決
    full_snippet = resolve_snippet(str(md_path), "snippets/test.cs")
    assert "using System;" in full_snippet
    
    # 不正なID
    missing_snippet = resolve_snippet(str(md_path), "snippets/test.cs", "Missing")
    assert "警告" in missing_snippet or "見つかりませんでした" in missing_snippet

def test_expand_markdown(tmp_path):
    cs_content = """
// <Snippet>
Console.WriteLine("Snippet Content");
// </Snippet>
"""
    cs_dir = tmp_path / "snippets"
    cs_dir.mkdir()
    cs_path = cs_dir / "test.cs"
    cs_path.write_text(cs_content, encoding="utf-8")
    
    md_content = """
# Header
This is a test.
:::code language="csharp" source="snippets/test.cs" id="Snippet":::
Footer
"""
    md_path = tmp_path / "test.md"
    md_path.write_text(md_content, encoding="utf-8")
    
    result = expand_markdown(str(md_path))
    assert "# Header" in result
    assert "```csharp" in result
    assert 'Console.WriteLine("Snippet Content");' in result
    assert "Footer" in result
    assert ":::code" not in result

def test_compile_reference(tmp_path):
    # テスト環境の構築
    # toc.yml
    toc_content = """
items:
- href: ./file1.md
- href: ./file2.md
"""
    (tmp_path / "toc.yml").write_text(toc_content, encoding="utf-8")
    
    # file1.md
    (tmp_path / "file1.md").write_text("Content of File 1", encoding="utf-8")
    # file2.md
    (tmp_path / "file2.md").write_text("Content of File 2", encoding="utf-8")
    # file3.md (目次にないファイル)
    (tmp_path / "file3.md").write_text("Content of File 3", encoding="utf-8")
    # includes/file4.md (インクルードされる部品ファイル、コンパイルから除外されるべき)
    includes_dir = tmp_path / "includes"
    includes_dir.mkdir()
    (includes_dir / "file4.md").write_text("Content of File 4", encoding="utf-8")
    
    output_dir = tmp_path / "output"
    
    compile_reference(str(tmp_path), str(output_dir), max_chars=100, max_files=5)
    
    # 成果物の確認
    outputs = sorted(list(output_dir.glob("output_*.md")))
    assert len(outputs) >= 1
    
    combined_content = ""
    for out in outputs:
        combined_content += out.read_text(encoding="utf-8")
        
    assert "Content of File 1" in combined_content
    assert "Content of File 2" in combined_content
    assert "Content of File 3" in combined_content
    # includes配下のファイルは除外されていること
    assert "Content of File 4" not in combined_content
