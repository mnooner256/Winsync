import os, os.path, queue
import lib.config as config

q = queue.Queue()
config.init_config(os.getcwd())
config.start_logger(q)
