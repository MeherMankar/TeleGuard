from teleguard.handlers.auto_reply_handler import AutoReplyHandler


def test_legacy_comma_separated_auto_reply_keywords_are_expanded():
    keywords = AutoReplyHandler._normalize_keyword_map(
        {
            "hi, hello, hey": "Legacy reply",
            "'hi', 'hello', 'hey'": "Quoted legacy reply",
            "hi": "Current reply",
            "hello": "Current reply",
            "hey": "Current reply",
        }
    )

    assert keywords == {
        "hi": "Current reply",
        "hello": "Current reply",
        "hey": "Current reply",
    }
