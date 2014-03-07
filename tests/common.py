# Copyright 2012 Canonical Ltd.
"""Common fixtures for lp2kanban tests."""

__metaclass__ = type

from leankit.leankit import Record


class FauxCardType:

    def __init__(self, id=1, name='Test', is_default=True):
        self.id = id
        self.name = name
        self.is_default = is_default
        self.ColourHex = "#000"
        self.IconPath = None


class FauxBoard:

    root_lane = None
    _next_lane_id = 0

    def __init__(self, cards=None, users=None, users_by_id=None,
                 default_cardtype=None, is_archived=False):
        if cards is None:
            cards = []
        self.cards = cards
        self.users = users
        self.users_by_id = users_by_id
        self.default_cardtype = default_cardtype or FauxCardType(id=1)
        self.cardtypes = {self.default_cardtype.id: self.default_cardtype}
        self.is_archived = is_archived
        self._cards_with_description_annotations = set()
        self._cards_with_external_links = set()
        self.lanes = {}
        self.root_lane = self.addLane('ROOT LANE')

    def getCardsWithDescriptionAnnotations(self):
        return self._cards_with_description_annotations

    def getCardsWithExternalLinks(self):
        return self._cards_with_external_links

    def getLaneByPath(self, path):
        for lane in self.lanes.values():
            if lane.path == path:
                return lane
        return None

    def addLane(self, path):
        lane = FauxLane(path, board=self, id=self._next_lane_id)
        self._next_lane_id += 1
        if self.root_lane is not None:
            self.root_lane.child_lanes.append(lane)
        self.lanes[lane.id] = lane
        return lane


class FauxLane:

    def __init__(self, path=None, title=None, id=None, type=None, board=None):
        self.id = id or 1
        self.type = type
        self.board = board or FauxBoard("Test")
        self.path = path
        self.next_lanes = None
        self.child_lanes = []
        if title is None:
            title = path
        self.title = title

    def getNextLanes(self):
        return self.next_lanes

    def addNextLane(self, lane):
        if self.next_lanes is None:
            self.next_lanes = [lane]
        else:
            self.next_lanes.append(lane)

    def addCard(self, card=None):
        if card is None:
            card = FauxCard()
        card.lane = self
        if self.board is not None:
            self.board.cards.append(card)
        return card


class FauxCard:

    def __init__(self, external_card_id=None, title=u"", description=u"",
                 description_annotations=None, lane=None,
                 assigned_user_id=None, external_system_name=None,
                 external_system_url=None):
        self.external_card_id = external_card_id
        self.title = title
        self.description = description
        self.description_annotations = description_annotations or Record()
        self.lane = lane
        self.assigned_user_id = assigned_user_id
        self.external_system_name = external_system_name
        self.external_system_url = external_system_url
        self.moved_to = None
        self.saved = False

    def save(self):
        """A no-op for compatibility."""
        self.saved = True

    def move(self, target_lane):
        self.moved_to = target_lane


class FauxLeankitUser:

    def __init__(self, id, user_name=None, full_name=None, email_address=None):
        self.id = id
        self.user_name = user_name
        self.full_name = full_name
        self.email_address = email_address


class FauxLaunchpadUser:

    def __init__(self, name, display_name=None):
        self.name = name
        self.display_name = display_name


class FauxLaunchpadUsersForBoard:

    def __init__(self, kanban_to_lp=None, lp_to_kanban=None):
        self.kanban_to_lp = kanban_to_lp
        self.lp_to_kanban = lp_to_kanban
