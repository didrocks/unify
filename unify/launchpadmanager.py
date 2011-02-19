# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# This file is in the public domain
### END LICENSE

from launchpadlib.launchpad import Launchpad
launchpad = Launchpad.login_with('unify', 'edge', allow_access_levels=["WRITE_PUBLIC"])


def getLaunchpad():
    '''Get THE Launchpad'''
    
    return launchpad
    

