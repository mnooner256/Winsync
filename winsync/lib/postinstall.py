import sys
import os.path
import os
import re
import shutil
import winsync.lib.util as util

#Get the start menu's location
start_menu = util.get_special_folder('COMMON_STARTMENU')

#This is where the program's shorcuts will be installed
program_folder = os.path.join(start_menu, 'Programs', 'Winsync')

#List of shorcuts to put in the start menu and desktop
shortcut_filepath = [
    os.path.join(program_folder, 'Sync Programs (command line).lnk'),
    os.path.join(program_folder, 'Sync Programs.lnk'),
    os.path.join(program_folder, 'Record Interactions.lnk')]

if sys.argv[1] == '-install':
    
    desktop_folder = util.get_special_folder('DESKTOP')
    
    #Look for C:\Python3#\python.exe in sys.path
    found = False
    python_exe = ''
    python_path = re.compile('^([A-Za-z]:\\\\Python3[0-9]).*$')
    for path in sys.path:
        m = python_path.match(path)
        if m:
            new_python_exe = os.path.join(m.group(1), 'python.exe')
            if os.path.exists(new_python_exe):
                found = True
                
                #Only install the shortcuts for the newest python version
                if new_python_exe > python_exe:
                    python_exe = new_python_exe
    
    #No python.exe found, cannot continue
    if not found:
        raise Exception('Could not find a valid python.exe from sys.path.')
    
    #When reinstalling, the program folder may already exist
    if not os.path.exists(program_folder):
        os.mkdir(program_folder)

    #Create the shortcuts
    util.create_shortcut(shortcut_filepath[0], python_exe,
                         description='Downloads and installs programs, administrator access required',
                         arguments='-m winsync.run')
    shutil.copy(shortcut_filepath[0], desktop_folder)
    
    #Not ready yet
    #util.create_shortcut(shortcut_filepath[1],
    #                     python_exe.replace('python.exe', 'pythonw.exe'),
    #                     description='Downloads and installs programs, administrator access required',
    #                     arguments='-m winsync.gui')
    #shutil.copy(shortcut_filepath[1], desktop_folder)
    
    util.create_shortcut(shortcut_filepath[2], python_exe,
                         description='Record user interactions for playback during synchronization',
                         arguments='-m winsync.record')
    shutil.copy(shortcut_filepath[2], desktop_folder)                     
    

elif sys.argv[1] == '-remove':
    #Delete the program's folder in the start menu
    if os.path.exists(program_folder):
        shutil.rmtree(program_folder)
        
    #Remove the desktop shortcuts, start by changing the
    #directory to the Desktop
    os.chdir(util.get_special_folder('DESKTOP'))    
    
    for shortcut in shortcut_filepath:
        #Get just the file name from the path
        shortcut = os.path.basename(shortcut)
        
        #Remove the shortcut if it exists
        if os.path.exists(shortcut):
            os.remove(shortcut)