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
import time
from extra import cairoplot

importance_order = ('Critical', 'High', 'Medium', 'Low', 'Wishlist', 'Undecided')

class WWWGenerator():

    def __init__(self):
        self.sourcepath = os.path.join(os.path.abspath('.'), 'site')
        self.webpath = os.path.join(self.sourcepath, 'www')
        with open(os.path.join(self.sourcepath, 'header.html.inc'), 'r') as f:
            self.header = f.read()
        with open(os.path.join(self.sourcepath, 'footer.html.inc'), 'r') as f:
            self.footer = f.read()
        self.generated_date = time.strftime('%A %B %d %Y %H:%M:%S %z')
        
    def write_page_on_disk(self, pagename, content):
        '''Write the actual page on disk'''
        
        with open(os.path.join(self.webpath, '%s.html' % pagename), 'w') as f:
            f.write(self.header)
            f.write(content.encode('utf-8'))
            f.write(self.footer)
            f.write("    <p>Last updated: %s</p>\n" % self.generated_date)
            f.write("   </div>\n </footer>\n</body>\n</html>")
        
    def generate_pages_workpages(self, untriaged_bugs, officially_signed_off, ready_to_develop_upstream,
                                 ready_to_develop_downstream, ready_to_land_downstream,
                                 ready_to_review, invalid_bugs, closed_reports_by_release):
        '''Generate all pages with the data'''

        self.generate_design_view(untriaged_bugs, officially_signed_off, ready_to_develop_upstream,
                                 ready_to_develop_downstream, ready_to_land_downstream,
                                 ready_to_review, invalid_bugs)
        self.generate_upstream_view(officially_signed_off, ready_to_develop_upstream,
                                    ready_to_land_downstream, ready_to_review)         
        self.generate_downstream_view(ready_to_develop_upstream, ready_to_develop_downstream,
                                      ready_to_land_downstream, ready_to_review)
        self.generate_stats(closed_reports_by_release)
       

    def generate_design_view(self, untriaged_bugs, officially_signed_off, ready_to_develop_upstream,
                             ready_to_develop_downstream, ready_to_land_downstream, ready_to_review,
                             invalid_bugs):
        '''Generate the design page'''
        
        main_content = "  <h1>Design View</h1>\n"
        comment = "Design changes that landed in Ubuntu and ready for the design team to review"
        main_content += self.generate_subsection("Design changes ready to review", comment, ready_to_review)
        comment = "Design changes are officially signed off, but that didn't get handed over upstream or downstream"
        main_content += self.generate_subsection("Design changes signed off but not handed over", comment, officially_signed_off)
        comment = "Bugs that are not triaged and have an ayatana-design task"
        main_content += self.generate_subsection("Untriaged design bugs", comment, untriaged_bugs, hidden=True)
        comment = "Design bugs that are in a inconsistent state"
        main_content += self.generate_subsection("Inconsistant design bugs", comment, invalid_bugs, hidden=True)
        main_content += self.generate_summary(
            [("Design changes ready to develop upstream", ready_to_develop_upstream),
             ("Design changes ready to develop downstream", ready_to_develop_downstream),
             ("Design changes ready to land in Ubuntu", ready_to_land_downstream)])
        self.write_page_on_disk("designer", main_content)
        
    def generate_upstream_view(self, officially_signed_off, ready_to_develop_upstream,
                               ready_to_land_downstream, ready_to_review):
        '''Generate the upstream page'''
        main_content = "  <h1>Upstream View</h1>\n"
        main_content += '''<h2>Upstream projects that can be worked on</h2>
    <div class="collapsable" id="div_upstream_work">
'''
        main_content += self.generate_subsections_by_project(ready_to_develop_upstream)
        main_content += "    </div>\n"
        # TODO: check why ready_to_review is 18 as land downstream and 6 on the other slide
        main_content += self.generate_summary(
            [("Design changes ready to review by the design team", ready_to_review),
             ("Design changes ready to land in Ubuntu", ready_to_land_downstream)])
        self.write_page_on_disk("upstream", main_content)

    def generate_downstream_view(self, ready_to_develop_upstream, ready_to_develop_downstream,
                                 ready_to_land_downstream, ready_to_review):
        '''Generate the downstream page'''
        main_content = "  <h1>Downstream View</h1>\n"
        main_content += '''<h2>Downstream projects that can be worked on</h2>
    <div class="collapsable" id="div_downstream_work">
'''
        main_content += self.generate_subsections_by_project(ready_to_develop_downstream)
        main_content += '''    </div>
    <h2>Upstream changes that are ready to land in distro</h2>
    <div class="collapsable" id="div_downstream_land">
'''        
        main_content += self.generate_subsections_by_project(ready_to_land_downstream)
        main_content += "    </div>\n"
        main_content += self.generate_summary(
            [("Design changes that are ready for upstream to work on", ready_to_develop_upstream),
             ("Design changes that landed and waiting for design review", ready_to_review)])
        self.write_page_on_disk("downstream", main_content)
       
       
    def generate_stats(self, reviewed_bugs):
        '''Generate the statistic page'''
        
        main_content = "  <h1>Statistics on design changes</h1>\n"
        main_content += "    <h2>Number of closed and reviewed design changes per release</h2>\n"
        
        # generate the graph
        data = []
        x_labels = []
        for release in sorted(reviewed_bugs):
            data.append(reviewed_bugs[release])
            x_labels.append(release)
        max_value = max(data)
        num_relevant_digits = len(str(max_value)) - 1
        max_graph_value = round(max_value, -num_relevant_digits) + pow(10, num_relevant_digits)
        i = 0
        y_labels = []
        while (i <= max_graph_value):
            y_labels.append(str(i))
            i += int(max_graph_value / 9);
        colors = [(1,0.2,0), (1,0.7,0), (1,1,0)]
        cairoplot.bar_plot (os.path.join(self.webpath, 'reviewed_design.svg'), data, 500, 300, border = 20, grid = True, rounded_corners = False, colors = colors, h_labels=x_labels, v_labels=y_labels, max_value=max_graph_value)
        main_content += '    <img src="reviewed_design.svg" alt="Number of bugs closed by release" />'
        self.write_page_on_disk("stats", main_content)
       
    def generate_subsections_by_project(self, bugs):
        '''Generate all subsections for this bugs'''
        
        content = ""
        for project in bugs:
            comment = "Design changes ready for upstream work on %s" % project
            content +=  self.generate_subsection(project, comment, bugs[project], use_h3=True)
        return content

    def generate_subsection(self, section_title, comment, bugs, hidden=False, use_h3=False):
        '''Generate a subsection tabular of bugs'''
        
        id_template = section_title.lower().replace(' ', '_')
        classname = hidden and "hiddencollapsable" or "collapsable"
        hbalise = use_h3 and "h3" or "h2"
        content = """    <%(header)s>%(section)s (%(number)s)</%(header)s>
    <p style="font-size: x-small;">%(comment)s</p>
    <div class="%(class_name)s", id="%(div_id)s">
      <table class=sortable id="%(table_id)s">
        <thead>
          <tr>
            <th>Bug</th>
            <th>Importance</th>
            <th>Assignee</th>
          </tr>
        </thead>
        <tbody>
""" % {'header': hbalise, 'section': section_title, 'number': len(bugs), 'comment': comment,
       'class_name': classname, 'div_id': "div_%s" % id_template, 'table_id': "table_%s" % id_template}
        
        # triage by importance
        sorted_bugs = {}
        for importance in importance_order:
            sorted_bugs[importance] = set()
        # we can have to formats:
        # a dict of bug_link: (bug title, importance, assignee)
        # or (bug_link, bug_title, importance, assignee) (if by project, which is the section title)
        for bug_data in bugs:
            if not isinstance(bug_data, tuple):
                bug_link = bug_data
                (bug_title, importance, assignee) = bugs[bug_link]        
            else:
                (bug_link, bug_title, importance, assignee) = bug_data
            sorted_bugs[importance].add((bug_title, bug_link, assignee))
        
        for importance in importance_order:
            for bug in sorted_bugs[importance]:
                content += """          <tr>
            <td><a href="%(link)s">%(bug_title)s</a></d>
            <td class="priority_%(importance)s">%(importance)s</td>
            <td>%(assignee)s</td>
          </tr>
""" % {'bug_title': bug[0], 'link': bug[1], 'importance': importance, 'assignee': bug[2]}

        content += "        </tbody>\n      </table>\n    </div>\n\n"
        return content
        
    def generate_summary (self, bugs_section):
        '''Generate the design summary by section'''
        
        main_content = """    <h2>Other status</h2>
    <p style="font-size: x-small;">Miscellanous other status summary. Go to the other pages for details.</p>
    <table>
      <thead>
        <tr>
          <th>Categorie of bugs</th>
          <th>Number</th>
        </tr>
      </thead>
      <tbody>
"""
    
        for bug in bugs_section:
            category = bug[0]
            number = 0
            for project in bug[1]:
                if isinstance(bug[1][project], set):
                    number += len(bug[1][project])
                else:
                    # categories are not set
                    number = len(bug[1])
                    break
            main_content += """        <tr class="status-postponed">
          <td>%s</td>
          <td>%s</td>
        </tr>
""" % (category, number)
        main_content += "    </table>\n"

        return main_content
        
