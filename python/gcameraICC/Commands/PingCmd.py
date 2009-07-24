#!/usr/bin/env python

""" PingCmd.py -- wrap 'ping' functions. """

import logging

import opscore.protocols.validation as validation

import Commands.CmdSet
from opscore.utility.qstr import qstr

class PingCmd(Commands.CmdSet.CmdSet):
    """ Wrap 'ping' and friends.  """
    
    def __init__(self, actor):
        Commands.CmdSet.CmdSet.__init__(self, actor)
        
        self.vocab = [
            ('ping', '', self.ping_cmd)
            ]

    def ping_cmd(self, cmd):
        """ Top-level "ping" command handler. Query all the controllers for liveness/happiness. """

        cmd.finish('text="Pong."')

