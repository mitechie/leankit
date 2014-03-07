import sys

from leankit.leankit import LeankitKanban
from leankit.scripts.common import (
    base_args,
    load_credentials,
)


def parse_args():

    desc = "Interact with your Leankit Kanban boards."
    parser = base_args(desc)
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    creds = load_credentials(args.ini)

    lk = LeankitKanban(creds.account, creds.username, creds.password)

    if not args.board_title and not args.board_id:
        for board in lk.getBoards():
            print str(board)
    else:
        board_info = {
            'board_id': int(args.board_id) if args.board_id else None,
            'title': args.board_title
        }
        board = lk.getBoard(**board_info)
        if not board:
            sys.exit("Board not found: {0}".format(board_info))

        if not args.lane_id and not args.lane_path:
            board.printLanes()
        else:
            if args.lane_id:
                lane = board.getLane(int(args.lane_id))
            elif args.lane_path:
                lane = board.getLaneByPath(args.lane_path, ignorecase=True)

            if not lane:
                sys.exit('Could not find lane: {0}'.format({
                    'lane_id': args.lane_id,
                    'path': args.lane_path,

                }))

            print "\n\nPlanningPoker.com import format.\n\n"
            print "\t".join(['Title', 'Description'])
            for card in lane.cards:
                print "\t".join([card.title, card.description])


if __name__ == '__main__':
    main()
