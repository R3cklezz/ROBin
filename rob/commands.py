

'''
Created on Jun 26, 2012

@author: Vecos
'''

from rob.console import ConsoleEngine
from rob.robengine import ROBEngine
from rob.util import MenuStr

import datetime
import Queue
import threading

def getcommands():
    '''
    Return a dictionary of all commands mapped to functions
    '''
    
    command_list = {}
    command_list['break'] = com_break
    command_list['cancel'] = com_cancel
    command_list['char'] = com_char
    command_list['colour'] = com_colour
    command_list['echo'] = com_echo
    command_list['evolve'] = com_evolve
    command_list['fill'] = com_fill
    command_list['look'] = com_look
    command_list['quit'] = com_quit
    command_list['reload'] = com_reload
    command_list['score'] = com_score
    command_list['sell'] = com_sell
    command_list['shutdown'] = com_shutdown
    command_list['update'] = com_update
    command_list['use'] = com_use
    
    return command_list

def expand(command, command_list):
    '''
    Given a user input string and a list of commands,
    return the possible command matches
    @keyword command: User input string to expand
    @keyword command_list: List of commands to check against
    @return: (list:<matched commands>, string:<arguments>)
    '''
    
    # Parse for arguments
    command = command.split(None, 1)
    arguments = None
    if (len(command) == 2):
            arguments = command[1]
    
    # Return if there is an exact match
    if (command[0] in command_list):
        return ([command[0]], arguments)
    
    # Check to see if there are multiple command candidates
    candidates = []
    for x in command_list:
        if (x[:len(command[0])].lower() == command[0].lower()):
            candidates.append(x)
    return (candidates, arguments)

#### Commands ####
# client: TelnetClient
# arguments: String containing all passed arguments

def com_break(client, arguments = None):
    client.send("Resumed from breakpoint.\n")

def com_cancel(client, arguments=None):
    if 'dispatcher' in client.robin:
        if client.robin['dispatcher'].is_alive(): 
            client.robin['dispatcher'].queue.put("CANCEL")
            client.send("Cancelling...")
            return
        
    client.send("No running commands.")
    
def com_char(client, arguments=None):
    engine = ROBEngine()
    
    # No arguments - show available characters
    if arguments is None:
        t = MenuStr()
        t.add("  Currently Available Characters:")
        t.add("  -------------------------------")
        chars = engine.getchars()
        if (len(chars) == 0):
            t.add("    None")
            t.add()
        else:
            for x in chars:
                char = engine.getchar(x)
                if char.updating:
                    updating = "[Updating]"
                else:
                    updating = ''
                t.add("  ^G{:15}^~ ^R[^C{}^R]^~".format(char.name, char.agent))
                t.add("  ^gC:{:8} S:{:10} R:{:10}^~ ^r{}^~".format("{}/{}".format(char.cards, char.maxcards),
                                                           "{}/{}".format(char.stamina, char.maxstamina),
                                                           char.rupies,
                                                           updating))
                t.add("  ^K?session_id={}&viewer_id={}^~".format(char.session, char.viewer))
                currtime = datetime.datetime.now()
                sincelogon = currtime - char.logontime
                slmin, slsec = divmod(sincelogon.seconds, 60)
                slhr, slmin = divmod(slmin, 60)
                slhr += sincelogon.days * 24
                slstr = "Logon: {:02d}:{:02d}:{:02d} ago".format(slhr, slmin, slsec)
                sinceupdate = currtime - char.lastupdatetime
                sumin, susec = divmod(sinceupdate.seconds, 60)
                suhr, sumin = divmod(sumin, 60)
                suhr += sinceupdate.days * 24
                sustr = "Updated: {:02d}:{:02d}:{:02d} ago".format(suhr, sumin, susec)
                t.add("  {:29}{}".format(slstr, sustr))
                numin, nusec = divmod(char.nextupdate.seconds, 60)
                nustr = "Auto-refresh in: {:02d}:{:02d}".format(numin, nusec)
                t.add("  {:29}".format(nustr))
                t.add()
        t.add("  ^cchar add [adb|<sessionstring>] [sensation|desire]^~ to add characters")
        t.add("  ^cchar delete <name>^~ to remove characters")
        t.add("  ^cchar update [all|<name>]^~ to update character stats")
        t.add("  ^cchar use <name>^~ to take control of a character")
        t.add("  ^cchar [save|load]^~ to save or load characters to/from disk")
        client.send_cc(t.get())
        return
    
    # Arguments passed. Expand
    # e.g. 'char add sensation adb'
    # 'char': command; 'add': arg1; 'sensation': arg2; etc. 
    arg1list = ["add", "delete", "update", "use", "save", "load"]
    candidates, rawarg2 = expand(arguments, arg1list)
    if (len(candidates) == 0):
        t = MenuStr()
        t.add("Possible options are:")
        t.add()
        t.add("  ^cchar add [adb|<sessionstring>] [sensation|desire]^~ to add characters")
        t.add("  ^cchar delete <name>^~ to remove characters")
        t.add("  ^cchar update [all|<name>]^~ to update character stats")
        t.add("  ^cchar use <name>^~ to take control of a character")
        t.add("  ^cchar [save|load]^~ to save or load characters to/from disk")
        client.send_cc(t.get())
        return
    elif (len(candidates) > 1):
        t = MenuStr()
        t.add("The command ^cchar {}^~ was not specific enough. Did you mean:".format(arguments.split(None, 1)[0]))
        for x in candidates:
            t.add("  ^cchar {}^~".format(x))
        client.send_cc(t.get())
        return
    elif (len(candidates) == 1):
        arg1 = candidates[0]
        
    # Got arg1
    
    # Add
    if (arg1 == "add"):
        # Need to parse for arg2(method) and arg3(device)
        # arg2 is taken without modification: it either matches 'adb' exactly, or is treated as a session string
        if rawarg2 is None:
            # No arg2 passed
            t = MenuStr()
            t.add("Possible options are:")
            t.add()
            t.add("  ^cchar add adb [sensation|desire]^~")
            t.add("  Look for recent sessions over ADB, use [sensation|desire] headers.")
            t.add()
            t.add("  ^cchar add <sessionstring> [sensation|desire]^~")
            t.add("  Add a character using <sessionstring>, use [sensation|desire] headers.")
            t.add("  (?session_id=<session>&viewer_id=<viewer>)")
            t.add()
            t.add("You must ensure the headers chosen match the device used to start the session.")
            client.send_cc(t.get())
            return
        
        rawarg2 = rawarg2.split(None, 1)
        arg2 = rawarg2[0]
        
        # Parse rawarg3
        if (len(rawarg2) == 1):
            # No arg3 passed
            t = MenuStr()
            t.add("Possible options are:")
            t.add()
            if (arg2 == "adb"):
                t.add("  ^cchar add adb [sensation|desire]^~")
                t.add("  Look for recent sessions over ADB, use [sensation|desire] headers.")
            else:
                t.add("  ^cchar add <sessionstring> [sensation|desire]^~")
                t.add("  Add a character using <sessionstring>, use [sensation|desire] headers.")
                t.add("  (^K?session_id=<session>&viewer_id=<viewer>^~)")
            t.add()
            t.add("You must ensure the headers chosen match the device used to start the session.")
            client.send_cc(t.get())
            return
        
        rawarg3 = rawarg2[1]
        arg3list = ["sensation", "desire"]
        candidates = expand(rawarg3, arg3list)[0]
        if (len(candidates) == 0 or len(candidates) > 1):
            t = MenuStr()
            t.add("Possible options are:")
            t.add()
            if (arg2 == "adb"):
                t.add("  ^cchar add adb [sensation|desire]^~")
                t.add("  Look for recent sessions over ADB, use [sensation|desire] headers.")
            else:
                t.add("  ^cchar add <sessionstring> [sensation|desire]^~")
                t.add("  Add a character using <sessionstring>, use [sensation|desire] headers.")
                t.add("  (^K?session_id=<session>&viewer_id=<viewer>^~)")
            t.add()
            t.add("You must ensure the headers chosen match the device used to start the session.")
            client.send_cc(t.get())
            return
        else:
            arg3 = candidates[0]
            
        # If we're still here, add a character using the options given
        t = engine.addchar(arg2, arg3)
        if (t == "CANCELLED"):
            client.send("Character add cancelled by server.\n")
        elif (t == "FAILED"):
            client.send("No recent sessions found over ADB.\n")
        elif (t == "MAINTENANCE"):
            client.send("ROB Servers undergoing maintenance.\n")
        else:
            client.send_cc("Successfully added [^G{}^~] with ^R[^C{}^R]^~ headers\n".format(t, arg3))
        return
    
    # Delete char
    if (arg1 == "delete"):
        if rawarg2 is None:
            # No arg2
            t = MenuStr()
            t.add("Possible options are:")
            t.add("  ^cchar delete <name>^~    - Remove a character from the character list")
            t.add()
            t.add("Available characters:")
            for x in engine.getchars():
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        
        # Parse arg2: a character name
        arg2list = []
        for x in engine.getchars():
            arg2list.append(x)
        candidates = expand(rawarg2, arg2list)[0]
        if (len(candidates) == 0):
            t = MenuStr()
            t.add("No such character.  Choices are:")
            for x in arg2list:
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        else:
            arg2 = candidates[0]
            char = engine.getchar(arg2)
            if (client.robin['char'] == char):
                client.robin['char'] = None
            engine.delchar(arg2)
            client.send_cc("Removed ^G{}^~ from character list.\n".format(char.name))
            return
    
    if (arg1 == "update"):
        # Parse arg2: either 'all' or a character name
        if rawarg2 is None:
            # No arg2
            t = MenuStr()
            t.add("Possible options are:")
            t.add("  ^cchar update all^~    - Manually update all characters (SLOW)")
            t.add("  ^cchar update <name>^~ - Manually update a character")
            t.add()
            t.add("Available characters:")
            for x in engine.getchars():
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        
        arg2list = ["all"]
        for x in engine.getchars():
            arg2list.append(x)
        candidates = expand(rawarg2, arg2list)[0]
        if (len(candidates) == 0):
            t = MenuStr()
            '''
            t.add("Possible options are:")
            t.add("  ^cchar update all^~    - Manually update all characters (SLOW)")
            t.add("  ^cchar update <name>^~ - Manually update a character")
            '''
            t.add("No such character.  Choices are:")
            t.add("  ^call^~")
            for x in engine.getchars():
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        elif (len(candidates) > 1):
            t = MenuStr()
            t.add("The command ^cchar update {}^~ was not specific enough. Did you mean:".format(rawarg2.split(None, 1)[0]))
            for x in candidates:
                t.add("  ^cchar update {}^~".format(x))
            client.send_cc(t.get()) 
            return
        else:
            arg2 = candidates[0]
            if (arg2 == "all"):
                client.send("Not implemented. Please specify a character name.\n")
                return
            else:
                char = engine.getchar(arg2)
                char.update()
            client.send("Stats updated.\n")
            return
            
    if (arg1 == "use"):
        if rawarg2 is None:
            # No arg2
            t = MenuStr()
            t.add("Possible options are:")
            t.add("  ^cchar use <name>^~ - Take control of a character")
            t.add()
            t.add("Available characters:")
            for x in engine.getchars():
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        
        # Parse arg2: a character name
        arg2list = []
        for x in engine.getchars():
            arg2list.append(x)
        candidates = expand(rawarg2, arg2list)[0]
        if (len(candidates) == 0):
            t = MenuStr()
            t.add("No such character.  Choices are:")
            for x in arg2list:
                t.add("  ^G{}^~".format(x))
            client.send_cc(t.get())
            return
        else:
            arg2 = candidates[0]
            char = engine.getchar(arg2)
            client.robin['char'] = char
            client.send_cc("Now controlling ^G{}^~.\n".format(char.name))
            return
    
    # Save/Load
    if (arg1 == "save"):
        engine.savechars()
        client.send("Characters saved.\n")
        return
    if (arg1 == "load"):
        t = engine.loadchars()
        client.send_cc(t)
        return 

def com_colour(client, arguments=None):
    '''
    Send sample colour table to client
    '''
    t = MenuStr()
    t.add("Colours:")
    t.add("  ^^k   = ^kblack^~")
    t.add("  ^^K   = ^Kbold black (grey)^~")
    t.add("  ^^r   = ^rred^~")
    t.add("  ^^R   = ^Rbold red^~")
    t.add("  ^^g   = ^ggreen^~")
    t.add("  ^^G   = ^Gbold green^~")
    t.add("  ^^y   = ^yyellow^~")
    t.add("  ^^Y   = ^Ybold yellow^~")
    t.add("  ^^b   = ^bblue^~")
    t.add("  ^^B   = ^Bbold blue^~")
    t.add("  ^^m   = ^mmagenta^~")
    t.add("  ^^M   = ^Mbold magenta^~")
    t.add("  ^^c   = ^ccyan^~")
    t.add("  ^^C   = ^Cbold cyan^~")
    t.add("  ^^w   = ^wwhite^~")
    t.add("  ^^W   = ^Wbold white^~")
    t.add("  ^^!   = ^!bold on (use within a block of non-bright text)^~")
    t.add("  ^^.   = ^.bold off^~") 
    t.add("  ^^d   = ^ddefault text colors, varies by client^~")    
    t.add("  ^^0   = ^0black background^~")
    t.add("  ^^1   = ^1red background^~")
    t.add("  ^^2   = ^2green background^~")
    t.add("  ^^3   = ^3yellow background^~")
    t.add("  ^^4   = ^4blue background^~")
    t.add("  ^^5   = ^5magenta background^~")
    t.add("  ^^6   = ^6cyan background^~")
    t.add("  ^^I   = ^Iinverse text on^~")  
    t.add("  ^^i   = ^iinverse text off^~")
    t.add("  ^^~   = ^~reset all^~")
    t.add("  ^^U   = ^Uunderline on^~")
    t.add("  ^^u   = ^uunderline off^~")
    t.add("  ^^^^   = escape a caret, ^^^^r = ^^r^~")
    client.send_cc(t.get())
    return

def com_echo(client, arguments=None): 
    client.send_cc(arguments+"\n")
    return

def com_evolve(client, arguments=None):
    '''
    Dispatches a thread to:
    Evolves all of current char's enhancer cards
    '''
    # Are we currently active?
    if (client.robin['char'] is None):
        client.send("You need to activate a character first.\n")
        return
    
    # No arguments
    if arguments is None:
        '''
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^cevolve start^~  - Start evolving all feeders")
        t.add("  ^cevolve cancel^~ - Cancel evolutions in progress")
        client.send_cc(t.get())
        return
        '''
        arguments = "start"
    
    # Parse arg1: either 'start' or 'cancel'
    arg1list = ["start", "cancel"]
    candidates = expand(arguments, arg1list)[0]
    if (len(candidates) == 0 or len(candidates) > 1):
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^cevolve start^~  - Start evolving all feeders")
        t.add("  ^cevolve cancel^~ - Cancel evolutions in progress")
        client.send_cc(t.get())
        return
    
    arg1 = candidates[0]
    if (arg1 == "start"):
        # Make sure we aren't already running a dispatcher
        if 'dispatcher' in client.robin:
            if client.robin['dispatcher'].is_alive():
                client.send_cc(MenuStr("You need to ^ccancel^~ any running commands first.").get())
                return
        
        client.send_cc("\n[Evolving feeders]\n")
        
        # DispatcherThread config
        # Preamble strings
        pre_console = "[{}] Evolving feeders...".format(client.robin['char'].name)
        # Worker thread
        work_target = client.robin['char'].evolve
        work_extra_args = ()
        name = "[{}] Evolve".format(client.robin['char'].name)
    
        client.robin['dispatcher'] = DispatcherThread(client,
                                                     pre_console,
                                                     work_target, work_extra_args,
                                                     name)
        client.robin['dispatcher'].start()
    elif (arg1 == "cancel"):
        client.robin['dispatcher'].queue.put("CANCEL")
        client.send("Cancelling...")
    return

def com_fill(client, arguments=None):
    '''
    Dispatches a thread to:
    Fill current char's card storage with feeders, either rupies or enhancers
    '''
    # Are we currently active?
    if (client.robin['char'] is None):
        client.send("You need to activate a character first.\n")
        return
    
    # No arguments
    if arguments is None:
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^cfill enhancers^~ - Fill with cards from quest 2-5 (Best for enhancing)")
        t.add("  ^cfill rupies^~    - Fill with cards from quest 2-2 (Best for rupie farming)")
        t.add("  ^cfill cancel^~    - Cancel a fill in progress")
        client.send_cc(t.get())
        return
    
    # Parse arg1: either 'enhancers' or 'rupies' or 'cancel'
    arg1list = ["enhancers", "rupies", "cancel"]
    candidates = expand(arguments, arg1list)[0]
    if (len(candidates) == 0 or len(candidates) > 1):
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^cfill enhancers^~ - Fill with cards from quest 2-5 (Best for enhancing)")
        t.add("  ^cfill rupies^~    - Fill with cards from quest 2-2 (Best for rupie farming)")
        client.send_cc(t.get())
        return
    
    arg1 = candidates[0]
    if (arg1 == "enhancers") or (arg1 == "rupies"):
        if (arg1 == "enhancers"):
            quest = '2/5'
            minstamina = 3
        elif (arg1 == "rupies"):
            quest = '2/2'
            minstamina = 3
        
        # Make sure we aren't already running a dispatcher
        if 'dispatcher' in client.robin:
            if client.robin['dispatcher'].is_alive():
                client.send_cc(MenuStr("You need to ^ccancel^~ any running commands first.").get())
                return
        
        client.send_cc("\n[Farming quest {}]\n".format(quest))
        
        # DispatcherThread config
        # Preamble strings
        pre_console = "[{}] Filling with {}...".format(client.robin['char'].name, quest)
        # Worker thread
        work_target = client.robin['char'].fillcards
        work_extra_args = (quest, minstamina)
        name = "[{}] Fill {}".format(client.robin['char'].name, quest)
        
        client.robin['dispatcher'] = DispatcherThread(client, pre_console, work_target, work_extra_args, name)
        client.robin['dispatcher'].start()
    elif (arg1 == "cancel"):
        client.robin['dispatcher'].queue.put("CANCEL")
        client.send("Cancelling...")
    return

def com_look(client, arguments=None):
    t = MenuStr()
    t.add("[^CThe Core^~]")
    t.add()
    t.add("You are standing in a large, white room, empty save for a")
    t.add("small computer terminal that flickers to life as you approach,")
    t.add("as if beckoning you to give it a command.")
    client.send_cc(t.get())
    return

def com_quit(client, arguments=None):
    client.send("Goodbye.\n")
    return "LOGOUT"

def com_reload(client, arguments=None):
    return "RELOAD"

def com_score(client, arguments=None):
    char = client.robin['char']
    
    # Prepare segments
    # Note that caret codes are counted as characters for format strings
    namestr = "[^G{}^~]".format(char.name)
    cardstr = "^C{}^~/^C{}^~".format(char.cards, char.maxcards)
    staminastr = "^R{}^~/^R{}^~".format(char.stamina, char.maxstamina)
    rupiesstr = "^Y{}^~".format(char.rupies)
    
    currtime = datetime.datetime.now()
    
    sincelogon = currtime - char.logontime
    slmin, slsec = divmod(sincelogon.seconds, 60)
    slhr, slmin = divmod(slmin, 60)
    slstr = "^K{:02d}^~:^K{:02d}^~:^K{:02d}^~ ago".format(slhr, slmin, slsec)
    
    sinceupdate = currtime - char.lastupdatetime
    sumin, susec = divmod(sinceupdate.seconds, 60)
    suhr, sumin = divmod(sumin, 60)
    sustr = "^K{:02d}^~:^K{:02d}^~:^K{:02d}^~ ago".format(suhr, sumin, susec)

    numin, nusec = divmod(char.nextupdate.seconds, 60)
    nustr = "   ^K{:02d}^~:^K{:02d}^~ min".format(numin, nusec)
    
    t = MenuStr()
    t.add("=" * 70)
    t.add()
    t.add("   [^KLv. {:>3}^~] ".format(char.level))
    t.add("   {:24} Device:       ^R[^C{}^R]^~".format(namestr, char.agent))
    t.add("   ^c?session_id={}&viewer_id={}^~".format(char.session, char.viewer))
    t.add()
    t.add("=" * 70)
    t.add()
    t.add("   Cards:    {:18} First logged on:   {}".format(cardstr, slstr))
    t.add("   Stamina:  {:18} Last updated:      {}".format(staminastr, sustr))
    t.add("   Rupies:   {:14} Auto-refresh in:   {}".format(rupiesstr, nustr))
    t.add()
    t.add("=" * 70)
    t.add()
    t.add("   ^GInbox^~:")
    t.add()
    for x in char.inbox:
        t.add("   {}".format(x[1]))
        t.add("   ^c{}^~".format(x[0]))
        t.add()
    
    client.send_cc(t.get())

def com_sell(client, arguments=None):
    '''
    Dispatches a thread to:
    Sell all farmed rupie cards
    '''
    # Are we currently active?
    if (client.robin['char'] is None):
        client.send("You need to activate a character first.\n")
        return
    
    # No arguments
    if arguments is None:
        '''
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^csell start^~  - Start selling all rupie cards")
        t.add("  ^csell cancel^~ - Cancel current sale operation")
        client.send_cc(t.get())
        return
        '''
        arguments = "start"
        
    # Parse arg1: either 'start' or 'cancel'
    arg1list = ["start", "cancel", "loop"]
    candidates = expand(arguments, arg1list)[0]
    if (len(candidates) == 0 or len(candidates) > 1):
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^csell start^~  - Start selling all rupie cards")
        t.add("  ^csell cancel^~ - Cancel current sale operation")
        t.add("  ^csell loop^~   - Start Fill-Sell loop")
        client.send_cc(t.get())
        return
    
    arg1 = candidates[0]
    if (arg1 == "start"):
        # Make sure we aren't already running a dispatcher
        if 'dispatcher' in client.robin:
            if client.robin['dispatcher'].is_alive():
                client.send_cc(MenuStr("You need to ^ccancel^~ any running commands first.").get())
                return
            
        client.send_cc("\n[Selling cards]\n")
        
        # DispatcherThread config
        # Preamble strings
        pre_console = "[{}] Selling cards...".format(client.robin['char'].name)
        # Worker thread
        work_target = client.robin['char'].sell
        work_extra_args = ()
        name = "[{}] Sell".format(client.robin['char'].name)
    
        client.robin['dispatcher'] = DispatcherThread(client,
                                                     pre_console,
                                                     work_target, work_extra_args,
                                                     name)
        client.robin['dispatcher'].start()
    elif (arg1 == "cancel"):
        client.robin['dispatcher'].queue.put("CANCEL")
        client.send("Cancelling...")
    elif (arg1 == "loop"):
        # Make sure we aren't already running a dispatcher
        if 'dispatcher' in client.robin:
            if client.robin['dispatcher'].is_alive():
                client.send_cc(MenuStr("You need to ^ccancel^~ any running commands first.").get())
                return
        
        client.send_cc("\n[Starting Fill-Sell Loop]\n")
        
        # DispatcherThread config
        # Preamble strings
        pre_console = "[{}] Fill-Sell loop...".format(client.robin['char'].name)
        # Worker thread
        work_target = client.robin['char'].loop_sell
        work_extra_args = ()
        name = "[{}] Fill-Sell".format(client.robin['char'].name)
    
        client.robin['dispatcher'] = DispatcherThread(client,
                                                     pre_console,
                                                     work_target, work_extra_args,
                                                     name)
        client.robin['dispatcher'].start()
    return

def com_shutdown(client, arguments=None):
    return "SHUTDOWN"

def com_update(client, arguments = None):
    '''
    Update the active character
    '''
    # Are we currently active?
    if (client.robin['char'] is None):
        t = MenuStr()
        t.add("You need to activate a character to use this command.")
        t.add("To update a non-active character, use the ^cchar update^~ command.")
        client.send_cc(t.get())
        return
    
    client.robin['char'].update()
    client.send("Stats updated.\n")

def com_use(client, arguments = None):
    # No arguments
    if arguments is None:
        t = MenuStr()
        t.add("Possible options are:")
        t.add("  ^cuse <name>^~ - Take control of a character")
        client.send_cc(t.get())
        return
    
    # Parse arg1: a character name
    engine = ROBEngine()
    arg1list = []
    for x in engine.getchars():
        arg1list.append(x)
    candidates = expand(arguments, arg1list)[0]
    if (len(candidates) == 0):
        t = MenuStr()
        t.add("No such character.  Choices are:")
        for x in arg1list:
            t.add("  ^G{}^~".format(x))
        client.send_cc(t.get())
        return
    else:
        arg1 = candidates[0]
        char = engine.getchar(arg1)
        client.robin['char'] = char
        client.send_cc("Now controlling ^G{}^~.\n".format(char.name))
        return

#### Dispatcher thread ####
class DispatcherThread(threading.Thread):
    '''
    Calls a method on a ROBChar.
    @ivar queue: Output queue. ROBChar puts, EvoThread gets and sends to client
    @ivar workerqueue: Notify queue. If we get a cancel, we send it along to ROBChar. 
    '''
    def __init__(self, client, pre_console, work_target, work_extra_args, name):
        threading.Thread.__init__(self)
        
        self.daemon = True
        
        # Internal variables
        self.queue = Queue.Queue()
        self.workerqueue = Queue.Queue()
        self.client = client
        self.cancelled = False
        
        # Configuration variables
        # Preamble strings
        self.pre_console = pre_console
        # Worker thread
        self.work_target = work_target
        self.work_extra_args = work_extra_args
        self.name = name
    
    def run(self):
        self._dispatcher_run(self.pre_console, self.work_target, self.work_extra_args)
        
    def _dispatcher_run(self, pre_console, work_target, work_extra_args):
        # Preamble
        console = ConsoleEngine()
        console.log("== Started: " + pre_console)
        
        # Start the actual worker thread
        work_args = (self.queue, self.workerqueue)
        work_args += work_extra_args
        self.worker = threading.Thread(target=work_target, args=work_args)
        self.worker.start()
        
        # Process output
        t = self.queue.get(True)
        while (t != "END"):
            if (t == "CANCEL"):
                self.workerqueue.put("CANCEL")
                t = self.queue.get(True)
                console.log("-- Cancelled: " + pre_console)
                self.cancelled = True
                continue
            
            self.client.send_cc(t)
            t = self.queue.get(True)
            
        # We made it
        if not self.cancelled:
            console.log("== Done: " + pre_console)
        # Hackity hack up a sendprompt()
        from telnet import TelnetEngine
        telnet = TelnetEngine()
        telnet.sendprompt(self.client)
        
#### Loop functions ####
        