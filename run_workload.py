import argparse
from helpers import *
import time
from update_swarm import restart_stack, set_compose_env, check_no_containers, cleanup
import asyncio

DSB_PATH = f"~/DeathStarBench/{get_current_service_name()}/"
CD_WRK = f"cd ~/DeathStarBench/{get_current_service_name()}/wrk2"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", metavar="ssh-comms", type=str, help="text file with ssh commands line by line")
    parser.add_argument("--time", "-t", type=int, default=120, help="time to run workload in seconds")
    parser.add_argument("--workload", "-w", type=int, default=0, help="which workload to run")
    parser.add_argument("--silent", "-s", action="store_true", help="don't print output")
    parser.add_argument("--append", "-a", action="store_true", help="whether to append to the output file (if it already exists)")
    parser.add_argument("--pickle-file", "-p", default=None, type=str, help="name of pickle file output; if already exists, will make new file with timestamp, unless append flag set to true")
    parser.add_argument("--no-dump", "-n", action="store_true", help="don't pickle output")
    parser.add_argument("--threads", "-T", type=int, default=2, help="number of threads to use")
    parser.add_argument("--cooldown", "-c", type=int, default=20, help="time to wait after running each load")
    parser.add_argument("--warmup", "-W", type=int, default=30, help="time to warmup before running workload")
    parser.add_argument("--stats", "-S", action="store_true", help="record stats while running workload")
    parser.add_argument("--power", action="store_true", help="record power while running workload")
    parser.add_argument("--cpufreq", action="store_true", help="record cpufreq while running workload")
    parser.add_argument("--restart", "-R", type=str, default=None, help="restart the swarm with the given csv file")
    parser.add_argument("--pin", "-P", action="store_true", help="pin the CPUs")
    parser.add_argument("--compose-file", type=str, default="docker-compose-swarm.yml", help="yaml file with service assignments")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sweep", type=int, nargs=4, default=[500, 8000, 500, 0], help="[start, stop, step, 0=add | else=multiply], start/stop is inclusive")
    group.add_argument("--loads", type=str, default=None, help="file with loads to run separated by newlines")
    return parser.parse_args()

def run_workload(nodes, wrk_type=0, input_rate=2000, time=30, warmup=0, 
                 threads=2, stats=False, power=False, cpufreq=False):
    # get the workloads for the current service
    workloads = get_current_service_workloads()

    # make sure the wrk_type given is valid
    assert(wrk_type >= 0 and wrk_type < len(workloads))
    # make sure nodes is a list
    assert(type(nodes) == list)

    # get the command to run for the workload
    wrk_script = workloads[wrk_type]["workload_cmd"]
    
    # if warmup time given, then run the workload for warmup amt of time
    if warmup > 0:
        print(f"running warmup for {warmup} seconds", flush=True)
        warmup_cmd = wrk_script.format(threads, warmup, input_rate)
        run_ssh_cmd(nodes[0], f"{CD_WRK} && sudo {warmup_cmd}", check=True)
    
    # get the command to run
    to_run = wrk_script.format(threads, time, input_rate)
    # print out time at which command started
    time_str = get_datetime(compact=False)
    print(f"running: [{to_run}], at {time_str}", flush=True)

    # if stats or power, then run the stats/power scripts in the background on each node
    if stats:
        asyncio.run(run_remote_async(nodes, f"./docker_stats.sh stats.txt {time-2}", background=True))
    if power:
        asyncio.run(run_remote_async(nodes, f"./rapl.sh rapl.txt {time-2}", background=True))
    if cpufreq:
        asyncio.run(run_remote_async(nodes, f"./cpufreq.sh cpufreq.txt {time-2}", background=True))

    # run and return the output of the wrk command
    return run_ssh_cmd(nodes[0], f"{CD_WRK} && sudo {to_run}", check=True), to_run

def str_to_float(str):
    # extract whatever is a digit or a decimal point from the string
    float_str = ''.join(c for c in str if c.isdigit() or c == '.')
    # extract the suffix from the string
    suffix = str.strip(float_str)
    
    # calculate the scale factor based on the suffix
    scale_factor = 1
    if suffix == '':
        pass
    elif suffix == "m":
        scale_factor = 60*1000
    elif suffix == "s":
        scale_factor = 1000
    elif suffix == "ms":
        pass
    elif suffix == "us":
        scale_factor = 0.001
    elif suffix == "k":
        scale_factor = 1000
    elif suffix == "%":
        pass
    else:
        print(f"unknown suffix: {suffix}, for the string: {str}")
        assert(False)
    
    # convert the float string to a float and scale it
    try:
        float_val = float(float_str)
    except ValueError:
        print(f"could not convert {float_str} to float, with the string {str}")
        assert(False)
    return float_val * scale_factor

def list_to_floats(lst):
    return [str_to_float(i) for i in lst]

def parse_output(wrk_output):
    lines = [l.strip() for l in wrk_output.split("\n")]
    avg_lat, req_sec = [], []
    lat_dist = []
    for i, line in enumerate(lines):
        line.strip()
        if line.startswith("Latency") and not line.startswith("Latency Distribution"):
            data = line.split()
            avg_lat = list_to_floats(data[1:])
        elif line.startswith("Req/Sec"):
            data = line.split()
            req_sec = list_to_floats(data[1:])
        elif line.startswith("Latency Distribution"):
            data = line.split()
            j = i + 1
            while lines[j] != "":
                data = lines[j].split()
                lat_dist.append(str_to_float(data[1]))
                j += 1
            break
    return avg_lat, req_sec, lat_dist

def parse_wrk_output(wrk_output, cmd, out_file=None, no_write=False):
    # make new directory for outputs
    dir = "outputs/"
    open_path(dir)
    
    if out_file is None:
        timestr = get_datetime()
        out_file = f"out_{timestr}"
    out_file = f"outputs/{out_file}"
    
    if not no_write:
        # write out output
        with open(out_file, 'w') as f:
            f.write(f"Command: {cmd}\n\n")
            f.write(wrk_output)
            
        print(f"wrk results written to: {out_file}")
    
    return parse_output(wrk_output)

def get_stats(nodes, docker=True, power=True, cpufreq=True, raw=False):
    node_stats = []
    node_rapls = []
    node_cpufreqs = []
    if docker:
        docker_stats = asyncio.run(run_remote_async(nodes, f"cat stats.txt"))
        
        stats_format = ["ID", "Name", "CPUPerc", "MemUsage", "NetIO", "BlockIO", "PIDs", "MemPerc"]
        for docker_stat in docker_stats:
            # if error code non-zero, then command failed
            if docker_stat[2] != 0:
                node_stats.append(None)
                continue
            # separate out each measurement - each line has a container measurement at some time
            s_data = docker_stat[0].split('\n')
            s_data = [d for d in s_data if d.strip() != ""]
            # remove the clear screen and home cursor escape sequences
            s_data = [d.strip("\x1b[2J\x1b[H2") for d in s_data]
            # for each line of data, split by comma into list of stats
            s_data = [d.split(',') for d in s_data]

            # loop through the measurements and extract the data into dicts - one per measurement
            data_dicts = []
            for sd in s_data: # loop through each measurement
                data_dict = {}
                for i, d in enumerate(sd): # loop through each stat type and put into dict
                    data_dict[stats_format[i]] = d
                data_dicts.append(data_dict)
            node_stats.append(data_dicts)
        
    if power:
        rapl_stats = asyncio.run(run_remote_async(nodes, f"cat rapl.txt"))
        # loop through the energy stats for each node
        for rapl_stat in rapl_stats:
            # if error code non-zero, then command failed
            if rapl_stat[2] != 0:
                node_rapls.append(None)
                continue
            # separate out each measurement by line and remove empty lines
            p_data = rapl_stat[0].split('\n')
            p_data = [d for d in p_data if d.strip() != '']
            # get the dict by splitting at the =
            p_data = [d.split('=') for d in p_data]
            # extract the data into a dictionary and add to list of per-node data
            p_data = {d[0]: float(d[-1]) for d in p_data}
            node_rapls.append(p_data)
    
    if cpufreq:
        cpufreq_stats = asyncio.run(run_remote_async(nodes, f"cat cpufreq.txt"))
        # loop through the recorded cpufreqs for each node
        for cpufreq_stat in cpufreq_stats:
            # if error code non-zero, then command failed
            if cpufreq_stat[2] != 0:
                node_cpufreqs.append(None)
                continue
            # separate out each measurement by line and remove empty lines
            c_data = cpufreq_stat[0].split('\n')
            # measurements are separated by a blank line
            all_data = []
            last = 0
            for i, d in enumerate(c_data):
                if d.strip() == '':
                    # convert to list of ints - remove decimal point
                    curr_data = [x.split('.')[0] for x in c_data[last:i]]
                    all_data.append(curr_data)
                    last = i + 1
                    
            node_cpufreqs.append(all_data)
            
    if raw:
        return docker_stats, rapl_stats, cpufreq_stats
            
    return node_stats, node_rapls, node_cpufreqs

def run_loads(nodes, loads, runtime=30, threads=2, sweep=False, cooldown=10, 
              workload=0, warmup=0, stats=False, power=False, cpufreq=False,
              restart=None, pin=False):
    # if sweep parameters given, override loads
    if sweep:
        assert(len(loads) == 4)
        # unpack variables
        start, stop, step, add = loads
        loads = []
        i = start
        while i <= stop:
            loads.append(i)
            if add == 0:
                i += step
            else:
                i *= step

    # lists of outputs to return
    outs = []
    out_stats = []

    # loop through loads to run and get outputs
    for i, l in enumerate(loads):
        if restart is not None:
            # cleanup previous stack/dangling containers
            cleanup(nodes)
            # just to be sure, sleep and check again
            time.sleep(5)
            # checking for no containers before starting stack
            check_no_containers(nodes)
            restart_stack(nodes, pin=restart if pin else None, dsb_path=DSB_PATH)
        # run the workload on the swarm, collect the output from master node
        cp, cmd = run_workload(nodes, wrk_type=workload, input_rate=l, 
                               time=runtime, threads=threads, warmup=warmup, 
                               stats=stats, power=power, cpufreq=cpufreq)
        print(f"load {l} done at {get_datetime(compact=False)}")

        # parse the output into standardized form (from string)
        out = (l, parse_wrk_output(cp, cmd, f"load_sweep", no_write=True))
        outs.append(out)
        print(out, flush=True)
        
        # if stats or power, then parse those
        if stats or power:  
            load_stats = get_stats(nodes, docker=stats, power=power, cpufreq=cpufreq)
            out_stats.append((l, load_stats))
        
        # if not the last run, then cooldown
        if i != len(loads) - 1:
            print(f"waiting {cooldown} seconds before next load", flush=True)
            time.sleep(cooldown) # sleep to allow for cool down
        print()
        
    return outs, out_stats
    
def read_loads(load_file):
    # get list of integer loads from file
    with open(load_file, 'r') as f:
        loads = [int(l.strip()) for l in f.readlines()]
    return loads

def main():
    # parse commandline args and get node names
    args = parse_args()
    nodes, _ = parse_ssh_file(args.ssh_comms)
    
    # run the load sweep
    sweep = args.loads is None
    if args.loads is not None:
        loads = read_loads(args.loads)
    else:
        loads = args.sweep

    # set the environment variables for the Docker containers
    if args.restart is not None:
        set_compose_env(nodes, args.compose_file, args.restart, False)

    data, stats = run_loads(nodes, loads, runtime=args.time, threads=args.threads, sweep=sweep, 
                            cooldown=args.cooldown, workload=args.workload, warmup=args.warmup,
                            power=args.power, stats=args.stats, cpufreq=args.cpufreq, restart=args.restart,
                            pin=args.pin)
    
    # dump the data (latencies, etc.) to pickle file
    if not args.no_dump:
        pickle_file_out = args.pickle_file if args.pickle_file is not None else f"load_sweep_{get_datetime(compact=True)}"
        data_dump(data, pickle_file_out, append=args.append)
    else:
        print("skipping data dump...", flush=True)
    
    # dump the stats (power, Docker stats) to pickle file
    if args.stats or args.power or args.cpufreq:      
        data_dump(stats, "stats/" + args.pickle_file + "_STATS", append=args.append)
    
    
if __name__ == "__main__":
    main()