#idle_queue.py

import queue

#Global queue, import this from anywhere, you will get the same object.
idle_loop = queue.Queue()

def idle_add(func, *args, **kwargs):
    #use this function to add your callbacks/methods
    def idle():
        func(*args, **kwargs)
        return False
    idle_loop.put(idle)
