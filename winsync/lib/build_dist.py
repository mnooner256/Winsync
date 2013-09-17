import os, os.path, platform, subprocess, shutil, sys
import winsync

#Get the python executable's path
python_exe = sys.executable

#Save the current directory
old_dir = os.getcwd()

#Change directory to site-packages where winsync is currently installed
os.chdir(os.path.realpath(
    os.path.join(os.path.split(winsync.__file__)[0], '..' )))

#Copy the setup to a better build location
shutil.copyfile('./winsync/lib/setup.py', './setup.py')
shutil.copyfile('./winsync/lib/postinstall.py', './install.py')
with open( 'README.txt', 'w' ) as f:
    pass

#Create zip based install file
subprocess.check_call([python_exe, '-m', 'winsync.lib.setup', 'sdist'])

#If the platform is windows, then create the exe installer
if sys.platform == 'win32':
    subprocess.check_call([python_exe, '-m', 'winsync.lib.setup', 'bdist_wininst',
                           '--install-script=install.py',
                           '--user-access-control=force',
                           '--target-version=3.2'])

#Make sure the install files were built, then clean up
if os.path.exists('build'):
    shutil.rmtree('build')
    os.remove('setup.py')
    os.remove('install.py')

#Move install files to their final location
for file in os.listdir('dist'):
    shutil.move(os.path.join('dist', file),
                os.path.join(old_dir, file))

#Finish clean up
os.rmdir('dist')
if os.path.exists('MANIFEST'):
    os.remove('MANIFEST')

os.remove('README.txt')
