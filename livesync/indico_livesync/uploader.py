# This file is part of Indico.
# Copyright (C) 2002 - 2014 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import transaction

from indico.core.db import db
from indico.util.struct.iterables import grouper

from indico_livesync import MARCXMLGenerator


class Uploader(object):
    """Handles batch data upload to a remote service."""

    #: Number of queue entries to process at a time
    BATCH_SIZE = 100
    #: Number of events to process at a time during initial export
    INITIAL_BATCH_SIZE = 100

    def __init__(self, agent):
        self.agent = agent
        self.task = agent.task
        self.logger = agent.task.logger if agent.task else agent.plugin.logger

    def run(self, records):
        """Runs the batch upload

        :param records: an iterable containing queue entries
        """
        self_name = type(self).__name__
        for i, batch in enumerate(grouper(records, self.BATCH_SIZE, skip_missing=True), 1):
            self.logger.debug('{} processing batch {}'.format(self_name, i))
            try:
                self.upload_records(batch, from_queue=True)
            except Exception:
                self.logger.exception('{} could not upload batch'.format(self_name))
                return
            self.processed_records(batch)
            if self.task:
                self.task.extend_runtime()

    def run_initial(self, events):
        """Runs the initial batch upload

        :param events: an iterable containing events
        """
        for i, batch in enumerate(grouper(events, self.INITIAL_BATCH_SIZE, skip_missing=True), 1):
            self.logger.debug('{} processing initial batch {}'.format(type(self).__name__, i))
            self.upload_records(batch, from_queue=False)

    def upload_records(self, records, from_queue):
        """Executed for a batch of up to `BATCH_SIZE` records

        :param records: records to upload (queue entries or events)
        :param from_queue: if `records` contains queue entries.
                           expect events if it is False.
        """
        raise NotImplementedError  # pragma: no cover

    def processed_records(self, records):
        """Executed after successfully uploading a batch of records from the queue.

        :param records: a list of queue entries
        """
        for record in records:
            self.logger.debug('Marking as processed: {}'.format(record))
            record.processed = True
        db.session.commit()
        transaction.abort()  # clear ZEO cache


class MARCXMLUploader(Uploader):
    def upload_records(self, records, from_queue):
        xml = MARCXMLGenerator.records_to_xml(records) if from_queue else MARCXMLGenerator.objects_to_xml(records)
        if xml is not None:
            self.upload_xml(xml)

    def upload_xml(self, xml):
        """Receives MARCXML strings to be uploaded"""
        raise NotImplementedError  # pragma: no cover