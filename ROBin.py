'''
Created on Jun 24, 2012

@author: Vecos
'''

from config import Config
import rob

if __name__ == '__main__':
    
    # Initialize console engine
    console = rob.ConsoleEngine()
    console.logtask("[ROBin v0.1]\n", status=False)
    
    # Initialize telnet server
    t = console.logtask("Initializing telnet server on port {}...".format(Config.port))
    telnet = rob.TelnetEngine()
    console.logstatus(t, "[OK]")
    
    # Initialize ROB engine
    t = console.logtask("Initializing ROB engine...")
    robengine = rob.ROBEngine()
    console.logstatus(t, "[OK]")
    
    # Initialization complete
    console.logtask("{:^79}".format('=' * 40), status=False)
    
    # Let the engines do their work.
    try:        
        telnet.shutdownevent.wait()
        console.logtask('Server shut down.', status=False)
    except KeyboardInterrupt:
        console.logtask('Server stopped by KeyboardInterrupt.', status=False)