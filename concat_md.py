#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

def get_all_md_files(input_dir):
    """ディレクトリ内のすべての.mdファイルを再帰的に取得し、ソートして返す"""
    input_path = Path(input_dir)
    md_files = sorted(list(input_path.rglob("*.md")))
    return md_files

def concat_md_files(md_files, output_dir, max_chars=490000, max_files=25):
    """ファイルを読み込み、制限に従って結合して出力する"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    current_file_index = 1
    current_char_count = 0
    current_content = []

    for md_file in md_files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"警告: ファイル '{md_file}' の読み込み中にエラーが発生しました: {e}")
            continue

        # ヘッダーの作成
        header = f"\n\n--- SOURCE: {md_file} ---\n\n"
        file_total_content = header + content
        file_char_count = len(file_total_content)

        # 1ファイルの制限を超える場合、または新しいファイルを開始する必要がある場合
        if current_char_count + file_char_count > max_chars:
            if current_content:
                # 現在の内容を書き出し
                save_output(output_path, current_file_index, current_content)
                current_file_index += 1
                
                # 25ファイル制限のチェック
                if current_file_index > max_files:
                    print(f"通知: 最大ファイル数（{max_files}）に達したため、残りのファイルは処理されません。")
                    return

                # リセット
                current_content = []
                current_char_count = 0

        # コンテンツを追加
        current_content.append(file_total_content)
        current_char_count += file_char_count

    # 最後に残ったコンテンツを書き出し
    if current_content and current_file_index <= max_files:
        save_output(output_path, current_file_index, current_content)

def save_output(output_path, index, content_list):
    """結合されたコンテンツをファイルに保存する"""
    output_file = output_path / f"output_{index}.md"
    print(f"保存中: {output_file} (文字数: {sum(len(c) for c in content_list)})")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(content_list))

def main():
    parser = argparse.ArgumentParser(description="NotebookLM向けにMarkdownファイルを結合します。")
    parser.add_argument("input_dir", help="入力元のディレクトリパス")
    parser.add_argument("output_dir", help="出力先のディレクトリパス")
    parser.add_argument("--max_chars", type=int, default=490000, help="1ファイルあたりの最大文字数 (デフォルト: 490,000)")
    parser.add_argument("--max_files", type=int, default=25, help="最大出力ファイル数 (デフォルト: 25)")

    args = parser.parse_args()

    md_files = get_all_md_files(args.input_dir)
    if not md_files:
        print("指定されたディレクトリに .md ファイルが見つかりませんでした。")
        return

    print(f"合計 {len(md_files)} 個のファイルが見つかりました。処理を開始します...")
    concat_md_files(md_files, args.output_dir, args.max_chars, args.max_files)
    print("完了しました。")

if __name__ == "__main__":
    main()
