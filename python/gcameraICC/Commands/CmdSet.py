#!/usr/bin/env python

""" CmdSet.py -- a vocabulary of MC commands. """

class CmdSet(object):
    def __init__(self, actor):

        self.actor = actor

        self.vocab = {}
        self.keys = ()
