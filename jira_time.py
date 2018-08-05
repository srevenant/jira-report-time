#!/usr/bin/env python3
"""
Jira time reporter lib

License: GNU Affero
"""

import os
import sys
import re
import json
import dictlib
import sys
import openpyxl
import argparse
import traceback
import requests
#from jira.client import JIRA
#from jira.config import get_jira
from jira import JIRA
import datetime
import dateutil.parser
import json
import argparse
#from slacker import Slacker

def warn(msg):
    print("{} {}".format(datetime.datetime.now(), msg))

DEBUG = True
def debug(msg):
    if DEBUG:
        warn(msg)

################################################################################
def didLog(workid, seconds):
    # check a historical db to see if we already logged time for this
    return False

################################################################################
class UserMap(object):
    users = None
    email2user = None
    dnameMap = None
    unameMap = None
    emailMap = None
    domain = None

    def __init__(self, slacker=None, domain=None):
        # what is our email domain (don't lookup users by email username outside our domain)
        self.domain = domain

        warn("Loading user map from slack...")
        response = slacker.users.list()
        if response.body['ok'] != True:
            sys.exit("\nABORT: Cannot load users?")

        # cross map a few things
        self.users = dict()
        self.emailMap = dict()
        self.unameMap = dict()
        self.dnameMap = dict()

        # shortcut
        def setIfExists(dstmap, src, srckey, idnbr):
            if src.get(srckey):
                dstmap[src[srckey].lower()] = idnbr

        for user in response.body['members']:
            if user['deleted']:
                continue
            self.users['id'] = user
            profile = user['profile']
            setIfExists(self.emailMap, profile, 'email', user['id'])
            setIfExists(self.dnameMap, profile, 'display_name_normalized', user['id'])
            setIfExists(self.unameMap, user, 'name', user['id'])

    # try to find the user.  fun nesting using exceptions rather than conditions
    def lookup(self, user, email):
        if user[0] == '@':
            user = user[1:]
        try:
            return self.unameMap[user.lower()]
        except KeyError:
            try:
                return self.emailMap[email.lower()]
            except KeyError:
                try:
                    return self.dnameMap[user.lower()]
                except KeyError:
                    if email:
                        emailparts = email.lower().split('@')
                        if emailparts[1] == self.domain:
                            try:
                                return self.unameMap[emailparts[0]]
                            except KeyError:
                                try:
                                    return self.dnameMap[emailparts[0]]
                                except KeyError:
                                    pass
        raise KeyError('Unable to map user to slack ({}, {})'.format(user, email))

################################################################################
class JiraData(object):
    pergrp = None
    perdev = None
    dev2email = None
    issues = None
    grpfield = None
    grpproj = None
    fieldMap = None

    ############################################################################
    def __init__(self, jira, date_start, date_end, grpfield=None, grpproj=None, grpempty='ALL'):
        self.date_start = date_start
        self.date_end = date_end
        self.jira = jira
        self.pergrp = dict()
        self.dev2email = dict()
        self.issues = dict()
        self.perdev = dict()
        self.worklogs = list()
        self.fieldMap = fieldMap = dict()
        self.grpfield = grpfield
        self.grpproj = grpproj
        self.grpempty = grpempty # what label to use if group is an empty list?
        if grpfield:
            # Make a map from field name -> field id
            for field in self.jira.fields():
                if self.fieldMap.get(field['name']):
                    warn("Collision of key {}: {} and {}".format(field['name'], self.fieldMap[field['name']], field['id']))
                else:
                    self.fieldMap[field['name']] = field['id']
            if not self.fieldMap.get(grpfield):
                print("Available fields:")
                for field in self.fieldMap:
                    print("\t" + field)
                sys.exit("\nABORT: Cannot find grouping field `{}`".format(grpfield))
        elif not grpproj:
            sys.exit("ABORT: Neither --groupfield nor --groupproject specified")

    ############################################################################
    def process_issue(self, issue, num):
        if self.grpfield:
            groups = [self.grpempty or 'ALL'] # an empty group set is implied to be all
            try:
                if issue.fields:
                    groups_map = getattr(issue.fields, self.fieldMap[self.grpfield])
                    if groups_map:
                        groups = [grp.value for grp in groups_map]
            except:
                pass
        elif self.grpproj:
            groups = [issue.fields.project.key]

        # map out only what we need so we don't have export problems
        self.issues[issue.key] = dictlib.Obj(
            key=issue.key,
            fields=dictlib.Obj(summary=issue.fields.summary))

        for wl in self.jira.worklogs(issue.key):
            updated = dateutil.parser.parse(wl.started) #.date()

            #debug("{} <= {} <= {}".format(
            #    self.date_start.strftime("%Y-%m-%d %H:%M %z %Z"),
            #    updated.strftime("%Y-%m-%d %H:%M %z %Z"),
            #    self.date_end.strftime("%Y-%m-%d %H:%M %z %Z")))
            if self.date_start <= updated < self.date_end:
                debug("{} Worklog {} {} {} {}".format(num, issue.key, updated, wl.updateAuthor.name, inHours(wl.timeSpentSeconds)))
                seconds = int(wl.timeSpentSeconds)

                # did we already log this in the past?
                if didLog(wl.id, seconds):
                    continue

                comment = ''
                try:
                    comment = wl.comment
                except:
                    pass

                author_name = wl.updateAuthor.displayName
                author_user = wl.updateAuthor.key.lower()
                author_email = wl.updateAuthor.emailAddress or ''
                if author_email and not self.dev2email.get(author_user):
                    self.dev2email[author_user] = author_email

                # log entry
                log = dictlib.Obj(
                  groups=groups,
                  issue=issue.key,
                  updated=updated,
                  author=dictlib.Obj(name=author_name,user=author_user),
                  seconds=seconds,
                  id=wl.id,
                  comment=comment
                )
                self.worklogs.append(log)

                # calc things per developer
                devwork = self.perdev.get(author_user)
                if not devwork:
                    devwork = self.perdev[author_user] = dictlib.Obj(issues=dict(), sum=0)
                if not devwork.issues.get(issue.key):
                    devwork.issues[issue.key] = dictlib.Obj(sum=0, logs=list(), key=issue.key)

                # append log to issues
                devwork.issues[issue.key].logs.append(log)
                # add to dev total
                devwork.sum = self.perdev[author_user].sum + seconds

                # add to dev/issue total
                devwork.issues[issue.key].sum = devwork.issues[issue.key].sum + seconds

                for grp in groups:
                    if not self.pergrp.get(grp):
                        self.pergrp[grp] = dictlib.Obj(
                            sum=0,
                            issues=dict()
                        )
                    pc = self.pergrp[grp]

                    pc.sum = pc.sum + seconds
                    if not pc.issues.get(issue.key):
                        pc.issues[issue.key] = dictlib.Obj(sum=0, logs=list(), key=issue.key)
                    pc.issues[issue.key].logs.append(log)
                    pc.issues[issue.key].sum = pc.issues[issue.key].sum + seconds

    def gather(self):
        # I would like to use this JQL, but it requires other plugins:
        #    issueFunction in workLogged("after {} before {}")
        # so instead we do it the hard way
        # the hammer approach, gather any changed issue-- easier for more recent, harder for older reports
        jql = 'updated >= "{}"'.format(self.date_start.strftime("%Y-%m-%d %H:%M"))
        if self.grpproj:
            grpprojs = re.split(r'\s*,\s*', self.grpproj)
            jql = 'project in ("{}") AND {}'.format('","'.join(grpprojs), jql)

        warn("JQL: " + jql)

        # api pagination, pita
        maxResults = 500
        cursor = 0
        counted = 0
        while True:
            results = self.jira.search_issues(jql, maxResults=maxResults, startAt=cursor)
            debug("total={} maxResults={} startAt={}".format(results.total, results.maxResults, results.startAt))
            counted = 1
            for issue in results:
                debug("{} Issue {} {}".format(counted, issue.key, issue.fields.summary))
                self.process_issue(issue, counted)
                counted = counted + 1

            if cursor < results.total: # == maxResults:
                debug("Incrementing Cursor")
                cursor = cursor + (counted-1)
            else:
                debug("Done cursor={} total={}".format(cursor, results.total))
                break

        return self

################################################################################
def inHours(seconds):
    hours = int(seconds/3600)
    mins = int((seconds%3600)/60)

    # do another mod by 15-min interval later
    return float("{}.{}".format(hours, mins))

