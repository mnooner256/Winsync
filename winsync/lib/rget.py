
session_file = None

def get_from_repo( suffix, out_file='-', invisible=False, wget_options=[],
                    **post_kwargs ):
    """This function uses util.wget() to download things from the repository.
    
    The suffix parameter specifies what comes after the value stored in the
    config.repo variable. For example, get a file from
    "http://example.com/repo/package", with the config.repo being
    "http://example.com/repo/" the suffix parameter should to be "package".
    
    The out_file parameter should be a string that specifies where to store
    the returned file. By default wget is instructed to simply push the
    file to stdout. This is usually not the desired behavior.
    
    When the invisible parameter is True no progress is displayed.
    
    The wget_options parameter specifies additional parameters to give to
    the wget program.
    
    Finally, any more keyword arguments are treated as name=value pairs. This
    data will then be POSTed to the repository. The names and values will be
    properly URL encoded, i.e. &'s, ='s, etc. will be escaped using the
    urllib.parse.quote() function.
    """
    import winsync.lib.config as config
    import winsync.lib.util as util
    import os
    from itertools import starmap
    from urllib.parse import quote
    
    global session_file
    
    #Calculate the URL
    url = '{0}/{1}'.format(config.repo, suffix)
    
    #Calculate the query string to POST, make sure the 
    #items and values are properly URL escaped
    query_str = '&'.join(starmap(lambda x,y: '{0}={1}'.format(quote(x),
                                                               quote(str(y))),
                                 post_kwargs.items()))

    #Add the query string to the options passed to wget if there were options
    if query_str:
        wget_options += ['--post-data', query_str]
    
    #If the out_file is stdout, i.e. '-', then make this invisible
    invisible = (invisible or out_file == '-')
    
    #If the session file exists then pass it along to wget
    if os.path.exists( session_file ):
        cookies_file = session_file
    else:
        cookies_file = None
    
    #Attempt to download the file
    try:
        util.wget( url, out_file, options=wget_options, 
                   cookies_file=cookies_file, 
                   invisible=invisible )
    except:
        #Cleanup the file if it has been written
        if os.path.exists( out_file ):
            os.remove( out_file )
        raise

def start_session():
    """Start a session with the remote repository. This function will use wget
    to log in to the repository using the var/key/repo.password file. If this
    file does not exist then this function will attempt to self register. If
    either self registery or logging in fails then an exception is thrown.
    """
    import os.path
    import winsync.lib.config as config
    import winsync.lib.util as util
    import os
    import socket
    import urllib.parse
    import uuid
    
    global session_file
    
    #Calculate the locations of the password and session files
    session_file = os.path.join( config.var_dir, 'session_file' )
    key_dir = os.path.join( config.var_dir, 'key' )
    password_file = os.path.join( key_dir, 'repo.password' )
       
    #If the password file does not exist then try self-registering
    if not os.path.exists( password_file ):
        try:
            #The login name is composed of a uuid and the machine name
            id = urllib.parse.quote( str(uuid.uuid4()) )
            machine_name = urllib.parse.quote( socket.gethostname() )
            
            if not os.path.exists( key_dir ):
                os.mkdir( key_dir )

            get_from_repo( 'self-register', password_file, name=machine_name,
                           uuid=id )
        except:
            #Sometimes the file gets written even when there is an error
            #in this case get rid of it
            if os.path.exists( password_file ):
                os.remove( password_file )
            raise
    
    #Read the password file
    with open( password_file ) as pf:
        key = pf.read()
        
    #Get the field for the POST
    machine_name, id, password = key.split( ':', 2 )
    
    try:
        get_from_repo( 'start-session', '-',
                       wget_options=['--keep-session-cookies',
                                     '--save-cookies',
                                     session_file ],
                       name=machine_name,
                       uuid=id, password=password )
    except:
        #Sometimes the files gets written even when there is an error
        #in this case get rid of them
        if os.path.exists( session_file ):
            os.remove( session_file )
        
        raise

def end_session():
    """This function logs out of the remote repository."""
    import os
    import os.path
    import winsync.lib.config as config
    
    get_from_repo( 'end-session', '-' )
    os.remove( os.path.join( config.var_dir, 'session_file' ) )
    
def download_profiles_ini():
    """This function downloads a new profiles.ini file from the repository
    and places it in the config.etc_dir directory.
    """
    import os.path
    import winsync.lib.config as config
    
    profiles_file = os.path.join( config.etc_dir, 'profiles.ini' )

    get_from_repo( 'profiles.ini', profiles_file, invisible=False )
   
def download_info( id ):
    """This function will download the package information file from the
    repository that matches the given id. The file will be written to the
    config.pkg_dir directory.
    """
    import winsync.lib.config as config
    import os.path
    
    ini_path = os.path.join( config.pkg_dir, id+'.ini' )
    
    get_from_repo( 'download-info/'+id, ini_path, invisible=True )
    
def download_installer( pkg ):
    """This function will download the install script from the repository for
    the package with the given pakcage. The pkg parameter should be a 
    PakcageInfo object.
    """
    import winsync.lib.config as config
    import os.path
    
    file_path = os.path.join( config.cache_dir, pkg.installer )
    
    get_from_repo( 'download-installer/'+pkg.id, file_path, invisible=True )

def download_file( pkg, file ):
    """This function downloads a single file from a package's archive in the
    repository. The pkg parameter should be a PakageInfo object specifing
    what package's archive to access. The file parameter should be a string
    representing the file name. This function will return the name of the
    path to the file.
    """
    import os.path
    
    file_path = os.path.join( pkg.files_dir, file )
    
    get_from_repo( 'download/{0}/{1}'.format( pkg.id, file ), file_path )

    return file_path

def download_archive( pkg ):
    """This function will download all the files in the package's repository.
    The pkg parameter should be a PakcageInfo object. This function will return
    the directory where the packages are stored.
    """
    file_dict = {}
    
    for file in pkg.files:
        path = download_file( pkg, file )
        file_dict[file] = path
        
    pkg.rget_files = file_dict
