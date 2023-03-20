import csv
import argparse
from helpers import *

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", metavar="csv-file", type=str, help="csv file that contains the constraints")
    parser.add_argument("--env", type=str, default=".env", help="name of env file to write out to")
    parser.add_argument("--delimeter", "-d", type=str, default=",", help="csv file delimeter")
    parser.add_argument("--fraction", "-f", type=str, default=None, help="ssh commands of the nodes to get core counts for the fractions, if None, then use raw numbers")
    parser.add_argument("--write", "-w", action="store_true", help="scp the env file to the node")
    return parser.parse_args()

def sort_csv_file(csv_file):
    # read and sort rows of csv file by first column
    rows = []
    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)
        rows.sort(key=lambda x: x[0])
        
    # write sorted rows to csv file
    with open(csv_file, 'w') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
        

def make_compose(csv_file, env_file, delimeter, nodes=[]):
    cores = []
    if nodes:
        cores = get_core_counts(nodes)
    print(f"reading from {csv_file}...", flush=True)
    csv_file = find_file(csv_file, env_csv=True)
    
    with open(csv_file, 'r') as csv_file, open(env_file, 'w') as out_file:
        csv_reader = csv.DictReader(csv_file, delimiter=delimeter)
        for row in csv_reader:
            sn = row["ServiceName"].replace("-", "_")
            n = row["Node"]
            cpus = row["CPUs"]
            mem = row["Memory"]
            if cores:
                cpus = cores[int(n)]*float(cpus)
            out_file.write(f"{sn}_placement=\"node.labels.node{n} == true\"\n")
            out_file.write(f"{sn}_cpu=\"{cpus}\"\n")
            out_file.write(f"{sn}_memory=\"{mem}\"\n")
    print(f"env file written out to {env_file}...", flush=True)

def main():
    args = parse_args()
    if args.fraction is None:
        nodes = []
    else:
        nodes, _ = parse_ssh_file(args.fraction)
    make_compose(args.csv_file, args.env, args.delimeter, nodes=nodes)

if __name__ == "__main__":
    main()