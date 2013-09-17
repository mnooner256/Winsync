from tkinter import *
from tkinter.font import *
import winsync.lib.config as config

import logging
import logging.handlers
import queue, sys

#This is the format used to display the messages in the window
format_template = '{levelname} ({name}): {message}'

class App:
    def __init__(self, master):
        self.wget_watcher = None
        
        master.wm_title('Winsync')
        master.protocol("WM_DELETE_WINDOW", sys.exit)
        self.master = master
        
        #This is the main frame we will pack the widgets into
        self.frame = Frame(master, width=640, height=480)
        self.frame.pack(fill=BOTH, expand=1)

        #This is a header identifing what the window is doing.
        self.header = Label(self.frame,
                            text="Winsync: Syncronizing",
                            font=("Helvetica", 16))
        self.header.pack(fill=X, expand=0, anchor=N)
        
        #This frame will have the two scroll bars an the text widget.
        self.text_frame = Frame(self.frame)
        self.text_frame.pack(fill=BOTH, expand=1, anchor=N)
        
        #The horizontal scroll bar
        self.xscrollbar = Scrollbar(self.text_frame, orient=HORIZONTAL)
        self.xscrollbar.pack(side=BOTTOM, fill=X)
        
        #The vertical scroll bar
        self.yscrollbar = Scrollbar(self.text_frame)
        self.yscrollbar.pack(side=RIGHT, fill=Y)
        
        #The text widget that will display the log
        self.text = Text(self.text_frame, borderwidth=2, relief=RIDGE, wrap=NONE)
        self.text.pack(side=LEFT,fill=BOTH, expand=1, anchor=N)
        
        #Tie the scroll bars and the text widget together
        self.xscrollbar.config(command=self.text.xview)
        self.text.config(xscrollcommand=self.xscrollbar.set)
        self.yscrollbar.config(command=self.text.yview)
        self.text.config(yscrollcommand=self.yscrollbar.set)
        
        #Font varients used in the log window
        normal = Font(family='Lucida Console', size=12)
        bold = Font(family='Lucida Console', size=12, weight=BOLD)
        
        #Declare the formatting for the log messages, the tag names are
        #the string names for the various log levels.
        self.text.tag_config('CRITICAL', foreground='white',
                             background='#500', font=normal,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        self.text.tag_config('ERROR', foreground='#CF3838', font=normal,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        self.text.tag_config('WARNING', foreground='#DEB350', font=normal,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        self.text.tag_config('INFO', foreground='#080', font=normal,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        self.text.tag_config('DEBUG', foreground='black', font=normal,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        self.text.tag_config('DOWNLOAD', foreground='yellow',
                             background='blue', font=bold,
                             spacing1=2, spacing3=2,
                             lmargin1=2, lmargin2=2)
        
        #A quit button
        self.quitbtn = Button(self.frame, text="QUIT", command=sys.exit)
        self.quitbtn.pack(side=LEFT, expand=True, anchor=E)
        
        #A button to start winsync
        self.test_btn = Button(self.frame, text="Start Winsync",
                               command=self.start_winsync)
        self.test_btn.pack(side=RIGHT, expand=True, anchor=W)

    def start_winsync(self):
        import winsync
        import winsync.lib.config as config
        
        import os.path
        import threading
        import time

        winsync_location = os.path.dirname(os.path.abspath(winsync.__file__))
        
        config.init_config(winsync_location, True)
        config.start_logger()
        
        #Tie the main logger and the GUI together using a Queue
        self.log_queue = queue.Queue()
        
        #This will enqueue log records emitted by the winsync
        #thread for later processing
        qh = logging.handlers.QueueHandler(self.log_queue)
        
        #Add the handler to the root logger
        logger = logging.getLogger()
        logger.addHandler(qh)
        
        #This will format the log records to make them human readable
        self.formatter = logging.Formatter(format_template, style='{')
        
        #Clear the text window in case winsync has been restarted
        self.text.config(state=NORMAL)
        self.text.delete(1.0, END)
        self.text.config(state=DISABLED)
        
        #Start processing the log queue every 250ms.
        root.after(250,self.show_log)
        
        #This thread is used to watch the wget process when downloading.
        #It will update the display with the downloads progress. Be careful
        #that we don't start an extra thread if we are re-running winsync
        if not self.wget_watcher:
            self.wget_watcher = threading.Thread(target=self.watch_wget)
            self.wget_watcher.daemon = True
            self.wget_watcher.start()
        
        #Start winsync in a background thread
        self.winsync = threading.Thread(target=self.run_winsync)
        self.winsync.daemon = True
        self.winsync.start()
        
    def watch_wget(self):
        import os.path
        import time

        while True:
            config.wget_start_barrier.wait()
            time.sleep(0.5) #Give wget time to flush the log file
            self.read_wget_log()
    
    def read_wget_log(self):
        import re
        import time
        
        failed = re.compile('failed')
        ignore_failed_line = re.compile('^[ \t]*[0-9]K')
        percentage_re = re.compile('([0-9]{1,3}%)')
        finished = False
        
        self.text.config(state=NORMAL)
        self.text.insert(END, '\n', 'DOWNLOAD')
        self.text.config(state=DISABLED)
        
        with open(config.wget_download_log, 'r') as log_file:
            while True:
                for line in log_file:
                    #Check if the download failed. If so output the entire
                    #log file except lines with the dots
                    if failed.search(line):
                        time.sleep(1) #Give wget time to finish up
                        log_file.seek(0)
                        self.text.config(state=NORMAL)
                        for line in log_file:
                            if not ignore_failed_line.search(line):
                                self.text.insert(END, '\n')
                                self.text.insert(END, line, 'ERROR')
                        self.text.config(state=DISABLED)
                        return
                
                    #Only output the highest percentatge of the download so far
                    m = percentage_re.search(line)
                    #Output the download percentage
                    if m:
                        self.text.config(state=NORMAL)
                        self.text.delete('{}-1l'.format(INSERT), INSERT)
                        self.text.insert(INSERT, 'Downloading: {}\n'.format(m.group(1)), 'DOWNLOAD')
                        self.text.config(state=DISABLED)
                        
                        #See if we are finished downloading
                        if '100' in m.group(1):
                            finished = True
                            break
                        
                #If the download is complete then signal wget and leave
                if finished:
                    config.wget_exit_barrier.wait()
                    return
                
                #Wait for the log file to update
                time.sleep(0.5)

    def run_winsync(self):
        import winsync.run
        
        config.logger.info('Starting Winsync...')
        winsync.run.main()
        
    
    def show_log(self):
        while not self.log_queue.empty():
            record = self.log_queue.get(block=True)
            
            output = self.formatter.format(record)
            
            #Only autoscroll the window if the scroll bar is at
            #the bottom *before* adding the new text
            scroll_location = self.yscrollbar.get()
            
            #Add the text to the window, then disable it
            self.text.config(state=NORMAL)
            self.text.insert(END, output, record.levelname)
            self.text.insert(END, '\n')
            self.text.config(state=DISABLED)

            #Autoscroll if the scrollbar was at the bottom.
            if scroll_location[1] == 1.0:
                self.text.yview(END)
            
        root.after(250,self.show_log)

if __name__ == '__main__':
    root = Tk()
    app = App(root)
    root.mainloop()