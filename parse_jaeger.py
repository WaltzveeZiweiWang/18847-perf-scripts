from bs4 import BeautifulSoup
import requests
import argparse
import json
from run_setup import get_ip_address
from helpers import *
from tqdm.contrib import tenumerate

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssh_comms", metavar="ssh-comms", type=str, help="text file with ssh commands line by line")
    parser.add_argument("--out-dir", type=str, default=None, help="output directory for json files (will be within outputs/jaeger_dir/")
    parser.add_argument("--html-file", type=str, default="Jaeger UI.html", help="html file to parse")
    parser.add_argument("--sort-by", type=str, default="operationName", help="json key to sort the spans by")
    return parser.parse_args()

def sort_trace(trace: dict, sort_key: str = 'operationName'):
    spans = trace['data'][0]['spans']
    new_span = sorted(spans, key=lambda k: k[sort_key])
    trace['data'][0]['spans'] = new_span
    return trace

def download_json(url, ip_addr, folder_path="", sort_key="operationName"):
    json_url = f"http://{ip_addr}:16686/api/traces/{url[-16::]}?prettyPrint=true"
    session = requests.Session()

    path = url[-16::] + '.json'
    out_file = folder_path + path

    with session.get(json_url, stream=True) as r, open(out_file, 'w') as f:
        trace = sort_trace(r.json(), sort_key=sort_key)
        json.dump(trace, f, indent=4)

def main():
    args = parse_args()
    nodes, _ = parse_ssh_file(args.ssh_comms)
    
    public_ip = get_ip_address(nodes[0])[1]
    
    # Passing the source code to BeautifulSoup to create a BeautifulSoup object for it.
    soup = BeautifulSoup(open(args.html_file), "html.parser")

    # Extracting all the <a> tags into a list.
    tags = soup.find_all('a', {'class': 'ResultItemTitle--item ub-flex-auto'})

    # Get the directory to output the JSON files into
    out_dir = "outputs/jaeger_json/"
    if args.out_dir is not None:
        out_dir = out_dir + args.out_dir + "/"
    p = open_path(out_dir, make_new=True)
    print(f"outputting json files to {p}")
    
    # Extracting URLs from the attribute href in the <a> tags.
    for i, tag in tenumerate(tags):
        link = tag.get('href')
        download_json(link, public_ip, folder_path=p, sort_key=args.sort_by)
    print("done!")

if __name__ == '__main__':
    main()