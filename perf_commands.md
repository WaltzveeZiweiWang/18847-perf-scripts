# find pid
```
sudo docker container ls
sudo docker top
```

# record cpu cycles
```
sudo perf record -j any_call,any_ret -p <PID> -- ./wrk -D exp -t 2 -c100 -d30s -R2800 -L -s ./scripts/social-network/compose-post.lua http://127.0.0.1:8080/index.html > ~/record.txt

sudo perf report --pid <PID> > ~/report.txt

```

# record lbr
```
sudo perf record -p <PID> --call-graph lbr -- ./wrk -D exp -t 2 -c100 -d30s -R2800 -L -s ./scripts/social-network/compose-post.lua http://127.0.0.1:8080/index.html > ~/record-lbr.txt

sudo perf report --pid <PID> > ~/report-lbr.txt

```

# Generate FlameGraph
```
git clone https://github.com/brendangregg/FlameGraph.git
sudo perf script | ~/FlameGraph/stackcollapse-perf.pl | ~/FlameGraph/flamegraph.pl > ~/output.svg

```
