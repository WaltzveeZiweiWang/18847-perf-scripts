from helpers import convert_range
import pickle
import matplotlib.pyplot as plt
import argparse
import pandas as pd

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("stats_files", metavar="stats-files", type=str, nargs='+', help="stats files")
    parser.add_argument("--to-plot", "-p", type=str, default=None, help="type of data to plot")
    parser.add_argument("--range", "-r", type=str, default=None, help="range of data to plot")
    return parser.parse_args()

def unpack_stats(file):
    with open(file, 'rb') as f:
        print(f"loading {file}")
        # data is in the form:
        # data = [stats_dict, stats_dict, ...] - one per load
        # stats_dict = (load, ([node0:stats,...,nodeN:stats]), [node0:rapl,...,nodeN:rapl])
        # stats is a list of dicts, one per measurement
        # rapl is a list of dicts, one dict per package per measurement
        data = pickle.load(f)
        loads = [d[0] for d in data]
        stats_data = [d[1][0] for d in data]
        rapl_data = [d[1][1] for d in data]
        if len(data[0][1]) > 2:
            cpufreq_data = [d[1][2] for d in data]
        # # check that the data is in the expected format
        # assert(isinstance(stats_data, list) and 
        #        isinstance(stats_data[0], list) and
        #        isinstance(stats_data[0][0], list) and
        #        isinstance(stats_data[0][0][0], dict))
        # assert(isinstance(rapl_data, list) and 
        #        isinstance(rapl_data[0], list) and 
        #        isinstance(rapl_data[0][0], dict))

        assert(len(loads) == len(stats_data) == len(rapl_data)) # each is a list per load
        # assert(len(stats_data[0]) == len(rapl_data[0])) # each is a list per node

    # check if all lists are empty in either
    no_stats_data = all(not stats_load for stats_load in stats_data)
    no_rapl_data = all(not rapl_load for rapl_load in rapl_data)
    no_cpufreq_data = all(not cpufreq_load for cpufreq_load in cpufreq_data)
    
    # add node number and load to each stats dict
    stats_dicts, rapl_dicts, cpufreq_dicts = [], [], []
    if not no_stats_data:
        # loop through each load
        for i, stats_load in enumerate(stats_data):
            # loop through each node
            for j, stats_node in enumerate(stats_load):
                if stats_node is None:
                    continue
                # loop through each measurement
                for k, stats_measurement in enumerate(stats_node):
                    if not stats_measurement or stats_measurement is None:
                        continue
                    stats_measurement['Node'] = j
                    stats_measurement['Load'] = loads[i]
                    stats_measurement['Measurement'] = k
                    stats_dicts.append(stats_measurement)
    if not no_rapl_data:
        # loop through each load
        for i, rapl_load in enumerate(rapl_data):
            # loop through each node (one measurement per node)
            for j, rapl_node in enumerate(rapl_load):
                if rapl_node is None:
                    continue
                rapl_node['Node'] = j
                rapl_node['Load'] = loads[i]
                rapl_dicts.append(rapl_node)
    if not no_cpufreq_data:
        # loop through each load
        for i, cpufreq_load in enumerate(cpufreq_data):
            # loop through each node (one measurement per node)
            for j, cpufreq_node in enumerate(cpufreq_load):
                if cpufreq_node is None:
                    continue
                for k, cpufreq_measurement in enumerate(cpufreq_node):
                    cpufreq_dict = {}
                    # cpufreq_node is a list of lists
                    # list for each second, then a list for each core
                    cpufreq_dict['Node'] = j
                    cpufreq_dict['Load'] = loads[i]
                    cpufreq_dict['Second'] = k
                    for l, core in enumerate(cpufreq_measurement):
                        cpufreq_dict[f'core{l}'] = core
                    cpufreq_dicts.append(cpufreq_dict)
        
    return loads, stats_dicts, rapl_dicts, cpufreq_dicts

def stats_to_dfs(file):
    loads, stats_dicts, rapl_dicts, cpufreq_dicts = unpack_stats(file)
    rapl_df = pd.DataFrame.from_dict(rapl_dicts) if rapl_dicts else None
    stats_df = pd.DataFrame.from_dict(stats_dicts) if stats_dicts else None
    cpufreq_df = pd.DataFrame.from_dict(cpufreq_dicts) if cpufreq_dicts else None

    if rapl_df is not None:
        # convert load to int
        rapl_df['Load'] = rapl_df['Load'].astype(float)
        # convert all rapl values to floats
        rapl_df = rapl_df.astype(float)
        # find columns of the form cpuX_package_joules
        package_cols = [col for col in rapl_df.columns if 'package_joules' in col]
        # calculate power for each package
        for i, col in enumerate(package_cols):
            rapl_df[f'cpu{i}_package_power'] = rapl_df[col] / rapl_df['duration_seconds']

    if stats_df is not None:
        # convert load to int
        stats_df['Load'] = stats_df['Load'].astype(float)
        # convert the cpu percent (of form '0.0%') to a float
        stats_df['CPUPerc'] = stats_df['CPUPerc'].str.rstrip('%').astype('float') / 100.0
        # convert the memory percent (of form '0.0%') to a float
        stats_df['MemPerc'] = stats_df['MemPerc'].str.rstrip('%').astype('float') / 100.0
        # split network stats (NetIO and BlockIO) into rx and tx
        # Standardize to bytes: kB=1024B, MB=1048576B, GiB=1073741824B, TiB=1099511627776B
        units = {'kB': '*1024', 'MB': '*1048576', 'MiB': '*1048576', 'GB': '*1073741824', 'GiB': '*1073741824', 
                 'TB': '*1099511627776', 'TiB': '*1099511627776'}
        split_stats = ['NetIO_rx', 'NetIO_tx', 'BlockIO_rx', 'BlockIO_tx', 'MemUsage_used', 'MemUsage_total']
        stats_df[['NetIO_rx', 'NetIO_tx']] = stats_df['NetIO'].str.split(' / ', expand=True)
        stats_df[['BlockIO_rx', 'BlockIO_tx']] = stats_df['BlockIO'].str.split(' / ', expand=True)
        stats_df[['MemUsage_used', 'MemUsage_total']] = stats_df['MemUsage'].str.split(' / ', expand=True)
        stats_df[split_stats] = stats_df[split_stats].replace(units, regex=True).replace({'B': ''}, regex=True)
        # loop through each value and eval it
        for i, row in stats_df.iterrows():
            for col in split_stats:
                # replace the value with the evaluated value (if not NaN)
                if not pd.isna(stats_df.at[i, col]):
                    stats_df.at[i, col] = eval(stats_df.at[i, col])
        stats_df[split_stats] = stats_df[split_stats].astype(float)
        # remove the NetIO and BlockIO columns
        stats_df = stats_df.drop(columns=['NetIO', 'BlockIO', 'MemUsage'])

    if cpufreq_df is not None:
        # convert load to int
        cpufreq_df['Load'] = cpufreq_df['Load'].astype(float)
        # convert second to int
        cpufreq_df['Second'] = cpufreq_df['Second'].astype(float)
        # convert all cpufreq values to floats
        cpufreq_df = cpufreq_df.astype(float)
        # get all column names that are of the form coreX
        core_cols = [col for col in cpufreq_df.columns if 'core' in col]
        # compute the mean of each core
        cpufreq_df['Mean'] = cpufreq_df[core_cols].mean(axis=1)
        # compute the min of each core
        cpufreq_df['Min'] = cpufreq_df[core_cols].min(axis=1)
        # compute the max of each core
        cpufreq_df['Max'] = cpufreq_df[core_cols].max(axis=1)
    
    return loads, rapl_df, stats_df, cpufreq_df

# select is a tuple of the form (column, value)
def get_means(df, select=None, groupby=None):
    if df is None:
        print("No stats")
        return
    # only select by the select
    if select is not None:
        assert(len(select == 2))
        df = df[df[select[0]] == select[1]]
    # group by the node
    if groupby is not None:
        df = df.groupby(groupby)
    # get the mean of each column
    df = df.mean()
    print(df)
    return df
        
def main():
    args = parse_args()
    if args.range is not None:
        rate_ranges = [convert_range(args.range)]
    mean_rapl_dfs = []
    mean_stats_dfs = []
    mean_cpufreq_dfs = []
    for i in range(len(args.stats_files)):
        loads, rapl_df, stats_df, cpufreq_df = stats_to_dfs(args.stats_files[i])
        # mean_rapl_df = get_means(rapl_df, select=None, groupby='Load')
        # mean_rapl_dfs.append(mean_rapl_df)
        # group by node number
        mean_rapl_df = get_means(rapl_df, select=None, groupby='Node')
        mean_rapl_dfs.append(mean_rapl_df)
        mean_stats_df = get_means(stats_df, select=None, groupby='Load')
        mean_stats_dfs.append(mean_stats_df)
        mean_cpufreq_df = get_means(cpufreq_df, select=None, groupby='Load')
        mean_cpufreq_dfs.append(mean_cpufreq_df)
    
    if args.to_plot == 'cpufreq':
        # loop through cpufreq_dfs and plot the mean, max, and min for loads for each file
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
        load_max = -1
        for i in range(len(mean_cpufreq_dfs)):
            # plt.plot(mean_cpufreq_dfs[i].loc[:loads[i], 'Mean'], label='Mean', marker='o')
            if load_max -1:
                load_max = mean_cpufreq_df.index.max()
            color = colors[i % len(colors)]
            plt.plot(mean_cpufreq_dfs[i].loc[:load_max, 'Min'], label=f'Min {args.stats_files[i]}', marker='o', color=color, linestyle='-')
            plt.plot(mean_cpufreq_dfs[i].loc[:load_max, 'Max'], label=f'Max {args.stats_files[i]}', marker='o', color=color, linestyle='--')
            # plt.plot(mean_cpufreq_dfs[i].loc[:loads[i], 'Median'], label='Median', marker='o')
            plt.legend()
            plt.xlabel('Load')
            plt.ylabel('Frequency (MHz)')
            plt.title(f'CPU Frequency for {args.stats_files[i]}')
        plt.show()
    elif args.to_plot == 'rapl':
        # plot index (load) vs. cpu0_package_joules for all of them on one plot
        labels = ['Ivy Bridge (2012)', 'Haswell (2013)']
        df = pd.DataFrame()
        for i in range(len(mean_rapl_dfs)):
            df = pd.concat([df, mean_rapl_dfs[i]['cpu0_package_joules']], axis=1)

        # load_max = -1
        # for i in range(len(mean_stats_dfs)):
        #     # only plot up to load_max
        #     if load_max == -1:
        #         load_max = mean_stats_dfs[i].index.max()
        #     plt.plot(mean_rapl_dfs[i].loc[:load_max, 'cpu0_package_power'], label=labels[i], marker='o')
        #     # plt.plot(mean_stats_dfs[i].loc[:load_max, 'NetIO_tx'], label=labels[i], marker='o')
        # plt.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
        #         mode="expand", borderaxespad=0, ncol=3)
        # plt.xlabel('Load')
        # plt.ylabel('Power (W)')
        # plt.ylabel('CPU Utilization')
        # plt.ylabel('Memory Utilization (bytes)')
        # plt.ylabel('Block IO read (bytes)')
        # plt.ylabel('Block IO written (bytes)')
        # plt.ylabel('Network IO received (bytes)')
        plt.ylabel('Network IO sent (bytes)')
        plt.show()

if __name__ == "__main__":
    main()