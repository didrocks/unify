# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (C) YYYY Didier Roche <didrocks@ubuntu.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

from unify import launchpadmanager
launchpad = launchpadmanager.getLaunchpad()

import datetime
import logging
import sys

def detectMilestones(project_name):
    """ detect the current and next milestones """
    
    project = launchpad.projects[project_name]
    current_milestone_pointer = None
    current_milestone_delta = 100000000000
    next_milestone_pointer = None
    next_milestone_delta = current_milestone_delta
    
    now = datetime.datetime.now()
    
    # current milestone is the one targeted today or in the past
    # the next one is <0 (in the future) and the min one
    for milestone in project.all_milestones:
        date_targeted = milestone.date_targeted
        if not date_targeted:
            continue
        duration = (now - date_targeted).total_seconds()
        if abs(duration) < current_milestone_delta and duration > 0:
            # new min
            current_milestone_pointer = milestone
            current_milestone_delta = duration
        if abs(duration) < next_milestone_delta and duration < 0:
            # new next min
            next_milestone_pointer = milestone
            next_milestone_delta = - duration            
    
    # Now, check that the results are plausables
    if not current_milestone_pointer or not next_milestone_pointer:
        print "Can't detect one of the two milestones, please provide them manually"
        sys.exit(1)
        
    if 'n' in raw_input("Current milestone: %s, Next milestone: %s. Ok to proceed? [Y]/n: " % (current_milestone_pointer.name, next_milestone_pointer.name)):
        sys.exit(0)
    
    return (current_milestone_pointer, next_milestone_pointer)

def getManualMilestones(project_name, milestone_name):
    """ get Milestone manually set for the project """
    
    project = launchpad.projects[project_name]
    return project.getMilestone(name=milestone_name)

def closeMilestone(milestone):
    """ set milestone as inactive """
    milestone.is_active = False
    milestone.lp_save()

def getCompletedBugTasks(milestone):
    """ get fix commited or fix released bug tasks from project and milestone """

    bugs = milestone.searchTasks(status=("Fix Committed", "Fix Released"))
    return [bug.bug for bug in bugs]

def moveOtherBugsToNextMilestone(current_milestone, next_milestone):
    """ move other bugs to next milestone """

    bugs = current_milestone.searchTasks(status=("New", "Incomplete", "Opinion", "Confirmed", "Triaged", "In Progress"))
    for bug_task in bugs:
        logging.info("Set bug to next milestone: %s" % bug_task.title)
        bug_task.milestone = next_milestone
        bug_task.lp_save()

