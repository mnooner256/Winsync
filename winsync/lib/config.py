"""This module holds configuration variables."""
import threading

#This is the location of the lib, etc and var directories, they will 
#be set latter in by calling main() the init_config() function.
base_dir = None
lib_dir = None
var_dir = None
etc_dir = None
pkg_dir = None
base_url = None
cache_dir = None
spool_dir = None
repo = None
sysinfo = None

#The global logger that we will use to log all events to
logger = None

#This variable alters some of winsyncs behavior. If True
#then winsync will act in GUI mode, which means that
#less information is displayed in the terminal.
gui_mode = False

#This variable defines the file path to a log file
#wget will use when we are in GUI mode.
wget_download_log = None

#This barrier is used to make sure util.wget does not
#return (and delete the log) until GUI is finished updating.
wget_exit_barrier = threading.Barrier(parties=2)
wget_start_barrier = threading.Barrier(parties=2)

def start_logger():
    """This funtion starts the logging process."""
    import os
    import os.path
    import logging
    import logging.config
    import logging.handlers
    import sys

    global logger, base_dir, etc_dir
    
    #Don't re-create the logger object if it already exists
    #Doing this allows this function to be called multiple
    #times without having any side effects.
    if logger:
        return
    
    #Sometimes this application is not called from the directory containing
    #the run.py file. So we will temporarily change to that directory.
    cur_dir = os.getcwd()
    os.chdir( base_dir )
    
    logger_conf_file = os.path.join( etc_dir, 'logging.ini' )
    
    if not os.path.exists( logger_conf_file ):
        print( 'Could not find the logging configuration '
                'file: ' + logger_conf_file )
        sys.exit( 1 )
    
    logging.config.fileConfig(logger_conf_file)
    logger = logging.getLogger('winsync')
    
    #Change the directory back
    os.chdir( cur_dir )

def init_config( winsync_dir, is_gui_mode=False ):
    import os.path
    
    global base_dir, lib_dir, var_dir, cache_dir, spool_dir
    global etc_dir, pkg_dir, repo, gui_mode, wget_download_log
    
    #This checks if a directory exists, and if it does not
    #the function then tries to create it. This makes
    #installation and error checking much easier.
    def dir_exists( path ):
        import os
        if not os.path.exists( path ):
            try:
                os.mkdir( path )
            except:
                raise IOError( 'Path does not exist, and could not create'
                               ' it: {}'.format(path) )
        elif not os.path.isdir( path ):
            raise IOError( 'Path is not a directory: {}'.format(path) )
    
    #Import the proper config parser, for python 2 or 3
    try:
        #python-2
        from ConfigParser import SafeConfigParser
    except ImportError:
        #python-3
        from configparser import SafeConfigParser
    
    base_dir = os.path.abspath( winsync_dir )
    dir_exists( base_dir )
    
    etc_dir = os.path.join( base_dir, 'etc'  )
    dir_exists( etc_dir )
    
    var_dir = os.path.join( base_dir, 'var' )
    dir_exists( var_dir )
    
    spool_dir = os.path.join( base_dir, 'var', 'spool' )
    dir_exists( spool_dir )
    
    cache_dir = os.path.join( base_dir, 'var', 'cache' )
    dir_exists( cache_dir )
    
    lib_dir = os.path.join( base_dir, 'lib' )
    dir_exists( lib_dir )
    
    pkg_dir = os.path.join( base_dir, 'pkg-info' )
    dir_exists( pkg_dir )
    
    parser = SafeConfigParser()
    parser.read( os.path.join( etc_dir, 'config.ini' ) )
    
    repo = parser.get( 'repo', 'base_url' )
    
    #Only change the mode if we are switching *into* GUI mode.
    if is_gui_mode:
        gui_mode = True
        wget_download_log = os.path.join(var_dir, 'wget_download.log')
        
        #If the application exited abnormally, it can leave an orphan
        #log file, get rid of it now.
        if os.path.exists(wget_download_log):
            os.remove(wget_download_log)
        
def init_sysinfo():
    """This function returns a dictionary containing all of the data
    returned by the systeminfo command. Warning, due to an error in Windows XP
    Service Pack 3, this command has the side effect of altering the registry
    entries for hotfixes.
    """
    import csv, io, os, re, subprocess, string
    from winsync.lib.util import WinsyncException
    global sysinfo
    
    logger.info('Gathering system information')
    
    #Fix the hotfix problem
    _fix_hotfix_error()
    
    #Get the system information in table format
    proc = subprocess.Popen( ['systeminfo'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True )
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        raise WinsyncException( 'The systeminfo command failed.' )

    #The easiest way to manipulate the data is as file
    #Create a file-like object for our manipulation
    sio = io.StringIO( stdout.decode( 'ASCII' ) )
    
    #Read off the initial blank line
    blank = sio.readline()

    #Win XP starts the stream with a blank line
    #Win 7 does not, so we need to somtimes back up
    if blank.strip() != '':
        sio.seek( 0, 0 )
        
    
    #This is the dictionary we will return at
    #the end of the function
    sysinfo = {}
    
    #Add the variables from os.environ
    sysinfo.update( os.environ )

    #We will use these regex's to scan the line for certain properties
    multi = re.compile(r'^ *\[([0-9]+)\]: (.*)$')
    kb = re.compile(r' *(KB|Q)[0-9]+.*')
    

    #Go through each line of outputed string looking for key value pairs
    key = None
    for line in sio:
        #See if this is a "hotfix" value
        if kb.search(line):
            m = multi.match(line)
            #Store the hotfixes in a list
            if isinstance(sysinfo[key], list):
                sysinfo[key].append(m.group(2))
            else:
                sysinfo[key] = [sysinfo[key], m.group(2)]
        #See if this is a key: value line
        elif line[0] in string.ascii_letters and ':' in line:
            key, value = line.split(':', 1)
            sysinfo[key] = value.strip(string.whitespace)
            
        #Everything else gets appened to the previous key's value
        else:
            sysinfo[key] = '{}\n{}'.format(sysinfo[key],
                                           line.strip(string.whitespace))

def _fix_hotfix_error():
    """There is a problem in XP SP3, where the systeminfo command will crash
    if there are any hotfix's with a 'File 1' subkey this will fix it so the
    error will not occur.
    """
    from winreg import OpenKey, EnumKey, DeleteKey, HKEY_LOCAL_MACHINE

    try:
        #Open the outer-most key for hotfixes
        hotfixes = OpenKey( HKEY_LOCAL_MACHINE, 
                    r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\HotFix' )
    except WindowsError:
        #This error means that no hotfixes are installed yet.
        #This happens when you do a fresh install of the OS.
        #Nothing to do, so just return
        return

    try:
        #Go through each hotfix
        i = 0
        while True:
            subkey = EnumKey( hotfixes, i )
            i = i + 1

            try:
                #Open each subkey and delete the "File 1" key if it exists
                with OpenKey( hotfixes, subkey ) as key:
                    DeleteKey( key, 'File 1' )
            except WindowsError:
                #This error is fine. It means that there was no 'File 1' key
                #which is what we want.
                pass
    except WindowsError:
        #This is how EnumKey indicates that there are no more keys to
        #loop through.
        pass

def get_installer_object(module_name):
    """This function returns an instance of the Installer subclass found in
    the given module name. The module_name parameter should be a string
    specifying where to look fo the Installer subclass. If no Installer subclass
    is found then None is returned.

    This function will only use the first subclass found, additional subclasses
    are ignored. Also, which one is considered "first" is not sepcified.
    """
    import inspect
    from winsync.lib.util import Installer

    #Import the installer module
    install_module = __import__(module_name, globals(), locals(), [], 0)

    #Find the class that inherits from winsync.lib.util.Install inside the
    #install module. 
    installer_class = None
    for name, cls in inspect.getmembers(install_module):
        if inspect.isclass(cls):
            if issubclass(cls, Installer):
                installer_class = cls
                break

    #Return the instantiated installer class if one was found
    if installer_class != None:
        return installer_class()
    else:
        return None
