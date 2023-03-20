import argparse

def parse_ssh_file(ssh_file):
    nodes = []
    ssh_commands = []
    with open(ssh_file, "r") as f:
        for line in f:
            line = line.strip()
            cmd = line[line.find("ssh"):] + "\n"
            ssh_commands.append(cmd)
            
    with open(ssh_file, "w") as f:
        f.writelines(ssh_commands)
        
    return nodes, ssh_commands

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, help="text file with ssh commands line by line")
    return parser.parse_args()

def main():
    args = parse_args()
    parse_ssh_file(args.file)

if __name__ == "__main__":
    main()