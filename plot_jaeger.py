import os
import json
import matplotlib.pyplot as plt
import argparse
import numpy as np
import pandas as pd
from prettytable import PrettyTable
from helpers import splitlines_file

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_dirs", metavar="json-dirs", type=str, nargs='+', help="directory with json files")
    parser.add_argument("--histogram", action="store_true", help="plot histogram of latencies")
    parser.add_argument("--raw", action="store_true", help="raw latencies")
    parser.add_argument("--labels", "-l", type=str, default=None, help="labels for each directory in text file")
    parser.add_argument("--filter", "-f", type=str, default=None, help="text file with services to include (filter out everything else), one service per line")
    return parser.parse_args()

def get_json_files(dir):
    return [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f)) and f.endswith(".json")]

def plot_histogram(dir):
    service_latencies = get_latencies(dir)
    
    for service in service_latencies:
        plt.hist(service_latencies[service], bins=10)
        plt.title(service)
        plt.show()
        
def get_latencies(dir, mean=True):
    # loop through all json files in directory
    if not dir.endswith("/"):
        dir += "/"
    files = get_json_files(dir)
    service_durations = {}
    for file in files:
        with open(dir + file, 'r') as f:
            try:
                data = json.load(f)
            except:
                print(f"error loading {file}")
                continue
            spans = data['data'][0]['spans']
            for span in spans:
                service = span['operationName']
                if service not in service_durations:
                    service_durations[service] = []
                service_durations[service].append(span['duration'])
    if mean:
        service_durations = {service: np.mean(durations) for service, durations in service_durations.items()}
    return service_durations
            
        
def compare_latencies(dirs, normalize=False, print_table=True, labels=None, services=None):
    df = pd.DataFrame()
    for i, dir in enumerate(dirs):
        print(f"getting latencies for {dir}")
        service_latencies = get_latencies(dir)
        service_latencies['dir'] = dir
        df = pd.concat([df, pd.DataFrame(service_latencies, index=[i])])
    
    # make dir the first column
    df = df[['dir'] + [col for col in df.columns if col != 'dir']]
    # use all columns except for dir - each row is a microservice, each column is a directory
    df_transposed = df[[col for col in df.columns if col != 'dir']].transpose()
    # units are microseconds, convert to milliseconds
    df_transposed = df_transposed / 1000
        
    if print_table:
        t = PrettyTable()
        # use all columns except for dir
        t.field_names = ['microservice'] + df_transposed.columns.tolist()
        # add values rounded to three decimal points
        rows = [[round(val, 3) for val in row] for row in df_transposed.values]
        for i, row in enumerate(rows):
            t.add_row([df_transposed.index[i]] + row)
        print(t)
    
    title = 'Avg. Latency (ms)'
    if normalize:
        row_maxes = df_transposed.max(axis=1)
        df_transposed = df_transposed.div(row_maxes, axis=0)
        # get the reciprocal
        df_transposed = 1 / df_transposed
        title = 'Normalized Avg. Latency (speedup - higher=better)'
    
    if services is not None:
        df_transposed = df_transposed.loc[services]

    fig, ax = plt.subplots(figsize=(10, 5))
    df_transposed.plot(kind='bar', ax=ax, width=0.8)
    # set legend labels to directory names
    if labels is not None:
        ax.legend(labels)
    else:
        ax.legend(df['dir'])
    ax.set_ylabel(title)
    ax.set_xlabel('Microservice')
    ax.set_title('Latency by Microservice')
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.5)
    plt.show()
        
def main():
    args = parse_args()
    
    if args.histogram:
        plot_histogram(args.json_dirs[0])
        return
    
    if args.filter is not None:
        services = splitlines_file(args.filter)
    
    compare_latencies(args.json_dirs, normalize=not args.raw, labels=splitlines_file(args.labels),
                      services=services)

if __name__ == "__main__":
    main()