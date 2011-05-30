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

import lazr
import logging
import os
import re
import textwrap


from unify import launchpadmanager
launchpad = launchpadmanager.getLaunchpad()

invalid_status_to_open_bug = ("Invalid", "Opinion", "Won't Fix", "Expired", "Incomplete")
old_releases = ("(Ubuntu Lucid)", "(Ubuntu Maverick)")

design_name = "ayatana-design"

def isDownstreamBug(name):
    """ Return True if it's a downstream bug """
    return ("(Ubuntu" in name) # only (Ubuntu before we can have (Ubuntu Natty)

def closeAllUpstreamBugs(bugs, upstream_filter):
    """ close all upstream bugs from the lists which are in upstream_filter """
    
    # get the bug tasks for a bug:
    for bug in bugs:
        for bug_task in bug.bug_tasks:
            project_name = bug_task.bug_target_name
            if (project_name in upstream_filter and
                not isDownstreamBug(project_name) and
                bug_task.status != "Fix Released"):
                logging.info("Close in fix released: %s" % bug_task.title)
                bug_task.status = "Fix Released"
                bug_task.lp_save()

# TODO: for sync state, don't use getRelevantbugLayout and just sync the status directly
    
def getRelevantbugLayout(bugs, meta_project, upstream_filter, downstream_filter):
    """ Get a dictionnary of the perfect bug layout with the meta_project rules
    
    the rule is quite simple:
    report a downtream task for each upstream project
    the only exception is if there is a a meta_project task
    AND another downstream or upstream task is present
    (we consider in that case that the upstream meta_project was only
    used as a milestone)
    Of course upstream and downstream tasks shouldn't be invalid
    
    the dictionnary is: key:bug_id:source_name:is_upstreambug:bug_task_id/None
    
    None means that the bug should be created as it's relevant"""
    
    
    # FIXME: the project should not strip (Ubuntu) in the downstream list
    # That will enable to remove the hack in openDownstreamBugsByProject()
    # for Ubuntu packages
    relevant_bugs_dict = {}
    for bug in bugs:
        # ignore duplicates
        if bug.duplicate_of:
            continue
        relevant_bugs_dict[bug] = {}
        for bug_task in bug.bug_tasks:
            project = bug_task.bug_target_name
            if not (project in upstream_filter or project in downstream_filter):
                continue
            try:
                project = re.search("(.*) \(Ubuntu.*\)",  project).group(1)
                is_upstream = False
            except AttributeError:
                # upstream task
                is_upstream = True
            if not project in relevant_bugs_dict[bug]:
                # create upstream and downstream task to None
                relevant_bugs_dict[bug][project] = {True: None, False: None}
            relevant_bugs_dict[bug][project][is_upstream] = bug_task
                
        # Now, the logic to determine if we should remove the meta_project
        # or not open the upstream or downstream task
        number_relevant_other_than_meta = 0
        removed_other = None
        for project in relevant_bugs_dict[bug]:
            if project == meta_project:
                continue
            for switch in (True, False):
                bug_task = relevant_bugs_dict[bug][project][switch]
                if bug_task and bug_task.status not in invalid_status_to_open_bug:
                    number_relevant_other_than_meta += 1
                if bug_task and bug_task.status in invalid_status_to_open_bug:
                    # don't open invalid task if there:
                    removed_other = project
        if removed_other:
            for switch in (True, False):
                # don't create the task as the other is invalid
                if not relevant_bugs_dict[bug][removed_other][switch]:
                    del(relevant_bugs_dict[bug][removed_other][switch])

        # so: if only invalid bugs: number_relevant_other_than_meta -> 0 OK
        #     and removed manually
        # if only a downstream/upstream meta-project bug -> OK
        # if only other relevant component bug -> need to open a upstream task only
        # if other relevant upstream bug and meta-projet task -> need to remove "None" downstream task
        
        
        if number_relevant_other_than_meta:
            # if no upstream meta_project task, add one:
            if meta_project not in relevant_bugs_dict[bug]:
                relevant_bugs_dict[bug][meta_project] = {True: None}
            # if the downstream meta_project task was "None", remove it
            if False in relevant_bugs_dict[bug][meta_project] and not relevant_bugs_dict[bug][meta_project][False]:
                del(relevant_bugs_dict[bug][meta_project][False])
 
    logging.debug("Relevant bug tasks: %s" % relevant_bugs_dict)
    return relevant_bugs_dict

def getAgregatedUpstreamDownstreamBugs(project_name):
    """ get a merge from upstream and downstream bugs for a project """
    
    project = launchpad.projects[project_name]
    bugs = [bug.bug for bug in project.searchTasks()]
    package = launchpad.distributions['ubuntu'].getSourcePackage(name = project_name)
    # add additional package bugs
    for task_bug in package.searchTasks():
        master_bug = task_bug.bug
        if master_bug not in bugs:
            bugs.append(master_bug)
    return bugs
    

def syncbugsForProject(project_name, meta_project, upstream_filter, downstream_filter):
    """ open all relevant upstream and downstream tasks for the full project """

    # get all bugs scope for the project but don't open them for fix released one on the entire scope
    # (avoid a lot of initial spam)
    bugs = getAgregatedUpstreamDownstreamBugs(project_name)
    syncbugs(bugs, meta_project, upstream_filter, downstream_filter, False)
    

def syncbugs(bugs, meta_project, upstream_filter, downstream_filter, open_for_fixreleased=False):
    """ open all relevant downstream and upstream tasks for projects in upstream_filter limited to the bugs content""" 
    
    relevant_bugs_dict = getRelevantbugLayout(bugs, meta_project, upstream_filter, downstream_filter)
    for bug in relevant_bugs_dict:        
        for project_name in relevant_bugs_dict[bug]:
            # open needed downstream and upstream bugs
            for is_upstream in (True, False):
                if is_upstream in relevant_bugs_dict[bug][project_name] and relevant_bugs_dict[bug][project_name][is_upstream] == None:
                    # The only reason to not open it is that open_for_fixreleased is false and the other (upstream/downstream task) is "fix released" as well
                    # or that the upstream or downstreams are in a ignored bug state
                    open_bug = True
                    other_task = not is_upstream
                    if (other_task) in relevant_bugs_dict[bug][project_name]:
                        if relevant_bugs_dict[bug][project_name][other_task].status == "Fix Released" and not open_for_fixreleased:
                            open_bug = False
                    if open_bug:
                        logging.debug("Open task for %s, upstream (%s): %i, %s" % (project_name, is_upstream, bug.id, bug.title))
                        if is_upstream:
                            component_to_open = launchpad.projects[project_name]
                        else:
                            component_to_open = launchpad.distributions['ubuntu'].getSourcePackage(name = project_name)
                        try:
                            new_task = bug.addTask(target=component_to_open)
                            relevant_bugs_dict[bug][project_name][is_upstream] = new_task
                        except lazr.restfulclient.errors.ServerError, e:
                            pass

def needs_log_no_action(bugid, component, new_status, design_status):
    """ decide if an action needs to be logged rather than commited """
    
    if new_status in invalid_status_to_open_bug and not design_status:
        log_file = open(os.path.expanduser("~/.unity_bugtriage.log"), "a")
        message = "Bug %i: %s should be set to %s, but no %s task\n" % (bugid, component, new_status, design_name)
        log_file.write(message)
        logging.info(message)
        log_file.close()
        return True
    return False

def syncstatus(project_name, meta_project):
    """ sync bug status for a project
    
    The rule is pretty simple: sync the "most advance" bug status.
    With the following rule:
    - sync meta_project status if more advanced and is a really master (meaning, there is no meta downstream). This one act then as an upstream status
    - don't sync fix released from upstream to downstream
    - if downstream is fix commited or fix released, don't touch upstream status (we can have the case of a cherry-pick patch)
    - sync back master_status if relevant
    - if all status are in invalid_status_to_open_bug state, we don't sync them as it's only noisy. If one isn't, we sync it to them.
    """
    
    # at this stage, all upstream and downstream correspondant bugs are supposed to be opened by previous commodities
    bugs = getAgregatedUpstreamDownstreamBugs(project_name)
    
    # define an order for status:
    status_weight = {"New": 0, "Incomplete": 1, "Opinion": 2, "Invalid": 3, "Won't Fix": 4, "Expired": 5, "Confirmed": 6, "Triaged": 7, "In Progress": 8, "Fix Committed": 9, "Fix Released": 10}
    
    for bug in bugs:
        # ignore duplicates
        if bug.duplicate_of:
            continue
        upstream_task = None
        downstream_task = None
        master_upstream_task = None
        master_downstream_task = None
        design_task = None
        for bug_task in bug.bug_tasks:
            project = bug_task.bug_target_name
            # ignore old releases
            skip = False
            for old_release in old_releases:
                if old_release in project:
                    skip = True
            if skip:
                continue
            # only get some interest in that project. Not fully optimized, but well…
            try:
                project = re.search("(.*) \(Ubuntu.*\)",  project).group(1)
                if project == project_name:
                    downstream_task = bug_task
                if project == meta_project:
                    master_downstream_task = bug_task
            except AttributeError:
                # upstream task
                if project == project_name:
                    upstream_task = bug_task
                if project == meta_project:
                    master_upstream_task = bug_task
                if project == design_name:
                    design_task = bug_task

        # check that there is something to sync
        if not upstream_task or not downstream_task:
            continue 
        
        # status
        master_upstream_status = None
        design_status = None
        if master_upstream_task:
            master_upstream_status = master_upstream_task.status
        if design_task:
            design_status = design_task.status
        upstream_status = upstream_task.status
        downstream_status = downstream_task.status
        
        # look at the meta_project status if relevant:
        # if there is a master downstream bug, discare it, other sync upstream from master
        master_bug_relevant = False
        if meta_project != project_name:
            if master_downstream_task:
                master_upstream_task = None
            if master_upstream_task:
                master_bug_relevant = True
                if (status_weight[master_upstream_status] > status_weight[upstream_status]):
                    upstream_status = master_upstream_status
        
        # sync downstream to upstream if relevant (FIXME: should check
        # milestone)
        if (status_weight[upstream_status] > status_weight[downstream_status]) and upstream_status != "Fix Released":
            downstream_status = upstream_status

        # sync upstream to downstream if relevant
        if (status_weight[downstream_status] >  status_weight[upstream_status]) and downstream_status != "Fix Committed" and downstream_status != "Fix Released":
            upstream_status = downstream_status

        # sync now upstream (or downstream, doesn't matter) to master if relevant
        if master_bug_relevant:
            if (status_weight[upstream_status] > status_weight[master_upstream_status]):
                master_upstream_status = upstream_status
        
        # bring the ayatana-design task to the dance
        if design_status:
            status_to_sync = None
            # if design says invalid (and not invalid task)
            if design_status in ("Opinion", "Won't Fix"):
                status_to_sync = design_status
            # if design says "Fix committed" or "Fix released", set the bug to "triaged" if < Triaged
            if design_status in ("Fix committed", "Fix released"):
                if (master_bug_relevant and status_weight[master_upstream_status] < status_weight["Triaged"] and master_upstream_status != "Invalid" and
                    status_weight[upstream_status] < status_weight["Triaged"] and upstream_status != "Invalid" and
                    status_weight[downstream_status] < status_weight["Triaged"] and downstream_status != "Invalid"):
                    status_to_sync = "Triaged"
            if status_to_sync:
                # reduce the noise
                if master_bug_relevant and master_upstream_status not in invalid_status_to_open_bug:
                    master_upstream_status = status_to_sync
                if upstream_status not in invalid_status_to_open_bug:
                    upstream_status = status_to_sync
                if downstream_status not in invalid_status_to_open_bug:
                    downstream_status = status_to_sync
        
        # sync status back
        bug_id = bug.id
        if (master_upstream_task and master_upstream_task.status != master_upstream_status):
            if not needs_log_no_action(bug_id, "Master", master_upstream_status, design_status):
                logging.info("Master bug %i status set to %s" % (bug_id, master_upstream_status))
                master_upstream_task.status = master_upstream_status
                master_upstream_task.lp_save()
        if (upstream_task.status != upstream_status):
            if not needs_log_no_action(bug_id, "Upstream", upstream_status, design_status):
                logging.info("Upstream bug %i status set to %s" % (bug_id, upstream_status))
                upstream_task.status = upstream_status
                upstream_task.lp_save()
        if (downstream_task.status != downstream_status):
            if not needs_log_no_action(bug_id, "Downstream", downstream_status, design_status):
                logging.info("Downstream bug %i status set to %s" % (bug_id, downstream_status))
                downstream_task.status = downstream_status
                downstream_task.lp_save()
            
    
def getFormattedDownstreamBugs(bugs):
    """ get a formatted bug with one line and (LP: #xxxx) numerotation for all downstreams bugs """

    changelog_by_line = {}
    for bug in bugs:
        formatted_entry = "%s (LP: #%s)" % (bug.title,bug.id)
        # now, look for impacted projects (all downstreams bugs should be opened)
        for bug_task in bug.bug_tasks:
            component = bug_task.bug_target_name
            if isDownstreamBug(component) and bug_task.status not in invalid_status_to_open_bug:
                component_name = re.search("(.*) \(Ubuntu.*\)",  component).group(1)
                if not component_name in changelog_by_line:
                    changelog_by_line[component_name] = []
                changelog_by_line[component_name].append(formatted_entry)
    return changelog_by_line

        
def getPackagesFormattedChangelog(bugs):
    """ get a formatted changelog, delimited with 80 characters """

    # can look at downstream bugs as we opened them before
    components = getFormattedDownstreamBugs(bugs)
    for package in components:
        content = []
        for entry in components[package]:
            content.append(textwrap.fill(entry, width= 78, initial_indent="    - ", subsequent_indent="      "))
        # ensure (LP: #xxxxx) is on the same line (as it's at the end, this won't change the number of lines)
        index = 0
        while index < len(content):
            content[index] = content[index].replace(" (LP:\n      ", "\n      (LP: ").encode("utf-8","ignore")
            index += 1
            
        print "-------------------------- %s --------------------------" % package
        print "\n".join(content)
