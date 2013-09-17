import os
import os.path
import re
import sys
import logging
import logging.config

from winsync.lib import util
from winsync.lib import config

installed_parser = None
logger = None

class WinsyncException(Exception):
    def __init__(self, str):
        Exception.__init__(self, str)

def get_profile_packages():
    """This function analizes the profiles.ini file and returns a list of
    package ids that are appicable to this computer.
    """
    global logger
    from winsync.lib.Profile import get_all_profiles

    #This is where we will store the list of packages
    #that apply to this machine
    package_ids = []

    #Get all the profiles out of the ini file
    profiles = get_all_profiles()

    #Examine each profile and see if it is applicable to this machine
    for profile_id, profile in profiles.items():
        logger.debug('Examining profile ' + profile_id)

        #Actually test to see if we match the profile's description
        if profile.applies():
            logger.info('This machine a member of the '
                        'profile ' + profile_id)

            #Add the list of packages
            package_ids += profile.packages

    return package_ids

def packages_to_install(packages):
    """This function will analyze the ini files for each package in the
    given sequence. It will then construct a dictionary of packages to
    be installed based on a package's Priority, Depends, and Chain
    options.
    """
    global logger
    from winsync.lib.PackageInfo import PackageInfo

    #This will hold all of the processed packages
    pkg_dict = {}

    logger.info('Starting to examine packages')
    for p in packages:
        #From the ini file construct the Package object
        #Some packages may have been constructed already by
        #build_dependencies and build_chained. So skip any
        #packages in the pkg_dict
        if p not in pkg_dict:
            PackageInfo(p, pkg_dict)

    return pkg_dict

def build_queue(package_list):
    """This function builds an install/upgrade/remove priority queue from
    a list of Package objects. The queue garentees several things.
      1. Packages marked for removal are removed from the system first.
      2. A package's dependancies will be installed first
      3. A package's chained dependancies will be installed sometime after
         it is installed."""
    import queue
    global logger

    installer_queue = queue.PriorityQueue()

    for pkg_object in package_list:
        logger.debug('Added package {} to queue.'.format(pkg_object.id))
        pkg_object.add_to_queue(installer_queue)

    return installer_queue

def analyze_installed(packages):
    """This function analyzes the package dictionary versus the installed
    packages file. This will inform the system of what changes that are
    being made.

    Packages that are in the packages dictionary but are not in the installed
    packages file will be installed.

    Packages that are in the packages dictionary and in the installed packages
    file, but whose version numbers are different will be upgraded.

    Packages not in the packages dictionary but are in the installed packages
    file will be removed from the system.

    This function will then returns a priority queues suitable for
    processing. The queue has the packages in the order that actions
    must be taken.
    """
    from configparser import SafeConfigParser, ParsingError
    global installed_parser
    global logger
    from winsync.lib.PackageInfo import PackageInfo

    logger.debug('Analyzing the installed packages.')

    #Load up the installed packages file
    installed_parser = SafeConfigParser()
    installed_parser.read(os.path.join(config.var_dir, 'installed.ini'))

    #Get a list of all the installed packages
    installed = installed_parser.sections()

    for installed_package in installed:
        #If this is true then the package is already installed,
        #it may need upgrading
        if installed_package in packages:
            installed_version = installed_parser.get(installed_package,
                                                     'version')
            if installed_version != packages[installed_package].version:
                logger.debug('Set package {} to '
                             'upgrade'.format(installed_package))
                packages[installed_package].method = 'upgrade'

            else:
                #The file is installed and does not need to be upgraded
                #remove it from dictionary of packages to install
                logger.debug('The package {} is already '
                             'installed.'.format(installed_package))
                del packages[installed_package]

        #If the package is in the file but not in the dict, then it needs
        #to be removed
        else:
            p = PackageInfo(installed_package, packages,
                            skip_dependents=True)
            p.method = 'remove'
            p.priority = 1000
            logger.debug('Set package {} to be '
                         'removed'.format(installed_package))

    return build_queue(packages.values())

def process_queue(queue):
    """This function is the workhorse of this module. This function
    handles handing off to the package installation scripts to perform
    the needed actions. At the end of this function all the packages
    in the given queue have been installed, upgraded, or removed.
    """
    import winsync.lib.rget as rget
    from winsync.lib.config import get_installer_object

    global logger
    global installed_parser


    reboot = False

    while not queue.empty():
        (priority, package) = queue.get()

        #Meta packages have no installation, so short-circuit
        if package.meta:
            if package.method == 'remove':
                package.save_to_cache(installed_parser)
            continue

        #Download the install script
        logger.info('Downloading install script for the {} '
                    'package'.format(package.name))
        rget.download_installer(package)

        #Get the module name from the file name
        (module_name, py) = os.path.splitext(package.installer)

        #Get the Installer object from the module
        installer = get_installer_object(module_name)

        #Make sure an Installer class was instaniated
        if installer == None:
            raise WinsyncException(
                'Could not find a class that inherits from {} in '
                '{}'.format('winsync.lib.util.Install', package.installer))

        #Set info the package may need
        installer._set_info(package,
                            logging.getLogger(package.installer))

        #Check to see if the software is installed
        logger.debug('Checking if {} is {}ed'.format(package,
                                                     package.method))
        if package.method != 'upgrade' and \
           ((package.method == 'remove' and not installer.check()) or \
           (package.method != 'remove' and installer.check())):
            logger.info('Package {1} is already {0}ed, will not '
                         '{0} it'.format(package.method, package))
            package.save_to_cache(installed_parser)
            continue
            
        #We need to switch to the package's downloads directory
        original_dir = os.getcwd()
        os.chdir(package.files_dir)

        #If we are not removing the package, download the files
        #Also this download is skipped if the package is already installed
        if package.method != 'remove':
            logger.info('Downloading the package\'s repository')
            rget.download_archive(package)

        #Time to try and process the installer
        logger.debug('Attempting to {} '
                     '{}.'.format(package.method, package))
        if not getattr(installer, package.method)():
            raise WinsyncException('Package {1} failed to '
                                    '{0}!'.format(package.method, package))

        else:
            logger.debug('Package {1} {0} method reports '
                         'success.'.format(package.method, package))
        
        #Switch the current directory back
        os.chdir(original_dir)
        
        #We need to check that the process really worked
        logger.debug('Checking that the installer functioned correctly')
        if (package.method != 'remove' and not installer.check()) or \
           (package.method == 'remove' and installer.check()):
            raise WinsyncException('Package {1} post-{0} checks '
                                   'failed!'.format(package.method,
                                                    package))
        else:
            #Update the cache with the new package state
            package.save_to_cache(installed_parser)

        #Delete any downloaded files
        installer._cleanup()

        logger.info('Successfully {0}ed {1}'.format(
                     package.method, package))

        #Set the reboot flag if necessary
        if package.reboot:
            reboot = True

    return reboot

def main():
    """This function acts as the driver for this "program."
    """
    import subprocess, sys, traceback
    import winsync.lib.rget as rget
    import winsync.lib.util as util
    global logger
    global installed_parser

    should_reboot = False

    #This allows for the script to executed from somewhere else than
    #the current directory. This is commonly done by web servers.
    module_location = os.path.dirname(os.path.abspath(__file__))

    #Setup the needed paths for the system
    config.init_config(module_location)
    
    #Start logging and make a shortcut to the logger
    config.start_logger()
    logger = config.logger
    logger.debug('Started logging')

    #Inspect the system for profile matching
    config.init_sysinfo()

    #Add the cache and lib directories to the module path
    sys.path.append(os.path.join(config.var_dir, 'cache'))
    sys.path.append(config.lib_dir)

    #Start a session with the repository
    try:
        logger.debug('Starting rget session')
        rget.start_session()
    except:
        logger.critical('Could not start session')
        logger.error(traceback.format_exc())
        
        if not config.gui_mode:
            input('Press the ENTER key to continue...')
        return

    try:
        #Make sure we are have elevated privledges
        if not util.is_admin():
            raise util.WinsyncException('Winsync requires administrative '
                                        'privledges to run.')

        #Get the new profiles.ini file
        logger.debug('Downloading Profiles file')
        rget.download_profiles_ini()

        #From the profiles.ini file figure out what needs to be installed
        #on this particular machine.
        packages = get_profile_packages()

        #Create the Package objects, they will auto-load their depenancies
        package_dict = packages_to_install(packages)

        #Figure out what packages need upgrading, installing, and removing
        install_queue = analyze_installed(package_dict)

        #Actually perform the installation tasks
        should_reboot = process_queue(install_queue)
    except Exception as e:
        logger.exception(e)
        logger.critical('Cannot continue, exiting')
    else:
        logger.info('Finished Successfully')
    finally:
        #Finally, write out the installed.ini file if we got that far.
        if installed_parser:
            with open(os.path.join(config.var_dir, 'installed.ini'), 
                      'w') as file:
                installed_parser.write(file)

        #Logout of the repository
        rget.end_session()

    #Don't wait for input if run within the GUI
    if not config.gui_mode:
        input('Press the ENTER key to continue...')

    if should_reboot:
        subprocess.check_call(['shutdown.exe', '-r'])

if __name__ == '__main__':
    main()
