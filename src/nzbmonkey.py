#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    NZB-Monkey
"""

import argparse
import base64
import io
import json
import operator
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from enum import Enum
from glob import glob
from os.path import basename, splitext, isfile, join, expandvars
from pathlib import Path
from time import sleep, time, localtime, strftime
from unicodedata import normalize
from urllib.parse import urlparse, parse_qs, quote

from nzblnkconfig import check_missing_modules

try:
    import pyperclip
    import requests
    import urllib3
    from configobj import ConfigObj, SimpleVal
    from validate import Validator
    from colorama import Fore, init, Style

    init()
except ImportError:
    check_missing_modules()
    sleep(10)
    sys.exit(1)

from nzblnkconfig import config_file, config_nzbmonkey
from version import __version__
from nzbmonkeyspec import getSpec

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WAITING_TIME_LONG = 5
WAITING_TIME_SHORT = 1
REQUESTS_TIMEOUT = 20
SAVE_STDOUT = sys.stdout
SAVE_STDERR = sys.stderr


class ExeTypes(Enum):
    EXECUTE = 'EXECUTE',
    NZBGET = 'NZBGET',
    SABNZBD = 'SABNZBD',
    SYNOLOGYDLS = 'SYNOLOGYDLS'


class Col:
    OK = Fore.GREEN + Style.BRIGHT
    WARN = Fore.YELLOW + Style.BRIGHT
    FAIL = Fore.RED + Style.BRIGHT
    OFF = Fore.RESET + Style.RESET_ALL


# region NZB-Verifier


class NZBSegment(object):
    def __init__(self, bytes_, number, message_id=None):
        """NZB Segment

        :param int bytes_: Size in bytes
        :param int number: Segment number
        :param str message_id: MessageID
        """
        self.bytes_ = int(bytes_)
        self.number = int(number)

        if message_id:
            self.message_id = message_id

    def set_message_id(self, message_id):
        self.message_id = message_id


class NZBFile(object):
    def __init__(self, poster, date, subject, groups=None, segments=None, debug=False):
        """NZB File

        :param str poster: Poster name
        :param str date: Unix date
        :param str subject: Header/ Subject
        :param list groups: List with groups
        :param list segments: List with segments
        :param boolean debug: Enable verbose output
        """
        self.poster = poster
        self.date = date
        self.subject = subject
        self.groups = groups or list()
        self.segments = segments or list()
        self.debug = debug
        self.segments_total = 0
        self.expected_segments = -1
        self.missing_segments = None

        self.regexes = {'segments_jbin': re.compile(r'.+?\.(\d{1,5})-(\d{1,5})@'),
                        'files_jbin': re.compile(r'.+?_(\d{1,5})o(\d{1,5})@'),
                        'segments_powerpost': re.compile(r'part(\d{1,4})of(\d{1,5})')}

        self.guessed_segments = False

    def add_group(self, group):
        """Append Group to group list"""
        self.groups.append(group)

    def add_segment(self, segment):
        """Append segment to segment list"""
        self.segments.append(segment)

    def get_segment_count(self):
        """Return segment count"""
        self.segments_total = len(self.segments)
        return self.segments_total

    def get_expected_segments(self):
        """"Return expected segments"""

        if self.expected_segments > -1:
            return self.expected_segments
        else:
            return None

    def get_missing_segments(self):
        """Calculate missing segments and return the value"""
        # If expected value is available calculate missing segments

        if self.expected_segments > -1:
            self.missing_segments = self.expected_segments - self.segments_total

        return self.missing_segments

    def guess_expected_segments(self):
        """Guess the expected segments from the number attribute

        <segment bytes="391347" number="1">sdfgsdfhbtzutenur_2o88@videoot.local</segment>
        ...
        <segment bytes="247767" number="55">sdfgsdfhbtzutenur_2o88@videoot.local</segment>
        The highest number for this file is 55. So we guess we should have 55 Segments.
        """
        max_number = 0

        for segment in self.segments:
            if int(segment.number) > max_number:
                max_number = int(segment.number)

        self.expected_segments = max_number
        self.guessed_segments = True

    def determine_expected_segments_message_id(self, skip_segment_debug):
        """Determine expected segments from message id

        :param bool skip_segment_debug: Skip debug output for segment check - NZBKing removes Segment part from Header

        If Upload was done by JBinDown or PowerPost it is possible to get the expected
        segments from MessageID
        """

        try:
            counter = re.search(self.regexes['segments_jbin'], self.segments[0].message_id).groups()
        except AttributeError:
            counter = (0,)
        if counter and len(counter) == 2:
            self.expected_segments = int(counter[1])

            if self.debug and not skip_segment_debug:
                print('      Got expected segments from jBinDown MessageID.')

            return
        try:
            counter = re.search(self.regexes['segments_powerpost'], self.segments[0].message_id).groups()
        except AttributeError:
            counter = (0,)
        if counter and len(counter) == 2:
            if self.debug and not skip_segment_debug:
                print('     Got expected segments from PowerPost MessageID.')

            self.expected_segments = int(counter[1])
            return
        if self.debug and not skip_segment_debug:
            print('       Can\'t get expected segments from MessageID.')
            print('       Try to get them from number attribute.')

        self.guess_expected_segments()

    def determine_expected_files_message_id(self):
        """Determine expected files from message id

        If Upload was done by JBinUp, it is possible to get the expected
        files from MessageID
        """

        try:
            counter = re.search(self.regexes['files_jbin'], self.segments[0].message_id).groups()
        except AttributeError:
            counter = (0,)
        if counter and len(counter) == 2:
            return int(counter[1])

        return -1


class NZBParser(object):
    """Check NZB completion
    1. Check filecount. Used the [1/10] part in Header to get the expected filecount.
        If the uploader uses (1/10) instead of [1/10] as required in yEnc specs NZBindex is filtering this
        and a filecount check is not possible. If the Segment Check is OK and the min age is exceeded
        then the upload should be finished.
    2. Check segments. Used the (1/255) part at the header end to get the expected Segment count.

    For both checks is a limit until the nzb file is OK
    ---------
    Based on pynzb by Eric Florenzano
        Copyright (c) 2009, Eric Florenzano
        All rights reserved.
        http://github.com/ericflo/pynzb/

    """

    def __init__(self, nzb_file, max_missing_files=2, max_missing_segments_percent=2.5, waiting_time=0.5, debug=False,
                 skip_segment_debug=False):
        """Initialize NZB Parser

        :param str,byte nzb_file: nzb file
        :param int max_missing_files: How many files may be missing
        :param float max_missing_segments_percent:  How many segments (in percentage) may be missing
        :param float waiting_time: Waiting time after output
        :param bool debug: Enable verbose output
        :param bool skip_segment_debug: Skip debug output for segment check - NZBKing removes Segment part from Header

        """
        try:
            self.nzb = bytearray(nzb_file, encoding='utf-8')
        except TypeError:
            pass

        # If a NZB download failed we receive sometimes malformed NZB Files or html.
        if self.nzb.lower().find(b'does not exist') != -1 or self.nzb.lower().find(b'doctype html') != -1:
            self.nzb_malformed = True
            print(Col.WARN + '   Received no NZB from Indexer' + Col.OFF)
        else:
            self.nzb_malformed = False

        self.files = list()
        self.segments_total = 0
        self.segments_missing = 0
        self.segments_additional = 0
        self.segments_missing_percent = -1.0
        self.segments_expected_total = 0

        self.files_total = 0
        self.files_expected = -1
        self.files_with_missing_segments = 0
        self.files_with_too_many_segments = 0
        self.files_with_unknown_segments = 0
        self.files_checked = 0
        self.files_missing = -1

        self.files_min_upload_time = 0
        self.files_max_upload_time = 0
        self.files_upload_duration = 0

        self.regexes = {
            'file_count_subject_1': re.compile(r'.*?[(\[](\d{1,4})/(\d{1,4})[)\]].*?\((\d{1,4})/(\d{1,5})\)', re.I),
            'file_count_subject_2': re.compile(r'.*?[\[](\d{1,4})/(\d{1,5})[\]]', re.I),
            'segment_count_subject': re.compile(r'.*?\((\d{1,4})/(\d{1,5})\)$', re.I)}

        self.max_missing_files = int(max_missing_files)
        self.max_missing_segments_percent = float(max_missing_segments_percent)

        self.waiting_time = waiting_time

        self.debug = debug
        self.skip_segment_debug = skip_segment_debug

        self.parse()

    @staticmethod
    def get_etree_iter(xml):

        return iter(ET.iterparse(io.BytesIO(xml), events=('start', 'end')))

    def get_files_missing(self):
        """Return  missing files"""
        return self.files_missing

    def get_segments_missing_percent(self):
        """Return missing segments in percent"""
        return self.segments_missing_percent

    def get_upload_start_time(self):
        """Return upload start time in human readable values

        :return str: Timestamp as YYYY-MM-DD HH:MM:SS if time stamp is available"""

        if self.files_max_upload_time == 0:
            self.determine_time_stamps()
        if self.files_max_upload_time > 0:
            return strftime('%Y-%m-%d', localtime(float(self.files_max_upload_time)))
        else:
            return 'Not available'

    def get_upload_duration(self):
        """Return upload duration time in human readable values

        :return str: Timestamp as [DD day(s)] HH:MM:SS if time stamp is available"""
        if self.files_upload_duration == 0:
            self.determine_time_stamps()
        if self.files_upload_duration > 0:
            return sec_to_time(self.files_upload_duration)
        else:
            return 'Not available'

    def get_upload_age(self):
        """Return Upload age in  human readable values

        :return str: Upload age as [DD day(s)] HH:MM:SS if time stamp is available"""
        if self.files_max_upload_time == 0:
            self.determine_time_stamps()
        if self.files_max_upload_time > 0:
            return sec_to_time(int(time() - self.files_max_upload_time), days_only=True)
        else:
            return 'Not available'

    def parse(self):
        """Parse NZB file"""

        if self.nzb_malformed:
            return
        context = self.get_etree_iter(self.nzb)
        current_file, current_segment = None, None

        for event, elem in context:
            if event == 'start':
                # If it's an NZBFile, create an object so that we can add the
                # appropriate stuff to it.
                if elem.tag == '{http://www.newzbin.com/DTD/2003/nzb}file':
                    current_file = NZBFile(
                        poster=elem.attrib['poster'],
                        date=elem.attrib['date'],
                        subject=elem.attrib['subject'],
                        debug=self.debug)

            elif event == 'end':
                if elem.tag == '{http://www.newzbin.com/DTD/2003/nzb}file':
                    self.files.append(current_file)

                elif elem.tag == '{http://www.newzbin.com/DTD/2003/nzb}group':
                    current_file.add_group(elem.text)

                elif elem.tag == '{http://www.newzbin.com/DTD/2003/nzb}segment':
                    current_file.add_segment(
                        NZBSegment(
                            bytes_=elem.attrib['bytes'],
                            number=elem.attrib['number'],
                            message_id=elem.text
                        )
                    )
                # Clear the element, we don't need it any more.
                elem.clear()

    def determine_expected_files(self, nzbfile):
        """Determine expected files

        :param nzbfile: NZBFile Object
        # Search subject for [file counter] (segment counter) or  (file counter) (segment counter)
        # [1/5] (1/235) or (1/5) (1/235)
        """

        try:
            counter = re.search(self.regexes['file_count_subject_1'], nzbfile.subject).groups()
        except AttributeError:
            counter = (0,)
        # Regex matched

        if counter and len(counter) == 4:
            return int(counter[1])

        # Found NZBs without segment counter
        # Second regex searches only for file counter  [1/5]

        if self.debug and not self.skip_segment_debug:
            print('       No segment counter in header - search now only for [x/y]')
        try:
            counter = re.search(self.regexes['file_count_subject_2'], nzbfile.subject).groups()
        except AttributeError:
            counter = (0,)
        # Regex matched

        if counter and len(counter) == 2:
            return int(counter[1])

        # NZBIndex removes filecount from Uploads with ($1/$2) filecount subject
        # If uploaded by jBinUp, filecount is in messageID
        counter = nzbfile.determine_expected_files_message_id()

        if int(counter) > 0:
            return int(counter)
        return -1

    def determine_expected_segments(self, nzbfile):
        """Determine expected segments

        :param nzbfile: NZBFile Object
        """
        try:
            counter = re.search(self.regexes['segment_count_subject'], nzbfile.subject).groups()
        except AttributeError:
            counter = (0,)
        # Regex matched

        if counter and len(counter) == 2:
            nzbfile.expected_segments = int(counter[1])
            return
        if self.debug and not self.skip_segment_debug:
            print(
                '       No segment counter in header found. Check for jBinDown or Powerpost message id segment counter')
        nzbfile.determine_expected_segments_message_id(self.skip_segment_debug)
        return

    def determine_expected_files_and_segments(self):
        """Parse file subjects to get expected file and segment count"""
        if self.nzb_malformed:
            return
        for item in self.files:
            # File count
            filecount = self.determine_expected_files(item)

            if self.files_expected == -1 and int(filecount) > 0:
                self.files_expected = int(filecount)
            # Some uploaders add additional files after download starts
            # Use the highest file count
            elif self.files_expected < int(filecount):
                self.files_expected = int(filecount)

            # Segment count
            self.determine_expected_segments(item)

    def determine_time_stamps(self):
        """Determine lowest and highest upload timestamp from files

        self.files_max_upload_time is the oldest files
        self.files_min_upload_time is the youngest file
        """

        for item in self.files:
            timestamp = int(item.date)
            if timestamp > self.files_max_upload_time:
                self.files_max_upload_time = timestamp

            if self.files_min_upload_time > timestamp:
                self.files_min_upload_time = timestamp
            elif self.files_min_upload_time == 0:
                self.files_min_upload_time = timestamp

        if self.files_min_upload_time > 0 and self.files_max_upload_time > 0:
            self.files_upload_duration = self.files_max_upload_time - self.files_min_upload_time

    def check_completion(self):
        """Check files and segments for completion"""

        # Clear counters
        self.files_total = 0
        self.files_expected = -1
        self.files_with_missing_segments = 0
        self.files_with_too_many_segments = 0
        self.files_with_unknown_segments = 0
        self.files_checked = 0
        self.files_missing = -2

        self.segments_total = 0
        self.segments_missing = 0
        self.segments_additional = 0
        self.segments_expected_total = 0
        self.segments_missing_percent = -1.0

        if self.nzb_malformed:
            return False, 1

        print('   - Check NZB (Max. {0} missing files - Max. {1}% missing Segments)'
              .format(self.max_missing_files, self.max_missing_segments_percent))

        # Update counters
        if self.debug:
            print('     Update counter ... ')
        self.files_total = len(self.files)
        self.determine_expected_files_and_segments()
        self.determine_time_stamps()

        file_check_ok = False
        segment_check_ok = False
        segments_guessed = False

        # Check files
        print('     Check file count ... ', end='', flush=True)
        if self.files_expected > -1:
            self.files_missing = self.files_expected - self.files_total

            # There is one extra file e.g. a nzb file as file number 000 - [000/xxx] "yyy.nzb"
            if self.files_missing == -1:
                self.files_missing = 0
                self.files_expected += 1
                if self.debug:
                    print(Col.WARN + 'One extra file ' + Col.OFF, end='', flush=True)
            # To many missing files
            if not self.files_total >= self.files_expected - self.max_missing_files:
                print(Col.FAIL + 'Failed - Only {0} from {1} files'
                      .format(self.files_total, self.files_expected) + Col.OFF)
                print_and_wait(Col.FAIL + '     Skip Segment check' + Col.OFF, self.waiting_time)
                return False, 2
            # More files than expected
            elif self.files_missing < 0:
                print(Col.WARN + 'More files than expected - {0} from {1} files'
                      .format(self.files_total, self.files_expected) + Col.OFF)
            # Filecount is OK
            else:
                print(Col.OK + 'OK - {0} from {1} files'
                      .format(self.files_total, self.files_expected) + Col.OFF)
                file_check_ok = True
        else:
            self.files_missing = self.files_total
            print(Col.WARN + 'Skip - No information found' + Col.OFF)

        # Check Segments for each file
        print('     Check segments ...')
        for item_count, item in enumerate(self.files, start=1):
            segments = item.get_segment_count()
            segments_missing = item.get_missing_segments()

            if segments_missing is None:
                self.files_with_unknown_segments += 1
            elif segments_missing == 0:
                self.files_checked += 1
            elif segments_missing > 0:
                self.segments_missing += segments_missing
                self.files_with_missing_segments += 1
                self.files_checked += 1
            elif segments_missing < 0:
                self.segments_additional += -segments_missing
                self.files_with_too_many_segments += 1
                self.files_checked += 1

            if item.get_expected_segments():
                self.segments_expected_total += item.get_expected_segments()

            # Because we guessed the expected segments we depreciate the check
            if item.guessed_segments:
                segments_guessed = True
                if self.segments_missing == 0:
                    self.segments_missing = 1
                    self.segments_total += 1

            self.segments_total += segments

        # Results
        if self.files_with_unknown_segments > 0:
            print('       Files with unknown segment count: ', end='', flush=True)
            print(Col.WARN + '{0}'.format(self.files_with_unknown_segments) + Col.OFF)

        if self.files_with_missing_segments > 0:
            print('       Files with missing segments: ', end='', flush=True)
            print(Col.WARN + '{0}'.format(self.files_with_missing_segments) + Col.OFF)

        if self.files_with_too_many_segments > 0:
            print('       Files with too many segments: ', end='', flush=True)
            print(Col.WARN + '{0}'.format(self.files_with_too_many_segments) + Col.OFF)

        if self.debug:
            print('       Total Segments:       {:6d}'.format(self.segments_total))
            print('       Expected Segments:    {:6d}'.format(self.segments_expected_total))
            print('       Missing Segments:     {:6d}'.format(self.segments_missing))
            print('       Additional Segments:  {:6d}'.format(self.segments_additional))

        # Check if missing segments are in OK range
        if self.segments_missing > 0:
            missing_percent = float(self.segments_missing) / (float(self.segments_expected_total) / 100)
            self.segments_missing_percent = missing_percent
            if missing_percent > self.max_missing_segments_percent:
                print_and_wait(Col.FAIL + '       Failed - Too many missing Segments: {0} = {1:.3f}%'
                               .format(self.segments_missing, missing_percent) + Col.OFF, self.waiting_time)
                return False, 3
            else:
                print(Col.WARN + '       Warning - missing Segments: {0} = {1:.3f}%\n'
                      .format(self.segments_missing, missing_percent) + Col.OFF)
                segment_check_ok = True

        if file_check_ok and self.files_with_missing_segments == 0 and self.files_with_too_many_segments == 0 \
                and self.files_with_unknown_segments == 0 and not segments_guessed:
            self.segments_missing_percent = 0.0
            print(Col.OK + '       OK - {0} from {1} segments\n'
                  .format(self.segments_total, self.segments_expected_total) + Col.OFF)
            print('     Overall result: ', end='', flush=True)
            print_and_wait(Col.OK + 'OK - All {0} files are complete'.format(self.files_checked) + Col.OFF,
                           self.waiting_time)
            return True, 1

        print('     Overall result: ', end='', flush=True)
        # File count and Segment count are OK and no files with unknown segment count
        if file_check_ok and segment_check_ok and self.files_with_unknown_segments == 0 and not segments_guessed:
            print_and_wait(Col.OK + 'OK - File check: OK - Segment check: OK' + Col.OFF, self.waiting_time)
            return True, 2

        # File count OK. Segment check is OK, but we had to guess the expected segment count
        if file_check_ok and segment_check_ok and segments_guessed:
            print_and_wait(Col.WARN + 'Warning - ' + Col.OK + 'File check: OK - ' + Col.WARN
                           + 'Segment check is OK, but we used a unreliable source' + Col.OFF, self.waiting_time)
            return True, 3

        # No check possible for file count.
        # Segment check was done for more than 1 file with no missing segments or check was in OK range and
        # no files without segment count
        if self.files_checked > 0 and (
                        self.segments_missing == 0 or segment_check_ok) and self.files_with_unknown_segments == 0:
            print_and_wait(Col.OK + 'OK - File count is unknown - Segment check is OK' + Col.OFF, self.waiting_time)
            return True, 4

        # No check possible for file count and segment count
        # Segment check was done for more than 1 file and was in OK range
        if self.files_checked > 0 and (self.segments_missing == 0 or segment_check_ok):
            print(Col.WARN + 'Warning - File count is unknown - Segment count is unknown' + Col.OFF)
            print_and_wait(Col.WARN + '       The odds are good that the download will be successful' + Col.OFF,
                           self.waiting_time)
            return True, 5

        self.segments_missing_percent = 100.0
        print_and_wait(Col.FAIL + 'Skip - No information found' + Col.OFF, self.waiting_time)
        return False, 4


# endregion

# region NZB-Download


class NZBDownload(object):
    """Search for NZB on one and download. Return NZB content if download was successful.

    :param str search_url: Search URL
    :param str regex: Regex to find NZB download data
    :param download_url: Download URL
    :param search_header: Header to search for
    :param debug: Verbose output

    :return bool, str: Status, NZB Content
    """

    def __init__(self, search_url, regex, download_url, search_header, debug=False):
        """Initialize NZB Downloader"""
        self.search_url = search_url
        self.regex = regex
        self.download_url = download_url
        self.header = search_header
        self.debug = debug

        self.nzb_url = ''
        self.nzb = ''

    def search_nzb_url(self):
        """Search for NZB Download URL and return the URL
        :return bool, str: """
        try:
            self.header = self.header.replace('_', ' ')
            res = requests.get(self.search_url.format(quote(self.header, encoding='utf-8')),
                               timeout=REQUESTS_TIMEOUT, headers={'Cookie': 'agreed=true'}, verify=False)
        except requests.exceptions.Timeout:
            print(Col.WARN + ' Timeout' + Col.OFF, flush=True)
            return False, None
        except requests.exceptions.ConnectionError:
            print(Col.WARN + ' Connection Error' + Col.OFF, flush=True)
            return False, None

        m = re.search(self.regex, res.text)
        if m is None:
            print(Col.WARN + ' NOT FOUND' + Col.OFF, flush=True)
            return False, None

        self.nzb_url = self.download_url.format(**m.groupdict())

        return True, self.nzb_url

    def download_nzb(self):
        """Download NZB and return the NZB content

        :returns bool, str:"""
        if not self.nzb_url:
            res, _ = self.search_nzb_url()
            if not res:
                return False, None
        try:
            res = requests.get(self.nzb_url, timeout=REQUESTS_TIMEOUT, verify=False)
        except requests.exceptions.Timeout:
            print(Col.WARN + ' Timeout' + Col.OFF, flush=True)
            return False, None
        except requests.exceptions.ConnectionError:
            print(Col.WARN + ' Connection Error' + Col.OFF, flush=True)
            return False, None

        if res.status_code != 200:
            print(Col.WARN + ' NOT FOUND' + Col.OFF, flush=True)
            return False, None

        print(Col.OK + ' DONE' + Col.OFF)

        self.nzb = res.text

        return True, self.nzb


def search_nzb(header, password, search_engines, best_nzb, max_missing_files, max_missing_segments_percent,
               skip_failed=True, debug=False):
    """Search for NZB file on several search engines and returns a NZB if successful

    :param str header: Header to search for
    :param str password: NZB password
    :param dict search_engines: List with search engines and their priority
    :param bool best_nzb: Search for best incomplete NZB if no complete NZB available
    :param int max_missing_files: How many missing files until NZB  file check failed
    :param int max_missing_segments_percent: How many missing segments (in percent) until NZB segment check failed
    :param bool skip_failed: Skip download for failed NZB files
    :param bool debug: Enable verbose output
    :returns int, str, str: Return code, NZB content, search engine name. Return code 0 is OK, return code > 0 is NOK
    """
    print(' - Searching NZB{}'.format(' - Search for best NZB enabled' if best_nzb else ''))

    search_defs = {
        'binsearch':
            {
                'name': 'BinSearch',
                'searchUrl': 'https://binsearch.info/?q={0}&max=100&adv_age=1100&server=',
                'regex': r'name="(?P<id>\d{9,})"',
                'downloadUrl': 'http://www.binsearch.info/?action=nzb&{id}=1',
                'skip_segment_debug': False
            },
        'binsearch_alternative':
            {
                'name': 'BinSearch - Alternative Server',
                'searchUrl': 'https://binsearch.info/?q={0}&max=100&adv_age=1100&server=2',
                'regex': r'name="(?P<id>\d{9,})"',
                'downloadUrl': 'http://www.binsearch.info/?action=nzb&{id}=1&server=2',
                'skip_segment_debug': False
            },
        'nzbking':
            {
                'name': 'NZBKing',
                'searchUrl': 'http://www.nzbking.com/search/?q={0}',
                'regex': r'href="/details:(?P<id>.*?)\/"',
                'downloadUrl': 'http://www.nzbking.com/nzb:{id}',
                'skip_segment_debug': True
            },
        'nzbindex':
            {
                'name': 'NZBIndex',
                'searchUrl': 'http://nzbindex.com/search/?q={0}&sort=agedesc&hidespam=1',
                'regex': r'label for="box(?P<id>\d{8,})".*?class="highlight"',
                'downloadUrl': 'http://nzbindex.com/download/{id}/',
                'skip_segment_debug': False
            },
        'newzleech':
            {
                'name': 'Newzleech',
                'searchUrl': 'https://www.newzleech.com/?m=search&q={0}',
                'regex': r'class="subject"><a\s+(?:class="incomplete"\s+)?href="\?p=(?P<id>\d+)',
                'downloadUrl': 'https://www.newzleech.com/?m=gen&dl=1&post={id}',
                'skip_segment_debug': False
            }
    }

    downloaded_nzbs = list()
    active_search_engines = dict()

    for engine in search_engines:
        if engine not in search_defs:
            print('   with {}{} is no valid value for search engines{}'.format(engine, Col.FAIL, Col.OFF))
            continue
        priority = int(search_engines[engine])
        if priority == 0:
            print('   with {} ... {}Disabled{}'.format(search_defs[engine]['name'], Col.OK, Col.OFF))
            continue
        if priority < 0 or priority > 9:
            print('   with {} ... {}Only values between 0-9 allowed!{}'.format(search_defs[engine]['name'], Col.FAIL,
                                                                               Col.OFF))
            continue
        if priority not in active_search_engines:
            active_search_engines[priority] = list()
        active_search_engines[priority].append(engine)

    found_complete_nzb = False

    for prio in sorted(active_search_engines):
        for engine in active_search_engines[prio]:
            if found_complete_nzb:
                continue
            print('   with {} ...'.format(search_defs[engine]['name']), end='', flush=True)

            result, nzb = NZBDownload(search_defs[engine]['searchUrl'],
                                      search_defs[engine]['regex'],
                                      search_defs[engine]['downloadUrl'],
                                      header).download_nzb()
            if not result:
                continue

            nzb_check = NZBParser(nzb,
                                  max_missing_files,
                                  max_missing_segments_percent,
                                  WAITING_TIME_SHORT if best_nzb else WAITING_TIME_LONG,
                                  debug,
                                  search_defs[engine]['skip_segment_debug'])
            nzb_complete, _ = nzb_check.check_completion()

            tmp_nzb = [search_defs[engine]['name'],
                       nzb,
                       nzb_check.get_files_missing(),
                       nzb_check.get_segments_missing_percent(),
                       nzb_complete,
                       nzb_check.get_upload_start_time(),
                       nzb_check.get_upload_duration(),
                       nzb_check.get_upload_age()]
            # NZB is complete
            if nzb_complete:
                tmp_nzb.append(True)
                downloaded_nzbs.append(tmp_nzb)
                # Stop downloading more NZB files
                if not best_nzb or (tmp_nzb[2] == 0 and tmp_nzb[3] == 0.0):
                    found_complete_nzb = True

            # NZB not complete. Add NZB if no complete NZB until now and we allow incomplete NZBs
            elif not downloaded_nzbs and not skip_failed:
                tmp_nzb.append(False)
                downloaded_nzbs.append(tmp_nzb)

    # No NZB download
    if not downloaded_nzbs:
        print(Col.FAIL + '\nNo NZB downloaded!\n' + Col.OFF, flush=True)
        return 2, '', ''

    res_best_nzb = get_best_nzb(downloaded_nzbs)
    nzb = res_best_nzb[1]
    if res_best_nzb:
        print('\n   use NZB from {}'.format(res_best_nzb[0]), flush=True)
        print('     Upload age:      {}'.format(res_best_nzb[7]))
        if debug:
            print('     Upload started:  {}'.format(res_best_nzb[5]))
            print('     Upload duration: {}'.format(res_best_nzb[6]))
        # Output warning if we push a failed NZB
        if not res_best_nzb[4]:
            print(Col.FAIL + '\n     You use a NZB with a failed completion test!\n' + Col.OFF, flush=True)
            sleep(WAITING_TIME_LONG)

    # inject password into nzb file, see: http://wiki.sabnzbd.org/nzb-specs
    if password is not None and nzb.find('<head>') < 0:
        # Check for illegal characters in xml &, <, >, " and '
        if re.search('[&"\'<>]', password) is not None:
            print(Col.WARN + ' - Can\'t inject password in NZB file, forbidden characters included.' + Col.OFF)
        else:
            nzb = nzb.replace('</nzb>', '<head><meta type="password">%s</meta></head></nzb>' % password)
    return 0, nzb, res_best_nzb[0]


def get_best_nzb(nzb_downloads):
    """Sort the NZB to return the first complete or best incomplete NZB

    :param nzb_downloads: NZB downloads
    :returns: list with values from best NZB
    """
    # Only one NZB file
    if len(nzb_downloads) == 1:
        return nzb_downloads[0]

    sorted_nzb = sorted(nzb_downloads, key=operator.itemgetter(2, 3))
    return sorted_nzb[0]


# endregion

# region  Misc Tools


def clean_nzb_folder(source_path, max_age=2):
    """Delete NZB files older than max_days and returns nu,ber of deleted files

     :param source_path: Folder to search for NZB files
     :param max_age: Max NZB file age
     :returns: number of deleted files
     """
    if not os.path.exists(source_path):
        return -1
    current_time = time()
    try:
        files = list()
        file_list = glob(os.path.join(source_path, '*.nzb'))
        for f in file_list:
            if not os.path.isfile(f):
                continue
            modification_time = os.path.getmtime(f)
            if (current_time - modification_time) // (24 * 3600) >= int(max_age):
                files.append(f)
        for f in files:
            os.remove(f)
        return len(files)

    except OSError as e:
        print(Col.FAIL + '  OSError: {}'.format(e) + Col.OFF)

    return -1


def check_folder(path):
    """ Check if path exists. If not create it. Returns a boolean status

    :param str path: Folder path to check
    :returns bool: Returns True if folder exists or successful created otherwise False
    """

    result = False
    if Path(path).exists():
        return True
    try:
        Path(path).mkdir(parents=True)
        result = True
    except OSError:
        return result
    return result


def print_and_wait(text, wait_time):
    """Print String and wait

    :param str text: string to print
    :param  wait_time: Waiting time after print
    :type text: str
    :type wait_time: float, int
    """
    print(text)
    sleep(float(wait_time))


class Writers(object):
    """Writer class for redirecting output for stderr and stdout

    :Example:
        logfile = open('logfile.log', 'a')
        sys.stdout = Writers(sys.stdout, logfile)
        sys.stderr = Writers(sys.stderr, logfile)"""

    def __init__(self, *writers):
        self.writers = writers
        self.ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')

    def write(self, string):
        for w in self.writers:
            w.write(self.escape_ansi(string))

    def flush(self):
        for w in self.writers:
            w.flush()

    def escape_ansi(self, string):
        return self.ansi_escape.sub('', string[:])


def debug_output_open(file_name, debug, message=''):
    """Enable Debug output

    :param str file_name: Path for a logfile
    :param bool debug:  Enable debug output if True
    :param str message: A message to inform user that debug output is enabled

    :return file: return a file handler
    """
    if debug:
        logfile = open(file_name, 'a')
        sys.stdout = Writers(sys.stdout, logfile)
        sys.stderr = Writers(sys.stderr, logfile)
        sys.stderr.write(message)
        return logfile
    return None


def debug_output_close(file_handler, debug):
    """Disable debug output and set back stdout and stderr

    :param file file_handler: file handler to close
    :param debug: Close only if debug is enabled
    """
    if debug:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = SAVE_STDOUT
        sys.stderr = SAVE_STDERR
        file_handler.close()


def sec_to_time(seconds, days_only=False, ):
    """Convert seconds in human readable values

    :param int seconds: Time in seconds
    :param bool days_only: Output only in days
    :return str: Human readable string """
    seconds = int(seconds)
    if seconds == 0:
        seconds = 1
    if seconds < 0:
        seconds *= (-1)

    days = seconds // 86400
    seconds -= days * 86400

    if not days_only:
        hours = seconds // 3600
        seconds -= hours * 3600
    else:
        hours = -1

    if not days_only:
        minutes = seconds // 60
        seconds -= minutes * 60
    else:
        minutes = -1

    return '{}{}{}{}'.format(
        '{} day{} '.format(days, 's' if days > 1 else '') if days > 0 else '< 1 day' if days_only else '',
        '{:02d}:'.format(hours) if hours > -1 else '',
        '{:02d}:'.format(minutes) if minutes > -1 else '',
        '{:02d}'.format(seconds) if minutes > -1 else '').strip()


# endregion

# region NZB Targets


def push_nzb_sabnzbd(host, port, ssl, api_key, basepath, basicauth_username, basicauth_password, category, paused,
                     sabnzbd_name, nzb_content, start_message='Pushing to SABNZBD', debug=False):
    """Push a NZB to SABnzbd

    :param str host: SABnzbd Hostname or IP
    :param str port: SABnzbd Port
    :param bool ssl: Use https
    :param str api_key: NZB Api Key
    :param str basepath: Basepath where SABnzbd lives
    :param str basicauth_username: Username for Basic Auth
    :param str basicauth_password: Password for Basic Auth
    :param str category: SABnzbd Category
    :param str paused: Add the nzb paused
    :param str sabnzbd_name: Name of the SABnzbd job. To send also the RAR password add {{password}} to the job name
    :param str nzb_content: Content for the NZB File upload
    :param str start_message: Customized start message
    :param bool debug: Verbose output

    :returns int: Return code 0 is OK, return code > 0 is NOK
    """

    print(start_message, end='', flush=True)

    scheme = 'https' if ssl else 'http'
    req_url = '{0}://{1}:{2}/{3}/api'.format(scheme, host, port, basepath)

    post_data = {
        'output': 'xml',
        'mode': 'addfile',
        'nzbname': sabnzbd_name,
        'apikey': api_key,
        'cat': category,
        'priority': -2 if paused else -100
    }

    nzbname = '{}.nzb'.format(normalize('NFKD', sabnzbd_name).encode('ascii', 'ignore').decode("utf-8", "ignore"))
    nzb_data = {'nzbfile': (nzbname, io.BytesIO(nzb_content.encode('utf8')))}

    try:
        auth = None
        if basicauth_username and basicauth_password:
            auth = (basicauth_username, basicauth_password)

        res = requests.post(req_url, data=post_data, files=nzb_data, verify=False, timeout=REQUESTS_TIMEOUT * 2,
                            auth=auth)
    except requests.exceptions.RequestException as e:
        print(Col.FAIL + 'FAILED: {}'.format(e) + Col.OFF)
        return 1

    if res.status_code == 200 and res.text.lower().find('<status>true') > 0:
        print(Col.OK + 'OK' + Col.OFF)
        return 0
    else:
        print(Col.FAIL + 'FAILED' + Col.OFF)

        if debug:
            print('   Response-Text: "{}"'.format(res.text))

        return 1


def push_nzb_nzbget(host, port, ssl, user, password, basepath, category, paused, nzb_filename, nzb_content,
                    start_message='Pushing to NZBGet', debug=False):
    """Push a NZB to NZBGet

    :param str host: NZBGet Hostname or IP
    :param str port: NZBGet Port
    :param bool ssl: Use https
    :param str user: NZBGet User
    :param str password: NZBGet password
    :param str basepath: NZBGet basepath
    :param str category: NZBGet category
    :param str paused: Add the nzb paused
    :param str nzb_filename: NZB filename for NZBGet
    :param str nzb_content: Content for the NZB File upload
    :param str start_message: Customized start message
    :param bool debug: Verbose output

    :returns int: Return code 0 is OK, return code > 0 is NOK
    """

    print(start_message, end='', flush=True)

    scheme = 'https' if ssl else 'http'

    req_url = '{0}://{1}:{2}/{3}'.format(scheme, host, port, basepath)

    # XMLRPC-request, see https://github.com/nzbget/nzbget/wiki/API-Method-%22append%22

    data = ('<?xml version="1.0"?><methodCall><methodName>append</methodName><params>' +
            '<param><value><string>{0}.nzb</string></value></param>' +  # Filename
            '<param><value><string>{1}</string></value></param>' +  # Content (NZB File)
            '<param><value><string>{2}</string></value></param>' +  # Category
            '<param><value><i4>0</i4></value></param>' +  # Priority
            '<param><value><boolean>0</boolean></value></param>' +  # AddToTop
            '<param><value><boolean>{3}</boolean></value></param>' +  # AddPaused
            '<param><value><string></string></value></param>' +  # DupeKey
            '<param><value><i4>0</i4></value></param>' +  # DupeScore
            '<param><value><string>ALL</string></value></param>' +  # DupeMode
            '</params></methodCall>').format(
        nzb_filename,
        base64.b64encode(nzb_content.encode('utf8')).decode('ascii'),
        category,
        1 if paused else 0
    )

    auth = None
    if password is not None:
        auth = (user, password)
    try:
        res = requests.post(req_url, data=data, auth=auth, verify=False, timeout=REQUESTS_TIMEOUT)

        if res.status_code == 200 and res.text.find('<fault>') < 0:
            print(Col.OK + 'OK' + Col.OFF)
        else:
            print(Col.FAIL + 'FAILED' + Col.OFF)
            if debug:
                print('   Response-Text: "{}"'.format(res.text))
            return 1

    except requests.exceptions.RequestException as e:
        print(Col.FAIL + 'FAILED' + Col.OFF)
        if debug:
            print('   Requests-Exception: {}'.format(e))
        return 1

    return 0


def write_nzb_file(nzb_folder, tag, password, nzb_content, debug=False):
    """Write NZB file

    :param str nzb_folder: Destination folder for the NZB file
    :param str tag: NZB Filename without .nzb
    :param str password: Password - append to filename
    :param str nzb_content: Content for the NZB File
    :param bool debug: Verbose output and append unix time to nzb file

    :returns int, str: status and nzb filename
    """
    # Append timestamp to file
    if debug:
        tag += '.{}'.format(int(time()))

    # append password to filename
    if password:
        if re.search('[*?:/"<>|]', password) is not None:
            print(' - Can not add password to filename, forbidden characters included - sorry.')
        else:
            tag += '{{%s}}' % password

    nzb_file = join(nzb_folder, tag + '.nzb')

    try:
        print(' - Saving NZB-file ... ', end='', flush=True)
        with open(nzb_file, 'w', encoding='utf8') as f:
            f.write(nzb_content)
            print(Col.OK + 'OK' + Col.OFF)

    except IOError as e:
        print(Col.FAIL + 'Failed: {}'.format(e) + Col.OFF)
        return 1, None
    return 0, nzb_file


def nzb_execute(nzb_folder, nzb_content, tag, nzb_password, passtofile, passtoclipboard, dontexecute, debug=False):
    """Handle NZB execution Task

    1. Copy password to clipboard
    2. append password to NZB filename {{password}}
    3. Write NZB to file

    :param str nzb_folder: Path to save NZB file
    :param str nzb_content: NZB content to save
    :param str tag: First part from file name
    :param str nzb_password: Password to append to filename
    :param bool passtofile: If enabled append password to file
    :param bool passtoclipboard: If enabled copy password to clipboard
    :param bool dontexecute: If enabled don't Execute default programm for .nzb extension
    :param bool debug: Enable verbose output

    :returns int: Return code 0 is OK, return code > 0 is NOK
    """

    # copy password to clipboard
    if nzb_password and passtoclipboard:
        pyperclip.copy(nzb_password)
        print(' - Password copied to clipboard!')

    # prepare password for nzb file
    if nzb_password and passtofile:
        password = nzb_password
    else:
        password = None

    res, nzb_file = write_nzb_file(nzb_folder, tag, password, nzb_content, debug)

    if res:
        print_and_wait('Close window in {} second(s)'.format(2 * WAITING_TIME_LONG), 2 * WAITING_TIME_LONG)
        return res

    if not dontexecute:
        print(' - Executing NZB-file ... ', end='', flush=True)

        # Let the system decide how to open a .NZB-file
        webbrowser.open(nzb_file)

        print(Col.OK + 'OK' + Col.OFF)

    return 0


def push_nzb_synologydls(host, port, ssl, username, password, basepath, tag, nzb_content, nzb_pass,
                         start_message=' - Pushing to SYNOLOGYDLS', debug=False):
    """Push a NZB to Synology DLS

    :param str host: Diskstation hostname or IP
    :param str port: Diskstation Port
    :param bool ssl: Use https
    :param str username: admin username
    :param str password: admin password
    :param str basepath: Basepath where Diskstation API lives
    :param str tag: Filename without extension .nzb
    :param str nzb_content: Content for the NZB File upload
    :param str nzb_pass: Unpack password
    :param str start_message: Customized start message
    :param bool debug: Verbose output

    :returns int: Return code 0 is OK, return code > 0 is NOK
    """

    print(start_message, end='', flush=True)

    scheme = 'https' if ssl else 'http'

    req_url = '{0}://{1}:{2}/{3}/auth.cgi?api=SYNO.API.Auth&version=2&method=login&account={4}&passwd={5}' \
              '&session=DownloadStation&format=cookie'.format(scheme, host, port, basepath, username, password)

    try:
        sid = json.loads(requests.get(req_url, verify=False, timeout=REQUESTS_TIMEOUT).text)['data']['sid']
    except requests.exceptions.RequestException as e:
        print(Col.FAIL + 'FAILED' + Col.OFF)
        if debug:
            print('   Requests-Exception: {}'.format(e))
        return 1

    req_url = '{0}://{1}:{2}/{3}/entry.cgi'.format(scheme, host, port, basepath)

    nzbname = '{}.nzb'.format(normalize('NFKD', tag).encode('ascii', 'ignore').decode("utf-8", "ignore"))

    # API reverse engineered, for some stupid reason the order of parameters matters - thx Synology!
    file_data = [
        ('api', (None, 'SYNO.DownloadStation2.Task', None)),
        ('method', (None, 'create', None)),
        ('version', (None, '2', None)),
        ('extract_password', (None, '"' + nzb_pass + '"', None)),
        ('destination', (None, '""', None)),
        ('create_list', (None, 'false', None)),
        ('type', (None, '"file"', None)),
        ('file', (None, '["torrent"]', None)),
        ('torrent', (nzbname, io.BytesIO(nzb_content.encode('utf8')), 'application/x-nzb; charset="UTF-8"'))
    ]

    try:
        res = requests.post(req_url, files=file_data, verify=False, timeout=REQUESTS_TIMEOUT, cookies={'id': sid})
        if res.status_code == 200 and res.text.find('success":true') > 0:
            print(Col.OK + 'OK' + Col.OFF)
        else:
            print(Col.FAIL + 'FAILED' + Col.OFF)
            if debug:
                print('   Response-Text: "{}"'.format(res.text))
            return 1

    except requests.exceptions.RequestException as e:
        print(Col.FAIL + 'FAILED' + Col.OFF)
        if debug:
            print('   Requests-Exception: {}'.format(e))
        return 1

    return 0


# endregion


def main():
    """NZB-Monkey - The easy way to download NZB files"""

    name = 'NZB-Monkey v{}'.format(__version__)
    print('\n %s\n %s' % (name, '=' * len(name)))

    script_path = sys.argv[0] if not hasattr(sys, 'frozen') else os.path.normpath(os.path.abspath(sys.executable))
    cfg_filename = splitext(script_path)[0] + '.cfg'
    log_filename = splitext(script_path)[0] + '.log'

    cfg = ConfigObj(cfg_filename, configspec=getSpec(), encoding='UTF-8', default_encoding='UTF-8',
                    write_empty_values=True)

    if isfile(cfg_filename):
        val = SimpleVal()
        test = cfg.validate(val)
        # We have to check explicit for not test == True
        # If everything is OK validate returns True
        # If a keyword or section is missing validate returns a dictionary
        if not test == True:
            val = Validator()
            cfg.validate(val, copy=True)
            cfg.write()

    else:
        val = Validator()
        cfg.validate(val, copy=True)
        config_file(cfg)
        config_nzbmonkey()
        sleep(WAITING_TIME_LONG)
        return 0

    exe_target = cfg['GENERAL'].get('target', 'EXECUTE').upper()
    exe_target_cfg = {} if exe_target not in cfg.keys() else cfg[exe_target]

    debug = cfg['GENERAL'].as_bool('debug')
    if debug:
        debug_message = 'Debug output enabled for {}'.format(name)
        debug_logfile = debug_output_open(log_filename, debug, '\n {}\n {}\n {}\n\n'.format(
            '=' * len(debug_message), debug_message, '=' * len(debug_message)))
        print(' Started: {} ({})'.format(strftime('%Y-%m-%d %H:%M:%S'), int(time())))
        text = 'Command line arguments passed to NZB-Monkey'
        print(' {}\n {}'.format(text, '-' * len(text)))
        for count, arg in enumerate(sys.argv):
            print(' Arg[{}]: {}'.format(count, arg))
        print(' {}\n'.format('-' * len(text)))
    else:
        debug_logfile = None

    # region Processing Input
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tag', action='store', help='Tag for Releasename')
    parser.add_argument('-s', '--subject', action='store', help='Subject (Header) for NZB Search')
    parser.add_argument('-p', '--password', action='store', help='Password to extract files')
    parser.add_argument('-c', '--category', action='store', help='Category for SABnzbd or NZBGet')
    parser.add_argument('nzblnk', nargs=argparse.REMAINDER, help='NZBLNK URI')
    args = parser.parse_args()

    if args.category:
        category_args = args.category
    else:
        category_args = None

    if len(args.nzblnk) > 0:
        called_by = 'by NZBLNK scheme'

        lnk = urlparse(args.nzblnk[0])
        if lnk.scheme.lower() != 'nzblnk':
            print_and_wait(Col.FAIL + ' ERROR: ' + Col.OFF + 'Please provide a NZBLNK.', WAITING_TIME_LONG)
            debug_output_close(debug_logfile, debug)
            return 1

        # parse query-part

        lnk = parse_qs(lnk.query)
        nzbsrc = {
            'tag': lnk.get('t', [None])[0],
            'header': lnk.get('h', [None])[0],
            'pass': lnk.get('p', [None])[0]
        }

    elif args.subject and args.tag:
        called_by = 'by Arguments'

        tag = args.tag
        header = args.subject
        if args.password:
            password = args.password
        else:
            password = ''

        nzbsrc = {
            'tag': tag,
            'header': header,
            'pass': password
        }

    else:
        called_by = 'with clipboard'
        tag = 'NZB Monkey'

        clip = pyperclip.paste()

        if clip is None or clip is '':
            print_and_wait(' Clipboard is empty. So please call {} <nzblnk> or with text in clipboard.'.format(
                basename(sys.argv[0])),
                WAITING_TIME_LONG)
            return 1

        found = re.search(r'(?mi)(^.*?S\d+E\d+.*$)', clip)
        if found is not None:
            tag = found.group(1)
        else:
            found = re.search(r'(?mi)(^.*?(?:720p|1080p|x264|x265|XviD|BluRay).*$)', clip)
            if found is not None:
                tag = found.group(1)
            else:
                found = re.search(r'(?m)(^(.*)$)', clip.strip())
                if found is not None:
                    tag = found.group(1)

        tag = re.sub('([^{]*).*', '\\1', tag.strip().replace(' ', '.'))

        header = None
        found = re.search(r'(?mi)(?:subject:|header:)\s+?(?:header:\s+)?(\S+)', clip.strip())
        if found is not None:
            header = found.group(1)

        password = ''
        found = re.search(r'(?mi)(?:passwor[dt]|pw|pwd):\s*?(\S+)', clip.strip())
        if found is not None:
            password = found.group(1)

        nzbsrc = {
            'tag': tag,
            'header': header,
            'pass': password
        }

    if nzbsrc['tag'] is None or nzbsrc['header'] is None:
        print_and_wait(Col.FAIL + ' ERROR: Please provide a tag and header info.' + Col.OFF, WAITING_TIME_LONG)
        debug_output_close(debug_logfile, debug)
        return 1

    print(""" Called {3}:\n
     - Tag     : {0}
     - Header  : {1}
     - Password: {2}
    """.format(nzbsrc['tag'],
               nzbsrc['header'],
               nzbsrc['pass'] or Col.WARN + 'EMPTY' + Col.OFF,
               called_by))
    # endregion

    # region Seach NZB

    res, nzb, used_search_engine, = search_nzb(nzbsrc['header'],
                                               nzbsrc['pass'],
                                               {'binsearch': cfg['Searchengines'].as_int('binsearch'),
                                                'binsearch_alternative':
                                                    cfg['Searchengines'].as_int('binsearch_alternative'),
                                                'nzbking': cfg['Searchengines'].as_int('nzbking'),
                                                'nzbindex': cfg['Searchengines'].as_int('nzbindex'),
                                                'newzleech': cfg['Searchengines'].as_int('newzleech')},
                                               cfg['NZBCheck'].as_bool('best_nzb'),
                                               cfg['NZBCheck'].get('max_missing_files', 2),
                                               cfg['NZBCheck'].get('max_missing_segments_percent', 2.5),
                                               cfg['NZBCheck'].as_bool('skip_failed'),
                                               debug)
    if res:
        print_and_wait('Close window in {} second(s)'.format(2 * WAITING_TIME_LONG), 2 * WAITING_TIME_LONG)
        debug_output_close(debug_logfile, debug)
        return res
    # endregion

    # region Categorizer

    category = category_args if category_args else exe_target_cfg.get('category', '')

    SEC_CATEGORIZER = 'CATEGORIZER'

    categorize_mode = cfg['GENERAL'].get('categorize', 'off').lower()
    categorize_mode = categorize_mode if categorize_mode in ['off', 'auto', 'manual'] else 'off'

    # Auto categorizer

    if categorize_mode == 'auto' and SEC_CATEGORIZER in cfg.keys():
        for cat in cfg[SEC_CATEGORIZER].keys():
            try:
                if re.compile(cfg[SEC_CATEGORIZER].get(cat), re.IGNORECASE).search(nzbsrc['tag']):
                    category = cat
                    print("\n - Categorizer set category to: {}{}{}".format(Col.OK, cat, Col.OFF))
                    break
            except:
                print_and_wait(Col.WARN + " > ERROR: Your category \"{}\" is a invalid regex!".format(cat) + Col.OFF,
                               WAITING_TIME_LONG)

    elif categorize_mode == 'manual':
        cat_choice = []

        # Ask SabNZBs for categories

        if ExeTypes.SABNZBD.name == exe_target:
            scheme = 'https' if exe_target_cfg.as_bool('ssl') else 'http'
            req_url = '{0}://{1}:{2}/{3}/api?mode=queue&output=json' \
                      '&apikey={4}'.format(scheme,
                                           exe_target_cfg.get('host', 'localhost'),
                                           exe_target_cfg.get('port', '8080'),
                                           exe_target_cfg.get('basepath', 'sabnzbd'),
                                           exe_target_cfg.get('nzbkey', ''))

            try:
                res = json.loads(requests.get(req_url, verify=False, timeout=REQUESTS_TIMEOUT * 2).text)
                if 'error' in res.keys() and res['error'].lower() == 'api key incorrect':
                    print(Col.FAIL + ' - Please use the API KEY not the NZB KEY in your config!' + Col.OFF)
                    raise EnvironmentError

                if 'queue' not in res.keys():
                    print(Col.FAIL + ' - Reading categories failed!' + Col.OFF)
                    raise EnvironmentError

                sabcats = res['queue']['categories']
                for sabcat in sabcats:
                    if sabcat != '*':
                        cat_choice.append(sabcat)

            except (EnvironmentError, ValueError):
                cat_choice = []

        # Ask NZBGet for categories

        if ExeTypes.NZBGET.name == exe_target:

            scheme = 'https' if exe_target_cfg.as_bool('ssl') else 'http'

            req_url = '{0}://{1}:{2}/{3}/config'.format(scheme,
                                                        exe_target_cfg.get('host', 'localhost'),
                                                        exe_target_cfg.get('port', '6789'),
                                                        exe_target_cfg.get('basepath', 'xmlrpc')
                                                        .replace('xmlrpc', 'jsonrpc'))
            auth = None
            if exe_target_cfg.get('pass', '') is not None:
                auth = (exe_target_cfg.get('user', ''), exe_target_cfg.get('pass', ''))

            try:
                res = json.loads(requests.get(req_url, auth=auth, verify=False, timeout=REQUESTS_TIMEOUT).text)
                if 'result' not in res.keys():
                    print(Col.FAIL + ' - Reading categories failed!' + Col.OFF)
                    raise EnvironmentError

                cfgregex = re.compile('Category\d\.Name', re.IGNORECASE)

                for cfg in res['result']:
                    if cfgregex.match(cfg['Name']):
                        cat_choice.append(cfg['Value'])

            except (ValueError, EnvironmentError):
                cat_choice = []

        if cat_choice:
            print(' - Choose from one of the categories or\n   just press enter to choose no category:\n')

            for idx, cat in enumerate(cat_choice):
                print('   [{}] {}'.format(idx + 1, cat))

            try:
                uch = int(input('\n   Your choice: ')) - 1
                if uch < 0 or uch >= len(cat_choice):
                    raise ValueError

                category = cat_choice[uch]
                print("\n - You set the category to: {}{}{}".format(Col.OK, category, Col.OFF))
            except ValueError:
                pass

    # endregion

    # region Exec NZBGET
    if ExeTypes.NZBGET.name == exe_target:
        res = push_nzb_nzbget(exe_target_cfg.get('host', 'localhost'),
                              exe_target_cfg.get('port', '6789'),
                              exe_target_cfg.as_bool('ssl'),
                              exe_target_cfg.get('user', ''),
                              exe_target_cfg.get('pass', ''),
                              exe_target_cfg.get('basepath', 'xmlrpc'),
                              category,
                              exe_target_cfg.as_bool('addpaused'),
                              nzbsrc['tag'],
                              nzb,
                              ' - Pushing to NZBGET ... ',
                              debug)
        if not debug:
            print(' - Done')
            if res:
                waiting_time = WAITING_TIME_LONG
            else:
                waiting_time = WAITING_TIME_SHORT
            print_and_wait('Close window in {} second(s)'.format(waiting_time), waiting_time)
            debug_output_close(debug_logfile, debug)
            return res
    # endregion

    # region Exec SABNZBD
    elif ExeTypes.SABNZBD.name == exe_target:

        res = push_nzb_sabnzbd(exe_target_cfg.get('host', 'localhost'),
                               exe_target_cfg.get('port', '8080'),
                               exe_target_cfg.as_bool('ssl'),
                               exe_target_cfg.get('nzbkey', ''),
                               exe_target_cfg.get('basepath', 'sabnzbd'),
                               exe_target_cfg.get('basicauth_username', ''),
                               exe_target_cfg.get('basicauth_password', ''),
                               category,
                               exe_target_cfg.as_bool('addpaused'),
                               nzbsrc['tag'] if nzbsrc['pass'] is None else '%s{{%s}}' % (
                                   nzbsrc['tag'], nzbsrc['pass']),
                               nzb,
                               ' - Pushing to SABNZBD ...',
                               debug)
        if not debug:
            print(' - Done')
            if res:
                waiting_time = WAITING_TIME_LONG
            else:
                waiting_time = WAITING_TIME_SHORT
            print_and_wait('Close window in {} second(s)'.format(waiting_time), waiting_time)
            debug_output_close(debug_logfile, debug)
            return res
    # endregion

    # region Exec SYNOLOGYDLS

    elif ExeTypes.SYNOLOGYDLS.name == exe_target:
        res = push_nzb_synologydls(exe_target_cfg.get('host', 'localhost'),
                                   exe_target_cfg.get('port', '8080'),
                                   exe_target_cfg.as_bool('ssl'),
                                   exe_target_cfg.get('user', ''),
                                   exe_target_cfg.get('pass', ''),
                                   exe_target_cfg.get('basepath', 'webapi'),
                                   nzbsrc['tag'],
                                   nzb,
                                   nzbsrc['pass'],
                                   ' - Pushing to SYNOLOGY-DLS ...',
                                   debug)
        if not debug:
            print(' - Done')
            if res:
                waiting_time = WAITING_TIME_LONG
            else:
                waiting_time = WAITING_TIME_SHORT
            print_and_wait('Close window in {} second(s)'.format(waiting_time), waiting_time)
            debug_output_close(debug_logfile, debug)
            return res

    # endregion

    # region Exec EXECUTE
    if ExeTypes.EXECUTE.name == exe_target or debug:

        if debug and exe_target != 'EXECUTE':
            # Read EXECUTE config to handle NZB saving if target is not EXECUTE
            exe_target_cfg = {} if exe_target not in cfg.keys() else cfg['EXECUTE']

        # Check NZB Folder
        nzb_folder = expandvars(exe_target_cfg.get('nzbsavepath', '%%TEMP%%'))
        if not check_folder(nzb_folder):
            print(Col.FAIL + " - Can't access or create NZB folder {}".format(nzb_folder)
                  + Col.OFF)
            print_and_wait('Close window in {} second(s)'.format(2 * WAITING_TIME_LONG), 2 * WAITING_TIME_LONG)
            debug_output_close(debug_logfile, debug)
            return 1

        # Nzb Save and execute
        nzb_execute(nzb_folder,
                    nzb,
                    nzbsrc['tag'] if not debug else '{}.{}'.format(nzbsrc['tag'], used_search_engine.lower()),
                    nzbsrc['pass'],
                    exe_target_cfg.as_bool('passtofile'),
                    exe_target_cfg.as_bool('passtoclipboard'),
                    exe_target_cfg.as_bool('dontexecute'),
                    debug)

        # Clean up NZB Folder
        if exe_target_cfg.as_bool('clean_up_enable') and int(time()) - exe_target_cfg.as_int(
                'clean_up_last_run') >= 24 * 3600:
            print(' - Clean up NZB folder ... ', end='', flush=True)
            counter = clean_nzb_folder(nzb_folder)
            if counter == -1:
                print(Col.FAIL + 'Cleaning failed.' + Col.OFF)
            elif counter == 0:
                print(Col.OK + 'Nothing to do.')
            elif counter > 0:
                print(Col.OK + 'Deleted {} NZB file(s)'.format(counter))
            exe_target_cfg['clean_up_last_run'] = int(time())
            cfg.write()

        print(' - Done')
        if res:
            waiting_time = WAITING_TIME_LONG
        else:
            waiting_time = WAITING_TIME_SHORT
        print_and_wait('Close window in {} second(s)'.format(waiting_time), waiting_time)
        debug_output_close(debug_logfile, debug)
        return 0
    # endregion

    else:
        print_and_wait(Col.FAIL + ' ERROR: ' + Col.OFF + ' Target "' + exe_target + '" unknown!', 2 * WAITING_TIME_LONG)
        debug_output_close(debug_logfile, debug)
        return 1


if __name__ == '__main__':
    sys.exit(main())
