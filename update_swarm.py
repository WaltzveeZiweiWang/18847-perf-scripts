import argparse
from helpers import *
from docker_services import print_table, get_service_nodes, get_ps, get_nodes_ps
from make_docker_compose import make_compose
from tqdm.contrib import tenumerate
import time
import csv

DSB_PATH = f"~/DeathStarBench/{get_current_service_name()}/"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", type=str, help="text file with ssh commands line by line")
    parser.add_argument("--csv-file", type=str, default="env.csv", help="csv file with service assignments")
    parser.add_argument("--compose-file", type=str, default="docker-compose-swarm.yml", help="yaml file with service assignments")
    parser.add_argument("--fraction", "-f", action="store_true", help="use fractions of total cores")
    parser.add_argument("--pin", "-p", action="store_true", help="pin services to cores")
    parser.add_argument("--sorted", "-s", action="store_true", help="sort cores by increasing number, so avoid SMT")    
    return parser.parse_args()

def get_stack(node):
    stack_name = run_ssh_cmd(node, "sudo docker stack ls").split("\n")
    if len(stack_name) <= 1:
        return None
    return stack_name[1].split()[0]

def deploy_stack(node, compose_file, env_file, dsb_path):
    run_ssh_cmd(node, f"./deploy_stack.sh {compose_file} {env_file} {get_current_service_name()}", cd=dsb_path, check=True)

def rm_stack(node, quiet=False):
    stack_name = get_stack(node)
    if stack_name is None:
        if not quiet:
            print("no stack to remove...", flush=True)
        return False

    print(f"removing stack '{stack_name}'...", flush=True)
    run_ssh_cmd(node, f"sudo docker stack rm {stack_name}")
    return True
    
def restart_stack(nodes, dsb_path, compose="docker-compose-swarm.yml", env=".env", no_print=False, pin=None, cleanup_nodes=True):
    print("sleeping for 30 seconds before starting...", flush=True)
    time.sleep(30) # need to do this because of weird Docker bug (https://stackoverflow.com/questions/53347951/docker-network-not-found)
    master_node = nodes[0]
    if cleanup_nodes:
        print("removing previous stack (if exists)...", flush=True)
        cleanup(nodes)
    print("re-deploying stack...", flush=True)
    deploy_stack(master_node, compose, env, dsb_path)
    time.sleep(30) # sleep for 30 seconds to let the stack start up
    
    table = None
    if not no_print:
         # print out to make sure changes look right
        print("printing updated table...", flush=True)
        table = print_table(master_node)
        print("NOTE: check table above to make sure all current states are running/started...", flush=True)
    if pin is not None:
        pin_cpus(nodes, pin)
    return table

def get_numa_nums(nodes: list):
    print("getting NUMA numbers...", flush=True)
    numa_nums = []
    for _, node in tenumerate(nodes):
        out = run_ssh_cmd(node, "sudo lscpu")
        lines = out.split("\n")
        lines = [line for line in lines if line.startswith("NUMA node") and "CPU(s)" in line]
        numa_num = []
        for line in lines:
            line = line.strip().split()[3]
            numa_num.append(line.split(","))
        numa_nums.append(numa_num)
        
    for i, n in enumerate(numa_nums):
        print(f"node{i}:", end=" ")
        for j, nn in enumerate(n):
            print(f"NUMA node {j}: {nn}", end="")
            if j < len(n) - 1:
                print(", ", end="")
        print()
    return numa_nums

def get_cpu_info(nodes: list, sort_cpus=False):
    print("getting socket numbers...", flush=True)
    socket_nums = []
    node_tables = []
    for _, node in tenumerate(nodes):
        out = run_ssh_cmd(node, "sudo likwid-topology -O")
        lines = out.split("\n")
        
        table_start = False
        header = False
        headers = ""
        node_dicts = []
        for line in lines:
            line = line.strip()
            
            if table_start and line.startswith("STRUCT"):
                break
            if line.startswith("TABLE"):
                table_start = True
                header = True
                continue
            elif header:
                headers = line.strip(",").split(",")
                header = False
            elif table_start:
                data = line.strip(",").split(",")
                data_dict = {headers[i]: data[i] for i in range(len(headers))}
                node_dicts.append(data_dict)
        node_tables.append(node_dicts)
            
        socket_lines = [line.strip() for line in lines if line.startswith("Socket ")]
        socket_cpus = [sl.split(":,")[1].strip().split(",") for sl in socket_lines]
        # sort in order to schedule on separate cores before on SMT threads
        if sort_cpus:
            socket_cpus = [sorted(sc, key=int) for sc in socket_cpus]
        socket_nums.append(socket_cpus)
        
    for i, s in enumerate(socket_nums):
        print(f"node{i}:", end=" ")
        for j, ss in enumerate(s):
            print(f"socket {j}: {ss}", end="")
            if j < len(s) - 1:
                print(", ", end="")
        print()
    return socket_nums, node_tables

def table_to_list(table):
    socket_nums = [int(t["Socket"]) for t in table]
    core_nums = [int(t["Core"]) for t in table]
    num_socket = max(socket_nums) + 1   # number of sockets on this server
    num_core = max(core_nums) + 1       # number of cores on this server
    
    cpu_list = []   # HWThread num = [socket][core][thread]
    next_cpu = []   # next cpu (logical core) to use on core = [socket][core]
    for i in range(num_socket):
        cpu_list.append([])
        core_list = []
        for _ in range(num_core):
            cpu_list[i].append([])
            core_list.append(0)
        next_cpu.append(core_list)
            
    
    for t in table:
        cpu_list[int(t["Socket"])][int(t["Core"])].append(int(t["HWThread"]))
        
    return cpu_list, next_cpu, num_core, num_socket

def get_from_table(table, cpu_num, key="Core"):
    # get the dict with HWThread == cpu_num
    cpu_dict = [t for t in table if int(t["HWThread"]) == cpu_num][0]
    return int(cpu_dict[key])

def pin_cpus(nodes, csv_file, sort_cpus=False):
    csv_file = find_file(csv_file, env_csv=True)
    # get the socket numbers for each node: list of logical cores = [node][socket]
    socket_nums, node_tables = get_cpu_info(nodes, sort_cpus=sort_cpus)
    cpu_lists, next_cpus, num_cores, num_sockets = [], [], [], []
    for nt in node_tables:
        cl, nc, cn, sn = table_to_list(nt)
        cpu_lists.append(cl)
        next_cpus.append(nc)
        num_cores.append(cn)
        num_sockets.append(sn)
    
    # mark if a (physical) core already has a pinned logical core - list for each node
    core_assigned = [[[False for _ in range(num_cores[i])] for _ in range(num_sockets[i])] for i in range(len(nodes))]
    # this is a list for each socket on the next core to assign - only used if all cores have already been assigned
    next_cpu = [[0 for _ in range(len(socket_nums[i]))] for i in range(len(socket_nums))]

    # get the node assignments for the services
    service_nodes = get_service_nodes(nodes[0])
    
    # get a dict of the containers on each node
    print("getting container info...", flush=True)
    containers_info = get_nodes_ps(nodes)
    
    for i, cinfo in enumerate(containers_info):
        print(f"node{i}: {cinfo}")
    
    print("pinning services to sockets...", flush=True)
    with open(csv_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        # get the header names
        headers = csv_reader.fieldnames
        ncpus = "NCPUs" in headers
        
        for row in csv_reader:
            service_name = row["ServiceName"]
            socket = int(row["Socket"])
            if socket == -1: # no socket pin for this service
                print(f"skipping pinning for {service_name}...")
                continue
            
            if ncpus:
                cpus = int(row["NCPUs"])
            
            # get the node that the service is running on
            node_num = service_nodes[f"{get_current_service_name()}_{service_name}"]
            if socket >= len(socket_nums[node_num]):
                print(f"socket {socket} not available on node {node_num}")
                assert(False)
                
            # loop through all containers running on the node
            for cinfo in containers_info[node_num]:
                # if the node contains the service that you're looking for
                id, name = cinfo[:2]
                if name.startswith(f"{get_current_service_name()}_{service_name}"):
                    # get the cpu numbers for this socket
                    cpus_to_pin = socket_nums[node_num][socket]
                    # only do this if the user has specified a number of cpus to pin
                    if ncpus and cpus != 0:
                        cpin = []
                        if not sort_cpus:
                            # loop through each core on this socket
                            for i in range(len(core_assigned[node_num][socket])):
                                # if no microservices on this core already
                                if not core_assigned[node_num][socket][i]:
                                    # loop through the logical cores on this core
                                    for j in range(len(cpu_lists[node_num][socket][i])):
                                        # add this logical core to the list
                                        cpin.append(cpu_lists[node_num][socket][i][j])
                                        # set this core as being assigned
                                        core_assigned[node_num][socket][i] = True
                                        # move the next cpu to assign to the next logical core on this core
                                        next_cpus[node_num][socket][i] += 1
                                        # if we've reached the number of cpus to pin, break
                                        if len(cpin) == cpus:
                                            break
                                    # if we've reached the number of cpus to pin, break
                                    if len(cpin) == cpus:
                                        break
                            
                            # if still not enough cpus, then start colocating on other cores, on empty cores first
                            if len(cpin) < cpus:
                                print(f"not enough cpus on socket {socket} for {service_name} on node {node_num} without physical core colocation...")
                                # loop through each core on this socket
                                for i in range(len(next_cpus[node_num][socket])):
                                    # if all logical cores have already been pinned, skip
                                    if next_cpus[node_num][socket][i] >= len(cpu_lists[node_num][socket][i]):
                                        continue
                                    # add the next (empty) logical core to the list
                                    cpin.append(cpu_lists[node_num][socket][i][next_cpus[node_num][socket][i]])
                                    # increment the next cpu to assign to the next logical core on this core
                                    next_cpus[node_num][socket][i] += 1
                                    # stop assigning to this core
                                    if len(cpin) == cpus:
                                        break
                                
                                # at this point every core on this socket has been pinned, so just start filling from 
                                # low to high
                                if len(cpin) < cpus:
                                    print(f"not enough cpus on socket {socket} for {service_name} on node {node_num} without logical core (SMT) colocation...")
                                while len(cpin) < cpus:
                                    cpin.append(cpus_to_pin[next_cpu[node_num][socket]])
                                    next_cpu[node_num][socket] += 1
                                    next_cpu[node_num][socket] %= len(cpus_to_pin)
                        else:
                            for _ in range(cpus):
                                cpin.append(cpus_to_pin[next_cpu[node_num][socket]])
                                next_cpu[node_num][socket] += 1
                                next_cpu[node_num][socket] %= len(cpus_to_pin)
                        cpus_to_pin = cpin
                    cpus_to_pin = [str(c) for c in cpus_to_pin]
                    cpus_to_pin = ",".join(cpus_to_pin)
                    print(f"pinning to cpus [{cpus_to_pin}], socket {socket}, node {node_num}, for {service_name}...", flush=True)
                    run_ssh_cmd(nodes[node_num], f"sudo docker update --cpuset-cpus={cpus_to_pin} {id}", stderr=True, check=True)
    print("done pinning services to sockets...", flush=True)
    
def rm_containers(nodes):
    assert(isinstance(nodes, list))
    ps_outs = get_nodes_ps(nodes)
    node_ids = [[p[0] for p in ps_out] for ps_out in ps_outs]
    if all([len(ids) == 0 for ids in node_ids]):
        print(f"no containers to remove on nodes...", flush=True)
        return False
    print(f"removing containers on node(s)...", flush=True)
    rm_nodes = []
    rm_ids = []
    for i, n in enumerate(nodes):
        if len(node_ids[i]) > 0:
            rm_nodes.append(n)
            rm_ids.append(node_ids[i])
    cmds = [f"sudo docker rm -f -v {' '.join(ids)}" for ids in rm_ids]
    asyncio.run(run_remote_async(rm_nodes, cmds, print_stderr=True, cmd_list=True, check=True))
    return True

def prune_nodes(nodes):
    assert(isinstance(nodes, list))
    print(f"pruning nodes...", flush=True)
    asyncio.run(run_remote_async(nodes, "sudo docker container prune -f && sudo docker network prune -f && sudo docker volume prune -f", 
                                 print_stderr=True, check=True))

def clean_nodes(nodes):
    return rm_stack(nodes[0], quiet=True) or rm_containers(nodes)
    
def cleanup(nodes):
    assert(isinstance(nodes, list))
    # this is for https://github.com/moby/moby/issues/32620
    print(f"cleaning up swarm nodes...", flush=True)
    while (clean_nodes(nodes)):
        time.sleep(5)
    prune_nodes(nodes)
    print(f"done cleaning up master node...", flush=True)
    
def check_no_containers(nodes):
    print("checking for dangling containers...", flush=True)
    containers = asyncio.run(run_remote_async(nodes, "sudo docker ps -q", print_stderr=True, check=True))
    for i, conts in enumerate(containers):
        conts = conts[0]
        if len(conts) > 0:
            print(f"containers still running on node {nodes[i]}", flush=True)
            assert(False)

def set_compose_env(nodes, compose_file, csv_file, fraction=False):
    # make the custom env file with the changes
    print("making custom env file...", flush=True)
    make_compose(csv_file, ".env", ",", nodes=nodes if fraction else [])

    # copy the new env file (and compose file) to the node
    print(f"copying {compose_file} and new .env to master node...", flush=True)
    run_scp_cmd(nodes[0], compose_file, f"{DSB_PATH}docker-compose-swarm.yml", check=True)
    run_scp_cmd(nodes[0], ".env", f"{DSB_PATH}.env", check=True)

def main():
    # parse arguments
    args = parse_args()
    nodes, ssh_commands = parse_ssh_file(args.ssh_comms)
    
    # set the compose file and env file
    set_compose_env(nodes, args.compose_file, args.csv_file, fraction=args.fraction)
    
    print("cleaning dangling containers...", flush=True)
    # cleanup previous stack/dangling containers
    cleanup(nodes)
    # just to be sure, sleep and check again
    time.sleep(5)
    # checking for no containers before starting stack
    check_no_containers(nodes)
    
    # restart the stack
    restart_stack(nodes, compose="docker-compose-swarm.yml", dsb_path=DSB_PATH, env=".env", cleanup_nodes=True)
    
    # if flag set, pin the services to sockets/cpus
    if args.pin:
        pin_cpus(nodes, args.csv_file, sort_cpus=args.sorted)
    
if __name__ == "__main__":
    main()