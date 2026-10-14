import logging
import cli
from logger_config import setup_logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)



def print_result_data(data):
    if isinstance(data, dict):
        # for key, value in data.items():
        #     print(f"{key}: {value}")
        print(data)
        return

    if isinstance(data, list):
        if not data:
            print("No data")
            return

        if isinstance(data[0], dict):
            for user in data:
                print(user)
            return

        for item in data:
            print(item)
        return

    print(data)


def main():
    setup_logging()

    

def main():
    setup_logging()

    parser = cli.build_parser()

    argv = sys.argv[:]

    if len(argv) > 1:
        argv[1] = argv[1].lower()

    args = parser.parse_args(argv[1:])
    
    result = args.handler(args)

    if not result:
        print(f"ERROR: {result.error}")
        logger.error("Operation failed: %s", result.error)
        return

    if result.data:
        print_result_data(result.data)

    logger.info("Operation completed successfully")



if __name__ == "__main__":
    main()