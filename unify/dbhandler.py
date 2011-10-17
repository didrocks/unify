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

import os
import sqlite3

class DBHandler():

    def __init__(self, db_path):
    
        if not db_path:
            db_path = os.path.join(os.path.abspath('.'), 'database', 'design_bugs.sql')

        try:
            os.mkdir(os.path.dirname(db_path))
        except OSError:
            pass
            
        db_conn = sqlite3.connect(db_path)
        db_conn.row_factory = sqlite3.Row
        self.db = db_conn.cursor()
        self.current_release = 'Precise'
        
        try:
            self.db.execute('CREATE TABLE closed_design_bugs (link VARCHAR(80) PRIMARY KEY, title VARCHAR(80), release VARCHAR(10));')
        except sqlite3.OperationalError:
            pass

    def ensure_not_in_db_closed_bugs(self, bug_link):
        """reopen a previously closed bugs"""
        self.db.execute("DELETE from closed_design_bugs where link='%s'" % bug_link)
        
    def add_closed_reports(self, bug_link, title, release=None):
        """add a new bug to the dance"""
        if not release:
            release = self.current_release
        try:
            self.db.execute("INSERT into closed_design_bugs (link, title, release) VALUES (?, ?, ?)", (bug_link, title, release))
        except sqlite3.IntegrityError:
            pass # don't add the same bug twice
            
    def get_closed_reports_by_release(self):
        """Get closed reports by release"""
        results = self.db.execute("SELECT release, COUNT(*) from closed_design_bugs GROUP BY release")
        result_by_release = {}
        for line in results:
            result_by_release[line[0]] = line[1]
        return result_by_release
    
    def close_db(self):
        """close db"""
        self.db.connection.commit()
        self.db.close()
        self.db = None
        

# singleton
db_handler = None
def get_db_handler(dbpath=None):
    global db_handler
    if not db_handler or not db_handler.db:
        db_handler = DBHandler(dbpath)
    return db_handler
    
    
# only used to first import history
def first_history_import():
    from unify import launchpadmanager
    launchpad = launchpadmanager.getLaunchpad()
    db = get_db_handler() 
    project = launchpad.projects["ayatana-design"]
    for closed_design_bug_task in project.searchTasks(status="Fix Released"):
        if ("reviewedbydesign" in closed_design_bug_task.bug.tags):
            release = "Natty"
        elif ("reviewedbydesigno" in closed_design_bug_task.bug.tags):
            release = "Oneiric"
        else:
            release = "N.A"
        db.add_closed_reports(closed_design_bug_task.web_link, closed_design_bug_task.bug.title, release=release)
    db.close_db()

