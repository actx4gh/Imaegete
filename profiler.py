import cProfile
import pstats
import io
from main import main
import logging
import atexit

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
    logging.getLogger('image_sorter').info("[main] Profiling data written")

def on_exit():
    stop_profiling()
    logging.getLogger('image_sorter').info("[main] Application exit triggered")

atexit.register(on_exit)

if __name__ == "__main__":
    start_profiling()
    main()

