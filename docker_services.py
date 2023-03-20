from helpers import *
import argparse
from prettytable import PrettyTable
import json
from tqdm.contrib import tenumerate

PS_FIELDS = ['ID', 'Names']
SERVICE_PS_FIELDS = ['ID', 'Node', 'CurrentState']
SERVICE_LS_FIELDS = ['ID', 'Name', 'Mode', 'Replicas', 'Ports']
SERVICE_NODE_FIELDS = ['ID', 'Hostname']

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", metavar="ssh-comms", type=str, help="text file with ssh commands line by line")
    return parser.parse_args()

def parse_out(out, separator=",", ind=0):
    out_lines = out.split("\n")
    return [l.split(separator)[ind] for l in out_lines]

def get_format(format):
    f = "".join(["{{."+p+"}}"+"," for p in format])
    return f[:-1]

def get_service_ps(node, ids):
    print("getting service ps information...", flush=True)
    out = []
    count = 0
    format = get_format(SERVICE_PS_FIELDS)
    # loop through all service IDs given
    for i, id in tenumerate(ids):
        # get the output of the ps command (get the service info)
        ps_out = run_ssh_cmd(node, f"sudo docker service ps --format '{format}' --filter 'desired-state=Running' {id}", True)
        
        # loop through the tasks for this service
        for p in ps_out.split("\n"):
            p = p.strip()
            if p:
                out.append(f"{count},{p}")
        count += 1
    return out

def get_ps(node):
    format = get_format(PS_FIELDS)
    ps_out = run_ssh_cmd(node, f"sudo docker ps --format '{format}'", stderr=True)
    
    # loop through the containers for this node
    return [p.strip().split(",") for p in ps_out.split("\n") if p.strip()]

def get_nodes_ps(nodes):
    format = get_format(PS_FIELDS)
    outs = asyncio.run(run_remote_async(nodes, f"sudo docker ps --format '{format}'"))
    assert(all([outs[2] == 0 for outs in outs]))
    ps_outs = [outs[0] for outs in outs]
    return [[p.strip().split(",") for p in ps_out.split("\n") if p.strip()] for ps_out in ps_outs]

def get_service_ls(node):
    print("getting service list...", flush=True)
    format = get_format(SERVICE_LS_FIELDS)
    dls = f"sudo docker service ls --format '{format}'"
    return run_ssh_cmd(node, dls, False)

def get_node_ls(node):
    format = get_format(SERVICE_NODE_FIELDS)
    nls = f"sudo docker node ls --format '{format}'"
    return run_ssh_cmd(node, nls, False)

def get_constraints(node, ids):
    print("getting service constraints...", flush=True)
    def convert_nano_cpus(nano_cpus):
        if nano_cpus is None:
            return None
        return int(nano_cpus) / 1e9
    
    # (node label, CPU, memory)
    outs = []
    for i, id in tenumerate(ids):
        inspect_out = run_ssh_cmd(node, f"sudo docker service inspect {id}", False)
        inspect_out = json.loads(inspect_out)[0]
        resources = finditem(inspect_out, "Resources")
        cpu_lim, mem_lim, cpu_res, mem_res = None, None, None, None
        if "Limits" in resources:
            limits = resources["Limits"]
            cpu_lim = convert_nano_cpus(finditem(limits, "NanoCPUs"))
            mem_lim = finditem(limits, "MemoryBytes")
        if "Reservations" in resources:
            reservations = resources["Reservations"]
            cpu_res = convert_nano_cpus(finditem(reservations, "NanoCPUs"))
            mem_res = finditem(reservations, "MemoryBytes")
        outs.append([finditem(inspect_out, "Constraints"), cpu_lim, mem_lim, cpu_res, mem_res])
    return outs

def get_node_ids(node):
    nls_out = get_node_ls(node)
    return parse_out(nls_out, ind=0)

def get_service_nodes(node):
    dls_out = get_service_ls(node)
    service_ids = parse_out(dls_out, ind=0)
    service_names = parse_out(dls_out, ind=1)
    ps_outs = get_service_ps(node, service_ids)
    service_dict = {}
    for i in range(len(ps_outs)):
        row = ps_outs[i].split(",")
        service_num = int(row[0])
        # match the service name to the service number
        service_dict[service_names[service_num]] = int(row[2].split(".")[0].strip("node"))
    return service_dict

def print_table(master_node):
    dls_out = get_service_ls(master_node)
    service_ids = parse_out(dls_out, ind=0)
    constraints = get_constraints(master_node, service_ids)
    service_names = parse_out(dls_out, ind=1)
    ps_outs = get_service_ps(master_node, service_ids)
    
    x = PrettyTable()
    x.field_names = ["Service #", "Service ID", "Service Name", "Task #"] + SERVICE_PS_FIELDS + ["Constraints", "CPULim", "MemLim", "CPURes", "MemRes"]
    for i in range(len(ps_outs)):
        # get the row information provided from ps
        row = ps_outs[i].split(",")
        
        # service information
        row[2] = row[2].split(".")[0].strip("node") # get the node ID from Node
        service_num = int(row[0]) # service number
        
        # task information
        row.insert(1, i) # task number
        row.insert(1, service_names[service_num].replace(f"{get_current_service_name()}_", "")) # task's service name
        row.insert(1, service_ids[service_num]) # task's service ID
        row += constraints[service_num] # constraints
        x.add_row(row)
        
    print(x)
    return x

def main():
    args = parse_args()
    
    nodes, _ = parse_ssh_file(args.ssh_comms)
    print_table(nodes[0])

if __name__ == "__main__":
    main()