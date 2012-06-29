'''
Created on Jun 25, 2012

@author: Vecos
'''

from config import Config
from rob.console import ConsoleEngine

from bs4 import BeautifulSoup
import requests

from cStringIO import StringIO
import os.path
import re
import threading
import random

class ROBConn:
    '''
    Manager for connections to ROB servers
    Also manages image cache
    '''

    _shared_state = {}
    inited = False
    
    def __init__(self):
        '''
        Set up main session 
        '''
        
        self.__dict__ = self._shared_state
        
        if not self.inited:
            # Default HTTP-related variables
            if (Config.proxy is not None):
                self.proxy = {'http': Config.proxy}
            else:
                self.proxy = None
                
            self.headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Language': 'en-SG, en-US',
                'Accept-Charset': 'utf-8, iso-8859-1, utf-16, *;q=0.7'
            }
            
            # Prepare cache
            self.cachepath = Config.cache
            if not (os.path.exists(self.cachepath)):
                os.makedirs(self.cachepath)
            elif not (os.path.isdir(self.cachepath)):
                raise RuntimeError('Cache path set in Config is not a directory')
            
            # Keep a list of viewer_ids and their most recent responses
            self.lastresponse = {}
            
            # Anti-spam lock
            self.spamlock = threading.Lock()
            
            self.inited = True
    
    def _spamrelease(self):
        self.spamlock.release()        
    
    def getnewsession(self, agent):
        # One session per character
        thead = self.headers
        if (agent == "sensation"):
            thead['User-Agent'] = 'Mozilla/5.0 (Linux; U; Android 4.0.3; en-sg; HTC Sensation XE with Beats Audio Z715e Build/IML74K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30'
        elif (agent == "desire"):
            thead['User-Agent'] = 'Mozilla/5.0 (Linux; U; Android 4.0.4; en-sg; HTC Desire Build/MR1) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30'
        elif (agent == "sony"):
            thead['User-Agent'] = 'Mozilla/5.0 (Linux; U; Android 2.3.3; en-sg; SonyEricssonLT15i Build/3.0.1.A.0.145) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
        else:
            # Agent not recognized
            pass
        return requests.session(proxies=self.proxy, headers=thead, prefetch=True)
    
    def geturl(self, url, conn_session, send_session=None, send_viewer=None, get_peripherals=True, 
               postdata=None, extra_headers={}, flash=False, spammy=False):
        '''
        Makes a request to the ROB servers.
        Will not honour requests that have no user-agent, or are made with an expired session
        
        @keyword url: The url to request, relative to the ROB host
        @keyword conn_session: The requests session associated with a character
        @keyword send_session: The character session string to send, None if not needed
        @keyword send_viewer: The character viewer string to send, None if not needed
        @keyword get_peripherals: Should we parse for and request CSS and images? 
        @keyword postdata: Data to send with POST requests
        @keyword extra_headers: Dictionary of extra headers to send
        @keyword flash: Is the target a flash file?
        @keyword spammy: Is the request a spammy one?
        '''
        console = ConsoleEngine()
        
        # Extract viewer from conn_session for our internal use even if send_viewer is None
        id_viewer = conn_session.robin['viewer']
        
        # Make sure that unclean shutdowns etc don't interfere with our request
        if 'robin' in conn_session.__attrs__:
            conn_session.__attrs__.remove('robin')
        
        # Prepare url
        finalurl = StringIO()
        finalurl.write('http://bahamut-n.cygames.jp/bahamut_n/')
        finalurl.write(url)
        if (send_session or send_viewer):
            finalurl.write('?')
        if (send_session):
            finalurl.write('session_id={}'.format(send_session))
            if (send_viewer):
                finalurl.write('&')
        if (send_viewer):
            finalurl.write('viewer_id={}'.format(send_viewer))
        url = finalurl.getvalue()
        
        if (flash):
            extra_headers['Accept'] = None
            
        # Check if user-agent is set
        uafound = False
        for x in conn_session.headers.keys():
            if (x.lower() == "user-agent"):
                uafound = True
        for x in extra_headers.keys():
            if (x.lower() == "user-agent"):
                uafound = True
        if not uafound:
            console.log("** ERROR: User-Agent not set properly for [{}]!".format(conn_session.robin['name']))
            return -1
        
        # Check if session has expired
        if conn_session.robin['expired']:
            console.log("** ERROR: Session for [{}] is expired!".format(conn_session.robin['name']))
            return -2
        
        # Perform actual request
        # Get spamlock first
        self.spamlock.acquire()
        
        # allow_redirects=False cannot be included with session so must be included here 
        if (postdata is not None):
            if (postdata == ''):
                # No form data, but we need to add headers
                extra_headers['Content-Length'] = '0'
                extra_headers['Content-Type'] = "application/x-www-form-urlencoded"
            self.lastresponse[id_viewer] = conn_session.post(url,
                                                               headers=extra_headers,
                                                               allow_redirects=False,
                                                               data=postdata)
        else:
            self.lastresponse[id_viewer] = conn_session.get(url,
                                                              headers=extra_headers,
                                                              allow_redirects=False)
        
        # Handle redirects properly, stripping custom headers etc
        while(self.lastresponse[id_viewer].status_code == 302):
            self.lastresponse[id_viewer] = conn_session.get(self.lastresponse[id_viewer].headers['Location'],
                                                              allow_redirects=False,
                                                              params={'viewer_id': id_viewer})
        
        # If spammy, set time-release. If not, release now
        if spammy:
            t = threading.Timer(Config.spaminterval, self._spamrelease)
            t.name = "SpamLock"
            t.daemon = True
            t.start()
        else:
            self.spamlock.release() 
            
        # Is ROB under maintenance
        if "/maintenance" in self.lastresponse[id_viewer].url:
            self.maintenance = True
        else:
            self.maintenance = False
            
        # Is the current session expired
        if "_reauthorize" in self.lastresponse[id_viewer].url:
            conn_session.robin['expired'] = True
            console.log("** ERROR: Session for [{}] is expired!".format(conn_session.robin['name']))
            return -2
        
        # If touching a flash file, we're done
        if (flash):
            return
        
        # Read server response and grab peripherals if needed
        soup = BeautifulSoup(self.lastresponse[id_viewer].text,'lxml')

        # Parse for peripheral items to retrieve
        if (get_peripherals):
            self.getperipherals(conn_session, soup, referer=self.lastresponse[id_viewer].url)

        return soup
    
    def getreferer(self, viewer):
        ''' Return the last opened url for a given viewer_id '''
        return self.lastresponse[viewer].url
    
    def getperipherals(self, conn_session, soup, referer):
        '''
        Parse soup for CSS and image files and retrieve them using conn_session.
        Images in particular are saved in the cache
        '''
        
        # Grab as we go
        cssheaders = {
            'Referer': referer,
            'Accept': 'text/css,*/*;q=0.1'
            }
        imgheaders = {
            'Referer': referer,
            'Accept': 'image/png,image/*;q=0.8,*/*;q=0.5'
            }
        
        # TODO: Check image headers
        
        peripheralthreads = []
        
        for child in soup.descendants:
            if (hasattr(child,'name') and child.name == 'link'):
                # For css files, grab everything
                if (re.match("http://bahamut-n.cygames.jp/bahamut_n/.*css", child['href'])):
                    cget = requests.get(child['href'], session=conn_session, headers=cssheaders,
                                        return_response=False, config={'safe_mode': True})
                    cthread = self.PeripheralThread(cget)
                    cthread.start()
                    peripheralthreads.append(cthread)
                    
            if (hasattr(child,'name') and child.name == 'img'):
                # For images, check cache first
                cpath = self.cachepath
                ipath = re.match('http://bahamut-n.cygames.jp/bahamut_n/(.*)', child['src'])
                if (ipath):
                    ipath = ipath.group(1).split("/")
                    for x in ipath:
                        cpath = os.path.join(cpath, x)

                # If image is already in cache, go to next peripheral
                if (os.path.exists(cpath)):
                    continue

                # Touch file
                dname = os.path.split(cpath)[0]
                if not (os.path.exists(dname)):
                    os.makedirs(dname)
                open(cpath, 'wb').close()

                iget = requests.get(url=child['src'], session=conn_session, headers=imgheaders,
                                    return_response=False, config={'safe_mode': True})
                ithread = self.PeripheralThread(iget, savepath=cpath)
                ithread.start()
                peripheralthreads.append(ithread)

        # Join last thread for a bit
        if (len(peripheralthreads) > 0):
            peripheralthreads[len(peripheralthreads)-1].join(self.getspaminterval())
    
    class PeripheralThread(threading.Thread):
        def __init__(self, request, savepath=None):
            threading.Thread.__init__(self)
            self.request = request
            self.savepath = savepath
            self.name = "GetPeripheral"
            self.daemon = True
        def run(self):
            self.request.send()
            if (self.savepath is not None):
                f = open(self.savepath, "wb")
                f.write(self.request.response.content)
                f.close()
                
    def getspaminterval(self):
        return Config.spaminterval + random.random()
        