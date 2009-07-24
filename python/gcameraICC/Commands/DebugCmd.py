#!/usr/bin/env python

""" DebugCmd.py -- wrap debugging functions. """

import logging
import time
import ConfigParser

import Commands.CmdSet
from opscore.utility.qstr import qstr

import opscore.protocols.validation as validation
import opscore.protocols.keys as keys
import opscore.protocols.types as types

class DebugCmd(Commands.CmdSet.CmdSet):
    """ Wrap debugging commands.  """
    
    def __init__(self, actor):
        Commands.CmdSet.CmdSet.__init__(self, actor)

        self.keys = keys.CmdKey.setKeys(
            keys.KeysDictionary("toy_debug", (1, 1),
                                keys.Key("pattern", types.String(), help="List of help topics to search"),
                                keys.Key("cmds", types.String()*(1,None),
                                         help="A list of command modules to reload"),
                                )
           )
        
        self.vocab = [
            ('reload', '[<cmds>]', self.do_reloadCommands),
            ('reloadConfiguration', '', self.do_reloadConfiguration),
            ('exitexit', '', self.do_exit),
            ('help', '[<pattern>]', self.do_help),
            ]
        
    def do_exit(self, cmd):
        cmd.fail('text="Huis clos"')

    def do_help(self, cmd):
        cmd.fail('text="Need help? Call 911."')

    def do_reloadCommands(self, cmd):
        """ If cmds defined, (re-)load the listed commands, otherwise reload all command sets. """
        
        if 'cmds' in cmd.cmd.keywords:
            # Load the specified module
            commands = cmd.cmd.keywords['cmds'].values
            for command in commands:
                cmd.respond('text="Attaching %s."' % (command))
                self.actor.attachCmdSet(command)
        else:
            # Load all
            cmd.respond('text="Attaching all command sets."')
            self.actor.attachAllCmdSets()
            
        cmd.finish('')
                                
    def do_reloadConfiguration(self,cmd):
        """ Reload the configuration. """
        cmd.respond('text="Reparsing the configuration file."')
        logging.warn("reading config file %s", self.actor.configFile)
        self.actor.config = ConfigParser.ConfigParser()
        self.actor.config.read(self.actor.configFile)
        cmd.finish('')

    def do_exit(self, cmd):
        """ Brutal exit when all else has failed. """
        from twisted.internet import reactor
        
        cmd.finish('text="exiting ... this should be the last you hear from me."')
        reactor.stop()
        sys.exit(0)
                                                                                                
        
