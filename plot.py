import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import argparse
import pickle
import numpy as np
from helpers import splitlines_file, convert_range, set_range
from scipy.interpolate import make_interp_spline, make_smoothing_spline, PchipInterpolator, interp1d

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("pickle_files", metavar="pickle-files", type=str, nargs='+', help="pickle file(s) with data output")
    parser.add_argument("--mode", "-m", type=str, default='p50', help="plot mode: avg, p50, p99, both")
    parser.add_argument("--labels", "-l", type=str, default=None, help="labels for each file")
    parser.add_argument("--list-file", action="store_true", help="treat first argument as a file with a list of pickle files")
    parser.add_argument("--range", "-r", type=str, default=None, help="range of data to plot")
    parser.add_argument("--label-columns", "-c", type=int, default=3, help="columns to use for labels")
    parser.add_argument("--rotate-markers", action="store_true", help="rotate markers")
    parser.add_argument("--log", nargs=2, type=str, default=("False", "True"), help="log scale for x and y axes")
    parser.add_argument("--interpolate", action="store_true", help="interpolate data")
    parser.add_argument("--hline", type=float, default=None, help="horizontal line")
    parser.add_argument("--vline", type=float, default=None, help="vertical line")
    parser.add_argument("--linewidth", type=float, default=0.75, help="line width")
    parser.add_argument("--markersize", type=float, default=6, help="marker size")
    parser.add_argument("--label-lines", action="store_true", help="label lines instead of markers in legend")
    parser.add_argument("--markeredgewidth", type=float, default=0.7, help="marker edge width")
    parser.add_argument("--markeredgecolor", type=str, default='k', help="marker edge color")
    return parser.parse_args()

def plot_single(xs, ys, color='b', ylabel='Avg. Latency (ms)', marker='o', line='-', data_labels=False, 
                stdevs=None, log=(False, True), interpolate=False, label=None, linewidth=0.75, label_lines=False,
                markersize=6, markeredgewidth=0.7, markeredgecolor='k', zorder=2):
    xscale = 'log' if log[0] else 'linear'
    yscale = 'log' if log[1] else 'linear'
    plt.xscale(xscale)
    plt.yscale(yscale)

    if marker == '':
        marker = 'o'
    if line == '':
        line = '-'
    
    if label is None:
        label = ''
    if interpolate:
        ml = f"{marker}"
    else:
        ml = f"{marker}{line}"

    plt_label = label
    if interpolate and label_lines:
        plt_label = "_nolegend_"
    plt.plot(xs, ys, ml, color=color, markersize=markersize, label=plt_label, 
             markeredgewidth=markeredgewidth, markeredgecolor=markeredgecolor,
             zorder=zorder)
    if interpolate:
        xnew = np.linspace(min(xs), max(xs), 300)
        ys_smooth = PchipInterpolator(xs, ys)(xnew)

        # spl = make_interp_spline(xs, ys, k=3)
        # spl = make_smoothing_spline(xs, ys, lam=0.1)
        # ys_smooth = spl(xnew)

        # plot with no markers
        interp_label = label
        if not label_lines:
            interp_label = "_nolegend_"
        plt.plot(xnew, ys_smooth, f"{line}",color=color, label=interp_label, 
                 linewidth=linewidth, zorder=zorder)
    if stdevs is not None:
        # plot with error bars
        plt.errorbar(xs, ys, yerr=stdevs, color=color)
    plt.xlabel('Input Rate (QPS)')
    plt.ylabel(ylabel)
    
    if not data_labels:
        return
    
    for x,y in zip(xs, ys):

        label = "{:.2f}".format(y)

        plt.annotate(label, 
                    (x,y), 
                    textcoords="offset points", 
                    xytext=(0, 8), 
                    ha='center')

def plot(data, files, mode='normal', labels=None, rate_ranges=None, label_columns=3, 
         rotate_markers=False, colors=None, markers=None, lines=None, log=(False, True),
         interpolate=False, hline=None, vline=None, linewidth=0.75, label_lines=False,
         markersize=6, markeredgewidth=0.7, markeredgecolor='k'):
    # colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'tab:orange', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']
    # list matploblib markers: https://matplotlib.org/3.1.1/api/markers_api.html
    r_markers = ['o', '*', 'x', '^', 's', 'P', '1', '+']
    # assert(len(data) <= len(colors))
    assert(len(files) == len(data))
    
    if colors is not None:
        assert(len(colors) == len(data))
        color = iter(colors)
    else:
        color = iter(plt.cm.rainbow(np.linspace(0, 1, len(data))))
    
    if lines is not None:
        assert(len(lines) == len(data))

    if labels is None:
        labels = [file.strip("outuputs/").strip(".p") for file in files]
    else:
        assert(len(labels) == len(data))

    if hline is not None:
        plt.axhline(y=hline, color='k', linestyle='--', alpha=0.5)
    if vline is not None:
        plt.axvline(x=vline, color='k', linestyle='--', alpha=0.5)
    
    for i, d in enumerate(data):
        c = next(color)
        label = labels[i]
        rates, avgs, p50s, p99s, stdevs = extract_data(d)
        # set zorder so that the first plot is on top
        zorder = len(data) - i
        if rate_ranges is not None:
            rate_range = None
            # if there is only one rate range, use it for all data
            if len(rate_ranges) == 1:
                rate_range = rate_ranges[0]
            else: # otherwise, use the rate range for the corresponding data
                assert(len(rate_ranges) == len(data))
                rate_range = rate_ranges[i]
            rates, [avgs, p50s, p99s, stdevs] = set_range(rate_range, rates, [avgs, p50s, p99s, stdevs])
        stdevs = None
            
        marker = 'o'
        if rotate_markers:
            marker = r_markers[i % len(r_markers)]
        elif markers is not None:
            marker = markers[i]

        line = '-'
        if lines is not None:
            line = lines[i]
        
        plt_data = None
        ylabel = None
        if mode == 'avg':
            plt_data = avgs
            ylabel = 'Mean Latency (ms)'
        elif mode == 'p99':
            plt_data = p99s
            ylabel = 'p99 Latency (ms)'
        elif mode == 'p50':
            plt_data = p50s
            ylabel = 'p50 Latency (ms)'
        else:
            raise ValueError(f"Invalid mode {mode}")
        plot_single(rates, plt_data, color=c, ylabel=ylabel, marker=marker, line=line, 
                    log=log, interpolate=interpolate, label=label, stdevs=stdevs,
                    linewidth=linewidth, label_lines=label_lines, markersize=markersize,
                    markeredgewidth=markeredgewidth, markeredgecolor=markeredgecolor,
                    zorder=zorder)
    # plt.legend(labels)

    # if interpolate:
    #     # change the legend to show marker and interpolated line
    #     handles, labels = plt.gca().get_legend_handles_labels()
    #     for i, h in enumerate(handles):
    #         if isinstance(h, Line2D):
    #             handles[i] = Line2D([0], [0], color=h.get_color(), marker=marker, linestyle=lines[i])
    #     plt.legend(handles, labels, bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
    #                mode="expand", borderaxespad=0, ncol=label_columns)
    # else:
    plt.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
                mode="expand", borderaxespad=0, ncol=label_columns) 
    plt.tight_layout()
    # add space above the legend
    # plt.subplots_adjust(top=0.5)
    
    plt.show()
    
def extract_data(data):
    rates, avgs, p50s, p99s, stdevs = [], [], [], [], []
    for d in data:
        # NOTE: d (for each load) is in the form:
        # (rate, (latency:[avg, stdev, p99, +- stdev], throughput:[avg, stdev, p99, +- stdev], tail-latency:[p50, p75, p90, p99, p99.9, p99.99, p99.999, p100]))
        
        # skip data that was not collected/empty
        if not d[1][0]:
            continue
        rates.append(d[0])
        avgs.append(d[1][0][0])
        p50s.append(d[1][2][0])
        p99s.append(d[1][2][3])
        stdevs.append(d[1][0][1])
    return rates, avgs, p50s, p99s, stdevs

def extract_pickle_data(files):
    data = []
    for p in files:
        with open(p, "rb") as f:
            d = []
            while True:
                try:
                    d += pickle.load(f)
                except EOFError:
                    break
            data.append(d)
    return data

def main():
    args = parse_args()
    pickle_files = args.pickle_files
    if args.list_file:
        pickle_files = splitlines_file(args.pickle_files[0])
    
    labels = None
    colors = None
    markers = None
    lines = None
    rate_ranges = None

    if args.range is not None:
        rate_ranges = [convert_range(args.range)]
    if args.labels is not None:
        labels = splitlines_file(args.labels)
        if all(["," in l for l in labels]):
            colors = [l.split(",")[1] for l in labels]
            # check if all of them have a marker
            if all([len(l.split(",")) >= 3 for l in labels]):
                markers = [l.split(",")[2] for l in labels]
            if all([len(l.split(",")) >= 4 for l in labels]):
                lines = [l.split(",")[3] for l in labels]
            if all([len(l.split(",")) >= 5 for l in labels]):
                ranges = [l.split(",")[4] for l in labels]
                if all([r == '' for r in ranges]):
                    ranges = [args.range]
                else:
                    for i, r in enumerate(ranges):
                        if r == '':
                            ranges[i] = "0:"
                rate_ranges = [convert_range(r) for r in ranges]
            labels = [l.split(",")[0] for l in labels]
    
    # check if element of colors is an int
    if colors is not None:
        if all([c.isdigit() for c in colors]):
            colors = [int(c) for c in colors]
            # get number of unique colors
            unique_colors = set(colors)
            unique_colors = plt.cm.rainbow(np.linspace(0, 1, len(unique_colors)))
            # get unique int to color dict
            color_dict = {c: unique_colors[i] for i, c in enumerate(set(colors))}
            # replace int with color
            colors = [color_dict[c] for c in colors]

    data = extract_pickle_data(pickle_files)
    log = [True if x == "True" else False for x in args.log]
    plot(data, pickle_files, mode=args.mode, labels=labels, rate_ranges=rate_ranges, 
         label_columns=args.label_columns, rotate_markers=args.rotate_markers, colors=colors,
         markers=markers, log=log, lines=lines, interpolate=args.interpolate,
         hline=args.hline, vline=args.vline, linewidth=args.linewidth,
         label_lines=args.label_lines, markersize=args.markersize,
         markeredgewidth=args.markeredgewidth, markeredgecolor=args.markeredgecolor)

if __name__ == "__main__":
    main()