DEBUG = True

def debug_log(*args):
    if DEBUG:
        print("[DEBUG]", *args)