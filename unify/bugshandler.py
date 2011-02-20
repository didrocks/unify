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

import logging
import re
import textwrap


from unify import launchpadmanager
launchpad = launchpadmanager.getLaunchpad()

_relevant_bugs_dict = None

ignored_status = ("Invalid", "Opinion", "Won't Fix")


def isDownstreamBug(name):
    """ Return True if it's a downstream bug """
    return ("(Ubuntu" in name) # only (Ubuntu before we can have (Ubuntu Natty)

def closeAllUpstreamBugs(bugs, upstream_filter):
    """ close all upstream bugs from the lists which are in upstream_filter"""
    
    # get the bug tasks for a bug:
    for bug in bugs:
        for bug_task in bug.bug_tasks:
            project_name = bug_task.bug_target_name
            if (project_name in upstream_filter and
                not isDownstreamBug(project_name) and
                bug_task.status != "Fix Released"):
                logging.debug("Close in fix released: %s" % bug_task.title)
                bug_task.status = "Fix Released"
                
    
def getRelevantbugTasks(bugs, meta_project, upstream_filter, downstream_filter):
    """ Get a dictionnary of all "revelant" bug task project by bug
    
    the rule is quite simple:
    report a downtream task for each upstream project
    the only exception is if there is a a meta_project task
    AND another downstream or upstream task is present
    (we consider in that case that the upstream meta_project was only
    used as a milestone)
    Of course upstream and downstream tasks shouldn't be invalid
    
    the set is: ("Project name", bug task, is_upstream)"""
    
    # cache
    global _relevant_bugs_dict
    if _relevant_bugs_dict:
        return _relevant_bugs_dict
    
    # FIXME: the project should not strip (Ubuntu) in the downstream list
    # That will enable to remove the hack in openDownstreamBugsByProject()
    # for Ubuntu packages
    relevant_bugs_dict = {}
    for bug in bugs:
        upstream_list = []
        downstream_list = []
        add_master_task = False
        relevant_bugs_dict[bug] = set()
        for bug_task in bug.bug_tasks:
            project = bug_task.bug_target_name
            if not (project in upstream_filter or project in downstream_filter):
                continue
            try:
                downstream_list.append((re.search("(.*) \(Ubuntu.*\)",  project).group(1), bug_task, False))
            except AttributeError:
                # upstream task:
                upstream_list.append((project, bug_task, True))
                
        # Now, the logic to determine if it's relevant or not
        for upstream in upstream_list:
            if upstream[0] != meta_project and upstream[1].status not in ignored_status:
                relevant_bugs_dict[bug].add(upstream)
        for downstream in downstream_list:
            if downstream[1].status not in ignored_status:
                relevant_bugs_dict[bug].add(downstream)   
            if downstream[0] == meta_project:
                add_master_task = True
        # if empty, that means that there was only the meta_project upstream task to the bug, add it
        if add_master_task or not relevant_bugs_dict[bug]:
            for upstream in upstream_list:
                if upstream[0] == meta_project:
                    relevant_bugs_dict[bug].add(upstream)
                    continue
            
    _relevant_bugs_dict = relevant_bugs_dict
    logging.debug("Relevant bug tasks: %s" % relevant_bugs_dict)
    return relevant_bugs_dict


def openDownstreamBugsByProject(project_name, meta_project, upstream_filter, downstream_filter):
    """ open all relevant dowstream tasks for projects in upstream_filter """
    
    # get all bugs scope for the project but don't open them for fix released one on the entire scope
    # (avoid a lot of initial spam)
    project = launchpad.projects[project_name]
    bugs = [bug.bug for bug in project.searchTasks()]
    openDownstreamBugsByProjectForBugScope(bugs, meta_project, upstream_filter, downstream_filter, False)

def openDownstreamBugsByProjectForBugScope(bugs, meta_project, upstream_filter, downstream_filter, open_for_fixreleased=False):
    """ open all relevant downstream tasks for projects in upstream_filter limited to the bugs content""" 
    
    relevant_bugs_dict = getRelevantbugTasks(bugs, meta_project, upstream_filter, downstream_filter)
    for bug in relevant_bugs_dict:
        # for, take all downstream bugs aready in the report
        downstream_bugs = []
        for bug_content in relevant_bugs_dict[bug]:
            if not bug_content[2]:
                downstream_bugs.append(bug_content[0])
        for bug_content in relevant_bugs_dict[bug]:
            # already a downstream bug
            if not bug_content[2]:
                continue
            # if already exists
            if bug_content[0] in downstream_bugs:
                continue
            if bug_content[1].status not in ignored_status and (bug_content[1].status != "Fix Released" or open_for_fixreleased):
                logging.debug("Open downstream task for %s: %s" % (bug_content[0], bug_content[1].title))
                package = launchpad.distributions['ubuntu'].getSourcePackage(name = bug_content[0])
                #bug.addTask(package)


def openUpstreamBugsByPackage(project_name, meta_project_name):
    """ open all upstream tasks for those packages and add master project task as well """

    package = launchpad.distributions['ubuntu'].getSourcePackage(name = project_name)
    project = launchpad.projects[project_name]
    meta_project = launchpad.projects[meta_project_name]
    bugs = package.searchTasks()
    for bug_task in bugs:
        # look if there is already a corresponding upstream bug existing for this one
        already_reported = False
        meta_project_already_report = False
        for other_task in bug_task.related_tasks:
            if other_task.bug_target_name == project_name:
                already_reported = True
            if other_task.bug_target_name == meta_project_name:
                 meta_project_already_report = True
        if not already_reported and bug_task.status not in ignored_status:
            logging.debug("Open upstream task for %s" % bug_task.title)
            print("Open upstream task for %s" % bug_task.title)
            #bug_task.bug.addTask(project)
        # add an unity upstream task for across project tracking if not there
        if not meta_project_already_report:
            logging.debug("Open a master project task for %s" % bug_task.title)
            print("Open an master project task for %s" % bug_task.title)
            #bug_task.bug.addTask(meta_project)
            
    
def getFormattedBugsByDownstream(bugs):
    """ get a formatted bug with one line and (LP: #xxxx) numerotation for all downstreams bugs ss"""

    changelog_by_line = {}
    for bug in bugs:
        formatted_entry = "%s (LP: #%s)" % (bug.title,bug.id)
        # now, look for impacted projects (all downstreams bugs should be opened)
        for bug_task in bug.bug_tasks:
            component = bug_task.bug_target_name
            if isDownstreamBug(component) and bug_task.status not in invalid_status:
                component_name = re.search("(.*) \(Ubuntu.*\)",  component).group(1)
                if not component_name in changelog_by_line:
                    changelog_by_line[component_name] = []
                changelog_by_line[component_name].append(formatted_entry)
    return changelog_by_line

        
def getPackagesFormattedChangelogByProject(bugs):
    """ get a formatted changelog, delimited with 80 characters """

    components = getFormattedBugsByDownstream(bugs)
    for package in components:
        content = []
        for entry in components[package]:
            content.append(textwrap.fill(entry, initial_indent="    - ", subsequent_indent="      "))
        # ensure (LP: #xxxxx) is on the same line (as it's at the end, this won't change the number of lines)
        index = 0
        while index < len(content):
            content[index] = content[index].replace(" (LP:\n      ", "\n      (LP:")
            index += 1
            
        print "-------------------------- %s --------------------------" % package
        print "\n".join(content)
