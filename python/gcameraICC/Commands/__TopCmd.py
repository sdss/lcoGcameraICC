#!/usr/bin/env python

""" TopCmd.py -- wrap top-level ICC functions. """

import pdb
import logging
import pprint
import sys
import ConfigParser

import Commands.CmdSet
from opscore.utility.qstr import qstr

class TopCmd(Commands.CmdSet.CmdSet):
    """ Wrap 'dis ping' and friends.  """
    
    def __init__(self, icc):
        Commands.CmdSet.CmdSet.__init__(self, icc)
        
        self.help = (
            ("reinit", "Reinitialize the system"),
            ("reloadCommands cmds=command,command", "Reload the command object from source."),
            ("reloadConfiguration", "Reload the boss.cfg file."),            
        )

        self.vocab = {
            'reCmds' : self.reloadCommands,
            'reloadCommands' : self.reloadCommands,
            'reloadConfiguration' : self.reloadConfiguration,
            'exitexit':self.exitCmd,
            }
        self.keys = ()
        
    def reloadCommands(self,cmd):
        """ If cmds defined, define the listed commands, other wise reload all command sets. """
        if 'cmds' in cmd.cmd.keywords:
            # Load the specified
            commands = cmd.cmd.keywords['cmds'].values
            for command in commands:
                cmd.respond('text="Attaching %s."' % (command))
                self.icc.attachCommandSet(command)
        else:
            # Load all
            cmd.respond('text="Attaching all command sets."')
            self.icc.attachAllCommandSets()
        cmd.finish('')
    
    def reloadConfiguration(self,cmd):
        """ Reload the configuration. """
        cmd.respond('text="Reparsing the configuration file."')
        logging.warn("reading config file %s", self.icc.configFile)
        self.icc.config = ConfigParser.ConfigParser()
        self.icc.config.read(self.icc.configFile)
        cmd.finish('')
    
    def exitCmd(self, cmd):
        """ Brutal exit when all else has failed. """
        from twisted.internet import reactor

        reactor.stop()
        sys.exit(0)
            

