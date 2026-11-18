from giongtoi.text.segment import split_chapters, split_sentences


def test_chapters_by_heading():
    text = "Lời nói đầu.\n\n# Chương một\nNội dung một.\n\n## Chương hai\nNội dung hai."
    chapters = split_chapters(text)
    assert [c.title for c in chapters] == ["Mở đầu", "Chương một", "Chương hai"]
    assert chapters[1].body == "Nội dung một."
    assert chapters[2].body == "Nội dung hai."


def test_chapters_by_double_blank_lines():
    text = "Phần A dòng 1.\n\nPhần A đoạn 2.\n\n\nPhần B."
    chapters = split_chapters(text)
    assert [c.title for c in chapters] == ["Phần 1", "Phần 2"]
    assert chapters[0].body == "Phần A dòng 1.\n\nPhần A đoạn 2."
    assert chapters[1].body == "Phần B."


def test_single_chapter():
    chapters = split_chapters("Chỉ một câu.")
    assert len(chapters) == 1
    assert chapters[0].title == "Toàn văn"


def test_empty_heading_sections_dropped():
    chapters = split_chapters("# A\n\n# B\nCó chữ.")
    assert [c.title for c in chapters] == ["B"]


def test_split_sentences_basic_and_paragraph_flag():
    segs = split_sentences("Câu thứ nhất khá dài đấy. Câu thứ hai cũng dài!\n\nĐoạn mới bắt đầu ở đây?")
    assert [s.text for s in segs] == [
        "Câu thứ nhất khá dài đấy.",
        "Câu thứ hai cũng dài!",
        "Đoạn mới bắt đầu ở đây?",
    ]
    assert [s.paragraph_end for s in segs] == [False, True, True]


def test_abbreviations_and_decimals_do_not_split():
    segs = split_sentences("Tôi sống ở TP. Hồ Chí Minh từ lâu rồi. Giá là 3.5 triệu đồng một tháng.")
    assert [s.text for s in segs] == [
        "Tôi sống ở TP. Hồ Chí Minh từ lâu rồi.",
        "Giá là 3.5 triệu đồng một tháng.",
    ]


def test_short_sentences_merged():
    segs = split_sentences("Ừ. Được. Mình sẽ đến vào buổi chiều nay nhé.")
    assert [s.text for s in segs] == ["Ừ. Được. Mình sẽ đến vào buổi chiều nay nhé."]


def test_long_sentence_split_at_commas_under_max():
    long = ", ".join(["đây là một vế câu khá dài"] * 12) + "."
    segs = split_sentences(long, max_chars=100)
    assert len(segs) > 1
    assert all(len(s.text) <= 100 for s in segs)
    assert " ".join(s.text for s in segs).replace(" ,", ",") .count("vế câu") == 12


def test_very_long_run_without_punctuation_split_by_words():
    long = " ".join(["chữ"] * 100)
    segs = split_sentences(long, max_chars=60)
    assert all(len(s.text) <= 60 for s in segs)
    assert sum(len(s.text.split()) for s in segs) == 100
