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


    
    
