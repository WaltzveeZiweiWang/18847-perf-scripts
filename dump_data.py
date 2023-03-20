from helpers import *
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_file", metavar="data-file", type=str, help="data file")
    return parser.parse_args()

def main():
    args = parse_args()
    data_load(args.data_file, print_obj=True)

if __name__ == "__main__":
    main()

