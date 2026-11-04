from src.utils.text import clean_text


def test_removes_urls_and_mentions():
    assert clean_text("Check https://spam.com and www.x.io @bot_123 now") == "check and now"


def test_hashtag_keeps_word():
    assert clean_text("#awesome video") == "awesome video"


def test_emojis_are_converted_to_words():
    out = clean_text("I love it 😍")
    assert out.startswith("i love it")
    assert "heart" in out  # 😍 -> "smiling face with heart eyes"


def test_punctuation_digits_and_case():
    assert clean_text("WOW!!! 10/10, Best VIDEO ever...") == "wow best video ever"


def test_contractions_and_repeated_letters():
    assert clean_text("Don't do thaaaat") == "dont do thaat"


def test_html_and_whitespace():
    assert clean_text("<b>Hello</b>\n\n   world") == "hello world"


def test_non_string_and_empty():
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("!!! 123") == ""
