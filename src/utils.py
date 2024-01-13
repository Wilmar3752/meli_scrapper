import asyncio
import time

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