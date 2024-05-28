import time
from dotenv import load_dotenv
import os
import random

load_dotenv()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
PROXY_USER = os.getenv("PROXY_USER")

def timer_decorator(func):
   def wrapper(*args, **kwargs):
       start_time = time.time()
       result = func(*args, **kwargs)
       end_time = time.time()
       print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
       return result
   return wrapper


def generate_proxy_url():
    port = random.randint(10000,10099)
    return f'http://{PROXY_USER}:{PROXY_PASSWORD}@gate.smartproxy.com:{port}'

