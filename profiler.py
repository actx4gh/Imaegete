import atexit
import cProfile
import io
import pstats
from functools import wraps

import logger
from new_main import main

def profile_function(func):
    """Decorator to profile a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        with open(f"{func.__name__}_profile.txt", "w") as f:
            f.write(s.getvalue())
        return result
    return wrapper

pr = cProfile.Profile()



def start_profiling():
    global pr
    pr.enable()


def stop_profiling():
    global pr
    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    with open("image_sorter_profile.txt", "w") as f:
        f.write(s.getvalue())


def on_exit():
    stop_profiling()
    logger.info("[main] Application exit triggered")


atexit.register(on_exit)

if __name__ == "__main__":
    start_profiling()
    main()
