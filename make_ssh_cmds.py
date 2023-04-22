import os
import sys

num_nodes = 32

if len(sys.argv) > 2:
    
    private_key = sys.argv[1]
    hostname = sys.argv[2]
    

    with open("ssh_commands", "w") as file:
        for n in range(1, num_nodes):
            file.write(f"ssh -i {private_key} node{n}.{hostname}\n")
