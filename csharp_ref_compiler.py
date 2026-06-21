#!/usr/bin/env python3
import os
import re
import argparse
import textwrap
from pathlib import Path

def parse_toc(toc_path):
    """YAMLファイルを簡易パースし、hrefで指定された.mdファイルの相対パスを順に抽出する"""
    if not os.path.exists(toc_path):
        print(f"警告: 目次ファイルが見つかりません: {toc_path}")
        return []
        
    md_files = []
    # href: の後に続く非空白文字を抽出
    href_pat = re.compile(r'href:\s*(\S+)')
    
    try:
        with open(toc_path, "r", encoding="utf-8") as f:
            for line in f:
                m = href_pat.search(line)
                if m:
                    path_str = m.group(1).strip()
                    # クォーテーションの除去
                    path_str = path_str.strip("'\"")
                    # .md ファイルのみを対象とする
                    if path_str.endswith(".md"):
                        # パスの正規化 (例: ./builtin-types/built-in-types.md -> builtin-types/built-in-types.md)
                        normalized = os.path.normpath(path_str)
                        if normalized.startswith("./") or normalized.startswith(".\\"):
                            normalized = normalized[2:]
                        if normalized not in md_files:
                            md_files.append(normalized)
    except Exception as e:
        print(f"エラー: 目次ファイル {toc_path} の読み込みに失敗しました: {e}")
        
    return md_files

def resolve_snippet(md_path, source_rel_path, snippet_id=None):
    """Markdownから参照されている.csファイルから、指定されたスニペットコードを抽出する"""
    cs_path = (Path(md_path).parent / source_rel_path).resolve()
    if not cs_path.exists():
        print(f"警告: スニペットファイルが見つかりません: {cs_path}")
        return f"<!-- 警告: スニペットファイルが見つかりませんでした: {source_rel_path} -->"
        
    try:
        with open(cs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"エラー: スニペットファイル {cs_path} の読み込みに失敗しました: {e}")
        return f"<!-- エラー: スニペットファイル {source_rel_path} の読み込み失敗 -->"

    if not snippet_id:
        return "".join(lines)

    # 指定された snippet_id に対応するコメントタグ // <id> から // </id> までを抽出
    start_pat = re.compile(rf"^\s*//\s*<\s*{re.escape(snippet_id)}\s*>\s*$")
    end_pat = re.compile(rf"^\s*//\s*</\s*{re.escape(snippet_id)}\s*>\s*$")
    
    extracted_lines = []
    in_snippet = False
    for line in lines:
        if start_pat.match(line):
            in_snippet = True
            continue
        elif end_pat.match(line):
            in_snippet = False
            continue
        
        if in_snippet:
            extracted_lines.append(line)
            
    if not extracted_lines:
        print(f"警告: スニペット ID '{snippet_id}' がファイル {cs_path} 内で見つかりませんでした。")
        return f"<!-- 警告: スニペット ID '{snippet_id}' が見つかりませんでした。 -->"
        
    # インデントを揃えて返す
    code = "".join(extracted_lines)
    return textwrap.dedent(code)

def expand_markdown(md_path):
    """Markdownファイル内の :::code ... ::: を、対応するC#コードブロックに展開する"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"エラー: Markdownファイル {md_path} の読み込みに失敗しました: {e}")
        return ""

    # :::code language="csharp" source="..." id="..." ::: などのパターンにマッチ
    code_block_pat = re.compile(r":::code\s+(.*?)\s*:::")
    
    def repl(match):
        attrs = match.group(1)
        source_m = re.search(r'source="([^"]+)"', attrs)
        if not source_m:
            return match.group(0) # source属性がない場合はそのまま
            
        source = source_m.group(1)
        id_m = re.search(r'id="([^"]+)"', attrs)
        snippet_id = id_m.group(1) if id_m else None
        
        # コードの解決
        code = resolve_snippet(md_path, source, snippet_id)
        
        # Markdownのコードブロック形式にする
        return f"\n```csharp\n{code.rstrip()}\n```\n"

    new_content = code_block_pat.sub(repl, content)
    return new_content

def save_output(output_path, index, content_list):
    """結合されたコンテンツをファイルに保存する"""
    output_file = output_path / f"output_{index}.md"
    total_chars = sum(len(c) for c in content_list)
    print(f"保存中: {output_file} (文字数: {total_chars})")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(content_list))

def compile_reference(input_dir, output_dir, max_chars=490000, max_files=25):
    """C#言語リファレンスを結合し、NotebookLM向けにコンパイルする"""
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. toc.yml から順序付きリストの取得
    toc_path = input_path / "toc.yml"
    toc_files_rel = parse_toc(toc_path)
    
    target_files = []
    processed_set = set()
    
    for rel_path in toc_files_rel:
        full_path = (input_path / rel_path).resolve()
        if full_path.exists() and full_path.is_file():
            target_files.append((rel_path, full_path))
            processed_set.add(str(full_path))
        else:
            print(f"警告: 目次に記載されているファイルが存在しません: {full_path}")
            
    # 2. 目次にないファイルの検出 (includes 配下は除外)
    all_md_files = sorted(list(input_path.rglob("*.md")))
    fallback_files = []
    for md_file in all_md_files:
        md_file_resolved = md_file.resolve()
        if str(md_file_resolved) in processed_set:
            continue
        if "includes" in md_file_resolved.parts:
            continue
            
        try:
            rel_path = md_file_resolved.relative_to(input_path)
            fallback_files.append((str(rel_path), md_file_resolved))
        except ValueError:
            pass
            
    if fallback_files:
        print(f"情報: 目次（toc.yml）に含まれていないMarkdownファイルを {len(fallback_files)} 件検出しました。これらは末尾に結合されます。")
        fallback_files.sort(key=lambda x: x[0])
        target_files.extend(fallback_files)
        
    print(f"合計 {len(target_files)} 件のファイルを処理します...")
    
    current_file_index = 1
    current_char_count = 0
    current_content = []
    
    for rel_path_str, md_path in target_files:
        expanded_text = expand_markdown(md_path)
        
        # 各ファイルの先頭にソース識別ヘッダーを挿入
        header = f"\n\n--- SOURCE: {rel_path_str} ---\n\n"
        file_total_content = header + expanded_text
        file_char_count = len(file_total_content)
        
        if current_char_count + file_char_count > max_chars:
            if current_content:
                save_output(output_path, current_file_index, current_content)
                current_file_index += 1
                
                if current_file_index > max_files:
                    print(f"警告: 最大出力ファイル数 ({max_files}) に達したため、処理を中断します。")
                    return
                
                current_content = []
                current_char_count = 0
                
        current_content.append(file_total_content)
        current_char_count += file_char_count
        
    # 残りのコンテンツを出力
    if current_content and current_file_index <= max_files:
        save_output(output_path, current_file_index, current_content)
        
    print("コンパイルが正常に完了しました。")

def main():
    parser = argparse.ArgumentParser(description="C#公式言語リファレンスをNotebookLM向けに結合・展開コンパイルします。")
    parser.add_argument("input_dir", help="入力元の言語リファレンスディレクトリパス")
    parser.add_argument("output_dir", help="出力先のディレクトリパス")
    parser.add_argument("--max_chars", type=int, default=490000, help="1ファイルあたりの最大文字数 (デフォルト: 490,000)")
    parser.add_argument("--max_files", type=int, default=25, help="最大出力ファイル数 (デフォルト: 25)")
    
    args = parser.parse_args()
    compile_reference(args.input_dir, args.output_dir, args.max_chars, args.max_files)

if __name__ == "__main__":
    main()
