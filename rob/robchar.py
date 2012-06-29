'''
Created on Jun 26, 2012

@author: Vecos
'''
from config import Config
from rob.console import ConsoleEngine
from rob.robconn import ROBConn
from rob.util import MenuStr

import datetime
import pprint
import Queue
import random
import re
import threading
import urllib

class ROBChar:
    '''
    Class describing an ROB account and game functions
    Attributes may be read directly, but all modifications should be made through public methods
    
    Each ROBChar also holds on to a requests.session object (in self.conn_session) that it gives to ROBConn every time it makes a request
    '''


    def __init__(self, session, viewer, agent):
        '''
        Initializes cookies, auto-refresh
        '''
        conn = ROBConn()
        console = ConsoleEngine()
        
        self.conn_session = conn.getnewsession(agent)
        self.agent = agent
        self.session = session
        self.viewer = viewer
        self.name = "<new>"
        
        # Ride on conn_session with some of our own data
        self.conn_session.robin = {}
        self.conn_session.robin['name'] = self.name
        self.conn_session.robin['expired'] = False
        self.conn_session.robin['viewer'] = self.viewer
        
        # Lock whenever modifications are being made
        self.lock = threading.Lock()
        
        # 1. Call ROB homepage to initialize cookies
        t = console.logtask("Initializing cookies for new character...")
        conn.geturl('', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        self.logontime = datetime.datetime.now()
        
        if conn.maintenance:
            console.logstatus(t, "[MAINTENANCE]")
            return
        else:
            console.logstatus(t, "[OK]")
        
        # 2. Scrape 'My Page', check for welcome event
        t = console.logtask("Retrieving character stats...")
        self.update()
        console.logstatus(t, "[OK]")
        console.log("== New character: [{}] ({})".format(self.name, self.agent))
    
    def _tick(self):
        '''
        Called every second by robengine
        '''
        # Handle refresh timer
        self.lock.acquire()
        self.nextupdate -= datetime.timedelta(seconds=1)
        if (self.nextupdate == datetime.timedelta(seconds=0)):
            self.lock.release()
            self.update()
            self.lock.acquire()
        
        # TODO: Handle auto action
        self.lock.release()
            
    def handlewelcome(self, soup):
        conn = ROBConn()
        
        # Must use formatter=None to ensure that '&' does not get turned into html entity
        # Also, the re seems to fail on unicode(soup)
        if ('http://bahamut-n.cygames.jp/bahamut_n/bonus_event/flash' in soup.encode(formatter=None)):
            url = re.findall(r"bonus_event/flash.*\?viewer_id=[0-9]*&flashParam=[0-9]*", soup.encode(formatter=None))[0]
            # Touch welcome flash. viewer_id already included in scraped link.
            conn.geturl(url, self.conn_session, extra_headers={'Referer': conn.getreferer(self.viewer)}, flash=True)
            
            # Scrape 'My Page' with session (emulate navbar press)
            return conn.geturl('mypage', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        else:
            return soup
        
    def update(self):
        with self.lock:            
            conn = ROBConn()
            console = ConsoleEngine()
            
            t = console.logtask("Updating stats for [{}]".format(self.name))
            self.updating = True
            
            # When doing arbitrary updates, emulate navbar press (i.e. send session)
            soup = conn.geturl('mypage', self.conn_session, send_session=self.session, send_viewer=self.viewer)
            soup = self.handlewelcome(soup)
            
            # Hmm. We only need to do this once, really.
            self.name = soup.find("div", "area_name").get_text().strip()
            self.conn_session.robin['name'] = self.name
            
            # Stats
            rawcards = soup.find("a", text="Cards").parent.find_next_sibling().get_text().split("/")
            self.cards = int(rawcards[0])
            self.maxcards = int(rawcards[1])
            
            self.rupies = soup.find('span', text=re.compile("Rupies:")).parent.find_next_sibling().get_text()
            self.rupies = int(self.rupies)
    
            rawstam = soup.find(text=re.compile("STAMINA:")).parent.span.get_text().strip().split("/")
            self.stamina = int(rawstam[0])
            self.maxstamina = int(rawstam[1])
            
            # Level and attribute points
            rawlevel = soup.find(text=re.compile("LVL:")).find_parent().span.get_text().strip()
            rawlevel = re.match("([0-9]*)(\(([0-9]*)\))?", rawlevel)
            self.level = int(rawlevel.group(1))
            if (rawlevel.group(3) is not None):
                self.points = int(rawlevel.group(3))
            else:
                self.points = 0
            
            # Scrape Inbox
            inboxlinks = soup.find(text=re.compile(r'Inbox(?! \()')).parent.find_next_sibling().find_all("a")
            self.inbox = [(re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", x['href']).group(1), x.get_text()) for x in inboxlinks]
            
            self.updating = False
            self.lastupdatetime = datetime.datetime.now()
            # Set next update anywhere between 10mins and 90mins
            self.nextupdate = datetime.timedelta(seconds=(random.randint(10, 90) * 60))
            
            console.logstatus(t, "[OK]")
    
    #### ROB Actions ####
    
    def fillcards(self, outqueue, inqueue, quest, minstamina):
        '''
        Given quest parameters, fill card storage with cards
        Return output to user using queue
        @keyword quest: String of the form "<chapter>/<quest>"
        @keyword minstamina: Minimum stamina at which to attempt quest
        @keyword outqueue: Queue to buffer output in. Sending "END" signals completion
        @keyword inqueue: Queue to listen for input. Receiving "CANCEL" signals cancellation.
        '''
        
        # Start by checking current cards/stamina
        self.update()
        if (self.cards == self.maxcards) or (int(self.stamina) < minstamina):
            t = MenuStr("\n\nNothing to do here. [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                                      self.stamina, self.maxstamina,
                                                                      self.rupies))
            outqueue.put(t.get())
            outqueue.put("END")
            return False
        
        conn = ROBConn()
        # soup = conn.geturl('mypage', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        
        # Emulate quest list presses
        t = MenuStr("\n\nEmulating quest list presses...")
        outqueue.put(t.get())
        conn.geturl('quest', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        conn.geturl('quest/quest_list', self.conn_session, send_viewer=self.viewer)
        conn.geturl('quest/mission_list/{}'.format(quest.split('/')[0]), self.conn_session, send_viewer=self.viewer)
        
        # Grab peripherals only the first time (emulating browser back presses)
        first = True
        
        while (self.cards != self.maxcards) and (int(self.stamina) >= minstamina):
            # Before hitting the server for the flash, check for cancel signal
            try:
                if (inqueue.get(False) == "CANCEL"):
                    outqueue.put(MenuStr("Cancelled.").get())
                    outqueue.put("END")
                    return False
            except Queue.Empty:
                pass
            
            # Force a post
            soup = conn.geturl('smart_phone_flash/questConvert/{}'.format(quest), self.conn_session, get_peripherals=first, postdata='')
            first = False
            
            # No Stamina (safety; should not get called)
            if re.match('http://bahamut-n.cygames.jp/bahamut_n/quest/life_empty', conn.getreferer(self.viewer)):
                t = MenuStr("")
                t.add("No more stamina.")
                outqueue.put(t.get())
                outqueue.put("END")
                return False
            
            # Touch the quest flash
            url = re.findall(r"quest/play/{}\?flashParam=[0-9]*".format(quest), soup.encode(formatter=None))[0]
            conn.geturl(url, self.conn_session, extra_headers={'Referer': conn.getreferer(self.viewer)}, flash=True, spammy=True)

            self.update()
        
            t = MenuStr("^GQuest run^~. [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                                   self.stamina, self.maxstamina,
                                                                   self.rupies))
            outqueue.put(t.get())

        # Done
        t = MenuStr("")
        if (int(self.stamina) < minstamina):
            t.add("No more stamina.")
        elif (self.cards == self.maxcards):
            t.add("Card list full.")
        outqueue.put(t.get())
        outqueue.put("END")
        return True

    def evolve(self, outqueue, inqueue):
        '''
        Evolve feeders in inventory as much as possible
        Return output to user using queue
        @keyword outqueue: Queue to buffer output in. Sending "END" signals completion
        @keyword inqueue: Queue to listen for input. Receiving "CANCEL" signals cancellation.
        '''
        
        # Start by checking current rupies
        self.update()
        if (int(self.rupies) < 575):
            t = MenuStr("\n\n^RInsufficient Rupies.^~ [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                                                     self.stamina, self.maxstamina,
                                                                                     self.rupies))
            outqueue.put(t.get())
            outqueue.put("END")
            return
        
        conn = ROBConn()
        anti_infinite = []
        
        # 1. Scrape current evolve menu
        soup = conn.geturl('card_union', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        if re.search('card_union/union_card', conn.getreferer(self.viewer)):
            # We were redirected to new base page
            # Send along cached new base data
            t = self._evo_newbase(soup)
            if not t:
                outqueue.put(MenuStr("\n\nNo available bases.").get())
                outqueue.put("END")
                return
            else:
                anti_infinite.append(t[0])
                soup = t[1]
        
        # Find card id tuple for current base
        base = soup.find(text=re.compile("Change card to evolve")).find_parent("div").div.get_text()
        base = [str.strip(str(x)) for x in base.split("\n")]
        while '' in base:
            base.remove('')
        base = tuple(base)
        
        # Make sure current base is in EvolveTable
        if base not in EvolveTable:
            t = self._evo_newbase()
            if not t:
                outqueue.put(MenuStr("\n\nNo available bases.").get())
                outqueue.put("END")
                return
            else:
                anti_infinite.append(t[0])
                soup = t[1]
                
                # Determine new base
                base = soup.find(text=re.compile("Change card to evolve")).find_parent("div").div.get_text()
                base = [str.strip(str(x)) for x in base.split("\n")]
                while '' in base:
                    base.remove('')
                base = tuple(base)
                
        t = MenuStr()
        basestr = pprint.pformat(base)
        t.add("\n\nUsing base: {}".format(basestr))
        outqueue.put(t.get())
        
        # Search for level 1 material in material list
        level1 = EvolveTable[base]['Material']
        matlink = self._evo_newmatlink(soup, level1)
        
        # Until we get a link to a proper level1 for a base, we'll keep recursing.
        while not matlink:
            outqueue.put(MenuStr("Could not find level 1 materials.  Looking for new base...").get())
            
            t = self._evo_newbase()
            if not t:
                outqueue.put(MenuStr("\n\nNo available bases.").get())
                outqueue.put("END")
                return
            else:
                if t[0] in anti_infinite:
                    y = MenuStr("\n\n** Infinite loop detected! **")
                    y.add("This probably means you have two or more feeder cards of the same kind that are higher than level 1.")
                    y.add("Please manually evolve your feeders so that for each card-type there is only one high level card and the rest are all level 1.")
                    outqueue.put(y.get())
                    outqueue.put("END")
                    return
                anti_infinite.append(t[0])
                soup = t[1]
                
            # Do we abort after finding the new base?
            try:
                if (inqueue.get(False) == "CANCEL"):
                    outqueue.put(MenuStr("Cancelled.").get())
                    outqueue.put("END")
                    return
            except Queue.Empty:
                pass
            
            # Find card id tuple for current base
            base = soup.find(text=re.compile("Change card to evolve")).find_parent("div").div.get_text()
            base = [str.strip(str(x)) for x in base.split("\n")]
            while '' in base:
                base.remove('')
            base = tuple(base)
            
            t = MenuStr()
            basestr = pprint.pformat(base)
            t.add("\n\nUsing base: {}".format(basestr))
            outqueue.put(t.get())
            
            # Search for level 1 material in material list
            level1 = EvolveTable[base]['Material']
            matlink = self._evo_newmatlink(soup, level1)
                
        outqueue.put(MenuStr("Evolving using {}...".format(pprint.pformat(level1))).get())
        
        # Go or no go?
        try:
            if (inqueue.get(False) == "CANCEL"):
                outqueue.put(MenuStr("Cancelled.").get())
                outqueue.put("END")
                return
        except Queue.Empty:
            pass
        
        # Evolve button form
        soup = conn.geturl(matlink, self.conn_session, send_viewer=self.viewer)
        eform = soup.find("form")
        eurl = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", eform['action']).group(1)
        evals = eform.find_all("input")
        equery = []
        
        # Copy all form values, make sure the submit button is there
        submitfound = False
        for x in evals[:]:
            if (x["type"] == 'submit'):
                submitfound = True
            else:
                equery.append((x["name"], x["value"]))
        
        if (not submitfound) or (re.match("(?i)Insufficient rupies", soup.encode(formatter=None))):
            t = MenuStr("\n^RInsufficient Rupies.^~ [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                                                     self.stamina, self.maxstamina,
                                                                                     self.rupies))
            outqueue.put(t.get())
            outqueue.put("END")
            return    
        
        equery = urllib.urlencode(equery)
        ehead = {'Cache-Control': 'max-age=0',
                 'Origin': 'http://bahamut-n.cygames.jp',
                 'Referer': conn.getreferer(self.viewer)}
        
        # Last chance to cancel
        try:
            if (inqueue.get(False) == "CANCEL"):
                outqueue.put(MenuStr("Cancelled.").get())
                outqueue.put("END")
                return
        except Queue.Empty:
            pass
        
        # Submit form and touch flash
        soup = conn.geturl(eurl, self.conn_session, postdata=equery, extra_headers=ehead)
        furl = re.findall(r"(?<=\"http://bahamut-n.cygames.jp/bahamut_n/)card_union.*?(?=\")", soup.encode(formatter=None))[0]
        #furl = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", form['action']).group(1)
        conn.geturl(furl, self.conn_session, extra_headers={'Referer': conn.getreferer(self.viewer)}, flash=True, spammy=True)
        
        # Done one evolution
        self.update()
        t = "^GEvolved^~. [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                     self.stamina, self.maxstamina,
                                                     self.rupies)
        outqueue.put(t)
        
        #  Recurse? As long as this is the final call
        self.evolve(outqueue, inqueue)
    
    def _evo_newbase(self, cached=None):
        '''
        Helper function for 'evolve' method
        Scrapes 'card_union/union_card' (or uses the cached data if passed) to 
        find and select  highest level feeder base for evolution.
        @return: (url, BeautifulSoup of new evolve page), or False if no available bases 
        '''
        conn = ROBConn()
        newbases = {}
        
        # Scrape cache/first page of bases
        if cached is not None:
            soup = cached
            t = self._evo_scrape(soup, "base")
            newbases.update(t)
        else:
            soup = conn.geturl('card_union/union_card', self.conn_session, send_session=self.session, send_viewer=self.viewer)
            t = self._evo_scrape(soup, "base")
            newbases.update(t)
        
        # If we see a level 3, we don't have to scrape the other pages
        level3found = False
        for k, v in t.iteritems():
            if v in EvolveTable:
                if (EvolveTable[v]['Level'] == 3):
                    level3found = True
        
        # If not, well go on and see what we get
        if not level3found:
            # Prepare page list
            pagelist = soup.find_all("a", "a_link")
            pagelist = [re.findall('card_union/union_card/.*', y['href'])[0] for y in pagelist]
            
            noDupes = []
            [noDupes.append(i) for i in pagelist if not noDupes.count(i)]
            pagelist = noDupes
                
            for y in pagelist:
                # pagelist is a list of urls
                soup = conn.geturl(y, self.conn_session, send_session=self.session, send_viewer=self.viewer)
                t = self._evo_scrape(soup, "base")
                newbases.update(t)
                # If we see a level 3 in t, get out of this loop
                # (Inefficient, but better than slowly hammering the ROB servers)
                level3found = False
                for k, v in t.iteritems():
                    if v in EvolveTable:
                        if (EvolveTable[v]['Level'] == 3):
                            level3found = True
                if level3found:
                    break
        
        # Now that we have links to all possible bases, list them by level
        selbase = []
        for k, v in newbases.iteritems():
            if v in EvolveTable:
                selbase.append((EvolveTable[v]['Level'], k))
        selbase = sorted(selbase, key=lambda x: x[0], reverse=True)
        
        # Now pick the highest level base
        if (len(selbase) > 0):
            soup = conn.geturl(selbase[0][1], self.conn_session, send_viewer=self.viewer)
            return selbase[0][1], soup
        else:
            return False
    
    def _evo_newmatlink(self, soup, level1):
        '''
        Helper function for 'evolve' method
        Given the BeautifulSoup of the first materials page,
        looks for level1 within all material pages, one at a time. 
        Returns level1 link as soon as one is found.
        @return: link for level1, or False if level1 not found 
        '''
        conn = ROBConn()

        t = self._evo_scrape(soup, "material")
        
        # Was there a level1 on the first page?
        for k, v in t.iteritems():
            if (v == level1):
                return k
        
        # Build page list
        pagelist = soup.find_all("a", "a_link")
        pagelist = [re.findall('card_union/index/.*', y['href'])[0] for y in pagelist]
        
        noDupes = []
        [noDupes.append(i) for i in pagelist if not noDupes.count(i)]
        pagelist = noDupes
            
        # Keep recursing through multiple material pages searching for level1
        for y in pagelist:
            # pagelist is a list of urls
            soup = conn.geturl(y, self.conn_session, send_session=self.session, send_viewer=self.viewer)
            t = self._evo_scrape(soup, "base")
            for k, v in t.iteritems():
                if (v == level1):
                    return k
        
        # If we're still here, we didn't find a level one.
        return False
    
    def _evo_scrape(self, soup, scrapetype):
        '''
        Helper for 'evolve' method
        Given a BeautifulSoup, return a dictionary of links
        {<href>: (<card id tuple>)}
        @param scrapetype: "base" or "material"
        '''
        
        if (scrapetype == "base"):
            findtext = "Evolve >>"
            findlink = "card_union/union_change/[0-9]*"
        elif (scrapetype == "material"):
            findtext = "Use as Evolver Card"
            findlink = "card_union/check/[0-9]*"
            
        links = {}
        
        for x in soup.find_all(text=re.compile(findtext)):
            link = re.findall(findlink, x.find_parent("a")['href'])[0]
            # Name is a table and a div up from link's div
            card_id = x.find_parent("div").find_previous_sibling("div").get_text()
            card_id = [str.strip(str(y)) for y in card_id.split("\n")]
            while '' in card_id:
                card_id.remove('')
            card_id = tuple(card_id)
            links[link] = card_id
        
        return links

    def sell(self, outqueue, inqueue):
        '''
        Sell rupie cards
        Return output to user using queue
        @keyword outqueue: Queue to buffer output in. Sending "END" signals completion
        @keyword inqueue: Queue to listen for input. Receiving "CANCEL" signals cancellation.
        '''
        conn = ROBConn()
        
        # Emulate sale list presses
        t = MenuStr("\n\nEmulating sale list presses...")
        outqueue.put(t.get())
        conn.geturl('card_list', self.conn_session, send_session=self.session, send_viewer=self.viewer)
        
        # Scrape initial sales page
        soup = conn.geturl('card_sale/index', self.conn_session, send_viewer=self.viewer)
        
        # Check to see if 'All' is selected 
        if (soup.find("div", "tabArea").find("a", href=re.compile("http://bahamut-n.cygames.jp/bahamut_n/card_sale/index/0"))):
            url = soup.find("div", "tabArea").find("a", href=re.compile("http://bahamut-n.cygames.jp/bahamut_n/card_sale/index/0"))['href']
            url = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", url).group(1)
            # Add viewer ourselves to avoid confusing ROBConn
            if '?' not in url:
                raise RuntimeError
            url = url + "&viewer_id=" + self.viewer
            
            outqueue.put(MenuStr("Setting display filter to 'All'...").get())
            
            soup = conn.geturl(url, self.conn_session)
        
        # Now check to see if sort order is 'last obtained'
        orderform = soup.find("form")
        if (orderform.find("option", selected=True).get_text() != 'Last Obtained'):
            # Prepare to make it so
            vals = []
            vals.append(('sort_type', orderform.find(text=re.compile("Last Obtained")).find_parent("option")['value']))
            for x in orderform.find_all("input"):
                if (x["type"] == 'submit'):
                    continue
                vals.append((x["name"], x["value"]))
            query = urllib.urlencode(vals)
            headers = {'Cache-Control': 'max-age=0',
                 'Origin': 'http://bahamut-n.cygames.jp',
                 'Referer': conn.getreferer(self.viewer)}
            url = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", orderform['action']).group(1)
            
            outqueue.put(MenuStr("Setting sort order to 'last obtained'...").get())
            
            soup = conn.geturl(url, self.conn_session, postdata=query, extra_headers=headers)
        
        # Ready to scrape
        sell_list, form = self._sell_scrape(soup)
        
        # Prepare pagelist
        pagelist = soup.find_all("a", "a_link")
        pagelist = pagelist = [re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", y['href']).group(1) for y in pagelist]
        
        noDupes = []
        [noDupes.append(i) for i in pagelist if not noDupes.count(i)]
        pagelist = noDupes
        
        # If there is only the one page and we have no suitable sale candidates:
        if (len(pagelist) == 0 and len(sell_list) == 0):
            outqueue.put("\nNo more cards to sell.\n")
            outqueue.put("END")
            return
        
        # If we're still here, recurse over pagelist looking for sales
        pagecount = 0
        while (len(sell_list) == 0):
            if ((pagecount + 1) > len(pagelist)):
                # We reached the end of the pagelist
                outqueue.put("\nNo more cards to sell.\n")
                outqueue.put("END")
                return
        
            soup = conn.geturl(pagelist[pagecount], self.conn_session, send_viewer=self.viewer)
            sell_list, form = self._sell_scrape(soup)
            
            pagecount += 1
        
        # If we're still here, we found sale candidates.
        t = MenuStr()
        t.add("\nSelling:")
        t.add(pprint.pformat(sell_list))
        t.add()
        outqueue.put(t.get())

        # Get sale confirmation form
        vallist = []
        for x in sell_list:
            vallist.append(('sleeve[]', x[0]))
        vallist = urllib.urlencode(vallist)

        eurl = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", form['action']).group(1)
        
        ehead = {'Cache-Control': 'max-age=0',
                 'Origin': 'http://bahamut-n.cygames.jp',
                 'Referer': conn.getreferer(self.viewer)}
        
        # Go or no go?
        try:
            if (inqueue.get(False) == "CANCEL"):
                outqueue.put(MenuStr("Cancelled.").get())
                outqueue.put("END")
                return
        except Queue.Empty:
            pass
        
        # Getting
        soup = conn.geturl(eurl, self.conn_session, postdata=vallist, extra_headers=ehead)

        # Scrape the received confirmation form
        eform = soup.find("form")
        eurl = re.match("http://bahamut-n.cygames.jp/bahamut_n/(.*)", eform['action']).group(1)
        ehead = {'Cache-Control': 'max-age=0',
                 'Origin': 'http://bahamut-n.cygames.jp',
                 'Referer': conn.getreferer(self.viewer)}
        # Duplicate all form data
        evals = eform.find_all("input")
        equery = []
        for x in evals[:]:
            if (x["type"] == 'submit'): continue
            equery.append((x["name"], x["value"]))
        equery = urllib.urlencode(equery)
        
        # Last chance to cancel
        try:
            if (inqueue.get(False) == "CANCEL"):
                outqueue.put(MenuStr("Cancelled.").get())
                outqueue.put("END")
                return
        except Queue.Empty:
            pass
        
        # Push button
        soup = conn.geturl(eurl, self.conn_session, postdata=equery, extra_headers=ehead)
        
        # Done. Give a status update
        self.update()
        t = "Sold. [C:{}/{} S:{}/{} R:{}]".format(self.cards, self.maxcards,
                                                     self.stamina, self.maxstamina,
                                                     self.rupies)
        outqueue.put(t)
        
        #  Recurse? As long as this is the final call
        self.sell(outqueue, inqueue)
    
    def _sell_scrape(self, soup):
        '''
        Given a BeautifulSoup, return:
        a list of tuples (<form value>, <card id tuple>)  
        the BeautifulSoup sell form
        '''
        
        # Prepare form return
        label_list = soup.find_all('label')
        form = label_list[0].find_parent('form')
        
        # Prepare sell_list return
        sell_list = []
        for x in label_list:
            # Get card name
            name = x.find("div","list_title").get_text()
            name = [str.strip(str(y)) for y in name.split("\n")]
            while '' in name: name.remove('')
            name = tuple(name)

            # If card not in farm list, go to next card on page
            if name not in RupieTable:
                continue
            
            # If it is a rupie card, add it to our sell_list 
            val = x.input['value']
            sell_list.append((val, name))
        return sell_list, form
    
    def loop_sell(self, outqueue, inqueue):
        '''
        Alternate between filling and selling rupie cards
        Return output to user using queue
        @keyword outqueue: Queue to buffer output in. Sending "END" signals completion
        @keyword inqueue: Queue to listen for input. Receiving "CANCEL" signals cancellation.
        '''
        self.update()
        
        while (int(self.stamina) > 3) and ((int(self.maxcards) - int(self.cards)) > 0):
            if (self._loop_thread(outqueue, inqueue, target=self.fillcards, extra_args=("2/2", 3)) == "CANCEL"):
                break
            if (self._loop_thread(outqueue, inqueue, target=self.sell, extra_args=()) == "CANCEL"):
                break
        
        # We're done with the loop. Send an "END" upstream
        outqueue.put("END")
        
    
    def _loop_thread(self, outqueue, inqueue, target, extra_args):
        '''
        Runs a method for a loop, buffering in/output and returning when done
        Also returns "CANCEL" if a cancel signal is passed on inqueue
        '''
        
        # queue and workerqueue are our internal variables
        # read from queue and send to outqueue
        # read from inqueue and send to workerqueue
        # we report to the parent dispatcher using outqueue and inqueue
        queue = Queue.Queue()
        workerqueue = Queue.Queue()
        
        args = (queue, workerqueue)
        args += extra_args
        
        thread = threading.Thread(target=target, args=args) 
        thread.start()
        
        # Don't have to join, because while loop will block until "END" is received
        selfin = None
        workerout = None
        cancelled = False
        while True:
            # Pass worker any input we get, send out any output we get except "END"
            try:
                selfin = inqueue.get(True, Config.timeout)
            except Queue.Empty:
                pass
            
            try:
                workerout = queue.get(True, Config.timeout)
            except Queue.Empty:
                pass
            
            if (selfin is not None):
                if (selfin == "CANCEL"):
                    # Just note the cancellation.  We'll quit when the worker follows up with an "END"
                    cancelled = True
                workerqueue.put(selfin)
                selfin = None
            
            if (workerout == "END"):
                break
            elif (workerout is not None):
                outqueue.put(workerout)
                workerout = None
                
        if (cancelled):
            return "CANCEL"
        
    
""" Module-wide Data Tables """

# Rupie Farming
RupieTable = [
    ('Man', 'Knight', '(Normal)'),
    ('Gods', 'Angel', '(Normal)'),
    ('Demons', 'Skeleton', '(Normal)')
    ]

# Enhancers
EvolveTable = {
    #### Young Shaman
    ('Man', 'Young Shaman', '(Normal)'): {
        'Material': ('Man', 'Young Shaman', '(Normal)'),
        'Level': 1
        },
    
    ('Man', 'Young Shaman+', '(Normal)'): {
        'Material': ('Man', 'Young Shaman', '(Normal)'),
        'Level': 2
        },
    
    ('Man', 'Young Shaman++', '(Normal)'): {
        'Material': ('Man', 'Young Shaman', '(Normal)'),
        'Level': 3
        },
    
    #### Goblin
    ('Demons', 'Goblin', '(Normal)'): {
        'Material': ('Demons', 'Goblin', '(Normal)'),
        'Level': 1
        },
    
    ('Demons', 'Goblin+', '(Normal)'): {
        'Material': ('Demons', 'Goblin', '(Normal)'),
        'Level': 2
        },
    
    ('Demons', 'Goblin++', '(Normal)'): {
        'Material': ('Demons', 'Goblin', '(Normal)'),
        'Level': 3
        },
    
    #### Angel
    ('Gods', 'Angel', '(Normal)'): {
        'Material': ('Gods', 'Angel', '(Normal)'),
        'Level': 1
        },
    
    ('Gods', 'Angel+', '(Normal)'): {
        'Material': ('Gods', 'Angel', '(Normal)'),
        'Level': 2
        },
    
    ('Gods', 'Angel++', '(Normal)'): {
        'Material': ('Gods', 'Angel', '(Normal)'),
        'Level': 3
        }
    }