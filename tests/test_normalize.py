import pytest

from giongtoi.text.normalize import normalize, number_to_words


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "không"),
        (5, "năm"),
        (10, "mười"),
        (11, "mười một"),
        (15, "mười lăm"),
        (20, "hai mươi"),
        (21, "hai mươi mốt"),
        (24, "hai mươi bốn"),
        (25, "hai mươi lăm"),
        (100, "một trăm"),
        (105, "một trăm lẻ năm"),
        (110, "một trăm mười"),
        (1000, "một nghìn"),
        (1005, "một nghìn không trăm lẻ năm"),
        (1050, "một nghìn không trăm năm mươi"),
        (2025, "hai nghìn không trăm hai mươi lăm"),
        (15000, "mười lăm nghìn"),
        (1_000_000, "một triệu"),
        (1_200_000, "một triệu hai trăm nghìn"),
        (3_000_000_000, "ba tỷ"),
    ],
)
def test_number_to_words(n, expected):
    assert number_to_words(n) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Tôi có 3 con mèo.", "Tôi có ba con mèo."),
        ("Giá 1.000.000 đồng", "Giá một triệu đồng"),
        ("Pi bằng 3,14", "Pi bằng ba phẩy mười bốn"),
        ("Tăng 50%", "Tăng năm mươi phần trăm"),
        ("Ngày 15/3/2025 trời đẹp", "Ngày mười lăm tháng ba năm hai nghìn không trăm hai mươi lăm trời đẹp"),
        ("Hẹn 15/4 nhé", "Hẹn ngày mười lăm tháng tư nhé"),
        ("Họp lúc 8h30", "Họp lúc tám giờ ba mươi phút"),
        ("Họp lúc 14:05", "Họp lúc mười bốn giờ không năm phút"),
        ("Giá 50.000đ", "Giá năm mươi nghìn đồng"),
        ("Giá 20k", "Giá hai mươi nghìn"),
        ("Chạy 5km", "Chạy năm ki lô mét"),
        ("Thứ 4 gặp", "Thứ tư gặp"),
        ("Từ 5-10 người", "Từ năm đến mười người"),
        ("Sống ở TP.HCM", "Sống ở thành phố Hồ Chí Minh"),
        ("Gọi 0912345678", "Gọi không chín một hai ba bốn năm sáu bảy tám"),
    ],
)
def test_normalize_vietnamese(text, expected):
    assert normalize(text, english_mode="native") == expected


def test_english_words_vietnamized_by_default():
    assert normalize("Đăng lên Facebook và YouTube") == "Đăng lên phây búc và diu túp"


def test_unknown_acronym_spelled_vietnamese():
    assert normalize("Đài VTV đưa tin") == "Đài vê tê vê đưa tin"


def test_english_mode_native_keeps_words():
    assert normalize("Đăng lên Facebook", english_mode="native") == "Đăng lên Facebook"


def test_user_lexicon_uppercase_key_is_case_sensitive():
    out = normalize("Dùng AI và ai đó", user_lexicon={"AI": "trí tuệ nhân tạo"})
    assert out == "Dùng trí tuệ nhân tạo và ai đó"


def test_user_lexicon_multiword():
    out = normalize("Học Machine Learning nhé", user_lexicon={"machine learning": "mơ sin lơ ninh"})
    assert out == "Học mơ sin lơ ninh nhé"


def test_lowercase_word_matching_acronym_lexicon_not_replaced():
    # "ai" tiếng Việt không được đổi thành "ây ai"
    assert normalize("Ai đến đó?") == "Ai đến đó?"


def test_whitespace_collapsed():
    assert normalize("Xin   chào\n bạn") == "Xin chào bạn"
