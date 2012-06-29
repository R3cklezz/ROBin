'''
Created on Jun 25, 2012

@author: Vecos
'''

from config import Config
from rob.console import ConsoleEngine
from rob.robchar import ROBChar
from rob.robconn import ROBConn
from rob.util import MenuStr

import copy
import cPickle as pickle
import datetime
import os
import random
import re
import shutil
import threading


class ROBEngine:
    '''
    Handles all ROB related functionality.

    Manages two other classes:
    ROBConn: Manager for connections to ROB servers
    ROBChar: Object describing an ROB account
    
    Also handles Auto-refresh and Auto-action tick timer
    '''
    
    _shared_state = {}
    inited = False

    def __init__(self):
        '''
        Initializes ROBConn, list of ROBChars, etc.
        '''
        
        self.__dict__ = self._shared_state
        
        if not self.inited:
            self.conn = ROBConn()
            self.chars = {}
            
            # Character save/load
            self.filelock = threading.Lock()
            self.loadchars()
            t = threading.Timer(Config.autosave*60, self._savetick)
            t.name = "Autosave"
            t.daemon = True
            t.start()
            
            # Tick timer
            t = threading.Timer(1, self._maintick)
            t.name = "MainTick"
            t.daemon = True
            t.start()
            
            self.inited = True
            
    def _maintick(self):
        '''
        Spawns threads for each ROBChar's _tick
        '''
        
        # Prepare loop
        t = threading.Timer(1, self._maintick)
        t.name = "MainTick"
        t.daemon = True
        t.start()
        
        # Update individual character timers
        for x in self.chars.keys():
            t = threading.Thread(target=self.chars[x]._tick)
            t.name = "CharTick"
            t.daemon = True
            t.start()
    
    def _savetick(self):
        '''
        Saves characters at specified intervals
        '''
        t = threading.Timer(Config.autosave*60, self._savetick)
        t.name = "Autosave"
        t.daemon = True
        t.start()
        
        self.savechars()
    
    def addchar(self, option, agent):
        if (option.lower() == "adb"):
            console = ConsoleEngine()
            t = console.logtask("Character add from ADB requested... (Ctrl-C cancels)")
            
            try :
                f = os.popen("adb -d logcat -d")
                d = f.read()
                c = re.findall(r"session_id=[a-z0-9]*&viewer_id=[0-9]*", d)
                c.reverse()
            except KeyboardInterrupt:
                console.logstatus(t, "[CANCELLED]")
                return "CANCELLED"

            if (len(c) == 0):
                console.logstatus(t, "[FAILED]")
                return "FAILED"
            else:
                rawsess = c[0]
                console.logstatus(t, "[OK]")
        else:
            rawsess = option
            
        rawsess = rawsess.split("&")
        session = rawsess[0].split("=")[1].strip()
        viewer = rawsess[1].split("=")[1].strip()
        
        char = ROBChar(session, viewer, agent)
        
        # If under maintenance
        if self.conn.maintenance:
            return "MAINTENANCE"
        else:
            self.chars[char.name] = char
            return char.name
    
    def delchar(self, char):
        '''
        Delete a character from the character list
        '''
        try:
            del self.chars[char]
        except KeyError:
            pass
        
        
    def getchar(self, char):
        '''
        Return a reference to a given char
        Case insensitive
        '''
    
        for x in self.chars.keys():
            if (x.lower() == char.lower()):
                return self.chars[x]
        return False
    
    def getchars(self):
        '''
        Return a list of accessible characters
        '''
        chars = self.chars.keys()
        chars.sort()
        return chars
    
    def savechars(self):
        '''
        Saves current characters to file
        '''
        console = ConsoleEngine()
        t = console.logtask("Saving character sessions to file...")
        
        with self.filelock:
            # Locks cannot be pickled, so prepare a lockless (shallow) copy
            charcopy = {}
            for x in self.getchars():
                char = self.chars[x]
                # Acquire all char locks while we rig up conn_session
                char.lock.acquire()
                charcopy[char.name] = copy.copy(char)
                charcopy[char.name].lock = None
                # Hack conn_session into existence
                charcopy[char.name].conn_session.__attrs__.append('robin')
            if (os.path.exists(Config.charsave)):
                # Make a backup of previous save
                shutil.copy(Config.charsave, Config.charsave + ".bak")
            f = open(Config.charsave, 'w')
            pickle.dump(charcopy, f)
            f.close()
            
            # Undo our conn_session rigging so that it can be used properly again
            for x in self.getchars():
                self.chars[x].conn_session.__attrs__.remove('robin')
                self.chars[x].lock.release()
            console.logstatus(t, "[OK]")
    
    def loadchars(self):
        '''
        Loads characters from file
        Characters loaded are automatically scheduled for an update between 0.5 and 10mins later
        '''
        console = ConsoleEngine()
        y = console.logtask("Loading character sessions from file...")
        t = MenuStr()
        
        with self.filelock:
            try:
                f = open(Config.charsave, 'r')
                tempchars = pickle.load(f)
                f.close()
            except IOError:
                console.logstatus(y, "[FAILED]")
                console.log("File '{}' not available for reading.".format(Config.charsave))
                return
            except:
                console.logstatus(y, "[FAILED]")
                console.log("Error reading '{}'".format(Config.charsave))
                return
            
        
        for x in tempchars.keys():
            tchar = tempchars[x]
            
            # Check last update time - we don't want anything too old
            currtime = datetime.datetime.now()
            sinceupdate = currtime - tchar.lastupdatetime
            maxage = Config.maxloadage
            if (maxage > 150):
                maxage = 150
            smaxage = maxage * 60
            if (sinceupdate.seconds > smaxage):
                # Too old
                console.log("Load: Skipped [{}] - Session too stale".format(tchar.name))
                t.add("Skipping [{}]: Session too stale.".format(tchar.name))
                continue
            
            # Check if same as existing character
            if (tchar.name in self.chars):
                # If so, see which has a fresher logon
                tsl = currtime - tchar.logontime
                sl = currtime - self.chars[tchar.name].logontime
                if (tsl < sl):
                    console.log("Load: Overrode [{}] - Fresher logon".format(tchar.name))
                    t.add("Overriding [{}]: Fresher logon.".format(tchar.name))
                else:
                    console.log("Load: Skipped [{}] - Not fresher than existing logon".format(tchar.name))
                    t.add("Skipping [{}]: Not fresher than existing logon.".format(tchar.name))
                    continue
            else:
                # New character
                console.log("Load: Added [{}]".format(tchar.name))
                t.add("Adding [{}]".format(tchar.name))
                
            # If we haven't continued by now, it's a valid character
            self.chars[tchar.name] = tchar
            self.chars[tchar.name].lock = threading.Lock()
            
            # Done. Let the other threads have at it
            self.chars[tchar.name].nextupdate = datetime.timedelta(seconds=(random.randint(30, 600))) 
            
        console.logstatus(y, "[OK]")
        return t.get()