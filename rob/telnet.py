'''
Created on Jun 24, 2012

@author: Vecos
'''

from config import Config
import rob.commands
from rob.console import ConsoleEngine
from rob.robengine import ROBEngine
from rob.util import MenuStr

import miniboa

import hashlib
import threading


class TelnetEngine:
    '''
    A thread that manages the telnet side of ROBin.
    Responsible for all telnet clients and functionality.
    Borg?
    '''
    
    _shared_state = {}
    inited = False
    
    def __init__(self):
        '''
        Initalizes the miniboa telnet server
        '''
        
        self.__dict__ = self._shared_state
        
        if not self.inited:
            # ROBin init
            self.server = miniboa.TelnetServer(port=Config.port,
                                               timeout=Config.timeout, 
                                               on_connect=self._on_connect,
                                               on_disconnect=self._on_disconnect)
            
            # Threading init
            self.runlevel = "NORMAL"
            self.shutdownevent = threading.Event()
            self.thread = threading.Thread(target=self._threadrun, name='Telnet')
            self.thread.daemon = True
            self.thread.start()
            
            # Commands
            self.command_list = rob.commands.getcommands()
            
            self.inited = True
    
    def _on_connect(self, client):
        console = ConsoleEngine()
        console.logtask("++ New connection from {}".format(client.addrport()), False)
        
        # Prompt for username/password
        client.robin = {}
        client.robin['state'] = "LOGIN_USER"
        
        
        # Login prompt
        t = MenuStr()
        t.add()
        t.add("[ROBin]")
        t.add()
        client.send(t.get())
        client.send("Username: ")
        
    def _on_disconnect(self, client):
        console = ConsoleEngine()
        try:
            t = "-- Lost connection to {} [{}]".format(client.addrport(), client.robin['user'])
        except KeyError:
            t = "-- Lost connection to {}".format(client.addrport())
        console.logtask(t, False)
    
    def _threadrun(self):
        while (self.runlevel == "NORMAL"):
            # Check for new clients, then process existing ones
            self.server.poll()
            self.process_clients()
        # Handle shutdown, flush output buffers and notify main thread
        self.handleshutdown()
        self.server.poll()
        self.shutdownevent.set()
            
    def process_clients(self):
        for client in self.server.client_list():
            # Don't need to wait for a command to kick
            if (client.robin['state'] == "KICK"):
                client.active = False
            if (client.cmd_ready):
                self.nanny(client, client.get_command())
                
    def nanny(self, client, command):
        '''
        Handles logins and logouts
        Also responsible for command-external spacers and prompt
        In charge of client.robin['state']
        '''
        console = ConsoleEngine()
        
        # First, handle logins
        if (client.robin['state'] == "LOGIN_USER"):
            # First line received should be username.
            # Note attempted username for logging
            client.robin['attempt_user'] = command
            if (command == Config.user):
                client.robin['state'] = "LOGIN_PASS"
                client.send('Password: ')
            else:
                console.logtask("** No user: {} tried to login as [{}]".format(client.addrport(), client.robin['attempt_user']), False)
                client.send('No such user.\nUsername: ')
        elif (client.robin['state'] == "LOGIN_PASS"):
            m = hashlib.md5()
            m.update(command)
            if (m.hexdigest() == Config.password):
                # Done with login. Send welcome.
                client.robin['user'] = client.robin['attempt_user']
                client.robin['state'] = "NORMAL"
                console.logtask("== {} successfully logged in as [{}]".format(client.addrport(), client.robin['user']), False)
                
                self.welcome(client)
                self.sendprompt(client)
            else:
                # Wrong password
                console.logtask("** Wrong password: {} tried to login as [{}]".format(client.addrport(), client.robin['attempt_user']), False)
                client.send("Wrong password.\n")
                client.robin['state'] = "KICK"
        elif (client.robin['state'] == "NORMAL"):
            # No command.
            if (command == ''):
                self.sendprompt(client)
                return
            
            # Apply spacers and call the parser
            client.send("\n")
            t = self.parse(client, command)
            
            # Process special returns
            if (t == "LOGOUT"):
                # Give them a chance to see our logout message - kick them after the next poll
                client.robin['state'] = "KICK"
                return
            if (t == "SHUTDOWN"):
                # We're going down
                self.runlevel = "SHUTDOWN"
                return
            if (t == "RELOAD"):
                # Catch 'reload' command to refresh command list
                y = console.logtask("Reloading command table ({})...".format(client.addrport()))
                reload(rob.commands)
                self.command_list = rob.commands.getcommands()
                console.logstatus(y, "[OK]")
                client.send("Reloaded command table.\n")
                
            self.sendprompt(client)
            
    def parse(self, client, command):
        '''
        Looks passed command up in command_list, calls command specific function
        '''
        
        # Expand client's command to possible command candidates
        candidates, arguments = rob.commands.expand(command, self.command_list.keys())
        
        if (len(candidates) == 0):
            client.send("Invalid command.\n")
        elif (len(candidates) > 1):
            t = MenuStr()
            t.add("The command ^c{}^~ was not specific enough. Did you mean:".format(command.split(None, 1)[0]))
            for x in candidates:
                t.add("  ^c{}^~".format(x))
            client.send_cc(t.get())
        elif (len(candidates) == 1):
            return self.command_list[candidates[0]](client=client, arguments=arguments)
                
    def welcome(self, client):
        # Convenience function for post-login initialization and data
        client.robin['char'] = None 
        
        # MOTD
        t = MenuStr()
        t.add()
        t.add('-' * 80)
        t.add("{:^80}".format("Welcome to ROBin!"))
        t.add('-' * 80)
        t.add()
        client.send(t.get())
        
        # Call 'char' command to show chars
        self.command_list['char'](client)
    
    def sendprompt(self, client):
        if client.robin['char'] is None:
            prompt = "\n> "
        else:
            char = client.robin['char']
            prompt = "\n[^G{}^~]\n^C{}/{}c ^R{}/{}s ^Y{}r^~> ".format(char.name,
                                                           char.cards, char.maxcards,
                                                           char.stamina, char.maxstamina,
                                                           char.rupies)
        
        client.send_cc(prompt)
    
    def broadcast(self, message):
        '''
        Broadcast a message to all connected clients
        '''
        for client in self.server.client_list():
            client.send_cc(message)
        
    def handleshutdown(self):
        '''
        Save sessions to disk, etc.
        '''
        engine = ROBEngine()
        engine.savechars()
        
        self.broadcast("Server shutting down.\n")
        pass