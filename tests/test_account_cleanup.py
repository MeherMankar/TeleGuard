from teleguard.core.bot_manager import BotManager


def test_account_cleanup_requires_both_plain_and_encrypted_sessions_to_be_missing():
    query = BotManager._accounts_missing_session_query()

    assert query == {
        "$and": [
            {
                "$or": [
                    {"session_string": {"$exists": False}},
                    {"session_string": {"$in": [None, "", False]}},
                ]
            },
            {
                "$or": [
                    {"session_string_enc": {"$exists": False}},
                    {"session_string_enc": {"$in": [None, "", False]}},
                ]
            },
        ]
    }
