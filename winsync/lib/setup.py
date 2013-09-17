from distutils.core import setup
import os, os.path, sys
from winsync.lib import config
import winsync

version='01.00.12'

winsync_dir = winsync.__path__[0]

def listdir(dir):
        global winsync_dir
        for x in os.listdir(os.path.join(winsync_dir, dir)):
            if not x.endswith('.pyc') and '__pycache__' not in x:
                yield os.path.join(dir, x)

def start_setup():
    #This module is Python3 only
    if sys.version[0] < '3':
        return

    #We need all the directory locations, this function calculates them for us
    config.init_config(winsync_dir)

    files = list(listdir('etc'))
    files.extend(listdir(os.path.join('lib', 'exec')))

    #Change to the parent directory of where winsync is installed
    os.chdir(winsync_dir+'/../')

    setup(name='Winsync',
          version=version,
          description='Windows Deployment Tool',
          author='Michael Nooner',
          author_email='mnooner@uca.edu',
          url='http://sun1.cs.uca.edu',
          packages=['winsync', 'winsync.lib'],
          package_data={'winsync': files},
          scripts=['install.py'])

if __name__ == '__main__':
    start_setup()
