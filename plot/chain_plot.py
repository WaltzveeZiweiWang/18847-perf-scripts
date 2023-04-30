import pandas as pd
import matplotlib.pyplot as plt

data = {"A":[10, 8, 7],
        "B":[3, 6, 5],
        "C":[2, 4, 1]}

df = pd.DataFrame(data, columns=['A', 'B', 'C'])

fig = plt.figure(figsize=(15,10))
# ax = plt.gca()
width = 0.35
ax = fig.add_subplot(1,1,1)
rects1 = ax.bar(["ChainA","ChainB", "ChainC"], df.A, width)
rects2 = ax.bar(["ChainA","ChainB", "ChainC"], df.B, width, bottom=df.A)
rects3 = ax.bar(["ChainA","ChainB", "ChainC"], df.C, width, bottom=df.B+df.A)
chains = ["A", "B", "C"]
for chain, r1, r2, r3, a, b, c in zip(chains, rects1, rects2, rects3, df.A, df.B, df.C):
    h1 = r1.get_height()
    h2 = r2.get_height()
    h3 = r3.get_height()
    ax.annotate(chain + '1  ' +'{}%'.format(a),
                    xy=(r1.get_x() + r1.get_width() / 3, h1/3),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha='center', va='bottom')
    ax.annotate(chain + '2  ' +'{}%'.format(b),
                    xy=(r2.get_x() + r2.get_width() / 3, h1+h2/3),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha='center', va='bottom')
    ax.annotate(chain + '3  ' +'{}%'.format(c),
                xy=(r3.get_x() + r3.get_width() / 3, h1+h2+h3 / 3),
                xytext=(0, 0),
                textcoords="offset points",
                ha='center', va='bottom')

ax.plot()
plt.show()
fig.savefig("chain.pdf")