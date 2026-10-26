from teleguard.utils.spam_detector import SpamDetector, SpamLimitType


def test_detector_handles_empty_and_blank_message_lists():
    detector = SpamDetector([" ", "", None])

    assert detector.appeal_messages == []
    assert detector.select_optimal_message(SpamLimitType.SPAMBLOCK) is None
    assert detector.select_from_messages(["", "  "], SpamLimitType.SPAMBLOCK) is None
    assert detector.get_detection_stats()["total_messages"] == 0


def test_detector_uses_general_category_when_no_message_matches():
    detector = SpamDetector(["A general appeal message"])

    selected = detector.select_optimal_message(SpamLimitType.SPAMBLOCK)

    assert selected == "A general appeal message"


def test_detector_accepts_empty_response_and_negative_account_age():
    detector = SpamDetector(["An appeal message long enough to be selected"])

    analysis = detector.analyze_spambot_response("")

    assert analysis["account_flagged"] is False
    assert analysis["spam_limit_type"] == SpamLimitType.GENERAL_RESTRICTION
    assert detector.get_account_age_category(-1) == "very_new"


def test_detector_categorizes_case_insensitively():
    detector = SpamDetector(["SPAM BLOCK appeal"])

    assert detector.categorized_messages[SpamLimitType.SPAMBLOCK] == [
        "SPAM BLOCK appeal"
    ]
