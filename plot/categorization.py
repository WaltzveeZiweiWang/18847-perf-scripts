import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv("report_with_type.csv")
df_filtered = df[["Overhead", "Source_Symbol", "function_name", "type"]].iloc[0:438]

df_filtered["Overhead"] = df_filtered["Overhead"].str.rstrip('%').astype('float')

df_groupby = df_filtered[["Overhead", "type"]].groupby(["type"]).sum()

df_groupby_only_tax = df_groupby[~df_groupby.index.isin(["none of above", "unknown"])]
print(df_groupby_only_tax)

plt.rcParams.update({'font.size': 7})
df_groupby_only_tax.plot(kind="pie", y="Overhead", autopct='%1.1f%%', legend=False)
plt.savefig("pie.pdf")
plt.show()

#
df_groupby_function = df_filtered[["Overhead", "function_name"]].groupby(["function_name"]).sum()
df_groupby_function_sorted = df_groupby_function.sort_values(by=["Overhead"], ascending=False)
# df_groupby_function_sorted_top10 = df_groupby_function_sorted.iloc[0:10]
df_groupby_function_sorted_top10 = df_groupby_function_sorted

fig = plt.figure(figsize=(15,10))
ax = fig.add_subplot(1,1,1)
width = 0.35

rects1 = ax.bar(df_groupby_function_sorted_top10.index, df_groupby_function_sorted_top10.Overhead, width)

ax.set_xticklabels(df_groupby_function_sorted_top10.index, rotation=90)
# plt.xticks(wrap=True)
ax.plot()
plt.show()
print(df_groupby_function_sorted_top10.index)

# df_groupby_function_sorted_top10.plot(kind="bar", ylabel="%", figsize=(15, 20))\
#     .set_xlabel(xlabel="function name")
#
# plt.savefig("hist.pdf")
# plt.show()

for func in df_groupby_function_sorted_top10.index:
    print(func)
    print(df_groupby_function_sorted_top10.loc[func].Overhead)



