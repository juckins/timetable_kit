#! /usr/bin/env python3
# amtrak/get_gtfs.py
# Part of timetable_kit
# Copyright 2022, 2023 Nathanael Nerode.  Licensed under GNU Affero GPL v.3 or later.
"""Retrieve Amtrak's static GTFS data from the canonical location."""

from timetable_kit.get_gtfs import AgencyGTFSFiles

# Found at transit.land.
# Also at The Mobility Database on GitHub.  MobilityData/mobility-database
# This is the URL we should download the GTFS from.
canonical_gtfs_url = "https://content.amtrak.com/content/gtfs/GTFS.zip"

# This is our singleton global.
_gtfs_files = AgencyGTFSFiles("amtrak", canonical_gtfs_url)


# External interface.
def get_gtfs_files():
    """Retrieve the AgencyGTFSFiles object for the agency"""
    return _gtfs_files


# MAIN PROGRAM
if __name__ == "__main__":
    get_gtfs_files().download_and_save()
