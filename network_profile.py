import argparse
from helpers import *
import jc
import json

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", metavar="ssh-comms", type=str, help='file with ssh commands to run iperf3 server on each host')
    parser.add_argument("--out-dir", type=str, default=None, help="output directory for json files (will be within outputs/iperf3_dir/")
    parser.add_argument("--duration", type=int, default=10, help="duration of iperf3 test in seconds")
    parser.add_argument("--interval", type=int, default=1, help="interval of iperf3 test in seconds")
    parser.add_argument("--port", type=int, default=5201, help="port to run iperf3 server on")
    return parser.parse_args()

def server_command(port):
    return f"iperf3 -s -p {port}"

def client_command(port, ip_addr, duration, interval):
    return f"iperf3 -c {ip_addr} -p {port} -i {interval} -t {duration} --json"

def ping_command(ip_addr, count=10):
    return f"ping -c {count} {ip_addr}"

def parse_ping(ping_out):
    return jc.parse('ping', ping_out)

def main():
    args = parse_args()
    nodes, _ = parse_ssh_file(args.ssh_comms)
    
    # master node is the first node in the list
    master_node = nodes[0]
    master_ip = "10.10.1.1"

    # run iperf3 server on master node
    print(f"Running iperf3 server on {master_node} on port {args.port}", flush=True)
    run_ssh_cmd(master_node, server_command(args.port), background=True)

    # run iperf3 client on all other nodes
    json_outs = []
    for node in nodes[1:]:
        print(f"Running iperf3 client on {node} to {master_node} on port {args.port}", flush=True)
        json_out = run_ssh_cmd(node, client_command(args.port, master_ip, args.duration, args.interval))
        json_outs.append(json.loads(json_out))
    
    for json_out in json_outs:
        # print the average throughput
        print(f"Average throughput: {json_out['end']['sum_received']['bits_per_second'] / 1e9} Gbps", flush=True)
    
    # get ping times
    ping_times = []
    for node in nodes[1:]:
        print(f"Running ping on {node} to {master_node}", flush=True)
        ping_out = run_ssh_cmd(node, ping_command(master_ip))
        ping_times.append(parse_ping(ping_out))
    
    for ping_time in ping_times:
        print(f"Average ping time: {ping_time['round_trip_ms_avg']} ms", flush=True)
    

if __name__ == '__main__':
    main()
