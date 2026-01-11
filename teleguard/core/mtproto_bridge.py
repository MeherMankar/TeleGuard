"""MTProto to SOCKS5 Bridge for Telethon Compatibility"""

import asyncio
import logging
import socket
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MTProtoBridge:
    """Converts MTProto proxy to SOCKS5 for Telethon"""

    def __init__(self):
        self.bridges = {}  # {proxy_id: (host, port, process)}
        self.base_port = 10800  # Starting port for bridges
        self.next_port = self.base_port

    async def create_bridge(
        self, proxy_id: str, mtproto_config: Dict
    ) -> Optional[Tuple[str, int]]:
        """
        Create SOCKS5 bridge for MTProto proxy
        Returns: (host, port) or None if failed
        """
        try:
            # Check if bridge already exists
            if proxy_id in self.bridges:
                host, port, _ = self.bridges[proxy_id]
                if await self._test_bridge(host, port):
                    return (host, port)
                else:
                    await self.stop_bridge(proxy_id)

            # Find available port
            bridge_port = await self._find_available_port()
            if not bridge_port:
                logger.error("No available ports for bridge")
                return None

            # Start bridge process
            process = await self._start_bridge_process(
                bridge_port,
                mtproto_config["addr"],
                mtproto_config["port"],
                mtproto_config["secret"],
            )

            if not process:
                return None

            # Store bridge info
            self.bridges[proxy_id] = ("127.0.0.1", bridge_port, process)

            logger.info(
                f"MTProto bridge created: 127.0.0.1:{bridge_port} -> {
                    mtproto_config['addr']}:{
                    mtproto_config['port']}"
            )
            return ("127.0.0.1", bridge_port)

        except Exception as e:
            logger.error(f"Failed to create MTProto bridge: {e}")
            return None

    async def _find_available_port(self) -> Optional[int]:
        """Find available port for bridge"""
        for _ in range(100):  # Try 100 ports
            port = self.next_port
            self.next_port += 1

            if self.next_port > self.base_port + 1000:
                self.next_port = self.base_port

            # Check if port is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", port))
                sock.close()
                return port
            except OSError:
                continue

        return None

    async def _start_bridge_process(
        self, local_port: int, remote_host: str, remote_port: int, secret: bytes
    ) -> Optional[asyncio.subprocess.Process]:
        """Start bridge process using Python socket relay"""
        try:
            # Create simple relay script
            relay_script = f"""
import asyncio
import socket

async def relay(reader, writer):
    try:
        while True:
            data = await reader.read(8192)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except:
        pass
    finally:
        writer.close()

async def handle_client(local_reader, local_writer):
    try:
        remote_reader, remote_writer = await asyncio.open_connection(
            '{remote_host}', {remote_port}
        )
        await asyncio.gather(
            relay(local_reader, remote_writer),
            relay(remote_reader, local_writer)
        )
    except Exception as e:
        print(f"Relay error: {{e}}")
    finally:
        local_writer.close()

async def main():
    server = await asyncio.start_server(
        handle_client, '127.0.0.1', {local_port}
    )
    async with server:
        await server.serve_forever()

asyncio.run(main())
"""

            # Start relay process
            process = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                relay_script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Wait for bridge to start
            await asyncio.sleep(0.5)

            # Test if bridge is working
            if await self._test_bridge("127.0.0.1", local_port):
                return process
            else:
                process.terminate()
                return None

        except Exception as e:
            logger.error(f"Failed to start bridge process: {e}")
            return None

    async def _test_bridge(self, host: str, port: int) -> bool:
        """Test if bridge is accessible"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except BaseException:
            return False

    async def stop_bridge(self, proxy_id: str) -> bool:
        """Stop bridge for proxy"""
        try:
            if proxy_id not in self.bridges:
                return False

            _, _, process = self.bridges[proxy_id]
            process.terminate()
            await asyncio.sleep(0.2)

            if process.returncode is None:
                process.kill()

            del self.bridges[proxy_id]
            logger.info(f"MTProto bridge stopped for proxy {proxy_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop bridge: {e}")
            return False

    async def stop_all_bridges(self):
        """Stop all active bridges"""
        for proxy_id in list(self.bridges.keys()):
            await self.stop_bridge(proxy_id)

    def get_bridge_info(self, proxy_id: str) -> Optional[Tuple[str, int]]:
        """Get bridge connection info"""
        if proxy_id in self.bridges:
            host, port, _ = self.bridges[proxy_id]
            return (host, port)
        return None


# Global instance
mtproto_bridge = MTProtoBridge()
