import time
import asyncio
import functools
import re
from dotenv import load_dotenv
import os
import random

load_dotenv()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
PROXY_USER = os.getenv("PROXY_USER")

def timer_decorator(func):
   if asyncio.iscoroutinefunction(func):
       @functools.wraps(func)
       async def wrapper(*args, **kwargs):
           start_time = time.time()
           result = await func(*args, **kwargs)
           end_time = time.time()
           print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
           return result
       return wrapper
   else:
       @functools.wraps(func)
       def wrapper(*args, **kwargs):
           start_time = time.time()
           result = func(*args, **kwargs)
           end_time = time.time()
           print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
           return result
       return wrapper


def clean_price(raw):
    """'$129.990.000' or 'current price $\xa083900000' → '129990000' (str, digits only)."""
    if not raw:
        return None
    digits = re.sub(r'[^\d]', '', raw)
    return digits if digits else None


def clean_km(raw):
    """'70.471 Km' or '352.073 km' → 70471 (int)."""
    if not raw:
        return None
    digits = re.sub(r'[^\d]', '', raw)
    return int(digits) if digits else None


def generate_proxy_url():
    port = random.randint(10000, 10099)
    return {
        'server': f'http://gate.decodo.com:{port}',
        'username': PROXY_USER,
        'password': PROXY_PASSWORD,
    }

