from run_setup import open_jaeger
import argparse
from helpers import *

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", metavar="ssh-comms", type=str, help="text file with ssh commands line by line")
    return parser.parse_args()

def main():
    args = parse_args()
    nodes, _ = parse_ssh_file(args.ssh_comms)
    open_jaeger(nodes[0])

if __name__ == "__main__":
    main()