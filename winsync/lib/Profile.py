from winsync.lib.config import logger
import winsync.lib.config as config
import winsync.lib.util as util
import os.path
import re

#Import the proper config parser, for python 2 or 3
try:
    #python-2
    from ConfigParser import SafeConfigParser
except ImportError:
    #python-3
    from configparser import SafeConfigParser
    
if config.etc_dir:
    profiles_file = os.path.join( config.etc_dir, 'profiles.ini' )
else:
    profiles_file = os.path.abspath( './profiles.ini' )


def get_all_profiles():
    """This function returns a dictionary of all the profiles in the
    profiles.ini file. The dictionary keys are the profile id's (section
    headers). The values are instances the Profile() class.
    """
    parser = parse_ini_file()
    
    profiles = {}
    
    #Go through each section
    for id in parser.sections():
        #Create a blank Profile object
        p = Profile( id, empty=True )
        
        #Fill in the information using the profiles.ini file
        p.from_parser( parser )
        
        #Add it to the dictionary
        profiles[id] = p
    
    return profiles
    
def write_ini_file( parser ):
    """This function writes the given ConfigParser into the 
    profiles.ini file."""
    global profiles_file
    
    with open( profiles_file, 'w' ) as ini_file:
        parser.write( ini_file )
    
def parse_ini_file():
    """This function reads the profiles.ini file and returns a ConfigParser
    representation of it.
    """
    global profiles_file
    
    if not os.path.exists( profiles_file ):
        raise IOError( 'Cannot find the profiles.ini file.\n'
                       'Tried: '+profiles_file )

    #Construct the parser and fill it in
    parser = SafeConfigParser()
    parser.read( profiles_file )
    
    return parser


class Profile:
    """This object represents information about a profile. Ideally this
    information either comes from or will go into the profiles.ini file.
    
    The id attribute is the unique identifier for this profile. In the
    profiles.ini file, this value is stored as the section heading.
    
    The variable attribute corresponds to a key in the client's os.environ
    dictionary.
    
    The match attribute is a regular expression that is used to test
    whether the given client should apply this profile.
    
    The packages attribute stores a list of package id's that specify what
    packages are to by installed by this profile.
    """
    def __init__( self, id, variable='', match='', packages=[], empty=False ):
        """Initializes the object. The parameters correspond to the attributes
        described above, excpet for the empty parameter. If the empty parameter
        is True then all the parameters except for the id, are ignored. You
        would use this parameter if you are going to call one of the 'from'
        functions later.
        
        Note, the regular expression passed into the match parameter is
        tested. It is tested by compiling the expression. An invalid expression
        will throw an exception.
        """
        self.id = id
        
        if empty:
            return
        
        self.variable = variable
        self.packages = packages
        
        #Make sure the regex is good
        self.re = re.compile( match )
        
        self.match = match
        
    def from_parser( self, parser ):
        """This method fills in this object's attributes using information
        from a ConfigParser object. The parser must contain a section
        that corresponds to this object's id. Also the packages variable
        expects its value to be a string representation of a list,
        i.e. package: ['pkg1', 'pkg2'].
        
        As with the constructor, the regular expression in the match attribute
        is compiled to it check for validity.
        """
        self.variable = parser.get( self.id, 'variable' )
        
        #Make sure the regex is good
        tmp_match = parser.get( self.id, 'match' )
        self.re = re.compile( tmp_match )
        self.match = tmp_match
        
        self.packages = eval(parser.get( self.id, 'packages' ))
        
    def from_form( self, form ):
        """This method is used by the repo.py file to fill in the Profile
        using data entered into a form.
        
        As with the constructor, the regular expression in the match attribute
        is compiled to it check for validity.
        """
        self.id = form.get( 'id' )
        self.variable = form.get( 'variable' )
        
        #Flask returns the list as unicode characters this creates
        #problems when reading/writting files between python 2 and 3
        #To fix this we are re-encoding them into ascii
        self.packages = map( lambda x: x.encode('ascii'), 
                             form.getlist( 'packages' ) )
        
        
        #Make sure the regex is good
        tmp_match = form.get( 'match' )
        self.re = re.compile( tmp_match )
        self.match = tmp_match

    def save_to_parser( self, parser ):
        """This method saves this object's state to the given ConfigParser.
        Note, if a section with this object's id does not yet exist in the
        parser object, it will be created.
        """
        if not parser.has_section( self.id ):
            parser.add_section( self.id )
            
        parser.set( self.id, 'variable', self.variable )
        parser.set( self.id, 'match', self.match )
        parser.set( self.id, 'packages', repr(sorted(self.packages)) )
        
    def make_package_list( self ):
        """This function returns a list of PackageInfo objects that correspond
        to the list of id in the package attribute.
        """
        from PackageInfo import PackageInfo
        
        package_list = []
        for p in self.packages:
            package_list.append( PackageInfo( p, skip_dependents=True, 
                                              skip_download=True ) )
            
        return package_list

    def applies( self ):
        return (self.variable in config.sysinfo) and \
               self.re.match( config.sysinfo[self.variable] )
