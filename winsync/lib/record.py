import tkinter as tk
import ctypes as ct
import winsync.lib.control_windows as control

#Shorten the name usded to access most of the Windows API
user32 = ct.windll.user32

class App:
    """This is the main application for recording Windows interactions."""
    def __init__(self, master):
        self.frame = tk.Frame(master)
        
        #Packing the window will make it too narrow by default,
        #so make the minimum width larger.
        master.minsize(200, 0)
        
        #Set this to None so there is no error at the end of the script
        self.process = None
        
        self.savebtn = tk.Button(self.frame, text="Save Recording",
                                 command=self.save)
        self.savebtn.pack(fill=tk.X)
        self.filename = None

        #The pick process button
        self.pickbtn = tk.Button(self.frame, text="Pick Exe",
                                 command=self.start_exe)
        self.pickbtn.pack(fill=tk.X)

        #This button will choose what window to process
        self.windowbtn = tk.Button(self.frame, text="Choose Window",
                                   command=self.choose_window)
        self.windowbtn.pack(fill=tk.X)
                
        self.frame.pack(fill=tk.BOTH, expand=tk.YES)
        
    def start_exe(self):
        """This function will show the Open File dialog, then execute the control.start_exe
        function on the selected file. If the user presses cancel nothing is done.
        """
        import tkinter.filedialog as filedialog
                
        #Have the user choose a file to record
        exe = filedialog.askopenfilename(defaultextension='.exe',
                                         filetypes=[('Executable',
                                                     '.exe .msi')],
                                         parent=self.frame,
                                         title='Choose the Exe to Record')

        #User pressed Cancel, so do nothing
        if exe == None:
            return
        
        self.process = control.start_exe(exe)

        
    def countdown(self, msg, seconds=5):
        """This is a general method used to show a small dialog with a
        countdown timer. The caller must provide a brief message to be
        displayed in the dialog. The message will be displayed above
        the countdown itself. The dialog will automatically close when the
        countdown reaches zero.
        
        This method will block the calling thread until the dialog reaches
        zero.
        
        You can specify the length of the countdown using the seconds
        parameter. Note that the ticks of the clock are very inprecise and can
        be affected my the systems state. Therefore, this method should not be
        used for precision timings.
        """
        #Number of seconds to wait (exclude the first second)
        self.seconds = seconds
        
        def tick():
            global seconds, countlabel, dialog
            
            self.countlabel['text'] = '{}\n\nYou have {} seconds.'.format(
                                                             msg, self.seconds)
            self.seconds -= 1
            if self.seconds > 0:
                self.dialog.after(1000, tick)
            else:
                self.dialog.destroy()           
        
        #Pop up dialog that will count down
        self.dialog = tk.Toplevel()
        self.dialog.geometry('+400+400')
        
        #Label that will display the count down
        self.countlabel = tk.Label(self.dialog,
                                  text='{}\n\nYou have {} seconds.'.format(
                                  msg, self.seconds))

        self.countlabel.pack(fill=tk.BOTH)
        self.countlabel.focus_set()
        
        #Tick the clock after 1 second
        self.dialog.after(1000, tick)
        
        #Make the dialog modal
        self.dialog.transient(self.frame)
        self.frame.wait_window(self.dialog)

    def choose_window(self):
        """This method is a callback that handles setting the active window.
        The method will show a App.countdown() dialog box asking the user
        to activate a window. This window then becomes the primary window.
        """
        from tkinter.messagebox import askyesno
        
        #Ask the user to choose the window
        self.countdown('Activate the target window')

        #Get the new foreground window
        fore_hwnd = user32.GetForegroundWindow()
        
        #Get the title of the window
        text = ct.create_unicode_buffer(255)
        size = user32.GetWindowTextW(fore_hwnd, text, 255)
        if size == 0:
            raise ct.WinError()
        
        #Make sure the correct window was selected.
        if askyesno('WinSync Recording', 'Is the window titled "{}" the '
                                 'correct window?'.format(text.value)):
            self.hwnd = fore_hwnd
            
            #Get the class of the window. This makes choosing the
            #window during playback more precise.
            classname = ct.create_unicode_buffer(255)
            user32.GetClassNameW(fore_hwnd, classname, 255)
            
            #Construct a representative Window object.
            self.fore_window = control.Window(classname, text, self.hwnd, self)
            
            #This is the GUI elements that will be show for the window.
            self.control_window = ControlWindow(self.frame, self.fore_window)

    def save(self):
        """This method handles saving the recording into a python script."""
        from tkinter.filedialog import asksaveasfilename
        
        #See if the user wants to save the recording in a new file.
        if self.filename and not askyesno('WinSync Recording',
                                          'Replace the recording "{}"?'.format(self.filename)):
            self.filename = None
        
        #If we already asked the user to choose a file, don't ask again.
        if not self.filename:
            filename = asksaveasfilename(parent=self.frame,
                                     title='Save Recorded Script',
                                     filetypes=[('Python Script', '.py')],
                                     defaultextension='.py')
            if filename:
                self.filename = filename
            else:
                return
            
        with open(self.filename, 'w') as f:
            #Write each recorded action followed by a new line
            for item in control.recording:
                f.write(item)
                f.write('\n')
                
            #Add the "main" clause at the end of the file
            f.write('\n\nif __name__ == "__main__":\n')
            f.write('\tplay()')

class ControlWindow:
    def __init__(self, master, window_control):
        self.master = master
        self.window_control = window_control
        self.frame = None
        

        #Show the control window 
        self.show_controls()
        
    def show_controls(self):
        if self.frame:
            self.frame.pack_forget()
            self.frame.destroy()
            
        self.frame = tk.Frame(self.master)
        
        self.button = tk.Button(self.frame, text='Rescan Controls',
                                command=self.refresh)
        self.button.pack(expand=tk.YES, fill=tk.X)
        
        button = self.window_control.make_button(self.frame)
        button.pack()
        
        for c in self.window_control.controls:
            button = c.make_button(self.frame)
            button.pack()
                
        self.frame.pack(expand=tk.YES, fill=tk.BOTH)
        self.master.pack()
        
    def refresh(self):
        self.window_control.scan_controls()
        self.show_controls()
    
    
#Start the Application
if __name__ == '__main__':
    root = tk.Tk()
    
    app = App(root)
    
    root.mainloop()
    
    if app.process and app.process.poll() is None:
            app.process.kill()
