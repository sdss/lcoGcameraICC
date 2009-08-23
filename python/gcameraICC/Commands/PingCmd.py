#!/usr/bin/env python

""" PingCmd.py -- wrap 'ping' functions. """

import logging

import opscore.protocols.validation as validation

from opscore.utility.qstr import qstr

class PingCmd():
    """ Wrap 'ping' and friends.  """
    
    def __init__(self, actor):
        self.actor = actor
        
        self.keys = {}
        self.vocab = [
            ('ping', '', self.ping_cmd)
            ]

    def ping_cmd(self, cmd):
        """ Top-level "ping" command handler. Query all the controllers for liveness/happiness. """

        cmd.finish('text="Pong."')

