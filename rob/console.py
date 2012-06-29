'''
Created on Jun 24, 2012

@author: Vecos
'''

from config import Config

import Queue
import threading
import time

class ConsoleEngine:
    '''
    Manages console-related functionality (primarily console logging)
    '''
    
    _shared_state = {}
    inited = False

    def __init__(self):
        '''
        Initialize console logging
        '''
        self.__dict__ = self._shared_state
        
        if not self.inited: 
            # ROBin init
            self.taskqueue = Queue.PriorityQueue()
            self.statusqueue = Queue.PriorityQueue()
            
            # Priority numbers for matching tasks to statuses
            self.nexttaskput = 0
            self.nextstatusget = None
            
            # Last printed task for line formatting
            self.lasttask = None
            
            # Threading init
            self.thread = threading.Thread(target=self._threadrun, name='ConsoleThread')
            self.thread.daemon = True
            self.thread.start()
            
            self.inited = True
    
    def _threadrun(self):
        '''
        Loop, printing tasks and statuses in order as they come in.
        '''
        while True:
            if (self.nextstatusget == None):
                # This means that there is no task waiting for a status
                task = self.taskqueue.get(True)
                # Note which status to wait for
                self.nextstatusget = task[0]
                self.lasttask = task[1]
                print task[1],
            else:
                # There is a task waiting for a status. If that status has already been queued, it should get returned 
                status = self.statusqueue.get(True)
                if (status[0] == self.nextstatusget):
                    # Got the right status
                    print "{:>{}}".format(status[1], 80 - (len(self.lasttask) + 1))
                    self.nextstatusget = None
                else:
                    # Wrong status. Drop it back in the queue and give the cpu a rest.
                    self.statusqueue.put(status)
                    time.sleep(Config.timeout)
                    continue
    
    def logtask(self, task, status=True):
        '''
        Put a new task on the log queue
        @keyword status: Should we block further output until the corresponding status is received?
        Return the priority number for status matching
        '''
    
        self.nexttaskput += 1
        self.taskqueue.put((self.nexttaskput, task))
        if (status == False):
            self.statusqueue.put((self.nexttaskput, ''))
        return self.nexttaskput
    
    def logstatus(self, priority, status):
        '''
        Put a new status on the log queue
        '''
        self.statusqueue.put((priority, status))
        
    def log(self, line):
        '''
        Log a line with no corresponding status
        '''
        self.logtask(line, False)