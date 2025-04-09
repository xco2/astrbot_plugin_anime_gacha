import re


def split_text(long_text: str, max_len: int, overlap_len: int):
    # 按标题分割
    def split_by_headers(text):
        parts = re.split(r'(?=\n#+ )', text)
        return [p for p in parts if p.strip()]

    # 按句子分割
    def split_by_sentences(text):
        sentences = re.split(r'(?<=[。！？；\n])\s*', text)
        return [s for s in sentences if s.strip()]

    # 硬截断
    def hard_split(text: str):
        chunks = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = min(start + max_len, text_length)
            chunks.append(text[start:end])
            start = end - overlap_len
            if start < 0:
                break
            if start >= text_length:
                break
        return chunks

    # 合并过小的块
    def merged_short_chunks(chunks: list[str]):
        merged = []
        for chunk in chunks:
            if merged and len(merged[-1]) + len(chunk) <= max_len:
                merged[-1] += chunk
            else:
                merged.append(chunk)
        return merged

    assert max_len > overlap_len, 'max_len must be greater than overlap_len'

    # 处理空文本
    if not long_text.strip():
        return []

    # 按标题分割
    header_chunks = split_by_headers(long_text)
    if len(header_chunks) > 1:
        result = []
        for chunk in header_chunks:
            result.extend(split_text(chunk, max_len, overlap_len))

        # 合并过小的块
        return merged_short_chunks(result)

    # 按句子分割
    if len(long_text) > max_len:
        sentence_chunks = split_by_sentences(long_text)
        if len(sentence_chunks) > 1:
            result = []
            for sentence in sentence_chunks:
                result.extend(split_text(sentence, max_len, overlap_len))

            # 合并过小的块
            return merged_short_chunks(result)

    # 硬截断处理
    if len(long_text) > max_len:
        return hard_split(long_text)
    else:
        return [long_text]


if __name__ == '__main__':
    file_name='./anime_scraper/若山诗音.txt'
    # file_name='./anime_scraper/Nintendo Switch2025年游戏列表.txt'
    # file_name='./anime_scraper/配音.txt'
    with open(file_name, 'r', encoding='utf-8') as f:
        long_text = f.read()

    result = split_text(long_text, 3500, 200)
    for r in result:
        print(r)
        print('-=' * 60)
        print(len(r))
        print('-=' * 60)
    print(len(result))
