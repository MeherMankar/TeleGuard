"""Geolocation and distance utilities for TeleGuard"""

import logging
import math
import aiohttp
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache for IP locations to avoid redundant API calls
_ip_cache: Dict[str, Dict] = {}

async def get_ip_location(ip: str) -> Optional[Dict]:
    """
    Get geolocation data for an IP address using ip-api.com (free for non-commercial use).
    Returns a dict with 'lat', 'lon', 'country', 'region', 'city', 'isp'.
    """
    if not ip or ip in ("127.0.0.1", "::1"):
        return None
    
    if ip in _ip_cache:
        return _ip_cache[ip]

    try:
        url = f"http://ip-api.com/json/{ip}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        location = {
                            "lat": data.get("lat"),
                            "lon": data.get("lon"),
                            "country": data.get("country"),
                            "region": data.get("regionName"),
                            "city": data.get("city"),
                            "isp": data.get("isp"),
                        }
                        _ip_cache[ip] = location
                        return location
                    else:
                        logger.warning(f"IP Geolocation failed for {ip}: {data.get('message')}")
    except Exception as e:
        logger.error(f"Error fetching IP location for {ip}: {e}")
    
    return None

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth in kilometers.
    """
    # Earth radius in km
    R = 6371.0
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

def calculate_speed(dist_km: float, time_diff_seconds: float) -> float:
    """
    Calculate speed in km/h.
    """
    if time_diff_seconds <= 0:
        return float('inf')
    
    hours = time_diff_seconds / 3600.0
    return dist_km / hours
