# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
import json
import os

import requests
from libmozdata import bugzilla


BUGS_DB = 'data/bugs.json'

ATTACHMENT_INCLUDE_FIELDS = [
    'id', 'is_obsolete', 'flags', 'is_patch', 'creator', 'content_type',
]

COMMENT_INCLUDE_FIELDS = [
    'id', 'text', 'author', 'time',
]


def get_bug_fields():
    os.makedirs('data', exist_ok=True)

    try:
        with open('data/bug_fields.json', 'r') as f:
            return json.load(f)
    except IOError:
        pass

    r = requests.get('https://bugzilla.mozilla.org/rest/field/bug')
    return r.json()['fields']


def read_db(path):
    with open(path, 'r') as f:
        for line in f:
            yield json.loads(line)


def write_db(path, bugs):
    with open(path, 'w') as f:
        for bug in bugs:
            f.write(json.dumps(bug))
            f.write('\n')


def append_db(path, bugs):
    with open(path, 'a') as f:
        for bug in bugs:
            f.write(json.dumps(bug))
            f.write('\n')


def get_bugs():
    bugs = {}
    for bug in read_db(BUGS_DB):
        bugs[bug['id']] = bug
    return bugs


def download_bugs(bug_ids):
    old_bug_ids = set()
    for bug in read_db(BUGS_DB):
        old_bug_ids.add(bug['id'])

    bug_ids = [bug_id for bug_id in bug_ids if bug_id not in old_bug_ids]

    print('Loaded ' + str(len(old_bug_ids)) + ' bugs.')

    print('To download ' + str(len(bug_ids)) + ' bugs.')

    new_bugs = {}

    def bughandler(bug):
        bug_id = int(bug['id'])

        if bug_id not in new_bugs:
            new_bugs[bug_id] = dict()

        for k, v in bug.items():
            new_bugs[bug_id][k] = v

    def commenthandler(bug, bug_id):
        bug_id = int(bug_id)

        if bug_id not in new_bugs:
            new_bugs[bug_id] = dict()

        new_bugs[bug_id]['comments'] = bug['comments']

    def attachmenthandler(bug, bug_id):
        bug_id = int(bug_id)

        if bug_id not in new_bugs:
            new_bugs[bug_id] = dict()

        new_bugs[bug_id]['attachments'] = bug

    def historyhandler(bug):
        bug_id = int(bug['id'])

        if bug_id not in new_bugs:
            new_bugs[bug_id] = dict()

        new_bugs[bug_id]['history'] = bug['history']

    bugzilla.Bugzilla(bug_ids, bughandler=bughandler, commenthandler=commenthandler, comment_include_fields=COMMENT_INCLUDE_FIELDS, attachmenthandler=attachmenthandler, attachment_include_fields=ATTACHMENT_INCLUDE_FIELDS, historyhandler=historyhandler).get_data().wait()

    print('Total number of bugs: {}'.format(len(old_bug_ids) + len(new_bugs)))

    if len(new_bugs):
        append_db(BUGS_DB, new_bugs.values())


def get_labels(augmentation=False):
    with open('classes.csv', 'r') as f:
        classes = dict([row for row in csv.reader(f)][1:])

    with open('classes_more.csv', 'r') as f:
        classes_more = [row for row in csv.reader(f)][1:]

    for bug_id, category in classes_more:
        if category == 'nobug':
            is_bug = 'False'
        else:
            is_bug = 'True'

        classes[bug_id] = is_bug

    for bug_id, is_bug in classes.items():
        assert is_bug == 'True' or is_bug == 'False'

    # Turn bug IDs into integers and labels into booleans.
    classes = {int(bug_id): True if label == 'True' else False for bug_id, label in classes.items()}

    # Use bugs marked as 'regression' or 'feature', as they are basically labelled.
    bug_ids = set()
    for bug in read_db(BUGS_DB):
        bug_id = int(bug['id'])

        bug_ids.add(bug_id)

        if bug_id in classes:
            continue

        if any(keyword in bug['keywords'] for keyword in ['regression', 'talos-regression']) or ('cf_has_regression_range' in bug and bug['cf_has_regression_range'] == 'yes'):
            classes[bug_id] = True
        elif any(keyword in bug['keywords'] for keyword in ['feature']):
            classes[bug_id] = False

    # Remove labels which belong to bugs for which we have no data.
    classes = {bug_id: label for bug_id, label in classes.items() if bug_id in bug_ids}

    return classes


if __name__ == '__main__':
    classes = get_labels()
    download_bugs([bug_id for bug_id in classes.keys()])
