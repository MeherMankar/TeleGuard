import asyncio
import base64

from teleguard.core.proxy_manager import ProxyManager


LONG_URLSAFE_SECRET = (
    "H____wxV0R23OuE7AMyQgCM4eFlnUldQOFpvTHVwZmNpaVI2ZkJFNDJMSXJxUW1yT2s4"
    "YzRCaVRaLi11cGRhd"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def test_parses_mtproto_t_me_link_with_optional_bot_and_channel():
    manager = ProxyManager()
    link = (
        "https://t.me/proxy?server=65.21.235.107&port=4455"
        "&secret=dd104462821249bd7ac519130220c25d09"
        "&bot=@mtpro_xyz_bot&channel=@mtpro_xyz"
    )

    parsed = asyncio.run(manager.parse_telegram_proxy_link(link))

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

    result = asyncio.run(manager.build_telethon_proxy(proxy))

    assert result == {
        **proxy,
        "secret": "104462821249bd7ac519130220c25d09",
    }


def test_rejects_mtproto_link_without_secret():
    manager = ProxyManager()

    result = asyncio.run(
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

    parsed = asyncio.run(manager.parse_telegram_proxy_link(link))
    decoded_secret = base64.urlsafe_b64decode(
        LONG_URLSAFE_SECRET + "=" * (-len(LONG_URLSAFE_SECRET) % 4)
    )

    assert parsed is not None
    assert parsed["type"] == "mtproto"
    assert parsed["server"] == "imtproxy.ir.hosting.server.qodrati.www.imtproxy-ir.info"
    assert parsed["port"] == 53556
    assert parsed["secret"] == decoded_secret[:16].hex()
