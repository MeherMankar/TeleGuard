"""Quick test for proxy HTML decoding"""
import asyncio
import html

async def test_decode():
    # Your proxy link with &amp;
    link = "https://t.me/proxy?server=oyslv.saladin-co.ir&amp;port=8443&amp;secret=eeNEgYdJvXrFGRMCIMJdCQtY2RueWVrdGFuZXQuY29tZmFyYWthdi5jb212YW4ubmFqdmEuY29tAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA&amp;bot=@mtpro_xyz_bot&amp;channel=@mtpro_xyz"
    
    print("Original link:")
    print(link)
    print("\nDecoded link:")
    decoded = html.unescape(link)
    print(decoded)
    
    # Parse it
    if '?' in decoded:
        query_part = decoded.split('?')[1]
        params = {}
        for param in query_part.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        print("\nParsed parameters:")
        for key, value in params.items():
            if key in ['server', 'port', 'secret']:
                print(f"  {key}: {value[:50]}..." if len(value) > 50 else f"  {key}: {value}")

asyncio.run(test_decode())
