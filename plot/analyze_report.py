import sys
import csv

with open('report_analyzed.csv', 'w', newline='') as destination, open('report.txt', 'r') as source:

    count = 0
    writer = csv.writer(destination)
    id1, id2, id3, id4, id5, id6 = 0, 0, 0, 0, 0, 0

    for line in source:
        count = count + 1

        if count < 9:
            continue
        elif count == 9:
            id1 = line.find("Overhead")
            id2 = line.find("Command")
            id3 = line.find("Source Shared Object")
            id4 = line.find("Source Symbol")
            id5 = line.find("Target Symbol")
            id6 = line.find("Basic Block Cycles")
            writer.writerow([line[id1:id2 - 2].strip(), line[id2:id3 - 2].strip(), line[id3:id4 - 2].strip(),
                             line[id4:id5 - 2].strip(), line[id5:id6 - 2].strip(), line[id6:-1].strip()])
        elif count > 11:
            writer.writerow([line[id1:id2 - 2].strip(), line[id2:id3 - 2].strip(), line[id3:id4 - 2].strip(),
                             line[id4:id5 - 2].strip(), line[id5:id6 - 2].strip(), line[id6:-1].strip()])
