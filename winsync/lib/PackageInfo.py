from winsync.lib.config import logger
import winsync.lib.util as util
import os.path

#Import the proper config parser, for python 2 or 3
try:
    #python-2
    from ConfigParser import SafeConfigParser
except ImportError:
    #python-3
    from configparser import SafeConfigParser

class PackageInfo:
    def __init__(self, pkg_id, pkg_dict={}, skip_dependents=False, 
                  skip_download=False, make_empty=False,
                  info_dir=None):
        """Construct the object using the given package id. The id should
        correspond with a package info ini file. From this ini file all of the
        package's information will be extracted.
        
        The package will add itself to the pkg_dict using the id as the key
        and this object as the value.
        
        Dependent packages will automatically be created and added as needed
        to the pkg_dict, unless the  skip_dependents parameter is set to True.
        
        Furthermore, the package info ini files are usually stored on a remote
        server. The correct file will automatically be downloaded. However,
        if skip_download parameter is True then it will look for the file in
        the local pkg-info directory instead. This directory is stored as
        winsync.lib.config.pkg_dir, but you can specify another directory using
        the info_dir parameter.
        
        There are certain cases, for example when you are creating an new
        package, that you will not want to associate this object with a
        package info ini file. To create such an object you simply need
        to specify an id and set the make_empty parameter to True.
        """
        global logger
        import winsync.lib.rget as rget
        import winsync.lib.config as config
        
        self.id = pkg_id
        self.pkg_dict = pkg_dict
        self.ini_file = self.id + '.ini'
        self.method = 'install'
        self.parser = SafeConfigParser()
        
        if info_dir:
            self.pkg_info_file = os.path.join(info_dir, self.ini_file)
        else:
            self.pkg_info_file = os.path.join(config.pkg_dir, self.ini_file)
        
        #This occurs when this object does not yet have an associated file
        if make_empty:
            return
        
        #Download the ini package file
        if not skip_download:
            logger.info("Downloading package {}'s ini file".format(self.id))
            rget.download_info(self.id)
                
        if not os.path.exists(self.pkg_info_file):
            raise IOError('The package file does not exist: '
                           '{}'.format(self.pkg_info_file))

        
        #Read out the information in the ini file
        self.parser.read(self.pkg_info_file)
        
        #Add fields to this object using values from the pkg info file
        self.check_option('name', required=True)
        self.check_option('installer', required=True)
        self.check_option('version', required=True)
        self.check_option('priority', required=True, is_int=True)
        self.check_option('reboot', default=False, is_boolean=True)
        self.check_option('meta', default=False, is_boolean=True)
        self.check_option('files', is_expression=True, default='[]')
        self.check_option('depend', is_expression=True, default='[]')
        self.check_option('chain', is_expression=True, default='[]')
        
        #This is a list of all the packages the depend on this package
        self.source = []
        
        #Add this package to the global repository of packages
        if self.pkg_dict is not None:
            self.pkg_dict[self.id] = self
        
        #Bulid the dependency packages
        if not skip_dependents:
            self.build_dependencies()
            self.build_chained()
        
    def __lt__(self, pkg):
        return self.id < pkg.id

    def check_option(self, option, required=False, default=None,
                       is_boolean=False, is_int=False,
                       is_expression=False):
        """Check that the ini file has the option, and make it a field. There
        are several optional parameters. The required parameter specifies
        whether or not the option must exist. If this parameter is true, and the
        option does not exist a ConfigParser.ParsingError is raised. The
        default parameter specifies what value an option should have if it is
        not specified in the file. The is_xxx parameters specify how to
        interpret the value of the options. They are mutually exclusive.
        """

        #See if the option exists
        if not self.parser.has_option('package', option):
            #If the option did not exist in the file but it is
            #required then emit an error
            if required:
                err_msg = 'Invalid package info file, no "{}" field in file {}.'.format(option, self.ini_file)
                logger.critical(err_msg)
                raise ParsingError(err_msg)

            #This is an optional value, so set the default
            #value to what was passed in or None
            else:
                self.parser.set('package', option, str(default))
            
        if is_boolean:
            #Add the field as a boolean value
            self.__dict__[option.lower()] = self.parser.getboolean('package', option)
        elif is_int:
            #Add the field as a boolean value
            self.__dict__[option.lower()] = self.parser.getint('package', option)
        elif is_expression:
            #Add the field by evaluating the expression
            self.__dict__[option.lower()] = eval(self.parser.get('package', option))
        else:
            #Add the field as a string value
            self.__dict__[option.lower()] = self.parser.get('package', option)
            
    def build_dependencies(self):
        """This function goes through the list of dependents
        found in the "Depend" field of the package info file. It then guarentees
        that the dependents have a higher priority than this package. If the
        dependent package object does not as yet exits it is at this time
        created.
        """
        global logger
        
        logger.debug('Processing dependencies for ' + self.id)
        
        #If there are no dependencies leave early
        if not self.depend:
            logger.debug('Found 0 dependents for package ' + self.id)
            return

        logger.debug('Found {} dependencies for package {}'.format(
                      len(self.depend), self.id))
        
        #Make a Package object for each of the dependencies listed
        for d in self.depend:
            #if the package not is already in the dictionary, then
            #make a new object
            if d not in self.pkg_dict:
                pkg = PackageInfo(d, self.pkg_dict)
            else:
                pkg = self.pkg_dict[d]
                
                
            #Make sure that the dependecy package has a
            #higher priority than this package so it installs first
            if pkg.priority <= self.priority:
                pkg.priority = self.priority + 1
                
                #Because dependencies can be chained we need to
                #recursively rebuild the package's dependency list
                #effectively updating all their priorities.
                #This takes care of cases where A depends on B 
                #which depends on C.
                pkg.build_dependencies()
            
            #Add this package as a source for the dependency
            if not self.id in pkg.source:
                logger.debug('Package {} became a source for package {}'.format(
                              self.id, pkg.id))
                pkg.source.append(self.id)
            
    def build_chained(self):
        """This function goes through the list of chained packages
        found in the "Chain" field of the package info file. It then guarentees
        that the packages have a lower priority than this package. If the
        chained package object does not as yet exits it is at this time
        created.
        """
        global logger
        
        logger.debug('Processing chains for ' + self.id)
        
        #If there are no dependencies leave early
        if not self.chain:
            logger.debug('Found 0 chains for package ' + self.id)
            return

        logger.debug('Found {} chains for package {}'.format(
                      len(self.chain), self.id))
        
        #Make a Package object for each of the dependents listed
        for d in self.chain:
            #if the package not is already in the dictionary, then
            #make a new object
            if d not in self.pkg_dict:
                pkg = PackageInfo(d, self.pkg_dict)
            else:
                pkg = self.pkg_dict[d]
                
            #Make sure that the dependant package has a
            #higher priority than this package so it installs first
            if pkg.priority >= self.priority:
                pkg.priority = self.priority - 1
                
                #Because chains can be in turn be chained we need to
                #recursively rebuild the package's chain list
                #effectively updating all their priorities.
                #This takes care of cases where A chains B 
                #which chains C.
                pkg.build_chained()
            
            #Add this package as a source for the chained package
            if not self.id in pkg.source:
                logger.debug('Package {} became a source for package {}'.format(
                              self.id, pkg.id))
                pkg.source.append(self.id)

    def save_to_cache(self, parser):
        """This method will ouput this object into the given ConfigParser.
        The purpose of this method is to add this package to the global cache.
        """
        #If the install method was remove, then remove this section from the 
        #the file
        if self.method == 'remove':
            parser.remove_section(self.id)
            return
        
        #The cache file may already have this package listed, in which case we
        #will just update. But if it is not there add the section.
        if not parser.has_section(self.id):
            parser.add_section(self.id)
        
        #Set all the options
        parser.set(self.id, 'name', self.name)
        parser.set(self.id, 'installer', self.installer)
        parser.set(self.id, 'version', self.version)
        parser.set(self.id, 'priority', str(self.priority))
        parser.set(self.id, 'meta', str(self.meta))
    
    def write_to_info_file(self, parser=None):
        """This method will write all the pertient information in this object
        to the appropriate package info ini file. If the package was origianlly
        read out of an ini file, then the object has a parser attribute. This
        attribute will be updated then written to the appropriate file. You
        can specify your own ConfigParser by passing it in through the parser
        parameter.
        """
        if parser is None:
            parser = self.parser

        if not parser.has_section('package'):
            parser.add_section('package')
        
        #Set all the required the options
        parser.set('package', 'name', self.name)
        parser.set('package', 'version', str(self.version))
        parser.set('package', 'priority', str(self.priority))
        parser.set('package', 'meta', str(self.meta))
        parser.set('package', 'reboot', str(self.reboot))
        
        if self.installer is None or \
           self.installer == b'' or \
           self.installer == '':
            parser.set('package', 'installer', 'None')
        else:
            parser.set('package', 'installer', self.installer)
        
        #Set the optional parameters if they are defined
        if hasattr(self, 'depend') and self.depend is not []:
            parser.set('package', 'depend', repr(sorted(self.depend)))
        if hasattr(self, 'chain') and self.chain is not []:
            parser.set('package', 'chain', repr(sorted(self.chain)))
        if hasattr(self, 'files') and self.files is not []:
            parser.set('package', 'files', repr(sorted(self.files)))
        
        #Write the information file
        with open(self.pkg_info_file, 'w', encoding='utf-8') as pkg_file:
            parser.write(pkg_file)
        
    def add_to_queue(self, prioity_queue):
        """This method adds this object to the given priority queue.
        """
        
        #Python priority queues start with the lowest number and go to the
        #highest. So the simple fix for this is to negate the priority to
        #maintain the intended order.
        prioity_queue.put((-self.priority, self))
        
    def update_from_form(self, form):
        """This method updates the fields based on a flask form.
        """
        self.name = form.get('name', type=str)
        self.installer = form.get('installer', type=str)
        self.version = form.get('version', type=str)
        self.priority = form.get('priority', type=int)
        self.meta = (form.get('meta') == 'True')
        self.reboot = (form.get('reboot') == 'True')
        
        #Flask returns the list as unicode characters this creates
        #problems when reading/writting files between python 2 and 3
        #To fix this we are re-encoding them into ascii
        self.depend = sorted(map(lambda x: x.encode('ascii'), 
                                   form.getlist('depend')))
        self.chain = sorted(map(lambda x: x.encode('ascii'), 
                                  form.getlist('chain')))
    
    def __str__(self):
        return self.name
