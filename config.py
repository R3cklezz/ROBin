'''
Created on Jun 24, 2012

@author: Vecos
'''

class Config:
    '''
    ROBin configuration variables
    '''
    
    ##### General #####
    
    # General default timeout, in seconds.
    # Used particularly to control the telnet server's polling
    # Higher values decrease cpu usage
    # Default: 0.005
    timeout = 0.05
    
    ##### Telnet #####
    
    # Port for telnet server
    # Default: 7777
    port = 7777
    
    # Telnet admin user/password (md5)
    user = 'vecos'
    password = '943e49e6be0934386085f59a038b7086'
    
    ##### ROB Client #####
    
    # Proxy for outgoing connections from the ROBin client
    # "<host>:<port>"
    # Set to None if no proxy is needed.
    proxy = "127.0.0.1:8888"
    
    # Cache path to hold downloaded images, relative to working directory
    # Will be created if it doesn't exist.
    # Default: 'cache'
    cache = 'cache'
    
    # File to hold saved sessions in, relative to working directory
    # On startup, sessions which are not too old will be reinitialized from
    # this file to create characters.
    # Default: 'sessions.txt'
    charsave = 'sessions.txt'
    
    # Maximum time since last update to allow when loading characters (in minutes)
    # ROB cookies are set every action, but expire in 3 hours.
    # There is a hard limit of 150mins (30mins buffer)
    # Default: 120 
    maxloadage = 120
    
    # Autosave interval for characters, in minutes
    # Default: 15
    autosave = 15
    
    # Minimum interval in seconds between spammy actions
    # (Flash requests, new page requests, etc)
    # A random number between 0.1 and 0.9 will automatically be added
    # Default: 1
    spaminterval = 1