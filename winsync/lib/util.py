"""
This module hosts many functions and objects needed to create installation
scripts. This is one of the most important modules in the entire
:mod:`winsync` library. The types of objects and functions hosted within
this module are quite diverse, so users need import as few modules as possible.

The preferred way to import this module is like this::

      import winsync.lib.util as util

Importing the module in this manner allow you to refer to it using only the
``util`` prefix.
"""

import winsync.lib.config as config

class WinsyncException(Exception):
    pass

class Installer:
    """This is the Installer prototype class. All individual installation
    scripts must contain a subclass of this class.
    
    The two most important methods are the install and check method. These two
    method form the backbone of any installation script. They are the only
    two methods you **must** override.
    
    Instances of this class have access to several convenient attributes. They
    are designed to help make the life of installation script writers easier.
    
    * The ``logger`` attribute allow you access to the clients logging \
    functionality. This attribute is an instance of the \
    :class:`logging.Logger` class. You can use it to easily add your own log \
    entries to the installation log file. You use it like this::
        
        def install(self):
            #Perform your installation here ...
            
            self.logger.info( 'Finished the installation.' )
            return True
            
    * The ``files_dir`` attribute points to where the installation files for \
    your system have been downloaded. For example, say you simply have to \
    silently run a file called install.exe, you could do it like this::
    
        def install(self):
            exe = os.path.join( self.files_dir, 'install.exe' )
            subprocess.check_call( [exe, '/S'] )
            return True
    
    * You have direct access to the data stored in the package information \
    file through the ``package`` attribute. This attribute an instance of the \
    :class:`winsync.lib.PackageInfo` class.
    
    """
    def __init__( self ):
        import logging

        logging.basicConfig( level=logging.DEBUG )
        self.logger = logging
        self.fake_download = True
        self.files_dir = None
        
    def check( self ):
        """This function checks to see if a package is installed. It should
        return True if the package is installed, and False otherwise. This
        function must be overloaded, otherwise the install method will always
        be seen to fail.
        """
        return False
    def install( self ):
        """This method installs the package. It should return True if it
        believes that the install went successfully. The main program will
        still call the :meth:`check` method afterward to make sure. This
        method **must be defined**.
        """
        return False
    def upgrade( self ):
        """This method performs an upgrade from the current state. By default,
        it simply calls the install method. But you can override it if you need
        to do something special.
        """
        return self.install()
    def remove( self ):
        """This method removes the package from the system. By default it 
        simply returns True, and does nothing else. Essentially this will
        tell the :mod:`winsync` to stop managing the package and remove it
        from its cache, in general this is not the desired behavior. If you
        want to actually remove the package's files from the system then
        you should override this method.
        """
        return True


    def _set_info( self, package, logger=None, fake_download=False ):
        """Sets the package info from the ini file and logger attribute for
        this object. That way users can access detailed information about the
        program directly within the object. Do not override this method.
        """
        from winsync.lib.PackageInfo import PackageInfo
        import os, os.path
        
        self.fake_download = fake_download

        #If the user passes in a PackageInfo instance then set it,
        #Otherwise treat it as a string and load the info file
        if isinstance(package, PackageInfo ):
            self.package = package
        else:
            self.package = PackageInfo( package, skip_dependents=True, 
                                        skip_download=True )
        
        self.files_dir = os.path.join( config.spool_dir, self.package.id )
        self.package.files_dir = self.files_dir
        
        if not os.path.exists( self.files_dir ):
            os.mkdir( self.files_dir )
        
        if logger is not None:
            self.logger = logger
            
    def _cleanup( self ):
        """This method will delete the files_dir created in set_info()."""
        import shutil, os, os.path
        
        shutil.rmtree( self.files_dir )
        
        if os.path.exists( self.files_dir ):
            os.rmdir( self.files_dir )
            if os.path.exists( self.files_dir ):
                os.remove( self.files_dir )
        
    def _download_from_repo( self ):
        """The purpose of this method is to simplify the downloading of the
        package files from the repository. This method will divine the correct
        URL for the file, it will then return the downloaded file's path.
        """
        import winsync.lib.rget as rget
        
        if self.fake_download:
            return self.files_dir

        return rget.download_archive( self.package )

def test_installer( installer, package_name, 
                    test=['install', 'check', 'remove', 'check'],
                    get_pkg_info=True, download=True ):
    """This is a convenience function used to test all aspects of an 
    :class:`Installer` object. It can test the :meth:`Installer.install`,
    :meth:`Installer.check`, :meth:`Installer.upgrade`, and
    :meth:`Installer.remove` methods. This function will download the package
    information file before beginning the tests. So make sure that the
    repository is aware of your package's existence. It will
    *not download the install script* since that is what we are testing.
    
    Usually you would only want this function to be executed when the script is
    run on its own. So semantically you use it like this::
    
        import winsync.lib.util as util

        class Firefox(util.Installer):
            def check(self):
                return util.uninstall_exists( 'Firefox.*' )
            def install(self):
                pass #TODO: install code
            def remove(self):
                pass #TODO: uninstall code

        if __name__ == '__main__':
            util.test_installer( Firefox(), 'firefox', test=['check'] )

    This function does not return anything. It will output a log of the
    activities to the screen. If the install or upgrade methods returns False
    or have an exception raised, this function will simply return.
    
    :param installer: This is an instance of the :class:`Installer` class \
    you want to test.
    :param package_name: This is the unique package identifier that the \
    function can use to access the correct package information file.
    :param test: This parameter is very important. It sets what functions are \
    tested and in what order. The test parameter must be a list of strings. \
    Each string must be either: install, check, upgrade, or remove. This \
    allows you the flexibility to test the methods in any order. For example, \
    after you finish working on the remove method, you may want to skip \
    testing the install and check methods. By default, the upgrade method is \
    skipped.    
    :param get_pkg_info: If you want to stop this function from downloading \
    the package information file you can specify the get_pkg_info parameter \
    as False. It still needs this file though. So you must put one with the \
    correct name in the correct place by hand. This parameter exists mostly \
    for offline testing.
    :param download: By default all the files in a package's archive are \
    downloaded. This parameter allows you to turn this feature off.
    
    """
    import winsync
    import winsync.lib.rget as rget
    import winsync.lib.config as config
    import os.path
    import shutil
    import subprocess
    import time
    
    winsync_location = os.path.dirname( winsync.__file__ )
    config.init_config( winsync_location )
    config.init_sysinfo()
    config.logger = installer.logger
    
    removed = False
    
    rget.start_session()

    original_dir = os.getcwd()

    try:
        
        flip_uac()

        if get_pkg_info:
            rget.download_info( package_name )
    
        installer._set_info( package_name, fake_download=(not download) )
        os.chdir(installer.files_dir)
        
        #Download all the files from the repository if we are 
        #going to test the install() method
        if 'install' in test:
            installer._download_from_repo()
            
        #Perform the tests
        for method in test:
            installer.logger.info( 'Beginning '+method )
            ret = getattr(installer, method)()
            installer.logger.info( 'Finished {} with the result: {}'.format(
                                   method, ret ) )
            if not ret:
                #check() == False after removing a package is not an error
                if not (removed and method == 'check'):
                    installer.logger.error( method.capitalize()+' failed!' )
                    return
                
            #Keep track of when we remove package, so when check() == False will
            #not report an error.
            if method == 'remove':
                removed = True
            else:
                removed = False
            
            #Pause because some settings need time to sync
            time.sleep( .5 )
            
        os.chdir(original_dir)
        shutil.rmtree( installer.files_dir )
    
    finally:
        flip_uac()
        
        #Gaurentee that the directory is reset
        os.chdir(original_dir)

        #Make sure we end the session with the repository
        rget.end_session()

def wget( url, out_file, options=None, invisible=False, cookies_file=None ):
    """This function allows for fine grained access to the wget program. This
    program is what performs all the downloading in the system. The wget
    program has many features an capabilities. To learn more about what
    it can do examine the
    `wget manual <http://www.gnu.org/software/wget/manual/wget.html>`_.
    
    :param url: The URL is to be accessed (don't forget the protocol).
    :param out_file: A string specifying where to store the downloaded \
    resource.
    :param options: A sequence of additional options given to the wget \
    program. For example, you may want to specify \
    ``['--continue', '--tries', '5']``, so that interrupted downloads are \
    retried 5 times, and only the undownloaded parts are finished instead of \
    re-downloading the whole file.
    :param invisible: When True no information is printed to the screen.
    :param cookies_file: If accessing a website that requires a login, you \
    will need to store the session cookies in a file. This parameter is a \
    the file path to that file.

    """
    import winsync.lib.config as config
    import os.path
    import subprocess
    
    wget_path = os.path.join( config.lib_dir, 'exec', 'wget.exe' )
    
    #Make sure we can find the wget command!
    if not os.path.exists( wget_path ):
        raise WinsyncException( 'Could not locate the wget program. '
                                'Tried ' + wget_path )
        
    #Make sure that the options parameter is not a string type
    assert not isinstance( options, str )
    assert not isinstance( options, bytes )
    
    #Start building the command list.
    cmd = [wget_path]
    
    #If we are not showing the window set wget to non-verbose mode
    if invisible:
        cmd.append( '-nv' )

    #If additional options passed in, add it to the list
    if options is not None:
        cmd += options
        
    #If the user specified a cookies file use it
    if cookies_file is not None:
        if not os.path.exists( cookies_file ):
            raise IOError( 'Could not find the specified cookies '
                           'file: '+cookies_file )
        else:
            cmd += ['--load-cookies', cookies_file]
    
    #Finally, add the url and where to store the downloaded file.
    cmd += [url, '-O', out_file]
    
    #config.logger.debug( 'Executing: ' + ' '.join( cmd ) )
    
    #Run wget
    if invisible:
        proc = subprocess.Popen( cmd, stderr=subprocess.PIPE )
    else:
        proc = subprocess.Popen( cmd )
    
    proc.wait()
    
    if proc.returncode != 0:
        if invisible:
            msg = 'The wget command failed. Reason:\n{}'.format(
                proc.stderr.read().decode('UTF-8'))
            raise WinsyncException( msg )
        else:
            raise subprocess.CalledProcessError( proc.returncode, cmd, '' )

def uninstall_info( key_name, check_display_name=True ):
    """This function will return a dictionary of the values in the
    uninstall key found in the Windows registry matching the given regular
    expression in key_name.
    
    A lot of programs, store a GUID as the key name. In
    which case you will need to look through all keys and examine the
    "DisplayName" value. This value is contains the program name shown in the
    *Add and Remove Progams* dialog. About half the time the key's name and
    "DisplayName" match, but just as often they don't. If you set the
    ``check_display_name`` parameter to False, it will not examine the
    "DisplayName" value of all the uninstall keys. This may make the function
    much faster on systems with many installed programs. Only do this if you
    know your program key name and  "DisplayName" match. To manually examine
    uninstall information is not always easy. The uninstall information can
    almost always be found in the registry at:
    
    ``HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall``
        
    For some examples of how to use Windows' uninstall information,
    see :func:`uninstall_exists` and :func:`uninstall_cmd`.
    
    Note, this function works on both 32 and 64 bit systems.

    :param key_name: A string containing a regular expression. This \
    function uses :func:`re.match` to test for the correct program entry.
    :param check_display_name: When True the DisplayName field of the \
    registry keys is used to determine the key name (see the discussion \
    above).
    :return: A dictionary representing the program's uninstall information \
    from the registry will be returned. The registry value names are the \
    keys, and their associated data are the values. If no match is found then \
    None is returned.
    
    """
    from winreg import OpenKey, EnumKey, EnumValue, QueryValueEx
    from winreg import KEY_READ, KEY_WOW64_64KEY, KEY_WOW64_32KEY
    from winreg import HKEY_LOCAL_MACHINE, HKEY_USERS
    

    #Going through the registry twice once on the 64bit view and agian
    #using the 32bit view is the recomended by microsoft.
    for view in [KEY_WOW64_32KEY, KEY_WOW64_64KEY]:
        #All of the 'Add and Remove Programs' entries are under this key
        uninstall_tree = OpenKey( HKEY_LOCAL_MACHINE,
                                  r'SOFTWARE\Microsoft\Windows'
                                  r'\CurrentVersion\Uninstall',
                                  0, KEY_READ | view )
                                  
        value = _uninstall_look_under( uninstall_tree, key_name, 
                                       check_display_name )
        
        #If we found something then we are done
        if value is not None:
            return value

            
    #Looking in the standard place failed, We now need to enumerate
    #HKEY_USERS and examine all the SID's under it. We still have to deal with
    #the 32 bit vs. 64 bit problem.
    for view in [KEY_WOW64_32KEY, KEY_WOW64_64KEY]:
        try:
            i = 0
            while True:
                sub_key = EnumKey(HKEY_USERS, i )
                i = i + 1

                try:
                    uninstall_tree = OpenKey( HKEY_USERS,
                                              sub_key + r'\SOFTWARE'
                                              r'\Microsoft\Windows'
                                              r'\CurrentVersion\Uninstall',
                                              0, KEY_READ | view )
                except WindowsError:
                    #This HKEY_USERS subkey does not contain the uninstall tree
                    continue
                    
                value = _uninstall_look_under( uninstall_tree, key_name,
                                               check_display_name )

                #If we found something then we are done
                if value is not None:
                    return value

        except WindowsError:
            #This error just means that we have finished the enumeration OR
            #that the HKEY_USERS key does not contain the uninstall tree.
            #Either way this is not an error.
            pass
            
    #We could not find the information
    return None
        
def _uninstall_look_under( uninstall_tree, key_name, check_display_name=True ):
    """Multiple root keys have to be examined when searching for an uninstall
    entry. To make the looping easier, the actual looking part is encapsulated
    within this function.
    
    This function takes a top-level key that corresponds to
    *\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall and searches its
    children for a match.
    
    This function's return values and other parameters follow the rules laid
    out by the uninstall_info() function.
    """
    from winreg import OpenKey, EnumKey, EnumValue, QueryValueEx
    import re
    
    key_pattern = re.compile( key_name )
    
    #Loop through looking at all the names of the subkeys for a match for the
    #key_name parameter.
    #Looping through all the keys in _winreg is retarded. The stop condition
    #is an exception, hence the try ... except and the infinit loop
    try:
        i = 0
        while True:
            subkey = EnumKey(uninstall_tree, i )
            i = i + 1
            
            #We use this variable in case check_display_name is true, then
            #we won't disturb the all important subkey variable
            value_to_check = subkey
            
            #Grab up the DisplayName value from the registry if necessary
            if check_display_name:
                key = OpenKey( uninstall_tree, subkey )
                try:
                    value_to_check, type = QueryValueEx( key, 'DisplayName' )
                except WindowsError:
                    #This key does not have a DisplayName value, this is not
                    #supposed to happen but it does. This usually occurs
                    #with Windows Updates, or bad uninstallers. It is safe
                    #to ignore this error.
                    pass
                finally:
                    key.Close()

            #If value_to_check's name matches the key
            #pattern we have a match
            if key_pattern.match( value_to_check ):
                key = OpenKey( uninstall_tree, subkey )
                index = 0
                info = {}
                try:
                    while True:
                        #Iterate over every value
                        name, data, type = EnumValue( key, index )
                        
                        #Add the name and data it to the dictionary
                        info[name] = data
                        
                        #Add one to the iterator
                        index = index + 1
                except WindowsError:
                    #Return the information we have found
                    return info
                finally:
                    key.Close()
    except WindowsError:
        #We failed to find the key
        pass
    finally:
        uninstall_tree.Close()

    #If we got to here then we failed to find a match
    return None

def uninstall_exists( key_name, version=None, check_display_name=True ):
    """This function will return True if an uninstall entry can be found in the
    windows registry that matches the key_name and version (if given). This
    function is an easy and fast way to check if most programs are installed
    in Windows. For example, you could check if Firefox is installed like
    this::
    
        def check(self):
            return util.uninstall_exists( 'Firefox.*' )
            
    :param version: A string containing a regular expression used to test \
    against the program's version information. Note, this function uses \
    :func:`re.match` to test if the versions are equivelent.
    :return: True if an appropriate entry was found, False otherwise.
    
    For more information on the parameters and other issues see 
    :func:`~winsync.lib.util.uninstall_info`.
    
    """
    import re
    info = uninstall_info( key_name, check_display_name )
    
    if info:
        if version:
            #Sometimes the version number is stored in DisplayVersion 
            #instead of the Version value
            if 'Version' not in info:
                if 'DisplayVersion' in info:
                    info['Version'] = info['DisplayVersion']
                else:
                    #The user asked for an exact version, the
                    #registry lacks any version information,
                    #therefore the test failed
                    return False

                return re.match( version, info['Version'] ) is not None
        else:
            return True
    else:
        return False

def uninstall_cmd( key_name, check_display_name=True ):
    """This function will return the uninstall command found in the
    windows registry matching the key_name. The string
    returned by this function is what is used by the "Add and Remove Progams"
    dialog to uninstall programs. Since that method is not designed to use
    silent uninstallation you will often have to alter the returned string
    giving it the appropriate parameters. For example, the following
    function uninstalls the
    `Foxit Reader <http://www.foxitsoftware.com/Secure_PDF_Reader/>`_
    program::
    
        def remove(self):
            #Get the uninstall command string
            cmd = util.uninstall_cmd( 'Foxit Reader.*' )
            
            #If we could not find the command, then fail
            if cmd is None:
                return False

            #Replace the update switch with the remove switch,
            #and break it apart based on spaces
            cmd = cmd.replace( '/I', '/x' ).split( ' ' )

            #Add some extras to suppress the GUI and rebooting
            cmd += ['/passive', '/norestart']

            #Run the uninstall program
            subprocess.check_call( cmd )
            
            return True

    For more information on the parameters and other issues see 
    :func:`~winsync.lib.util.uninstall_info`.
    
    :return: A string containing the uninstall string from from the Windows \
    registry, or None if the entry could not be found.
    """
    info = uninstall_info( key_name, check_display_name )
    if isinstance( info, dict ):
        return info['UninstallString']
    else:
        return False

def task_kill( task ):
    """This function uses the ``taskkill`` program to terminate a
    the given program name forcefully. It is a convenience function
    to wrap up some logic.
    
    :param task: The file name of the program to terminate, i.e. 'python.exe'.
    :raise subprocess.CalledProcessError: If the ``taskkill`` program fails \
    for any reason other than the fact that the program is not currently \
    running this error is raised.
    """
    import subprocess
    
    try:
        subprocess.check_output( ['taskkill', '/f', '/im', task], 
                                 stderr=subprocess.STDOUT )
    except subprocess.CalledProcessError as cpe:
        #128 means the task is not running
        if cpe.returncode != 128: raise
        
def extract7z( archive, dest_dir ):
    """Extract the given archive into the given directory using 7-Zip.
    The 7-Zip program works with many types of file archives including: zip,
    tar, bzip, and rar. 7-Zip automatically detects what type of archive it
    is and how to properly extract it. The command-line program is include with
    the py:mod:`winsync` module.
    
    This function does have one side effect. It creates a log in the same
    directory as the archive file called ``7z.log``. In the event that this
    function fails, this file is left alone to help you determine what went
    wrong. If this function succeeds, then the file is cleaned up.
    
    For more information about the 7-Zip program head over to
    http://www.7-zip.org
    
    :param archive: A string specifying what archive file to be undone.
    :param dest_dir: A string specifying what directory to extract the file \
    into.
    :raise winsync.lib.WinsyncException: This exception is raised for various \
    reasons. The particular reasoning behind the failure can be found in the \
    exception's message.
    """
    import subprocess
    import os
    import os.path
   
    if not os.path.exists( archive ):
        raise WinsyncException('The file path of the archive does not exist.')
    elif not os.path.exists( dest_dir ):
        raise WinsyncException('The destination directory does not exist.')
    elif not os.path.isdir( dest_dir ):
        raise WinsyncException('The destination specified is not a directory.')
    
    curdir = os.getcwd()
    os.chdir( dest_dir )

    prog_path = os.path.join( config.lib_dir, 'exec', '7z.exe' )
    log_path = os.path.join( os.path.dirname( archive ), '7z.log' )
    
    try:
        with open( log_path, 'w' ) as f:
            sevenz = subprocess.Popen( [prog_path, 'x', '-y', '-bd', archive],
                                       stdout=f )
            sevenz.communicate()
            
            if sevenz.returncode != 0:
                raise WinsyncException( 'Failed to unzip the file properly, '
                                        'check the log at ' + log_path )
                
        #If there is no error then get rid of the log file
        os.remove( log_path )
    finally:
        os.chdir( curdir )

        
def create_shortcut( lnk_file, target_path, arguments=None,
                     working_directory=None, description=None,
                     hotkey=None, icon_location=None, icon_index=None,
                     window_style=None ):
    """This function creates a Windows shortcut.
    There is not a dependency-less method for creating Windows shortcuts in
    Python, so this function implements a round-about method for creating them.
    It creates a temporary JScript file and executes Windows Scripting Host to
    actually do the shortcut creation. Here is an example how you would use
    this function::
    
        #Gather the needed paths for the shortcut
        lnk = os.path.join( os.environ['ALLUSERSPROFILE'], 'Start Menu',
                            'Programs', 'emacs.lnk' )
        target = os.path.join( r'C:\\emacs\\bin\\runemacs.exe' )
        icon = os.path.join( r'C:\\emacs\\etc\\icons\\emacs.ico' )
        
        #Create the shortcut
        util.create_shortcut( lnk, target, icon_location=icon )

    
    Because the Windows API is being invoked to create the shortcut the 
    arguments to this function closely corresponds to the 
    `CreateShortcut <http://msdn.microsoft.com/en-us/library/xk6kst2k(v=vs.84).aspx>`_
    scripting object. The arguments have the following meaning:
    
    :param lnk_file: A string indicating the file path of the shortcut \
    file to be created (should end with a .lnk extension )
    :param target_path: A string indicating file or directory the shortcut \
    will point to.
    :param arguments: A string representing any arguments that are to be \
    passed to the target. For example a shortcut to python.exe that runs a \
    module would need the argument string '-m module_name'.
    :param working_directory: A string indicating the directory the target \
    will start in (defaults to the directory containing the target path).
    :param description: A string that gives a brief description of the \
    shortcut, this message appears a the shortcut's tool-tip.
    :param hotkey: A string representing the global key combination that will \
    be associated with this shortcut. Can be any of the following: ALT+, \
    CTRL+, SHIFT+, and/or a keyname. For example, 'CTRL+ALT+SHIFT+X' is a \
    valid value.
    :param icon_location: A string indicating the path to the file containing \
    the shortcut's icon. By default is the target path is used.
    :param icon_index: The zero based index of the icon inside the above \
    mentioned file (default is 0).
    :param window_style: Set the style of the window that will be shown. It \
    must be either: 1 which displays the window in a "normal" state, 3 which \
    displays a maximized window, or 7 which displays a minimized window.
    
    """
    import os, os.path, re, subprocess, uuid
    
    #JScript needs / converted to \ and \ represented as \\
    #This function makes the necessary adjustments
    def fix_slashes(var):
        if isinstance( var, str ):
            var = var.replace( '/', '\\' ).replace( '\\', '\\\\' )
        return var

    lnk_file = fix_slashes( lnk_file )
    target_path = fix_slashes( target_path )
    arguments = fix_slashes( arguments )
    working_directory = fix_slashes( working_directory )
    description = fix_slashes( description )
    hotkey = fix_slashes( hotkey )
    icon_location = fix_slashes( icon_location )
    
    
    #Figure out the temporary script file's path and name
    script_file = os.path.join( os.environ['temp'], str(uuid.uuid4())+'.js' )
    
    #Set the default values if necessary
    if not os.path.exists( target_path ):
        raise WinsyncException( 'Cannot create a shortcut to a '
                                 'nonexistent file.' )
    if not working_directory:
        working_directory = os.path.dirname( target_path )
    if not icon_location:
        icon_location = target_path
    if not icon_index:
        icon_index = 0

    #Create the JScript file
    with open( script_file, 'w' ) as script:
        script.write( 'Shell = new ActiveXObject("WScript.Shell");\n' )
        script.write( 'link = Shell.CreateShortcut("{}");\n'.format(lnk_file))
        script.write( 'link.TargetPath = "{}";\n'.format( target_path ) )
        script.write( 'link.WorkingDirectory = '
                      '"{}";\n'.format( working_directory ) )
        
        #Set the optional properties
        if arguments:
            script.write( 'link.Arguments = "{}";\n'.format( arguments ) )
        if icon_location:
            script.write( 'link.IconLocation = "{},{}";\n'.format(
                                    icon_location, icon_index ) )
        if description:
            script.write( 'link.Description = "{}";\n'.format( description ) )
        if hotkey:
            script.write( 'link.HotKey = "{}";\n'.format( hotkey ) )
        if window_style:
            script.write( 'link.WindowStyle = {};\n'.format( window_style ) )

        script.write( 'link.Save();\n' )

    #We need to make sure the script file is cleaned up, so wrap the process
    #in a try-finally block.
    try:
        #Run our generated JScript file.
        cscript = subprocess.Popen( ['cscript', '/nologo', script_file],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT )
        (stdout, stderr) = cscript.communicate()
        
        if cscript.returncode != 0:
            raise WinsyncException('Failed to create shortcut. Reason:\n'
                                    '{}'.format(stdout.decode('ascii')))
    finally:
        #Cleanup the script file
        os.remove( script_file )
    
def cacls( filename, options ):
    """This function is a convenient wrapper for the CACLS program. The CACLS
    program can be notoriously difficult to script because it sometimes
    wants input but not always. This function takes much of the headache out
    of using it. Here is an example::

        link = r'C:\\Documents and Settings\\All Users\\Desktop\\jEdit.lnk'
        util.cacls( link, ['/E', '/P', 'Student:R'] )
        util.cacls( link, ['/E', '/G', 'Administrator:F'] )
        util.cacls( link, ['/E', '/G', 'SYSTEM:F'] )

    :param filename: This string represents what file or directory to run \
    CACLS on.
    :param options: A list of options to pass to the CACLS program.
    """
    import winsync.lib.config as config
    import subprocess
    
    cmdline = ['cacls', filename]
    cmdline.extend( options )
    
    #If you are not editing a permission, then you must allow it to go through
    #by typing y on the command line. This variable will simulate it.
    if '/E' not in options and '/e' not in options:
        input = b'y\n'
    else:
        input = b''
    
    with subprocess.Popen( cmdline, stdin=subprocess.PIPE, 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT ) as proc:
        (stdout, stderr) = proc.communicate( input )
    
        if proc.returncode != 0:
            config.logger.error('CACLS failed, reason '
                                'given: {}'.format(stdout.decode('ascii')))
            raise subprocess.CalledProcessError( returncode=proc.returncode,
                                                 cmd=cmdline, output=stdout )

def rcacls( directory, options, topdown=False ):
    """This function calls the CACLS program on all the files and directories
    within the given directory (including the passed in directory). The
    options parameter should be a list of options to be passed onto the CACLS
    program. Essentially this function does a :func:`os.walk` across all the
    files and subdirectories, starting the bottom of the tree, calling the
    :func:`cacls()` function on each one.
    
    You might wonder why you should use this function instead of just using the
    /T option in CACLS. Basically, you can easily run into situations where you
    lock a directory but not the files and subdirectories inside of it.
    
    For more information see :func:`cacls`.
    
    :param topdown: This specifies the direction to walk through the directory.
    """
    import os, os.path
    
    for (dirpath, dirnames, filenames) in os.walk( directory, topdown=False):
        print( 'Processing directory: '+dirpath )
        for fname in filenames:
            cacls( os.path.join( dirpath, fname ), options )
        
        for fname in dirnames:
            cacls( os.path.join( dirpath, fname ), options )

uac_installed = None
def flip_uac():
    """This function turns UAC on or off depending on its state. When the
    function is first called, it first determines if UAC is installed and
    what its current state is. If UAC is enabled, it will turn it off. If
    UAC is off then it will leave it alone.
    
    When called a second time this function will return UAC to the state
    it first found it in.
    
    If the system does not have UAC (e.g. Windows XP) then this function
    will do nothing.
    """
    import subprocess
    
    global uac_installed
    global uac_state

    #This is the first run of the function
    if uac_installed is None:
        try:
            state = subprocess.check_output(['reg', 'QUERY', 
                                             'HKEY_LOCAL_MACHINE\\SOFTWARE\\'
                                             'Microsoft\\Windows\\'
                                             'CurrentVersion\\Policies\\'
                                             'System',
                                              '/v', 'EnableLUA'] )
        except:
            #This occurs when the machine does not have UAC
            uac_installed = False
            return

        state = state.decode( 'ascii' )
        
        #If there was no error then UAC is installed
        uac_installed = 'ERROR' not in state
        
        if '0x1' in state:
            uac_state = True
        else:
            #Since the initial condition is that UAC exists but
            #it is turned off, then just don't do any flipping
            uac_state = False
            uac_installed = False
            

    if uac_installed:
        #Rotate the state so we set it to its oposite
        uac_state = not uac_state
        
        subprocess.check_call( ['reg', 'ADD', 
                                'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\'
                                'Windows\\CurrentVersion\\Policies\\System',
                                '/v', 'EnableLUA', '/t', 'REG_DWORD', '/d',
                                str(int(uac_state)), '/f'],
                                stdout=subprocess.PIPE )


#Stubs until I can update
def countdown(seconds, message='Waiting {} seconds'):
    pass
def create_shortcut( lnk_file, target_path, arguments=None,
                     working_directory=None, description=None,
                     hotkey=None, icon_location=None, icon_index=None,
                     window_style=None ):
    pass

def is_admin():
    pass

def get_special_folder(name):
    return ''
