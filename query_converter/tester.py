import .parser
from .parse_tree import SAM_query_to_MetaCat
import logging

if __name__ == "__main__":
    import sys

    loglevel = logging.INFO
    if "-d" in sys.argv:
        loglevel = logging.DEBUG

    logging.basicConfig(level = loglevel )

    for line in sys.stdin:
        print( SAM_query_to_MetaCat(line.strip()) )
