#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This module runs the server side portion of winsync. It handles
the administrative interface as well as the interface the winsync module
uses to download packages.
"""

from flask import Flask, Markup, session, request, render_template, redirect
from flask import abort, send_file, current_app, flash, make_response
from werkzeug.exceptions import InternalServerError
import logging

APP = Flask(__name__)

def templated(template=None):
    """This function offers the @templated decorator.
       It takes one parameter, the template file. Optionally, the
       decorated function can return a dictionary whose name-values
       pairs will be forwarded to the template.
    """
    from functools import wraps
    def decorator(func):
        "Makes this function a decorator."
        @wraps(func)
        def decorated_function(*args, **kwargs):
            """Handles the redering of the template file, and send it to the
            user's web browser.
            """
            template_name = template
            if template_name is None:
                template_name = request.endpoint \
                    .replace('.', '/') + '.html'
            ctx = func(*args, **kwargs)
            if ctx is None:
                ctx = {}
            elif not isinstance(ctx, dict):
                return ctx

            #Disable warning about using ** below.
            #pylint: disable-msg=W0142
            return render_template(template_name, **ctx)

        return decorated_function
    return decorator

def login_required(func):
    """This function offers the @login_required decorator.
    The decorator does not require any parameters. The effect of
    this decorator is that if the user is not logged in but trys
    to access a protected URL, then the user will be redirected
    to the login page.
    """
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        """Checks to see if the user is logged in, and redirects him if
        necessary.
        """
        if 'user' not in session or session['user'] is None:
            return redirect('/login')
        else:
            return func(*args, **kwargs)

    return decorated_function


def general_download(dirname, filename):
    """This function handles the downloading of any resource in the repository.
    Given that there are several methods for downloading the various resources
    within the repository, this function allows the code to be called by
    several functions.
    """
    import os.path

    #This takes care of any file names with .'s in them
    filename = os.path.basename(filename)
    dirname = os.path.abspath(dirname)

    #Calculate the files location
    file_path = os.path.join(dirname, filename)

    #Make sure the file exists
    if not os.path.exists(file_path):
        abort(404)

    #Create the response object
    response = send_file(file_path, as_attachment=True,
                          attachment_filename=filename)

    #Add the file's lentgth to the headers
    response.headers.add('Content-Length',
                          str(os.path.getsize(file_path)))

    return response

def make_package_list():
    """This is a helper function that returns a list of tuples for all the
    packages. The list that is returned contains tuples in the format
    (id, name). The list is sorted alphabeticlly by the package name.
    """
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path

    package_list = []

    #Examine every ini file in the info directory
    for info_file in os.listdir(APP.info_dir):
        #If the file is an ini file this will give you the package's id
        (pkg_id, ext) = os.path.splitext(info_file)

        #Only look at ini files.
        if ext.lower() == '.ini':
            #Read the ini file
            pkg_info = PackageInfo(pkg_id, skip_dependents=True,
                                   skip_download=True,
                                   info_dir=current_app.info_dir)

            #Add the entry to the list
            package_list.append((pkg_id, pkg_info.name))

    return sorted(package_list, key=lambda x:x[1].lower())

@APP.route('/')
@templated('index.html')
@login_required
def root():
    """The homepage of the repository."""

@APP.route('/login', methods=['GET'])
@templated('login.html')
def show_login():
    """This function shows the login page.
    Everything is handled by the @templated decorator.
    """
    pass

@APP.route('/login', methods=['POST'])
def do_login():
    """This function logs the user in."""
    #Import winsyc's crypt system
    import winsync.lib.keys as keys
    import os.path

    username = os.path.basename(request.form.get('username'))
    password = request.form.get('password')

    key_file = os.path.join(current_app.keys_dir, 'user', username+'.key')

    if not os.path.exists(key_file):
        flash('Incorrect username/password combination.')
        return redirect('/login')

    if not keys.password_valid(password, key_file):
        flash('Incorrect username/password combination.')
        return redirect('/login')

    session['user'] = username
    session.modified = True


    return redirect('/')

@APP.route('/logout')
@login_required
def logout():
    """This function logs the user out of the repository."""
    session['user'] = None
    session.modified = True

    return redirect('/login')


@APP.route('/list-packages')
@login_required
@templated('list-packages.html')
def list_packages():
    """This function displays the page with a list of all the packages."""
    return {'package_list':make_package_list()}

@APP.route('/package/<cur_id>', methods=['GET'])
@login_required
@templated('package.html')
def get_package_info(cur_id):
    """This function displays all the information for the given package. It
    requires that URL contain the package id (cur_id). It will then display
    a form that will allow the user to update the package information ini
    file.

    If the cur_id is 'new' then the page that is displayed is suitable for
    creating a new package.
    """
    from winsync.lib.PackageInfo import PackageInfo

    #Sane Defaults
    pkg_id = cur_id
    id = pkg_id

    #Get a list of all the existing packages
    package_list = make_package_list()

    #If the user is creating a new package, there is nothing to do.
    if pkg_id.lower() == 'new':
        return locals()

    #We need to look up a package
    try:
        #Read the information out of the package file,
        #and return the object's dictionary
        info = PackageInfo(pkg_id, None, skip_dependents=True,
                            skip_download=True,
                            info_dir=current_app.info_dir)
        info.package_list = package_list
        info.pkg_id = info.id

        return info.__dict__

    except IOError:
        abort(404)

@APP.route('/package/<cur_id>', methods=['POST'])
@login_required
def post_package_info(cur_id):
    """This function handles a POST from the form displayed by the
    get_package_info() function. It will either create a new package info
    file if one does not exist, or it will update an existing one.

    After completing its job it redirects back to get_package_info().
    """
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path

    #Get important basic information from the form
    pkg_id = request.form.get('id', type=str).lower()
    meta = request.form.get('meta', type=str) == 'True'
    cur_id = cur_id.lower()
    pkg_info = None

    #If the user uploaded an install script, get a hold of the file object
    installer = request.files.get('installer')

    #Gaurd agains directory traversal attack
    if installer.filename is None:
        #Set this installer varible to None, so we know the user
        #did not upload an install script
        installer = None

    #Check to see if we are creating a new package
    if cur_id == 'new':
        #Make sure that thepkg_id passed in is does not already exist
        if os.path.exists(os.path.join(APP.info_dir, pkg_id+'.ini')):
            raise InternalServerError('A package with the id "{}" '
                                      'already exists.'.format(pkg_id))

        #Create an empty package object
        pkg_info = PackageInfo(pkg_id, make_empty=True,
                               info_dir=current_app.info_dir)

        #Create the files directory for this package (meta packages
        #don't have one)
        if not meta:
            os.mkdir(os.path.join(current_app.files_dir, pkg_id))

    #Update a package
    else:
        pkg_info = get_existing_package_info(cur_id, pkg_id, meta)

    #See if the user uploaded an installation script
    if (installer is not None) and installer.filename != '':
        #Protect against directory traversal attack
        script_name = os.path.basename(installer.filename)

        #Write the new install script to disk
        installer.save(os.path.join(APP.tmp_dir, script_name))

        #Test the script and update packge info
        update_installer_script(pkg_info, script_name)

    #Update the package information to reflect what was put into the form
    pkg_info.update_from_form(request.form)


    #Write to the ini file
    pkg_info.write_to_info_file()

    #Double check that we updated/created the file correctly
    try:
        PackageInfo(pkg_id, skip_dependents=True,
                    skip_download=True,
                    info_dir = current_app.info_dir)
    except:
        #If the file was created, delete the file
        if cur_id == 'new' and os.path.exists(pkg_info.pkg_info_file):
            os.remove(pkg_info.pkg_info_file)

        #Continue raising the exception
        raise

    #Send back the appropriate "all clear" message
    if cur_id == 'new':
        flash('Successfully created the package.')
    else:
        flash('Update successfull.')

    #Redirect to display the update
    return redirect('/package/'+pkg_id)

def update_installer_script(pkg_info, filename):
    """This function updates the installer script file on disk
    when a new one has been uploaded.
    """
    import py_compile
    import os
    import os.path
    import shutil
    import winsync.lib.config

    if pkg_info.installer:
        old_script = os.path.join(APP.script_dir, pkg_info.installer)
    else:
        old_script = None

    #Calculate file paths for the new install script
    new_script = os.path.join(APP.tmp_dir, filename)
    script_dest = os.path.join(APP.script_dir, filename)

    module_name = os.path.splitext(filename)[0]

    #Compile the file to see if it is a vailid python file
    try:
        py_compile.compile(new_script, doraise=True)
    except py_compile.PyCompileError as e:
        os.remove(new_script)
        msg = '<p>The uploaded python install script had a compliation error.</p>'
        msg += '<pre>{}</pre>'.format(e.msg)
        
        raise InternalServerError(msg)

    #Make sure the file has an util.Installer class
    try:
        if not winsync.lib.config.get_installer_object(module_name):
            raise InternalServerError(
                'The uploaded python install script {} is missing an '
                'Installer class.'.format(filename))

    except:
        os.remove(new_script) #Get rid of the bad script file
        raise

    #Delete the compiled file since we are done with the test
    os.remove(new_script+'c')

    #Replace the old script with the new
    if old_script and os.path.exists(old_script):
        os.remove(old_script)
    shutil.move(new_script, script_dest)

    #Update the package information object
    pkg_info.installer = filename

def get_existing_package_info(cur_id, pkg_id, meta=False):
    """When updating a package, this function loads the existing
    package information into a PakageInfo object and returns it.
    """
    import os.path
    from winsync.lib.PackageInfo import PackageInfo

    #Make sure that the package exists
    if not os.path.exists(os.path.join(APP.info_dir, cur_id+'.ini')):
        raise InternalServerError('The package "{}" does not exist.'.format(cur_id))

    #If the user changed the package's id, then we need
    #to rename the ini file
    if cur_id != pkg_id:
        old_name = os.path.join(APP.info_dir, cur_id+'.ini')
        new_name = os.path.join(APP.info_dir, pkg_id+'.ini')

        os.rename(old_name, new_name)

    #Create a package info object, have it read the
    #contents of the ini file
    pkg_info = PackageInfo(pkg_id, skip_dependents=True,
                           skip_download=True,
                           info_dir = current_app.info_dir)

    if not meta:
        #Meta packages don't need to worry about this part
        files_path = os.path.join(current_app.files_dir, pkg_id)

        if os.path.exists(files_path):
            #Also rename the associated files directory,
            #skip for meta packages
            if cur_id != pkg_id:
                os.rename(os.path.join(current_app.files_dir, cur_id),
                           files_path)

        #Make the directory only when meta status has changed
        #and it does not exist
        elif meta != pkg_info.meta:
            os.mkdir(files_path)

    #We changed the package's meta status from False to True.
    #Get rid of the files directory
    elif meta != pkg_info.meta:
        import shutil
        shutil.rmtree(os.path.join(current_app.files_dir, pkg_id))

    return pkg_info

@APP.route('/delete-package/<pkg_id>', methods=['POST'])
@login_required
def delete_package(pkg_id):
    """This function delete a package from the repository based on its id."""
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path, shutil

    #Make sure the pkg_id is for an existing package
    try:
        pkg = PackageInfo(pkg_id, skip_dependents=True, skip_download=True,
                          info_dir = current_app.info_dir)
    except IOError:
        abort(404)

    #Delete the extra files directory (meta packages don't have one)
    if not pkg.meta:
        shutil.rmtree(os.path.join(current_app.files_dir, pkg_id))

    #Delete the ini file
    os.remove(os.path.join(APP.info_dir, pkg_id+'.ini'))

    flash('Successfully removed the "{}" package.'.format(id))
    
    return redirect('/list-packages')

@APP.route('/update-files/<pkg_id>', methods=['GET', 'POST'])
@login_required
def update_files(pkg_id):
    """This function handles the case where the user
    manually places a large file into a package's files
    directory. This function will scan the directory and
    update the package information file to reflect the
    change.
    """
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path

    #Calcualate the relevent paths
    pkg_path = os.path.join(current_app.files_dir, pkg_id)

    #Make sure there is a file's directory
    if not os.path.exists(pkg_path):
        raise InternalServerError('The package "{}" does not have a files '
                                   'folder.'.format(pkg_id))

    #List the files in the directory
    files = os.listdir(str(pkg_path))

    #Parse the ini file
    pkg = PackageInfo(pkg_id, skip_dependents=True, skip_download=True,
                       info_dir = current_app.info_dir)

    #Make the information file aware of the new files
    if len(new_files) > 0:
        pkg.files = files
        pkg.write_to_info_file()

    return redirect('/package/'+pkg_id)

@APP.route('/upload/<pkg_id>', methods=['POST'])
@login_required
def upload(pkg_id):
    """This function handles the uploading of extra package files.
    It will place the files in the "current_app.files_dir/package_id/"
    directory.
    """
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path

    #Get ahold of the object representing the file that was uploaded
    upfile = request.files.get('fileupload')

    #This takes care of any file names with .'s in them
    upfile.filename = os.path.basename(upfile.filename)

    #Calcualate the relevent paths
    pkg_path = os.path.join(current_app.files_dir, pkg_id)
    file_path = os.path.join(pkg_path, upfile.filename)

    #Make sure there is a file's directory
    if not os.path.exists(pkg_path):
        raise InternalServerError('The package "{}" does not have a files '
                                   'folder.'.format(pkg_id))

    #If we are updating the file, remove the old one
    if os.path.exists(file_path):
        os.remove(file_path)

    #Write the new install script to disk
    upfile.save(file_path)

    #Parse the ini file
    pkg = PackageInfo(pkg_id, skip_dependents=True, skip_download=True,
                       info_dir = current_app.info_dir)

    #Only update the ini file if we are adding a new file, not updating
    if upfile.filename not in pkg.files:
        pkg.files.append(upfile.filename)
        pkg.write_to_info_file()

    flash(Markup('Added the <tt>{}</tt> file.'.format(upfile.filename)))
    return redirect('/package/'+pkg_id)

@APP.route('/download/<pkg_id>/<filename>')
@APP.route('/repo/download/<pkg_id>/<filename>', methods=['GET', 'POST'])
@login_required
def download(pkg_id, filename):
    """This function will allow the user to download an extra package file."""
    import os.path

    pkg_id = os.path.basename(pkg_id)

    #Caclucate the files location
    directory = os.path.join(current_app.files_dir, pkg_id)

    return general_download(directory, filename)

@APP.route('/download-info/<pkg_id>', methods=['GET'])
@APP.route('/repo/download-info/<pkg_id>', methods=['GET', 'POST'])
@login_required
def download_info(pkg_id):
    """This function will allow the user to download the
    package information ini file.
    """

    return general_download(current_app.info_dir, pkg_id+'.ini')

@APP.route('/download-installer/<pkg_id>', methods=['GET'])
@APP.route('/repo/download-installer/<pkg_id>', methods=['GET', 'POST'])
@login_required
def download_installer(pkg_id):
    """This function is used to downloads the python installer script
    based on the package's id.
    """
    from winsync.lib.PackageInfo import PackageInfo
    import os.path

    pkg_id = os.path.basename(pkg_id)
    pkg = PackageInfo(pkg_id, skip_dependents=True, skip_download=True,
                       info_dir = current_app.info_dir)

    return general_download(current_app.script_dir, pkg.installer)

@APP.route('/delete-file/<pkg_id>/<filename>')
@login_required
def delete_file(pkg_id, filename):
    """This function will allow the user to delete an extra package file."""
    from winsync.lib.PackageInfo import PackageInfo
    import os, os.path

    #This takes care of any file names with .'s in them
    filename = os.path.basename(filename)
    pkg_id = os.path.basename(pkg_id)

    #Calculate the file's real path
    file_path = os.path.join(current_app.files_dir, pkg_id, filename)

    #Make sure the file exists
    if os.path.exists(file_path):
        #Remove this file from the list in the ini file
        pkg = PackageInfo(pkg_id, skip_dependents=True, skip_download=True,
                           info_dir = current_app.info_dir)
        pkg.files.remove(filename)
        pkg.write_to_info_file()

        #Delete the file
        os.remove(file_path)
    else:
        abort(404)

    flash('Successfully delete the file: {}'.format(filename))
    return redirect('/package/'+pkg_id)

@APP.route('/profiles', methods=['GET'])
@login_required
@templated('list-profiles.html')
def list_profiles():
    """This function renders a list of profiles for the administrator to
    use.
    """
    from winsync.lib.Profile import get_all_profiles

    return {'profiles':get_all_profiles().keys()}


@APP.route('/profile/<profile_id>', methods=['GET'])
@templated('profile.html')
@login_required
def get_profile(profile_id):
    """This function renders a profiles web page (including the new profile
    page) based on its id or the word 'new'.
    """
    from winsync.lib.Profile import parse_ini_file, Profile

    if profile_id == 'new':
        profile = Profile('new', empty=True)
    else:
        parser = parse_ini_file()
        profile = Profile(profile_id)
        profile.from_parser(parser)

    package_list = make_package_list()

    return {'id':profile_id, 'profile': profile, 'package_list': package_list}
    #return locals()


@APP.route('/profile/<profile_id>', methods=['POST'])
@login_required
def post_profile(profile_id):
    """This function handles the updating/creation of a profile."""
    from winsync.lib.Profile import Profile, parse_ini_file, write_ini_file

    #Open and parse the profile.ini file
    parser = parse_ini_file()

    #Create a profile and update it from the form
    profile = Profile(profile_id, empty=True)
    profile.from_form(request.form)

    cur_id = request.form.get("cur_id")

    #If thepkg_id changed remove the old section
    if cur_id != 'new' and cur_id != profile.id:
        parser.remove_section(cur_id)

    #Make the parser aware of the changes
    profile.save_to_parser(parser)

    #Save the profiles.ini file
    write_ini_file(parser)

    if cur_id == 'new':
        flash('Created the "{}" profile.'.format(profile.id))
    else:
        flash('Updated the "{}" profile.'.format(profile.id))

    return redirect('/profile/'+profile.id)

@APP.route('/delete-profile/<profile_id>', methods=['POST'])
@login_required
def delete_profile(profile_id):
    """This function deletes a profile from the repository."""
    from winsync.lib.Profile import parse_ini_file, write_ini_file

    #Open and parse the profile.ini file
    parser = parse_ini_file()

    #Delete the section from the ini file
    parser.remove_section(profile_id)

    #Save the profiles.ini file
    write_ini_file(parser)

    flash('Deleted the "{}" profile.'.format(profile_id))
    return redirect('/profiles')


#------------------------------------------------------------------------#

@APP.route('/repo/self-register', methods=['POST'])
def repo_self_register():
    """This function allows a client to self register
    for a password file. It only works if the
    allow_self_register value is True in the config file.

    It expects the client to send it a machine name (name)
    and a UUID string in the post data. It returns
    a 128 character password.
    """
    import winsync.lib.keys as keys
    import os.path

    #Check if self registration is allowed
    if not current_app.allow_self_register:
        abort(403)

    #Digest the form data
    machine_name = os.path.basename(request.form.get('name')).lower()
    uuid = os.path.basename(request.form.get('uuid')).lower()
    key_filename = '{}-{}.key'.format(machine_name, uuid)

    #Calculate the key file location
    key_file = os.path.join(current_app.keys_dir, 'client', key_filename)

    #Already registered is an error
    if os.path.exists(key_file):
        abort(500)

    #Create a new password
    password = keys.gen_machine_password()

    #Write the key file
    keys.write_password(key_file, password)

    return '{}:{}:{}'.format(machine_name, uuid, password)


@APP.route('/repo/start-session', methods=['POST'])
def repo_start_session():
    """This function allows a client to login.

    It expects the client to send it a machine name (name),
    a mac address (mac), and a password (password) in the
    post data. It returns nothing. A HTTP return status of
    200 signals that the login was successful. An error
    code of 403 is used for all errors.
    """

    #Import winsyc's crypt system
    import winsync.lib.keys as keys
    import os.path

    #Digest the form data
    machine_name = os.path.basename(request.form.get('name')).lower()
    uuid = os.path.basename(request.form.get('uuid')).lower()
    password = request.form.get('password')

    #Calculate the name of the key file
    key_filename = '{}-{}.key'.format(machine_name, uuid)

    #Calculate the location of the key file
    key_file = os.path.join(current_app.keys_dir, 'client', key_filename)

    #Make sure the key file exists
    if not os.path.exists(key_file):
        logger.error('Bad username/password for '.format(machine_name))
        abort(403)

    #See if the password is valid
    if not keys.password_valid(password, key_file):
        logger.error('Bad username/password for '.format(machine_name))
        abort(403)

    #Record the username
    session['user'] = machine_name
    session.modified = True

    return ''

@APP.route('/repo/end-session', methods=['GET', 'POST'])
@login_required
def repo_end_session():
    """This function allows the client to gracefully logout.
    A HTTP return status of 200 signals that the process
    was successful.
    """
    session['user'] = None
    session.modified = True
    return ''

@APP.route('/repo/profiles.ini', methods=['GET', 'POST'])
@login_required
def repo_profiles_ini():
    """This functions is used to dowload the profiles.ini file from the
    repository.
    """
    return general_download(current_app.packages_dir, 'profiles.ini')

def init_app():
    """This function initializes some important variables, and should be
    called when the app starts. This function makes sure that winsync and
    winsync.lib are in the path. Further, it specifies where to save extra
    package files.
    """
    import os, os.path, sys, uuid
    import configparser
    import winsync.lib.Profile as Profile

    def set_dir(path):
        """This function is used to create needed directories on a
        fresh install. If the given path does not exist it will create
        the necessary directory. It returns an absolute path.
        """
        path = os.path.abspath(path)
        if not os.path.exists(path):
            try:
                os.mkdir(path)
            except:
                raise IOError('Path does not exist, and could not create'
                               ' it: {}'.format(path))
        elif not os.path.isdir(path):
            raise IOError('Path is not a directory: {}'.format(path))
        return path

    #This allows for the script to executed from somewhere else than
    #the current directory. This is commonly done by web servers.
    module_location = os.path.dirname(os.path.abspath(__file__))

    #Caclulate where to store various files
    APP.keys_dir = set_dir(os.path.join(module_location, 'keys'))
    APP.packages_dir = set_dir(os.path.join(module_location, 'packages'))
    APP.script_dir = set_dir(os.path.join(APP.packages_dir, 'script'))
    APP.files_dir = set_dir(os.path.join(APP.packages_dir, 'files'))
    APP.info_dir = set_dir(os.path.join(APP.packages_dir, 'info'))

    #Change where the Profile module looks for the profiles.ini file
    Profile.profiles_file = os.path.join(APP.packages_dir, 'profiles.ini')

    #Create a new temporary directory inside /tmp, this directory is only used
    #for compiling uploaded python scripts. We need to make sure it does not
    #already exist because of multiprocessing servers
    tmp_dir_exists = True
    while tmp_dir_exists:
        APP.tmp_dir = os.path.join('/tmp', str(uuid.uuid4()))
        tmp_dir_exists = os.path.exists(APP.tmp_dir)
    os.mkdir(APP.tmp_dir)

    #Add the installer chache directory so we can inpsect them as modules
    sys.path.append(APP.script_dir)

    #Add the temporary directory so we can test the scripts
    sys.path.append(APP.tmp_dir)

    #Load the server configuration information
    config_path = os.path.join(module_location, 'config.ini')
    if os.path.exists(config_path):
        parser = configparser.SafeConfigParser()
        parser.read(config_path)

        APP.allow_self_register = parser.getboolean('repo',
                                                    'allow_self_register')
        APP.secret_key = parser.get('repo', 'secret_key')
        APP.debug = parser.getboolean('repo', 'debug')
        APP.address = parser.get('repo', 'address')
        APP.port = parser.getint('repo', 'port')

    else:
        logger.error('Warning: Could not find the configuration file '
                     'in the module directory, falling back to default values!')

        APP.allow_self_register = True
        APP.secret_key = 'This is a bad key, set up your config!!!'
        APP.debug = True
        APP.address = 'localhost'
        APP.port = 8080

    return APP

#Initialize the module
init_app()

if __name__ == '__main__':
    #Start the server
    APP.run(host=APP.address, port=APP.port, debug=APP.debug)
