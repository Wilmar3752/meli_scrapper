import asyncio
import time
import pandas as pd

def timer_decorator(func):
   def wrapper(*args, **kwargs):
       start_time = time.time()
       result = func(*args, **kwargs)
       end_time = time.time()
       print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
       return result
   return wrapper


def async_timer_decorator(func):
   async def wrapper(*args, **kwargs):
       start_time = time.time()
       result = await func(*args, **kwargs)
       end_time = time.time()
       print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
       return result
   return wrapper

def run_async(func, *args):
   loop = asyncio.get_event_loop()
   return loop.run_until_complete(func(*args))

def async_apply(df, func, *args, **kwargs):
   loop = asyncio.get_event_loop()
   return pd.Series(loop.run_until_complete(asyncio.gather(*(func(x, *args, **kwargs) for x in df))))
