# DeathStarBench Profiling Scripts

## Getting Started
First just clone this repository locally using `git clone`.

For installing dependencies, just do

    pip install -r requirements.txt

First list all the ssh commands to use to log into each node into a text file called "ssh_commands.txt" (one per line). If copying and pasting from CloudLab, run this to strip out the unnecessary information:

    python3 strip_commands.py ssh_commands.txt

For more information on using CloudLab (if this is what you're using to get a set of remote nodes), see here: [CloudLab Guide](https://docs.google.com/document/d/1GrKCDhDhn1kJt16YAqBLqeadVqiVPahB7FoA6ZU73Xs/edit?usp=sharing).

## Workflow

You should be able to follow along with the example commands on a local machine that is installed with Python 3+. I suggest using a virtual environment. All the commands will run ssh remote commands to either the mater or the worker nodes. Suggested workflow is as follows (read below for descriptions of each script involved and various flags that can be used to customize your workflow):

1. Setup the nodes and specify service name (create a swarm, setup Jaeger, configure json etc.):

        python3 run_setup.py ssh_commands.txt socialNetwork

2. (If necessary - as the setup will default to let Docker place services how it wants to, so if no specific setup necessary, skip this step). Update the swarm to place certain microservices on certain nodes, pin microservices to CPUS, etc. as defined in one of the given csv files or your own custom one in the `env_csvs` directory:

        python3 update_swarm.py --csv-file env.csv ssh_commands.txt

    This command will just do placement, for pinning, an example command:

        python3 update_swarm.py --csv-file env_pin_single_cpu.csv --pin ssh_commands.txt
    
    This command will do placement and upload a customized copy of docker compose file other than default
    `docker-compose-swarm.yml` to the master node:

        python3 update_swarm.py ssh_commands.txt --pin --csv-file env_pin_single_cpu.csv --compose-file docker-compose-swarm-hotelReservation.yml

3. Run the workload and perform a load sweep. You can either define a constant start, step, stop to sweep over request rate values, or you can put specific loads into a text file (separated by newline) where each one will run. The suggested workload setup is: duration of 120 seconds, warmup of 30 seconds, cooldown of 20 seconds. An example of this is as follows:

        python3 run_workload.py --pickle-file sweep_d120s_w30_c20 --time 120 --warmup 30 --cooldown 20 ssh_commands.txt

4. Plot load sweep data like so (can also supply multiple pickle files to plot them at the same time):

        python3 plot.py outputs/sweep_d120s_w30_c20.p

5. (Only do this if you want per-microservice information as opposed to end-to-end latencies). NOTE: this doesn't work well with load sweeps, so to do this, run under one load and then get the traces, don't sweep over multiple loads. Go to the Jaeger web UI page (this URL is printed to the terminal and also opened automatically in a browser in step 1). Query to show all traces for the previous run (at a constant load) - so show 1000 of the last traces - and then download the HTML of the page (should be `Jaeger UI.html` by default) into the working directory. Then run something like:

        python3 parse_jaeger.py --out-dir load_jsons ssh_commands.txt

6. (Again only if doing per-microservice Jaeger stuff). Plot Jaeger information. One way to do this is like so:

        python3 plot_jaeger.py --raw outputs/jaeger_json/load_jsons

## Running Workloads
Running a workload will perform a sweep - this can be tuned with command line arguments. The results (latencies from different input loads) will be serialized to pickle files, written to a created folder `output/`:

    python3 run_workload.py --pickle-file load_sweep ssh_commands.txt

You can list as many of the output pickle files as you want - and they will all be plotted together.

You can also specify exact loads to sweep through in a text file (separated by new lines), which can be passed into `run_workload.py` through the `--load` flag. 

For any of the Python scripts, run with `--help` to see what the options are.

## Plotting
Once a workload is run, the results can then be read and processed using `plot.py` as follows:

    python3 plot.py outputs/load_sweep.p

Where `outputs/load_sweep.p` is the pickle file with the output information.

## Updating Docker Swarm
Use the `update_swarm.py` script to make updates to things like node placements, CPU pinnings, etc. These can be specified in csv files (examples can be found in the repository). Then updates to an existing swarm can be made like so:

    python3 update_swarm.py --csv-file env.csv ssh_commands.txt

Or with csv files that define CPU/socket pinning placements (not the --pin flag):

    python3 update_swarm.py --csv-file env_pin_single_cpu.csv --pin ssh_commands.txt

Or with a customized docker compose swarm file with cpu pinning placements:

    python3 update_swarm.py ssh_commands.txt --pin --csv-file env_pin_single_cpu.csv --compose-file docker-compose-swarm-hotelReservation.yml
For customized compose file, make sure it corresponds to current service name which was specified when running `run_setup.py`.

To check whether the pinning worked, you'll (currently) have to run `docker inspect` on each node and look for the `CPUSet` to check whether the proper CPUs were pinned. 

## Viewing Docker Service Information
It is often useful to view which services are running on which nodes, whether they are running properly, what are the service constraints on the nodes, etc. To view this in a table, simply run:

    python3 docker_services.py ssh_commands.txt

## Parsing Jaeger Traces
Once you run a load (ideally you would only run one load before trying to parse the jaeger traces), you should go to the Jaeger web page that automatically opens (and is printed to the terminal) during setup. Then put in how many results you want (something like 1000 is reasonable) and then produce the search. Then download the HTML of the page and save it within the working directory. Then you can run `parse_jaeger.py` with the `--out-dir` to set the output directory to store all the JSON files with the Jaeger traces:

    python3 parse_jaeger.py --out-dir jaeger_jsons ssh_commands.txt

Then once this is done, you can use the `plot_jaeger.py` scripts to plot the results.

    python3 plot_jaeger.py outputs/jaeger_json/jaeger_jsons

## Adding New Services
Service names and commands to run each service are defined in `config.json`. For service names and commands for running workload generator, please refer to [DeathStarBench Repo](https://github.com/delimitrou/DeathStarBench/tree/master). 

To add a new service, please append the following to `services` list in `config.json`:

    {
        "service_name": "<service name specified in DSB repo>", 
        "service_workloads": [
            {
                "workload_type": "<type of workload>", 
                "workload_cmd": "<command for generating this type of workload>"
            }
        ]
    }

To pin cpus to the new service, add new cpu pinning csv files in `env_csvs` directory and create a customized compose file similar to `docker-compose-swarm.yml` and `docker-compose-swarm-hotelReservation.yml`.
