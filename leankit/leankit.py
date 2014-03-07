# Copyright 2011-2012 Canonical Ltd
# -*- coding: utf-8 -*-

from collections import namedtuple
from pprint import pprint
from textwrap import dedent
import json
import operator
import re
import requests
import time


ANNOTATION_REGEX = re.compile('^\s*{.*}\s*$', re.MULTILINE|re.DOTALL)
Auth = namedtuple('Auth', ['account', 'username', 'password'])


class Record(dict):
    """A little dict subclass that adds attribute access to values."""

    def __hash__(self):
        return hash(repr(self))

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, name, value):
        self[name] = value


class LeankitResponseCodes:
    """Enum listing all possible response codes from LeankitKanban API."""
    NoData = 100
    DataRetrievalSuccess = 200
    DataInsertSuccess = 201
    DataUpdateSuccess = 202
    DataDeleteSuccess = 203
    SystemException = 500
    MinorException = 501
    UserException = 502
    FatalException = 503
    ThrottleWaitResponse = 800
    WipOverrideCommentRequired = 900
    ResendingEmailRequired = 902
    UnauthorizedAccess = 1000

    SUCCESS_CODES = [
        DataRetrievalSuccess,
        DataInsertSuccess,
        DataUpdateSuccess,
        DataDeleteSuccess,
        ]


class LeankitConnector(object):
    def __init__(self, account, username=None, password=None, throttle=1):
        host = 'https://' + account + '.leankitkanban.com'
        self.base_api_url = host + '/Kanban/Api'
        self.http = self._configure_auth(username, password)
        self.last_request_time = time.time() - throttle
        self.throttle = throttle

    def _configure_auth(self, username=None, password=None):
        """Configure the http object to use basic auth headers."""
        http = requests.sessions.Session()
        if username is not None and password is not None:
            http.auth = (username, password)
        return http

    def post(self, url, data, handle_errors=True):
        data = json.dumps(data)
        return self._do_request("POST", url, data, handle_errors)

    def get(self, url, handle_errors=True):
        return self._do_request("GET", url, None, handle_errors)

    def _do_request(self, action, url, data=None, handle_errors=True):
        """Make an HTTP request to the given url possibly POSTing some data."""
        assert self.http is not None, "HTTP connection should not be None"
        headers = {'Content-type': 'application/json'}

        # Throttle requests to leankit to be no more than once per THROTTLE
        # seconds.
        now = time.time()
        delay = (self.last_request_time + self.throttle) - now
        if delay > 0:
            time.sleep(delay)
        self.last_request_time = time.time()
        try:
            request = self.http.request(
                method=action,
                url=self.base_api_url + url,
                data=data,
                auth=self.http.auth,
                headers=headers,
                config={},
                return_response=False)
            sent = request.send()
        except Exception as e:
            raise IOError("Unable to make HTTP request: %s" % e.message)

        resp = request.response
        if (not sent or
            resp.status_code not in LeankitResponseCodes.SUCCESS_CODES):
            print "Error from kanban"
            pprint(resp)
            raise IOError('kanban error %d' % (resp.status_code))

        response = Record(json.loads(resp.content))

        if (handle_errors and
            response.ReplyCode not in LeankitResponseCodes.SUCCESS_CODES):
            raise IOError('kanban error %d: %s' % (
                response.ReplyCode, response.ReplyText))
        return response


class Converter(object):
    """Convert JSON returned by Leankit to Python classes.

    JSON returned by Leankit is in the form of a dict with CamelCase
    named values which are converted to lowercase underscore-separated
    class attributes.

    Any required attributes are defined in attribute 'attributes',
    and optional ones in 'optional_attributes' using the originating
    key names (CamelCase).  Optional values will be set to None if
    they are not defined.

    Whenever any of required or optional attributes are modified,
    is_dirty will be set to True and dirty_attrs will contain a set
    of modified attributes.
    """
    attributes = []
    optional_attributes = []

    def direct_setattr(self, attr, value):
        super(Converter, self).__setattr__(attr, value)

    def __init__(self, raw_data):
        self.direct_setattr('is_dirty', False)
        self.direct_setattr('dirty_attrs', set([]))
        self.direct_setattr('_raw_data', raw_data)
        self.direct_setattr('_watched_attrs', set([]))

        for attr in self.attributes:
            attr_name = self._prettifyName(attr)
            self._watched_attrs.add(attr_name)
            self.direct_setattr(attr_name, raw_data[attr])

        for attr in self.optional_attributes:
            attr_name = self._prettifyName(attr)
            self._watched_attrs.add(attr_name)
            self.direct_setattr(attr_name, raw_data.get(attr, None))

    def _prettifyName(self, camelcase):
        camelcase = camelcase.replace('ID', '_id')
        if len(camelcase) > 1:
            repl_func = lambda match: '_' + match.group(1).lower()
            camelcase = camelcase[0].lower() + camelcase[1:]
            return re.sub('([A-Z])', repl_func, camelcase)
        else:
            return camelcase.lower()

    def _toCamelCase(self, name):
        if len(name) > 1:
            repl_func = lambda match: match.group(1)[1:].upper()
            name = name[0].upper() + name[1:]
            return re.sub('(_[a-z])', repl_func, name)
        else:
            return name.upper()

    def __setattr__(self, attr, value):
        if ((not hasattr(self, attr) or
             getattr(self, attr, None) != value) and
            attr in self._watched_attrs):
            self.direct_setattr('is_dirty', True)
            self.dirty_attrs.add(attr)
        self.direct_setattr(attr, value)


class LeankitUser(Converter):
    attributes = ['UserName', 'FullName', 'EmailAddress', 'Id']

class LeankitCardType(Converter):
    attributes = ['Name', 'IsDefault', 'ColorHex', 'IconPath', 'Id']

class LeankitCard(Converter):
    attributes = ['Id', 'Title', 'Priority', 'Description', 'Tags',
                  'TypeId']

    optional_attributes = [
        'ExternalCardID', 'AssignedUserId', 'Size', 'IsBlocked',
        'BlockReason', 'ExternalSystemName', 'ExternalSystemUrl',
        'ClassOfServiceId', 'DueDate',
        ]

    def __init__(self, card_dict, lane):
        super(LeankitCard, self).__init__(card_dict)

        self.lane = lane
        self.tags_list = set([tag.strip() for tag in self.tags.split(',')])
        if '' in self.tags_list:
            self.tags_list.remove('')
        self.type = lane.board.cardtypes[self.type_id]
        self._description_annotations = None

    @property
    def is_new(self):
        return self.id is None

    def addTag(self, tag):
        tag = tag.strip()
        if tag not in self.tags_list or self.tags.startswith(','):
            if tag != '':
                self.tags_list.add(tag)
            self.tags = ', '.join(self.tags_list)

    def save(self):
        self._setDescriptionAnnotations(self.description_annotations)
        if not (self.is_dirty or self.is_new):
            # no-op.
            return
        data = self._raw_data
        data["UserWipOverrideComment"] =  None;
        if ("AssignedUsers" in data and
            "assigned_user_id" not in self.dirty_attrs):
            if 'AssignedUserId' in data.keys():
                del data['AssignedUserId']
            if 'AssignedUserName' in data.keys():
                del data['AssignedUserName']
            data['AssignedUserIds'] = map(
                lambda X: X['AssignedUserId'], data['AssignedUsers'])

        for attr in self.dirty_attrs:
            #print "Storing %s in %s..." % (attr, self._toCamelCase(attr))
            data[self._toCamelCase(attr)] = getattr(self, attr)

        if self.is_new:
            del data['Id']
            del data['LaneId']
            position = len(self.lane.cards)
            url_parts = ['/Board', str(self.lane.board.id), 'AddCard',
                         'Lane', str(self.lane.id), 'Position', str(position)]
        else:
            url_parts = ['/Board', str(self.lane.board.id), 'UpdateCard']

        url = '/'.join(url_parts)

        result = self.lane.board.connector.post(url, data=data)

        if (self.is_new and
                result.ReplyCode in LeankitResponseCodes.SUCCESS_CODES):
            self.id = result.ReplyData[0]['CardId']

        return result.ReplyData[0]

    def move(self, target_lane):
        if target_lane is not None and target_lane != self.lane:
            self.lane = target_lane
            self._raw_data['LaneId'] = self.lane.id
            if not self.is_new:
                return self._moveCard()
            else:
                return self.save()
        else:
            return None

    def _moveCard(self):
        target_pos = len(self.lane.cards)
        url = '/Board/%d/MoveCard/%d/Lane/%d/Position/%d' % (
            self.lane.board.id, self.id, self.lane.id, target_pos)
        result = self.lane.board.connector.post(url, data=None)
        if result.ReplyCode in LeankitResponseCodes.SUCCESS_CODES:
            return result.ReplyData[0]
        else:
            raise Exception(
                "Moving card %s (%s) to %s failed. " % (
                    self.title, self.id, self.lane.path) +
                "Error %s: %s" % (result.ReplyCode, result.ReplyText))

    @classmethod
    def create(cls, lane):
        default_card_data = {
            'Id': None,
            'Title': '',
            'Priority': 1,
            'Description': '',
            'Tags': '',
            'TypeId': lane.board.default_cardtype.id,
            'LaneId': lane.id,
            'IsBlocked': "false",
            'BlockReason': None,
            'ExternalCardID': None,
            'ExternalSystemName': None,
            'ExternalSystemUrl': None,
            'ClassOfServiceId': None,
        }
        card = cls(default_card_data, lane)
        return card

    def copy(self, src):
        self.title = src.title
        self.priority = src.priority
        self.description = src.description
        self.tags = src.tags
        self.type_id = src.type_id
        self.lane = src.lane
        self.is_blocked = src.is_blocked
        self.size = src.size
        self.block_reason = src.block_reason
        self.due_date = src.due_date
        self.external_card_id = src.external_card_id
        self.assigned_user_id = src.assigned_user_id


    @property
    def parsed_description(self):
        """Parse the card description to find key=value pairs.

        :return: A tuple of (json_annotations, text_before_json,
                 text_after_json), where json_annotations contains the
                 JSON loaded with json.loads().
        """
        match = ANNOTATION_REGEX.search(self.description)
        if match:
            start = match.start()
            end = match.end()
            try:
                annotations = Record(json.loads(self.description[start:end]))
            except ValueError, ex:
                print "Unable to parse card %i: %s" % (self.id, ex.message)
                annotations = Record()
            return (
                annotations,
                self.description[:start].strip(),
                self.description[end:].strip())
        else:
            return Record(), self.description, ''

    def _setDescriptionAnnotations(self, new_annotations):
        """Update the card's description annotations.

        Note that this will overwrite all the annotations in the
        description.

        :param new_annotations: A dict of new annotations to store.
        """
        old_annotations, text_before_json, text_after_json = (
            self.parsed_description)
        annotation_text = json.dumps(new_annotations)
        new_description = dedent(u"""
            {text_before_json}
            {json_data}
            {text_after_json}
        """).format(
            text_before_json=text_before_json, json_data=annotation_text,
            text_after_json=text_after_json)
        self.description = new_description.strip()

    @property
    def description_annotations(self):
        if self._description_annotations is None:
            annotations, ignored_1, ignored_2 = self.parsed_description
            self._description_annotations = annotations
        return self._description_annotations


class LeankitLane(Converter):
    attributes = ['Id', 'Title', 'Index', 'Orientation', 'ParentLaneId']
    optional_attributes = ['Type']

    def __init__(self, lane_dict, board):
        super(LeankitLane, self).__init__(lane_dict)
        self.parent_lane = None
        self.board = board
        self.child_lanes = []
        self.cards = [LeankitCard(card_data, self)
                      for card_data in lane_dict['Cards']
                      if card_data['TypeId']]

    @property
    def path(self):
        components = [self.title]
        lane = self.parent_lane
        while lane is not None:
            if lane.id != 0:
                components.insert(0, lane.title)
            lane = lane.parent_lane
        return '::'.join(components)

    def _getChildrenDeep(self, lane):
        if len(lane.child_lanes) == 0:
            # Can't go any deeper.
            return lane
        else:
            if lane.orientation == 1:
                # Any of the following child lanes is a candidate.
                return [self._getChildrenDeep(child)
                        for child in lane.child_lanes]
            else:
                return self._getChildrenDeep(lane.child_lanes[0])

    def _getNextLanes(self, parent_lane, index, orientation):
        result = None
        if parent_lane is None:
            return None
        if orientation != 1:
            # No lanes have been found on this level,
            # try the next level up.
            for lane in parent_lane.child_lanes:
                if lane.index > index:
                    result = lane
                    break
        else:
            # We don't want the sibling sub-lanes in this case because
            # they are just horizontal subdivisions.
            pass

        if result is None:
            # We found no next lane at the same level as this one.
            return self._getNextLanes(
                parent_lane.parent_lane, parent_lane.index,
                parent_lane.orientation)
        else:
            # We found appropriate sibling lane, but now go as deep as we
            # can to ensure we do not end up in the "container" lane.
            child = self._getChildrenDeep(result)
            if isinstance(child, list):
                return child
            else:
                return [child]

    def getNextLanes(self):
        # If a lane has children lanes, ignore this lane.
        # Raise an exception instead?
        if len(self.child_lanes) > 0:
            return None
        else:
            return self._getNextLanes(self.parent_lane, self.index,
                                      self.orientation)

    def addCard(self):
        card = LeankitCard.create(self)
        self.cards.append(card)
        return card

class LeankitBoard(Converter):

    attributes = ['Id', 'Title', 'CreationDate', 'IsArchived']

    base_uri = '/Boards/'

    def __init__(self, board_dict, connector):
        super(LeankitBoard, self).__init__(board_dict)

        self.connector = connector
        self.root_lane = LeankitLane({
            'Id': 0,
            'Title': u'ROOT LANE',
            'Index': 0,
            'Orientation': 0,
            'ParentLaneId': -1,
            'Cards': [],
            }, self)
        self.lanes = {0: self.root_lane}
        self.cards = []
        self._cards_with_external_ids = set()
        self._cards_with_description_annotations = set()
        self._cards_with_external_links = set()
        self.default_cardtype = None

    def getCardsWithExternalIds(self):
        return self._cards_with_external_ids

    def getCardsWithExternalLinks(self):
        return self._cards_with_external_links

    def getCardsWithDescriptionAnnotations(self):
        return self._cards_with_description_annotations

    def fetchDetails(self):
        self.details = self.connector.get(
            self.base_uri + str(self.id)).ReplyData[0]

        self._populateUsers(self.details['BoardUsers'])
        self._populateCardTypes(self.details['CardTypes'])
        self._archive = self.connector.get(
            "/Board/" + str(self.id) + "/Archive").ReplyData[0]
        archive_lanes = [lane_dict['Lane'] for lane_dict in self._archive]
        archive_lanes.extend(
            [lane_dict['Lane'] for
            lane_dict in self._archive[0]['ChildLanes']])
        self._backlog = self.connector.get(
            "/Board/" + str(self.id) + "/Backlog").ReplyData[0]
        self._populateLanes(
            self.details['Lanes'] + archive_lanes + self._backlog)
        self._classifyCards()

    def _classifyCards(self):
        """Classify the cards into buckets for lookups later."""
        print "   Classifying cards %s cards." % len(self.cards)
        for card in self.cards:
            if card.external_card_id:
                self._cards_with_external_ids.add(card)
            if card.description_annotations:
                self._cards_with_description_annotations.add(card)
            if card.external_system_url:
                self._cards_with_external_links.add(card)
        print "   - %s cards with external ids" % len(
            self._cards_with_external_ids)
        print "   - %s cards with external links" % len(
            self._cards_with_external_links)
        print "   - %s cards with description annotations" % len(
            self._cards_with_description_annotations)

    def _populateUsers(self, user_data):
        self.users = {}
        self.users_by_id = {}
        for user_dict in user_data:
            user = LeankitUser(user_dict)
            self.users[user.user_name] = user
            self.users_by_id[user.id] = user

    def _populateLanes(self, lanes_data):
        self.root_lane.child_lanes = []
        for lane_dict in lanes_data:
            lane = LeankitLane(lane_dict, self)
            self.lanes[lane.id] = lane
        for lane_id, lane in self.lanes.iteritems():
            if lane.id == 0:
                # Ignore the hard-coded root lane.
                continue
            else:
                lane.parent_lane = self.lanes.get(lane.parent_lane_id, None)
                lane.parent_lane.child_lanes.append(lane)
            self.cards.extend(lane.cards)
        self._sortLanes()

    def _populateCardTypes(self, cardtypes_data):
        self.cardtypes = {}
        for cardtype_dict in cardtypes_data:
            cardtype = LeankitCardType(cardtype_dict)
            self.cardtypes[cardtype.id] = cardtype
            if cardtype.is_default:
                self.default_cardtype = cardtype

        assert self.default_cardtype is not None

    def _sortLanes(self, lane=None):
        """Sorts the root lanes and lists of child lanes by their index."""
        if lane is None:
            lane = self.root_lane
        lanes = lane.child_lanes
        lanes.sort(key=operator.attrgetter('index'))
        for lane in lanes:
            self._sortLanes(lane)

    def getLane(self, lane_id):
        flat_lanes = {}
        def flatten_lane(lane):
            flat_lanes[lane.id] = lane
            for child in lane.child_lanes:
                flatten_lane(child)
        map(flatten_lane, self.root_lane.child_lanes)
        return flat_lanes[lane_id];

    def getLaneByTitle(self, title):
        if len(self.root_lane.child_lanes) > 0:
            return self._getLaneByTitle(self.root_lane, title)

    def _getLaneByTitle(self, lane, title):
        if (lane.title == title):
            return lane
        else:
            for child in lane.child_lanes:
                result = self._getLaneByTitle(child, title)
                if result != None:
                    return result
            return None

    def getLaneByPath(self, path, ignorecase=False):
        if len(self.root_lane.child_lanes) > 0:
            return self._getLaneByPath(self.root_lane, path, ignorecase)

    def _getLaneByPath(self, lane, path, ignorecase):
        if ignorecase == True:
            if lane.path.lower() == path.lower():
                return lane
        else:
            if lane.path == path:
                return lane

        for child in lane.child_lanes:
            result = self._getLaneByPath(child, path, ignorecase)
            if result != None:
                return result
        return None


    def _printLanes(self, lane, indent, include_cards=False):
        next_lane = lane.getNextLanes()
        if next_lane is None:
            next_lane = ''
        else:
            next_lane = (' (next: any of [' +
                         ', '.join([my_lane.path for my_lane in next_lane])
                         + '])')
            next_lane += ' - %d cards' % len(lane.cards)
        print "  " * indent + "* " + lane.title + next_lane
        for card in lane.cards:
            print ("  " * (indent + 1) + "- #" + card.external_card_id +
                   ': ' + card.title)
        for child in lane.child_lanes:
            self._printLanes(child, indent + 1)

    def printLanes(self, include_cards=False):
        """Recursively prints all the lanes in the board with indentation."""
        if len(self.root_lane.child_lanes) == 0:
            return
        print "Board lanes:"
        indent = 1
        for lane in self.root_lane.child_lanes:
            self._printLanes(lane, indent, include_cards)


class LeankitKanban(object):

    def __init__(self, account, username=None, password=None):
        self.connector = LeankitConnector(account, username, password)
        self._boards = []
        self._boards_by_id = {}
        self._boards_by_title = {}

    def getBoards(self, include_archived=False):
        """List all the boards user has access to.

        :param include_archived: if True, include archived boards as well.
        """
        boards_data = self.connector.get('/Boards').ReplyData
        boards = []
        for board_dict in boards_data[0]:
            board = LeankitBoard(board_dict, self.connector)
            if board.is_archived and not include_archived:
                continue
            boards.append(board)
        return boards

    def _refreshBoardsCache(self):
        self._boards = self.getBoards(True)
        self._boards_by_id = {}
        self._boards_by_title = {}
        for board in self._boards:
            self._boards_by_id[board.id] = board
            self._boards_by_title[board.title] = board

    def _findBoardInCache(self, board_id=None, title=None):
        assert title is not None or board_id is not None, (
            "Either a board title or board id are required.")
        if board_id is not None and board_id in self._boards_by_id:
            return self._boards_by_id[board_id]
        elif title in self._boards_by_title:
            return self._boards_by_title[title]
        else:
            return None

    def _findBoard(self, board_id=None, title=None):
        board = self._findBoardInCache(board_id, title)
        if board is None:
            # Not found, try once more after refreshing the cache.
            self._refreshBoardsCache()
            board = self._findBoardInCache(board_id, title)
        return board

    def getBoard(self, board_id=None, title=None):
        board = self._findBoard(board_id, title)
        if board is not None:
            board.fetchDetails()
        return board


if __name__ == '__main__':
    kanban = LeankitKanban('launchpad.leankitkanban.com',
                           'user@email', 'password')
    print "Active boards:"
    boards = kanban.getBoards()
    for board in boards:
        print " * %s (%d)" % (board.title, board.id)

    # Get a board by the title.
    board_name = 'lp2kanban test'
    print "Getting board '%s'..." % board_name
    board = kanban.getBoard(title=board_name)
    board.printLanes()

    # Print all users.
    print board.users
