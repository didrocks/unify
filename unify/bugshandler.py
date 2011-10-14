# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (C) 2011 Didier Roche <didrocks@ubuntu.com>
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

from __future__ import absolute_import, unicode_literals

import lazr
import logging
import os
import re
import textwrap

from unify import launchpadmanager
launchpad = launchpadmanager.getLaunchpad()

invalid_status_to_open_bug = ("Invalid", "Opinion", "Won't Fix", "Expired", "Incomplete")
invalid_status_to_take_bugtask_into_account = ("Invalid", "Opinion", "Won't Fix", "Expired") # we can have ayatana-design/unity (upstream): incomplete/compiz (downstream): incomplete
old_releases = ("(Ubuntu Lucid)", "(Ubuntu Maverick)", "(Ubuntu Natty)")

design_name = "ayatana-design"
db = None

def isValidDownstreamBug(name):
    """ Return True if it's a current release downstream bug """
    return ("(Ubuntu)" in name) # even if there is only an Oneiric (current release) task, we will have: (Ubuntu) and (Ubuntu Oneiric)
    
def reportUpstreamName(bug_target_name):
    """ Check if the bug is an upstream task and return the upstream task if a distro one)
    
    Return: is_upstream, upstream_name"""

    try:
        bug_target_name = re.search("(.*) \(Ubuntu.*\)",  bug_target_name).group(1)
        is_upstream = False
    except AttributeError:
        # upstream task
        is_upstream = True
    return (is_upstream, bug_target_name)

def closeAllUpstreamBugs(bugs, upstream_filter):
    """ close all upstream bugs from the lists which are in upstream_filter """
    
    # get the bug tasks for a bug:
    for bug in bugs:
        for bug_task in bug.bug_tasks:
            project_name = bug_task.bug_target_name
            if (project_name in upstream_filter and
                bug_task.status != "Fix Released"):
                logging.info("Close in fix released: %s" % bug_task.title)
                bug_task.status = "Fix Released"
                bug_task.lp_save()

# TODO: for sync state, don't use getRelevantbugLayout and just sync the status directly
    
def getRelevantbugLayout(bugs, meta_project, upstream_filter, downstream_filter):
    """ Get a dictionnary of the perfect bug layout with the meta_project rules
    
    the rule is quite simple:
    report a downtream task for each upstream project (don't open an upstream task
    if the project is only in downstream_filter like compiz/metacity)
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
    for bug in bugs.values():
        # ignore duplicates
        if bug.duplicate_of:
            continue
        relevant_bugs_dict[bug] = {}
        for bug_task in bug.bug_tasks:
            project = bug_task.bug_target_name
            if not project in upstream_filter and not project in downstream_filter:
                continue
            (is_upstream, project) = reportUpstreamName(project)
            if not project in relevant_bugs_dict[bug]:
                # create upstream and downstream task to None
                relevant_bugs_dict[bug][project] = {True: None, False: None}
            relevant_bugs_dict[bug][project][is_upstream] = bug_task
            # remove upstream task if tasks like compiz, metacity: only one downstream in filter
            # and we don't want to open an upstream one (as not handled in launchpad)
            if project not in upstream_filter and True in relevant_bugs_dict[bug][project]:
                relevant_bugs_dict[bug][project].pop(True)
                
        # Now, the logic to determine if we should remove the meta_project
        # or not open an upstream or downstream task
        number_relevant_other_than_meta = 0
        removed_other = None
        for project in relevant_bugs_dict[bug]:
            if project == meta_project:
                continue
            for switch in (True, False):
                try:
                    bug_task = relevant_bugs_dict[bug][project][switch]
                except KeyError: # for compiz/metacity, True doesn't exist for instance
                    continue
                if bug_task and bug_task.status not in invalid_status_to_take_bugtask_into_account:
                    number_relevant_other_than_meta += 1
                if bug_task and bug_task.status in invalid_status_to_open_bug:
                    # don't open invalid task if there:
                    removed_other = project
        if removed_other:
            for switch in (True, False):
                # don't create the task as the other is invalid
                try:
                    if not relevant_bugs_dict[bug][removed_other][switch]:
                        del(relevant_bugs_dict[bug][removed_other][switch])
                except KeyError: # for compiz/metacity, True doesn't exist for instance
                    continue

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
    package = launchpad.distributions['ubuntu'].getSourcePackage(name = project_name)
    bugs = {}
    for bug_task in project.searchTasks():
        bugs[re.search("(.*)/([0-9]+)", bug_task.self_link).group(2)] = bug_task.bug
    for bug_task in package.searchTasks():
        bugs[re.search("(.*)/([0-9]+)", bug_task.self_link).group(2)] = bug_task.bug
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
                        logging.debug("Open task for %s, upstream (%s): https://bugs.launchpad.net/bugs/%i, %s" % (project_name, is_upstream, bug.id, bug.title))
                        if is_upstream:
                            component_to_open = launchpad.projects[project_name]
                        else:
                            component_to_open = launchpad.distributions['ubuntu'].getSourcePackage(name = project_name)
                        try:
                            new_task = bug.addTask(target=component_to_open)
                            relevant_bugs_dict[bug][project_name][is_upstream] = new_task
                        except (lazr.restfulclient.errors.ServerError, lazr.restfulclient.errors.BadRequest), e:
                            pass

def needs_log_no_action(bugid, component, new_status, design_status):
    """ decide if an action needs to be logged rather than commited """
    
    if new_status in invalid_status_to_open_bug and not design_status:
        log_file = open(os.path.expanduser("~/.unity_bugtriage.log"), "a")
        message = "Bug https://bugs.launchpad.net/bugs/%i: %s should be set to %s, but no %s task\n" % (bugid, component, new_status, design_name)
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
    
    for bug in bugs.values():
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
                logging.info("Master bug https://bugs.launchpad.net/bugs/%i status set to %s" % (bug_id, master_upstream_status))
                master_upstream_task.status = master_upstream_status
                master_upstream_task.lp_save()
        if (upstream_task.status != upstream_status):
            if not needs_log_no_action(bug_id, "Upstream", upstream_status, design_status):
                logging.info("Upstream bug https://bugs.launchpad.net/bugs/%i status set to %s" % (bug_id, upstream_status))
                upstream_task.status = upstream_status
                upstream_task.lp_save()
        if (downstream_task.status != downstream_status):
            if not needs_log_no_action(bug_id, "Downstream", downstream_status, design_status):
                logging.info("Downstream bug https://bugs.launchpad.net/bugs/%i status set to %s" % (bug_id, downstream_status))
                downstream_task.status = downstream_status
                downstream_task.lp_save()

def setimportance(project_name, meta_project):
    """ set bug importance for a project
    
    The rule is pretty simple: all crashers is critical
    """
    
    # at this stage, all upstream and downstream correspondant bugs are supposed to be opened by previous commodities
    bugs = getAgregatedUpstreamDownstreamBugs(project_name)            

    for bug in bugs.values():
        # ignore duplicates
        if bug.duplicate_of:
            continue

        need_set_to_critical = 'apport-crash' in bug.tags
        if not need_set_to_critical:
            continue

        for bug_task in bug.bug_tasks:
            if (bug_task.status in invalid_status_to_open_bug or bug_task.status == "Fix Released"):
                continue
            project = bug_task.bug_target_name
            # ignore old releases
            for old_release in old_releases:
                if old_release in project:
                    continue
            # only work on that component (strip package name info to get upstream name)
            try:
                project = re.search("(.*) \(Ubuntu.*\)",  project).group(1)
            except AttributeError:
                pass
            if project != project_name:
                continue
            # only change status for Medium priority (which are the new ones)
            if bug_task.importance != 'Medium':
                continue

            if bug_task.importance != 'Critical':
                logging.info("Setting a task importance at crash https://bugs.launchpad.net/bugs/%i as critical" % bug.id)
                bug_task.importance = 'Critical'
                try:
                    bug_task.lp_save()
                except (lazr.restfulclient.errors.Unauthorized, lazr.restfulclient.errors.PreconditionFailed), e:
                    pass
                
    
def getFormattedDownstreamBugs(bugs):
    """ get a formatted bug with one line and (LP: #xxxx) numerotation for all downstreams bugs """

    changelog_by_line = {}
    for bug in bugs:
        formatted_entry = "%s (LP: #%s)" % (bug.title,bug.id)
        # now, look for impacted projects (all downstreams bugs should be opened)
        for bug_task in bug.bug_tasks:
            component = bug_task.bug_target_name
            if isValidDownstreamBug(component) and bug_task.status not in invalid_status_to_open_bug:
                component_name = re.search("(.*) \(Ubuntu.*\)", component).group(1)
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
                
def get_bug_mastered_track_reports(master_task, db, subset_bugs=None):
    """ get all bugs triaged by category compared to master task
    
    subset_bugs is for unit tests
    
    return: bugs not yet triaged (a)
            changes officially signed off but not yet handed over to a developer (b)
            changes officially signed off and handed over to a canonical upstream developer (c)
            changes officially signed off and handed over to a canonical downstream developer (d)
            changes officially signed off, worked by canonical upstream and ready to land in the distro (e)
            changes ready to review for design in distro (f)
            bugs in invalid shape (g)
            
            a, b, f, g bugs are a dict of bug_link: (bug title, importance, assignee)
            c, d, e bugs are dict of projects: (bug_link, bug_title, importance, assignee)"""

    project = launchpad.projects[master_task]

    untriaged_bugs = {}
    officially_signed_off = {}
    ready_to_develop_upstream = {}
    ready_to_develop_downstream = {}
    ready_to_land_downstream = {}
    ready_to_review = {}
    bugs_in_invalid_state = {}
    
    # simple cases first when looking only at the master task status
    get_bug_master_track_bug_status(project, "New", untriaged_bugs, db, subset_bugs)
    get_bug_master_track_bug_status(project, "Confirmed", untriaged_bugs, db, subset_bugs)
    get_bug_master_track_bug_status(project, "Triaged", officially_signed_off, db, subset_bugs)
    get_bug_master_track_bug_status(project, "In Progress", untriaged_bugs, db, subset_bugs)
            
    # More complicate cases where it can be either ready to develop upstream, 
    # or ready to land/develop downstream
    if subset_bugs:
        bugs = searchTasks_forstatus_in_reduce_scope(project.name, subset_bugs, "Fix Committed")
    else:
        bugs = project.searchTasks(status="Fix Committed")
    for design_bug_task in bugs:
        parent_bug = design_bug_task.bug
        if parent_bug.duplicate_of:
            continue
        bug_content = {}
        for child_task in parent_bug.bug_tasks:
            target_project = child_task.bug_target_name
            # ignore the master tracking task
            if target_project == master_task:
                continue
            (is_upstream, target_project) = reportUpstreamName(target_project)                
            if not target_project in bug_content:
                # create upstream and downstream task to None
                bug_content[target_project] = {True: None, False: None}
            assignee_name = ""
            if child_task.assignee:
                assignee_name = child_task.assignee.name
            bug_content[target_project][is_upstream] = (child_task.web_link, child_task.bug.title, child_task.status, child_task.importance, assignee_name)
            
        # ok, now let's triage this. There are multiple cases:
        # A: 1 upstream (!= fix committed, fix released), 0 or 1 downstream matching -> some work needed by upstream dev. Opening downstream task if none (if status is valid).
        # B: 1 upstream (== fix committed or fix released), 0 or 1 downstream matching (!= fix released) -> needs to land in distro. Opening downstream task if none (if status is valid).
        # C: 1 downstream without upstream matching (!= fix released) -> some work needed by downstream dev  
        # D: all tasks with (0/1 upstream, all downstream (== fix released)) -> ready for review by the change design owner
        all_downstream_closed = True
        at_least_one_downstream = False
        added_somewhere = False
        for target_project in bug_content:
            # A, B or D (valid upstream bug)
            if bug_content[target_project][True] and bug_content[target_project][True][2] not in invalid_status_to_open_bug:
                link, title, status, importance, assignee = bug_content[target_project][True]
                # a downstream bug is maybe needed
                try:
                    if not bug_content[target_project][False]:
                        component_to_open = launchpad.distributions['ubuntu'].getSourcePackage(name = target_project)
                        new_task = parent_bug.addTask(target=component_to_open)
                        logging.info("Adding downstream tasks for %s" % design_bug_task.web_link)
                        bug_content[target_project][False] = (new_task.web_link, new_task.bug.title, new_task.status, new_task.importance, None)
                        all_downstream_closed = False # we just opened the bug, obviously not landed yet. invalidate D
                    at_least_one_downstream = True # we have at least a valid downstream bug
                except lazr.restfulclient.errors.BadRequest:
                    continue # this upstream doesn't count
                # A
                if status not in ('Fix Committed', 'Fix Released'):
                    bug_to_add = (link, title, importance, assignee)
                    add_to_project_bug(ready_to_develop_upstream, target_project, bug_to_add)
                    added_somewhere = True
                    (downstream_link, downstream_title, downstream_status, downstream_importance, downstream_assignee) = bug_content[target_project][False]
                    # Something landed upstream. Ignore invalid_status_to_open_bug as this should mean
                    # we have something downstream to land.
                    # /!\ unity, as used as a metatarget though is ignoring this exception as invalid is possible…
                    if downstream_status != 'Fix Released' and (target_project != 'unity' or downstream_status not in invalid_status_to_open_bug):
                        all_downstream_closed = False # invalidate D
                # B or D
                else:
                    # Same remark as above
                    (downstream_link, downstream_title, downstream_status, downstream_importance, downstream_assignee) = bug_content[target_project][False]
                    # B
                    if downstream_status != 'Fix Released' and (target_project != 'unity' or downstream_status not in invalid_status_to_open_bug):
                        bug_to_add = (downstream_link, downstream_title, downstream_importance, downstream_assignee)
                        add_to_project_bug(ready_to_land_downstream, target_project, bug_to_add)
                        all_downstream_closed = False # invalidate D
                        added_somewhere = True
                    
            # no valid upstream task: C or D
            else:
                # invalid upstream task and no downstream opened, continue
                if not bug_content[target_project][False]:
                    continue
                link, title, status, importance, assignee =  bug_content[target_project][False]
                if status in invalid_status_to_open_bug:
                    continue
                at_least_one_downstream = True
                # C
                if status != 'Fix Released':
                    bug_to_add = (link, title, importance, assignee)
                    add_to_project_bug(ready_to_develop_downstream, target_project, bug_to_add)
                    added_somewhere = True
                    all_downstream_closed = False # invalidate D
        
        # deal with D
        if at_least_one_downstream and all_downstream_closed:
            # assignee and importance is the design bug then
            assignee_name = ""
            if design_bug_task.assignee:
                assignee_name = design_bug_task.assignee.name
            ready_to_review[design_bug_task.web_link] = (design_bug_task.bug.title, design_bug_task.importance,
                                                         assignee_name)
            added_somewhere = True
            
        if not added_somewhere:
            assignee_name = ""
            if design_bug_task.assignee:
                assignee_name = design_bug_task.assignee.name
            bugs_in_invalid_state[design_bug_task.web_link] = (design_bug_task.bug.title, design_bug_task.importance,
                                                                assignee_name)
        db.ensure_not_in_db_closed_bugs(design_bug_task.web_link)

    return (untriaged_bugs,
            officially_signed_off,
            ready_to_develop_upstream,
            ready_to_develop_downstream,
            ready_to_land_downstream,
            ready_to_review,
            bugs_in_invalid_state)

def get_bug_master_track_bug_status(project, bugstatus, bug_dict, db, subset_bugs):
    """ get data for get_bug_mastered_track_reports by status and add
    them to bug_dict"""
    
    if subset_bugs:
        bugs = searchTasks_forstatus_in_reduce_scope(project.name, subset_bugs, bugstatus)
    else:
        bugs = project.searchTasks(status=bugstatus)
    for bug_task in bugs:
        if not bug_task.bug.duplicate_of:
            assignee_name = ""
            if bug_task.assignee:
                assignee_name = bug_task.assignee.name
            bug_dict[bug_task.web_link] = (bug_task.bug.title, bug_task.importance, assignee_name)
            db.ensure_not_in_db_closed_bugs(bug_task.web_link)
        
def log_newly_closed_bugs(master_task, db, subset_bugs=None):
    """ log in the database all closed bugs since latest run to have stats """
    fix_released_bugs = {}
    project = launchpad.projects[master_task]
    if subset_bugs:
        bugs = searchTasks_forstatus_in_reduce_scope(project.name, subset_bugs, "Fix Released")
    else:
        bugs = project.searchTasks(status="Fix Released")
    for closed_design_bug_task in bugs:
        db.add_closed_reports(closed_design_bug_task.web_link, closed_design_bug_task.bug.title)
        
def add_to_project_bug(bugs, target_project, bug_to_add):
    """Add (and create if needed) to a set of bug for a project"""
    try:
        bugs[target_project].add(bug_to_add)
    except KeyError:
        bugs[target_project] = set()
        bugs[target_project].add(bug_to_add)
    
def searchTasks_forstatus_in_reduce_scope(bug_target_name, bugs, status):
    """Fake searchTask on a reduce scope"""
    
    result = []
    for bug_task in bugs:
        if bug_task.status == status and bug_task.bug_target_name == bug_target_name:
           result.append(bug_task) 
    return result
