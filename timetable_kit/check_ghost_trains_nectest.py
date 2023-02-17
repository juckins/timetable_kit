#! /usr/bin/env python3
# check_ghost_trains.py
# Part of timetable_kit
# Copyright 2021, 2022 Nathanael Nerode.  Licensed under GNU Affero GPL v.3 or later.
# Initial version started by Christopher Juckins

import sys
from urllib.request import Request, urlopen

if __name__ == "__main__":
    
    #--- 
    # Quick comparison framework test
    #---
    # Below gathered and concatenated with: 
    # ./find_trains.py NYP PHL PHL NYP NYP BOS BOS NYP
    # Note that you will then need to subtract trains running HAR-PHL

    csv_input = ['2190', '190', '150', '2150', '2152', '162', '2154', '172', '2248', '2250', '86', '152', '164', '2160', '174', '2252', '82', '88', '2164', '176', '2166', '2254', '194', '2168', '184', '94', '2170', '168', '2172', '178', '66', '2151', '2153', '2249', '95', '195', '2155', '2251', '171', '99', '2159', '93', '161', '87', '85', '2163', '2253', '173', '163', '2261', '2165', '2167', '135', '137', '2169', '2181', '2171', '175', '2173', '2175', '169', '179', '65', '151', '2103', '89', '51', '661', '183', '641', '79', '79', '2203', '153', '185', '2151', '155', '663', '643', '141', '2153', '2249', '95', '43', '2155', '91', '195', '125', '2251', '645', '171', '147', '609', '2159', '2215', '665', '99', '2121', '93', '161', '647', '19', '649', '2163', '2253', '87', '85', '667', '97', '173', '2261', '2165', '651', '163', '129', '2167', '159', '653', '669', '193', '2181', '2169', '2119', '135', '137', '655', '55', '2171', '57', '175', '671', '2173', '657', '2175', '187', '639', '65', '180', '640', '2152', '642', '162', '2154', '600', '172', '54', '660', '2248', '644', '56', '152', '662', '2250', '86', '646', '164', '182', '664', '2160', '648', '174', '82', '2252', '84', '88', '666', '2164', '176', '650', '140', '2166', '2254', '194', '184', '42', '2168', '94', '670', '156', '2178', '2170', '2218', '148', '168', '652', '2172', '134', '178', '146', '2122', '654', '196', '80', '80', '672', '192', '2124', '656', '138', '158', '2126', '658', '674', '2228', '2128', '90', '124', '186', '624', '66', '98', '20', '92', '50']
    print('csv_input: ', csv_input)
    print('')

    with open("trains_running_nectest.txt") as f:
        trains_running = [line.rstrip('\n') for line in f]
    print('trains_running: ', trains_running)
    print('')
    
    missing_from_csv_input = list(set(trains_running).difference(csv_input))
    print('missing_from_csv_input:', missing_from_csv_input)
    print('')
    
    csv_ghost_train = list(set(csv_input).difference(trains_running))
    print('csv_ghost_train: ', csv_ghost_train)
