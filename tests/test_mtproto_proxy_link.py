import base64

from teleguard.core.proxy_manager import ProxyManager


def run_coroutine_without_loop(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Expected this proxy helper to complete without awaiting")


LONG_URLSAFE_SECRET = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"


def test_parses_mtproto_t_me_link_with_optional_bot_and_channel():
    manager = ProxyManager()
    link = (
        "https://t.me/proxy?server=65.21.235.107&port=4455"
        "&secret=dd104462821249bd7ac519130220c25d09"
        "&bot=@mtpro_xyz_bot&channel=@mtpro_xyz"
    )

    parsed = run_coroutine_without_loop(manager.parse_telegram_proxy_link(link))

    assert parsed == {
        "type": "mtproto",
        "server": "65.21.235.107",
        "port": 4455,
        "secret": "104462821249bd7ac519130220c25d09",
    }


def test_builds_native_telethon_mtproto_proxy_configuration():
    manager = ProxyManager()
    proxy = {
        "type": "mtproto",
        "server": "65.21.235.107",
        "port": 4455,
        "secret": "dd104462821249bd7ac519130220c25d09",
    }

    result = run_coroutine_without_loop(manager.build_telethon_proxy(proxy))

    assert result == {
        **proxy,
        "secret": "104462821249bd7ac519130220c25d09",
    }


def test_rejects_mtproto_link_without_secret():
    manager = ProxyManager()

    result = run_coroutine_without_loop(
        manager.parse_telegram_proxy_link(
            "https://t.me/proxy?server=65.21.235.107&port=4455"
        )
    )

    assert result is None


def test_parses_and_normalizes_urlsafe_mtproto_secret():
    manager = ProxyManager()
    link = (
        "https://t.me/proxy?server=imtproxy.ir.hosting.server.qodrati."
        "www.imtproxy-ir.info&port=53556&secret="
        f"{LONG_URLSAFE_SECRET}&bot=@mtpro_xyz_bot&channel=@mtpro_xyz"
    )

    parsed = run_coroutine_without_loop(manager.parse_telegram_proxy_link(link))
    decoded_secret = base64.urlsafe_b64decode(
        LONG_URLSAFE_SECRET + "=" * (-len(LONG_URLSAFE_SECRET) % 4)
    )

    assert parsed is not None
    assert parsed["type"] == "mtproto"
    assert parsed["server"] == "imtproxy.ir.hosting.server.qodrati.www.imtproxy-ir.info"
    assert parsed["port"] == 53556
    assert parsed["secret"] == decoded_secret[:16].hex()


def test_parses_manual_mtproto_uri():
    manager = ProxyManager()

    parsed = run_coroutine_without_loop(
        manager.parse_telegram_proxy_link(
            "mtproto://proxy.example.invalid:443:"
            "0123456789abcdef0123456789abcdef"
        )
    )

    assert parsed == {
        "type": "mtproto",
        "server": "proxy.example.invalid",
        "port": 443,
        "secret": "0123456789abcdef0123456789abcdef",
    }


def test_parses_tg_scheme_mtproto_link():
    manager = ProxyManager()

    parsed = run_coroutine_without_loop(
        manager.parse_telegram_proxy_link(
            "tg://proxy?server=proxy.example.invalid&port=443"
            "&secret=0123456789abcdef0123456789abcdef"
        )
    )

    assert parsed == {
        "type": "mtproto",
        "server": "proxy.example.invalid",
        "port": 443,
        "secret": "0123456789abcdef0123456789abcdef",
    }


def test_parses_html_encoded_mtproto_link():
    manager = ProxyManager()

    parsed = run_coroutine_without_loop(
        manager.parse_telegram_proxy_link(
            "https://t.me/proxy?server=proxy.example.invalid&amp;port=443"
            "&amp;secret=0123456789abcdef0123456789abcdef"
        )
    )

    assert parsed == {
        "type": "mtproto",
        "server": "proxy.example.invalid",
        "port": 443,
        "secret": "0123456789abcdef0123456789abcdef",
    }
