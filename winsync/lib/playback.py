import winsync.lib.control_windows as control
import ctypes as ct

control.playback = True

user32 = ct.windll.user32

def find_window(class_name, title, wait_time=3600):
    """This function returns a Window with the given class name and title.
    The class_name parameter is expected to be something returned from
    GetClassName win32 API function (this will often take the form of
    a string representing a hex number). The title parameter should be the
    text located in the title bar of the window.
     
    This function will repeatedly look for the window until the number of
    seconds specified in wait_time has expired. This is useful for when
    a window may take a long time to load. By default this function will wait
    1 hour for the window to appear. If the window does not appear within the
    allotted time then a WindowsError is raised.
    
    This function will return a new Window object that represents the found
    window. 
    """
    import time
    
    #Convert python strings to LPWSTR's
    name_buffer = ct.create_unicode_buffer(class_name)
    text_buffer = ct.create_unicode_buffer(title)
    
    #Get the time wait_time seconds from now
    time_out = time.time() + wait_time
    
    #Try locating the window, but quit after time out
    while time.time() < time_out:
        
        #Try locating the window
        hwnd = user32.FindWindowExW(None, None, name_buffer, text_buffer)
        
        #An HWND handle means we found the window
        if hwnd != 0:
            return control.Window(class_name, title, hwnd)

        #Did not find the window so wait 1/2 second and try again
        time.sleep(1)

    raise WindowsError('Did not find the window within the given timeout')
    
def find_control(parent, resource_id, class_name, text, wait_time=18000):
    """This function returns a Control subclass with the given class name
    and text. The class_name parameter is expected to be something
    returned from GetClassName win32 API function (this will often take the
    form of a string representing a hex number). The text parameter should be
    the text the control displays.
     
    This function will repeatedly look for the control until the number of
    seconds specified in wait_time has expired. This is useful for when
    a control may take a long time to load. By default this function will wait
    5 hours for the control to appear. If the control does not
    appear within the allotted time then a WindowsError is raised.
    
    This function will return a new object, that is a subclass of Control,
    that represents the found window.
    
    Note, this method uses the Window.scan_controls() method to find the
    window. This is done because there are some odd edge-cases were the
    FindWindowEx() function in the win32 API can fail. The problem with this
    way of finding a control is that it can be time consuming.
    """
    import time
    
    #Get the time 1 hour from now
    time_out = time.time() + wait_time
    
    #Try locating the window, but quit after time out
    while time.time() < time_out:
    
        parent.scan_controls()

        for control in parent.controls:
            if control.actual_text == text and \
               control.class_name == class_name:
                return control
                
        time.sleep(1)
        
    raise WindowsError('Did not find the control within the given timeout')

def start_exe(exe):
	"""This is simply a wrapper for winsync.lib.control_window.start_exe()."""
	return control.start_exe(exe)