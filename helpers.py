import subprocess
import asyncio
from os.path import exists
from pathlib import Path
import time
import pickle
import json
import numpy as np

NO_KEY = "-o \"StrictHostKeyChecking no\""
CONFIG_JSON_PATH = "config.json"

def get_datetime(compact=True):
    if not compact:
        return time.strftime("%d-%m-%Y_%H:%M:%S", time.localtime())
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())

def finditem(obj, key):
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v,dict):
            item = finditem(v, key)
            if item is not None:
                return item

def get_ssh_cmd(node, cmd, background=False, cd="~"):
    if background:
        # run command in background with nohup and redirect stdout and stderr to /dev/null and return pid
        return f"ssh -i /users/waltzvee/id_rsa {NO_KEY} {node} \"cd {cd}; sh -c 'nohup {cmd} > /dev/null 2>&1 &'\""
    return f"ssh -i /users/waltzvee/id_rsa {NO_KEY} {node} \"cd {cd}; {cmd}\""

def run_ssh_cmd(node, cmd, stderr=True, background=False, cd="~", check=False):
    cp = subprocess.run(get_ssh_cmd(node, cmd, background=background, cd=cd), 
                        shell=True, 
                        capture_output=True)
    # only print if non-zero exit code or if stderr is True
    if stderr or cp.returncode != 0:
        stderr_out = cp.stderr.decode().strip().strip("\n")
        if stderr_out:
            print(stderr_out, flush=True)
    if check:
        cp.check_returncode()
    return cp.stdout.decode().strip()

def get_scp_cmd(node, to_cpy, path="~/", exec=False):
    to_cpy = find_file(to_cpy, script=True)
    assert(exists(to_cpy))
    cmd = f"scp {NO_KEY} {to_cpy} {node}:{path}"
    file_name = Path(to_cpy).name
    if exec:
        cmd += " && " + get_ssh_cmd(node, f"sudo chmod +x {path}{file_name}")
    return cmd

def run_scp_cmd(node, to_cpy, path="~/", stderr=True, check=False, exec=False):
    cp = subprocess.run(get_scp_cmd(node, to_cpy, path=path, exec=exec), 
                        shell=True, 
                        capture_output=True)
    if stderr or check:
        stderr_out = cp.stderr.decode("utf-8").strip()
        if stderr_out and stderr_out != "\n":
            print(cp.stderr.decode("utf-8").strip(), flush=True)
    if check:
        cp.check_returncode()
    return cp.stdout.decode("utf-8").strip()

async def run(cmd, print_stderr=True):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()

    print(f'[{cmd!r} exited with {proc.returncode}]', flush=True)
    if stderr and print_stderr:
        print(f'[stderr]\n{stderr}', flush=True)
    return stdout, stderr, proc.returncode
        
def get_scp_cmds(nodes, to_cpy, exec=False, path="~/"):
    print(f"copying '{to_cpy}' to node(s)...", flush=True)
    return [get_scp_cmd(node, to_cpy, path=path, exec=exec) for node in nodes]

def get_ssh_cmds(nodes, cmd, background=False, cd="~"):
    print(f"running '{cmd}' on node(s)...", flush=True)
    return [get_ssh_cmd(node, cmd, background=background, cd=cd) for node in nodes]
        
async def run_remote_async(nodes, cmd, scp=False, print_stderr=True, background=False, 
                           cd="~", cmd_list=False, exec=False, path="~/", check=False):
    if cmd_list:
        assert(isinstance(cmd, list))
        assert(len(nodes) == len(cmd))
    if scp:
        if not cmd_list:
            cmds = get_scp_cmds(nodes, cmd, exec=exec, path=path)
        else:
            cmds = [get_scp_cmd(node, cmd, exec=exec, path=path) for node, cmd in zip(nodes, cmd)]
    else:
        if not cmd_list:
            cmds = get_ssh_cmds(nodes, cmd, background=background, cd=cd)
        else:
            cmds = [get_ssh_cmd(node, cmd, background=background, cd=cd) for node, cmd in zip(nodes, cmd)]
    
    output = await asyncio.gather(*[run(cmd, print_stderr=print_stderr) for cmd in cmds])

    if check:
        for o in output:
            if o[2] != 0:
                print(f"Error in node {nodes[output.index(o)]} with command {cmds[output.index(o)]}", flush=True)
                print(f"Error: {o[1]}", flush=True)
    
    return output
        
def parse_ssh_file(ssh_file):
    nodes = []
    ssh_commands = []
    with open(ssh_file, "r") as f:
        for line in f:
            # ignore empty liness
            line = line.strip()
            if not line:
                continue
            # append node to list of nodes
            nodes.append(line.split()[-1])
            ssh_commands.append(line)
    return nodes, ssh_commands

def file_exists(file):
    return exists(file)

def get_core_counts(nodes):
    return [int(run_ssh_cmd(node, "sudo nproc").strip()) for node in nodes]

def open_path(path, file=False, make_new=False):
    p = Path(path)
    if file:
        p = p.parent
    # check if path exists
    if p.exists() and make_new:
        # update name of last dir with current time
        curr_time = time.strftime("%Y%m%d-%H%M%S")
        p = p.parent / f"{p.name}_{curr_time}"
    # create path
    p.mkdir(parents=True, exist_ok=True)
    # return path as string, if dir return with trailing slash
    return str(p) + "/" if not file else str(p)

def convert_range(range_str):
    rate_range = range_str.split(":")
    assert(len(rate_range) == 2)
    if rate_range[0] == '':
        rate_range[0] = 0
    if rate_range[1] == '':
        rate_range[1] = 10000000000
    return range(*[int(x) for x in rate_range])

def set_range(rate_range, rates, data):
    first_ind, last_ind = -1, -1
    for j, r in enumerate(rates):
        if r >= rate_range.start and first_ind == -1:
            first_ind = j
        if r > rate_range.stop:
            last_ind = j
            break
    if last_ind == -1:
        last_ind = len(rates)
    if first_ind == -1:
        first_ind = 0
    rates = np.array(rates[first_ind:last_ind])
    for i, d in enumerate(data):
        data[i] = np.array(d[first_ind:last_ind])
    return rates, data
    
# recursively sort dict
def sort_dict(d: dict):
    return {k: sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(d.items())}

def find_file(file, env_csv=False, script=False):
    ex = file_exists(file)
    if ex:
        return file

    if env_csv and file_exists(f"env_csvs/{file}"):
        return f"env_csvs/{file}"
    elif script and file_exists(f"scripts/{file}"):
        return f"scripts/{file}"
    else:
        raise FileNotFoundError(f"file '{file}' not found")
    
def data_dump(data, out_file, append=False):
    out_file.strip(".p")
    out_file.lstrip("/")
    out_file = f"outputs/{get_current_service_name()}/{out_file}"
    if file_exists(out_file + ".p") and not append:
        timestr = time.strftime("%Y%m%d-%H%M%S")
        out_file += "_" + timestr
    out_file += ".p"
    open_path(out_file, file=True)
    pickle.dump(data, open(out_file, "ab"))
    print(f"dumped data to '{out_file}'")

def data_load(in_file, print_obj=False):
    in_file = find_file(in_file)
    obj = pickle.load(open(in_file, "rb"))
    if print_obj:
        print(obj)
    return obj
    
def splitlines_file(file, strip=True, ignore_empty=True, ignore_start=None):
    if file is None:
        return None
    lines = []
    with open(file, "r") as f:
        for line in f:
            if strip:
                line = line.strip()
            if ignore_empty and not line:
                continue
            if ignore_start is not None and line.startswith(ignore_start):
                continue
            lines.append(line)
    return lines

    
def load_json(file):
    if file is None:
        return None
    with open(file, "r") as f:
        config = json.load(f)
        return config

def update_json(file, config):
    with open(file, "w") as f:
        json.dump(config, f, indent=4, separators=(", ", ": "))

#return service config if service_name matches existing service names
def find_service(service_name):
    config = load_json(CONFIG_JSON_PATH)
    for service in config["services"]:
        if service["service_name"].startswith(service_name):
            return service
    return None

def update_current_service(service_name):
    config = load_json(CONFIG_JSON_PATH)
    config["current_service"] = service_name
    update_json(CONFIG_JSON_PATH, config)

def get_current_service_name():
    config = load_json(CONFIG_JSON_PATH)
    return config["current_service"]

def get_current_service_workloads():
    return find_service(get_current_service_name())["service_workloads"]

def get_compose_file_name():
    return f"docker-compose-swarm-{get_current_service_name()}.yml"




 