# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# This file is in the public domain
### END LICENSE

from unify import launchpadmanager
launchpad = launchpadmanager.getLaunchpad()

def getMilestonedBugTasksOnStatus(milestone, status):
    """ get milestone bug task on status """
    bugs = milestone.searchTasks(status=("Fix Committed", "Fix Released"))
    meta_bugs = [bug.bug for bug in bugs]
    return meta_bugs
    

def getCompletedBugTasks(project_name, milestone_name):
    """ get fix commited or fix released bug tasks from project and milestone """

    project = launchpad.projects[project_name]
    milestone = project.getMilestone(name=milestone_name)
    return getMilestonedBugTasksOnStatus(milestone, status=("Fix Committed", "Fix Released"))

def moveOtherBugsToNextMilestone(project_name, milestone_name):
    """ move other bugs to next milestone """

    project = launchpad.projects[project_name]
    milestone = project.getMilestone(name=milestone_name)
    meta_bugs = getMilestonedBugTasksOnStatus(milestone, status=("New", "Incomplete", "Opinion", "Confirmed", "Triaged", "In Progress"))


    
    
