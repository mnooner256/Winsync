import ctypes as ct
import ctypes.wintypes as wintypes
import tkinter as tk

user32 = ct.windll.user32

#These structures are used to simulate a mouse event, see Window.click().
class MOUSEINPUT(ct.Structure):
    '''See: http://msdn.microsoft.com/en-us/library/windows/desktop/ms646273(v=vs.85).aspx'''
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ct.c_ulong),
    ]
    
class INPUT_TYPE_UNION(ct.Union):
    '''This emulates the union in INPUT Structure. Note, in the future
    ki, and hi field may be added for keyboard and hardware inputs.
    But for now, only mouse events are necessary.
    '''
    _fields_ = [
        ('mi', MOUSEINPUT),
    ]

class INPUT(ct.Structure):
    '''See: http://msdn.microsoft.com/en-us/library/windows/desktop/ms646270(v=vs.85).aspx'''
    _anonymous = ['_0']
    _fields_ = [
        ('type', wintypes.DWORD),
        ('_0', INPUT_TYPE_UNION),
    ]

#Constants used by buttons to broadcast a windows click event
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
    
#This list is used to generate a "recording" of the actions to taken by the
#user. Initially, the necessary import and play function is created.
recording = ['''
def play():
    import winsync.lib.playback as play
''']

#This variable specifies whether the library is in record or playback mode
playback = False

#This dictionary holds all the known variables so object are not recreated
#unnecessarily in the play back script
variables = {}

def get_logger(suffix):
    """This function returns a logger object with a useful context. The suffix
    parameter should be the either a class name or a function name. If the
    program is not in playback mode then None is returned instead.
    """
    import logging

    if playback:
        return logging.getLogger('winsync.lib.control_windows.{}'.format(suffix))
    else:
        return None

def make_var_name(control):
    """This function creates a unique variable name for a "control" to be used
    in the play back script. The control parameter is the Control or Window object
    to create the name for. The names are specialized based on their class. 
    
    The variable names take the form of class_n, where "class" is the
    class name in lower case and n is an ever incrementing number that makes
    the variable name unique. For example, this function will generate these
    names: window_1, button_5, edit_2, etc. This makes the recording script
    slightly more readable/editable.
    """
    global variables
    
    #Variable names have a number suffix. This specifies that number.
    i = 1
    

    template = None

    #Set the variable's prefix or if the object already has a variable name,
    #return it    
    if control in variables.values():
        vlist = list(variables.values())
        return vlist[vlist.index(control)].name
    else:
        template = '{}_{{}}'.format(control.__class__.__name__.lower())
    
    #Cycle through all possible suffix numbers until an unused number
    #is found.
    name = template.format(i)
    while name in variables:
        name = template.format(i)
        i += 1

    #Register this variable so it will not be recreated.
    variables[name] = control
    
    #Return the unique variable name
    return name

def start_exe(exe):
    """This function starts the given executable as a subprocess, returning
    the process. The exe parameter can be a string representing the executable
    or a list corresponding to the documentation for the first
    parameter in subprocess.Popen().
    
    Be aware that this function has two special conditions builtin to make it
    more compatible with winsync. First, it treats MSI files special. Instead
    of simply executing the file, it will execute "msiexec /i" on the file.
    Second, *during playback* the file is first looked for in the current
    directory instead of at the path given. If the file is not found then the
    it will try executing the file at the given path.
    """
    import subprocess
    import os.path
    
    original_exe = exe
    
    #Try looking for the exe file in the current directory
    #(for winsync compatibility)
    if isinstance(exe, str):
        if os.path.exists(os.path.basename(exe)):
            exe = os.path.basename(exe)

        #Treat msi install files special    
        if exe.endswith('.msi'):
            exe = ['msiexec', '/i', exe]
        else:
            exe = [exe]
    
    if playback:
        logger = get_logger('start_exe')
        logger.info('Starting executable using: {}'.format(exe))

    process = subprocess.Popen(exe)
    
    recording.append('\tplay.start_exe("{}")'.format(original_exe))
    
    return process
    
class Window:
    """This class represents a window shown by the Windows operating system.
    It is mostly used to find and manipulate the controls found within this
    window.
    """
    label_template = 'Window Title:\n{c.text}'
    
    def __init__(self, class_name, text, hwnd, app=None):
        self.hwnd = hwnd
        self.app = app
        
        if isinstance(class_name, str):
            self.class_name = class_name
        else:
            self.class_name = class_name.value
        
        if isinstance(text,str):
            self.text = text
        else:
            self.text = text.value
        
        self.name = make_var_name(self)
        
        self.prep_window()
        
        self.record('\n\t{name} = play.find_window("{class_name}", "{text}")')
        
        #This will be the master list of controls for the window
        self.controls = []
        
        self.menu_items = [('Click At', self.click),
                           ('Close Window', self.close)]
        
        self.scan_controls()
        
    def prep_window(self):
        'This function alters the Window to make it more amenable to control.'
        
        #Make the window un-moveable by the system menu.
        mnu = user32.GetSystemMenu(self.hwnd, False);
        user32.DeleteMenu(mnu, 0xF010, 0); #Disable the Move menu item
        
        #Get rid of the title bar and window borders, that way
        #the user can't play with the window during playback
        #Start by getting the window's current style
        cur_style = user32.GetWindowLongW(self.hwnd, -16)
        
        #Remove the caption, thick frame or dialgo frame
        cur_style = cur_style & ~(0x00C00000 | 0x0040000 | 0x00040000)
        
        #Set the new style
        user32.SetWindowLongW(self.hwnd, -16, cur_style)
        
        #Move the window to the top-left of the screen, don't resize the window.
        user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0040)
        
        if playback:
            logger = get_logger('Window.prep_window')
            logger.debug('Window "{}" has been prepared for control.'.format(self.text))

    def scan_controls(self):
        '''This callback will scan the window for child windows that can be controled.'''

        #This function handled the enumeration process used by the Windows API.
        def winchild_callback(hwnd, lpparm):
            #Get the control's class name
            classname = ct.create_unicode_buffer('', 255)
            user32.GetClassNameW(hwnd, classname, 255)
            
            #Get the text of the control
            text = ct.create_unicode_buffer('', 255)
            user32.GetWindowTextW(hwnd, text, 255)
            
            resource_id = user32.GetDlgCtrlID(hwnd)
                       
            #If the child window is a type we can control then
            #create a component object to represent it 
            control = self.get_control(resource_id, classname.value,
                                       text.value, hwnd)
            if control is not None:
                try:
                    old = self.old_controls.index(control)
                    self.controls.append(self.old_controls[old])
                except ValueError:
                    self.controls.append(control)
                    
            #Recurse to gobble up any grandchildren
            user32.EnumChildWindows(hwnd, enumchildproc, None)
            
            return True
                    
        #Keep the old controls so we can detect repeats
        self.old_controls = self.controls
        
        #Clear the list for the new control list
        self.controls = []
        
        #Have Windows enumerate all of the child windows for our window
        enumchildproc_type = ct.WINFUNCTYPE(ct.c_bool, ct.c_int, ct.c_void_p)
        enumchildproc = enumchildproc_type(winchild_callback)
        
        user32.EnumChildWindows(self.hwnd, enumchildproc, None)
        
        del(self.old_controls)
        
    def get_control(self, resource_id, classname, text, hwnd):
        """This method returns an object that is a subclass of control.Control
        such that it can be used to operate a Window's control. If the control
        is not usable by this program, then None is returned.
        """
        #Trim text longer than 50 characters
        if len(text) > 50:
            text = '{}...'.format(text[:47])
            
        if classname == 'Button':
            return Button(self, resource_id, classname, text, hwnd)
        elif classname == 'Edit':
            return Edit(self, resource_id, classname, text, hwnd)
        else:
            return Control(self, resource_id, classname, text, hwnd)
            
    def make_button(self, tkwindow):
        '''This method creates the "button" in the GUI that allows the user
        to perform various actions.
        '''
        label = self.label_template.format(c=self)
        
        self.parent_window = tkwindow
        self.frame = tk.Frame(tkwindow, relief=tk.SUNKEN, borderwidth=1)
        
        self.label = tk.Label(self.frame, text=label, justify=tk.LEFT,
                              takefocus=1, foreground='white',
                              background='darkblue')
        self.label.pack(expand=tk.YES, fill=tk.X)
        
        self.popup = tk.Menu(tkwindow, tearoff=0)
        for label, command in self.menu_items:
            self.popup.add_command(label=label,
                                   command=command)
        
        self.label.bind('<Button-1>', self.do_popup)
        self.frame.bind('<Button-1>', self.do_popup)

        self.frame.pack(expand=tk.YES, fill=tk.X)
        
        return self.frame
    
    def do_popup(self, event):
        '''This callback shows the pop window in the GUI.'''
        try:
            self.popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.popup.grab_release()
            
    def click(self, x=None, y=None, wait=0.5):
        '''When the user selects "Click At" this callback is executed. This
        function will insert two messages into Windows' input stream. Namely,
        a left mouse button down message followed, 1/4 of a second later, by
        a left mouse buttun up message.
        
        During recording, the location for the mouse is discovered using a
        record.App.countdown() dialiog. Wherever the mouse is at the expiration
        of the dialog, a click is recorded and sent to that location.
        
        During playback, the x and y parameter indicate the absolute location
        of the mouse using screen coordinates. The click is then sent to that
        location.
        
        The wait parameter specifies a period for the thread to sleep before
        sending the click. The value is passed directly time.sleep(). In
        practice the time a button or window is available for clicking and
        able to actually process the message is not zero. The reason for this
        is Winsync is capabable clicking multiple controls at inhuman speeds.
        GUI designers often do not take this into account. Therefore, the
        default wait time is half of a second to make the process "fast" but
        not too fast. This parameter often has increased from this default
        value.
        '''
        import ctypes.wintypes as wintypes
        import time
        import copy
        
        point = wintypes.POINT()
        
        if not playback:
            self.app.countdown('Hover the mouse cursor over where\n'
                               'you want the click to happen.')
        else:
            logger = get_logger('Window.click')
            logger.debug('Waiting {} seconds before clicking'.format(wait))
            time.sleep(wait)
        
        #Make sure the window will be available for clicking.    
        user32.SetForegroundWindow(self.hwnd)
        user32.SetFocus(self.hwnd)
        
        #Don't allow any other action until the window is redrawn
        user32.RedrawWindow(self.hwnd, None, None, 1)
        
        if not playback:
            #Get the Mouse position in screen coordinates
            user32.GetCursorPos(ct.byref(point))
        else:
            point.x = x
            point.y = y
            
        user32.SetCursorPos(point.x, point.y)
        
        #Simulating events in Windows is now quite complicated,
        #they deprecated all of the easy ways. Basically we have
        #to fill out a complicated structure and place it in a
        #two item array. 90% of the code below is just to fill
        #in the structures.
        mouse = INPUT * 2
        
        #Press the left mouse button down
        itu = INPUT_TYPE_UNION()
        mills = int(time.time() * 1000)
        itu.mi = MOUSEINPUT(point.x, point.y, 0, 0x8000 | 0x0002, mills, 0)
        
        #Release the left mouse button 1 millisecond later
        itu2 = INPUT_TYPE_UNION()
        itu2.mi = MOUSEINPUT(point.x, point.y, 0, 0x8000 | 0x0004, itu.mi.time + 1, 0)
        
        #Create the array containing our click event
        x = mouse((0,itu), (0,itu2))
        
        if playback:
            logger.debug('Clicking window "{}" at ({},{})'.format(self.text, x, y))
        
        #Broadcast the click event
        user32.SendInput(2, ct.byref(x), ct.sizeof(x[0]))
        
        self.record('\t{{name}}.click({}, {})'.format(point.x, point.y))
    def close(self):
        if playback:
            logger = config.logger.getChild('Window.close')
            logger.debug('Closing window "{}"'.format(self.text))
            
        if not user32.SendMessageW(self.hwnd, 0x0010, 0, 0):
            raise ct.WinError()
            
        self.record('\t{name}.close()')
        
    def record(self, template):
        global recording
        
        if not playback:
            recording.append(template.format(**self.__dict__))

class Control:
    label_template = 'Class: {c.class_name}\nText: {c.text}'
    menu_items = []
    
    def __init__(self, parent, resource_id, class_name, text, hwnd):
        self.parent = parent
        self.resource_id = resource_id
        self.hwnd = hwnd
        
        if isinstance(class_name, str):
            self.class_name = class_name
        else:
            self.class_name = class_name.value
        
        if isinstance(text,str):
            self.actual_text = text
        else:
            self.actual_text = text.value
        
        self.name = make_var_name(self)
        self.instantiated = False
        
        #In windows the & corresponds to what letter can be pressed after ALT
        #to identify the control. leaving it makes displaying the text 
        #awkward. So remove it.
        self.text = text.replace('&','')
        
        #This is a list of items to be shown in the pop window, subclasses
        #will either add to or override these default options
        self.menu_items = [('Enable/Disable', self.toggle_state),
                           ('Set Text', self.set_text)]
      
    def __eq__(self, other):
        if isinstance(other, type(self))            and \
           self.parent.hwnd == other.parent.hwnd    and \
           self.resource_id == other.resource_id    and \
           self.class_name == other.class_name      and \
           self.hwnd == other.hwnd                  and \
           self.actual_text == other.actual_text:
            return True
        
        return False
    
    def record(self, template):
        global recording
        
        if playback:
            return
        
        if not self.instantiated:
            recording.append('\t{name} = play.find_control({parent.name}, '
                             '{resource_id}, "{class_name}", '
                             '"{actual_text}")'.format(**self.__dict__))
            self.instantiated = True
        
        recording.append(template.format(**self.__dict__))

    def make_button(self, window, *args, **kwargs):
        label = self.label_template.format(c=self)
        
        self.parent_window = window
        self.frame = tk.Frame(window, relief=tk.SUNKEN, borderwidth=1)
        
        self.label = tk.Label(self.frame, text=label, anchor=tk.W,
                              justify=tk.LEFT, takefocus=1, *args, **kwargs)
        self.label.pack(expand=tk.YES, fill=tk.X)
        
        self.popup = tk.Menu(window, tearoff=0)
        for label, command in self.menu_items:
            self.popup.add_command(label=label,
                                   command=command)
        
        self.label.bind('<Button-1>', self.do_popup)
        self.frame.bind('<Button-1>', self.do_popup)

        self.frame.pack(expand=tk.YES, fill=tk.X)
        
        return self.frame
    
    def do_popup(self, event):
        try:
            self.popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.popup.grab_release()
            
    def toggle_state(self):
        toggle_to = not user32.IsWindowEnabled(self.hwnd)
        
        if playback:
            logger = get_logger('Control.toggle_state')
            logger.debug('Setting "{}" control\'s Enabled state to {}'.format(self.text, toggle_to))
            
        user32.EnableWindow(self.hwnd, toggle_to)
        self.record('\t{name}.toggle_state()')

    def set_text(self, text=None):
        from tkinter.simpledialog import askstring
        
        if text:
            new_text = text
        else:
            new_text = askstring('New Text for the window',
                                 'What do you want to set the text to?',
                                 initialvalue=self.actual_text,
                                 parent=self.parent_window)
        
        if new_text:
            self.set_focus()
            
            if playback:
                logger = get_logger('Control.set_text')
                logger.debug('Changing the "{}" control\'s text to "{}"'.format(self.text, new_text))
            
            new_text = ct.create_unicode_buffer(new_text)
            if not user32.SendMessageW(self.hwnd, 0x000C, None,
                                       new_text):
                raise ct.WinError()
            
            #Redraw the component
            if not user32.RedrawWindow(self.hwnd, None, None, 1):
                raise ct.WinError()
            
            self.actual_text = new_text.value
            self.text = new_text.value.replace('&','')
            
            self.record('\t{name}.set_text({actual_text})')
            
    def is_enabled(self):
        return bool(user32.IsWindowEnabled(self.hwnd))
    
    def set_focus(self):
        return user32.SetFocus(self.hwnd)
  
class Button(Control):
    def __init__(self, parent, resource_id, class_name, text, hwnd):
        Control.__init__(self, parent, resource_id, class_name, 
                         text, hwnd)
        
        #The only added command for a button is to click it.
        self.menu_items.append(('Click Button', self.click))
        
    def click(self, wait=0.5):
        import time
        
        if playback:
            logger = get_logger('Button.click')

            logger.debug('Waiting until the "{}" button is enabled before clicking.'.format(self.text))
            while not self.is_enabled():
                time.sleep(1.0/2.0)
        
        #The MSDN documentation recommends calling this function first
        user32.SetForegroundWindow(self.parent.hwnd)
        self.set_focus()
        
        if playback:
            logger.debug('Waiting {} seconds before clicking the "{}" button.'.format(wait, self.text))
            time.sleep(wait)
        
        #Notify the parent window we clicked the button
        if user32.SendMessageA(self.hwnd, WM_LBUTTONDOWN, 1, 1) != 0:
            raise ct.WinError()
        elif user32.SendMessageA(self.hwnd, WM_LBUTTONUP, 1, 1) != 0:
            raise ct.WinError()
        
        if playback:
            #Don't allow any other action until the window is redrawn
            logger.debug('Forcing the button to redraw.')
            user32.RedrawWindow(self.hwnd, None, None, 1)
        else:
            self.record('\t{name}.click()')
   
class Edit(Control):
    
    WM_SETTEXT = 0x000C
    
    def __init__(self, parent, resource_id, class_name, text, hwnd):
        Control.__init__(self, parent, resource_id, class_name, 
                         text, hwnd)