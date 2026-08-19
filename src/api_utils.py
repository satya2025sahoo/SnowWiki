import time
import re
import functools

def with_retry(max_retries=5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import groq
            retries = max_retries
            while retries > 0:
                try:
                    return func(*args, **kwargs)
                except groq.RateLimitError as e:
                    msg = str(e)
                    wait_time = 15.0 # default fallback
                    match = re.search(r'try again in ([\d\.]+)s', msg)
                    if match:
                        wait_time = float(match.group(1)) + 2.0 # 2s buffer
                    print(f"⚠️ Groq rate limit reached. Retrying in {wait_time:.1f}s... (Retries left: {retries})")
                    time.sleep(wait_time)
                    retries -= 1
            # Last attempt, if it fails it will raise
            return func(*args, **kwargs)
        return wrapper
    return decorator
