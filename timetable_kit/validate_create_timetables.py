#!/usr/bin/env python3
"""
validate_create_timetables.py

This script will help you easily find spec files that need the train
numbers updated. This happens *A LOT* for Acela and NEC trains but, 
also it happens for Keystone and Empire Service. 

Even if some routes do not have their train numbers changing, this script
will update the corresponding .toml file for the latest working 
reference date.

Via command-line argument (-r / --run-create), it can also create timetables
for checks that pass validation. The output directory, author, and executable
can be configured as global settings or overridden via CLI flags.

Usage Examples:
    # List detailed help and running instructions:
    ./validate_create_timetables.py -h

    # List all available checks:
    ./validate_create_timetables.py -l

    # Run all checks 2 weeks out (default):
    ./validate_create_timetables.py

    # Show only MISMATCH entries in the summary report:
    ./validate_create_timetables.py -m

    # Validate specific checks and in the screen output print a list 
    # of the passing/valid .csv/.toml files:
    ./validate_create_timetables.py -c Acela -p
    ./validate_create_timetables.py -c 0-5 -p

    # Validate specific checks and generate timetables for passing/valid ones:
    ./validate_create_timetables.py -c Acela -r
    ./validate_create_timetables.py -c 0-5 -r

    # Run generation with opt-in auto-recovery for "No trip found" errors:
    ./validate_create_timetables.py -c Crescent -r -a
    ./validate_create_timetables.py -c 15 -r -a

    # Force individual timetable creation using each .csv file (for trains with 
    # a .list file) to help with debugging/troubleshooting:
    ./validate_create_timetables.py -c Acela -r -f

    # Run timetable generation using custom output directory or author credit:
    ./validate_create_timetables.py -c 0-5 -r --output-dir ./out --author "Your Name <url>"

Change Log:
2026-08-21  C Juckins  Added green banner output when GTFS data is current and valid.
2026-08-21  C Juckins  Added prominent red warning if GTFS file is older than 36 hours (or missing).
2026-08-21  C Juckins  Added explicit status tracking in summary for auto-recovered timetables.
2026-08-21  C Juckins  Updated auto-recovery to rewrite .toml reference dates upon successful recovery.
2026-08-21  C Juckins  Made auto-recovery optional via -a / --auto-recover flag.
2026-08-21  C Juckins  Added auto-recovery logic for "No trip found" errors using --search 14.
2026-08-21  C Juckins  Added exit code tracking for timetable creation errors.
2026-08-21  C Juckins  Added auto-recovery to try additional dates if the "No trip found" 
                       error occurs on a certain day.


"""

import argparse
import os
import subprocess
import sys
import re
import shlex
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration - adjust these if your paths differ
# ---------------------------------------------------------------------------

LIST_TRAINS_DIR = Path("/home/juckins/ttkit/timetable_kit/timetable_kit")
SPECS_DIR = LIST_TRAINS_DIR / "specs_amtrak"

TIMETABLE_SCRIPT = "./timetable.py"
DEFAULT_OUTPUT_DIR = Path("/home/juckins/ttkit/timetable_kit/timetable_kit/output")
DEFAULT_AUTHOR = 'Christopher Juckins <a href="https://juckins.net">https://juckins.net</a>'

GTFS_FILE_PATH = Path.home() / ".local/share/timetable_kit/amtrak/gtfs.zip"
GTFS_MAX_AGE_HOURS = 36

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# ANSI Escape Sequences for Colored Text
RED_BOLD = "\033[1;31m"
GREEN_BOLD = "\033[1;32m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Checks to run. Add a new dict here for each new CSV / command combination.
# ---------------------------------------------------------------------------
CHECKS = [
    {
        "name": "Acela - Weekday Southbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-weekday-sb.csv",
        "ref_weekday": "tuesday",
        "spec": "acela.list",
    },
    {
        "name": "Acela - Weekday Northbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-weekday-nb.csv",
        "ref_weekday": "tuesday",
        "spec": "acela.list",
    },
    {
        "name": "Acela - Saturday Southbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-saturday-sb.csv",
        "ref_weekday": "saturday",
        "spec": "acela.list",
    },
    {
        "name": "Acela - Saturday Northbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-saturday-nb.csv",
        "ref_weekday": "saturday",
        "spec": "acela.list",
    },
    {
        "name": "Acela - Sunday Southbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-sunday-sb.csv",
        "ref_weekday": "sunday",
        "spec": "acela.list",
    },
    {
        "name": "Acela - Sunday Northbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-sunday-nb.csv",
        "ref_weekday": "sunday",
        "spec": "acela.list",
    },

    {
        "name": "Adirondack",
        "day": None,
        "sort": ["MTR", "MTR", "NYP", "NYP", "MTR"],
        "csv": SPECS_DIR / "adirondack.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Auto Train",
        "day": None,
        "sort": ["LOR", "LOR", "SFA", "SFA", "LOR"],
        "csv": SPECS_DIR / "auto-train.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Berkshire Flyer",
        "day": None,
        "sort": ["NYP", "NYP", "PIT", "PIT", "NYP", "ALB", "PIT", "PIT", "ALB"],
        "csv": SPECS_DIR / "berkshire-flyer.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Borealis",
        "day": None,
        "sort": ["CHI", "CHI", "MSP", "MSP", "CHI"],
        "csv": SPECS_DIR / "borealis.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "California Zephyr",
        "day": None,
        "sort": ["CHI", "CHI", "EMY", "EMY", "CHI"],
        "csv": SPECS_DIR / "california-zephyr.csv",
        "ref_weekday": "tuesday",
        "allowed_csv_trains": ['5005', '5006'],
    },

    {
        "name": "Cardinal",
        "day": None,
        "sort": ["NYP", "NYP", "CHI", "CHI", "NYP"],
        "csv": SPECS_DIR / "cardinal.csv",
        "ref_weekday": "wednesday",
        "ignore_trains": ['48', '49'],
    },

    {
        "name": "Carolinian/Piedmont - Southbound",
        "day": None,
        "sort": ["RGH", "RGH", "CLT", "GRO", "CLT"],
        "csv": SPECS_DIR / "carolinian-piedmont-sb.csv",
        "ref_weekday": "tuesday",
        "spec": "carolinian-piedmont.list",
    },
    {
        "name": "Carolinian/Piedmont - Northbound",
        "day": None,
        "sort": ["CLT", "CLT", "GRO", "CLT", "RGH", "CLT", "NYP"],
        "csv": SPECS_DIR / "carolinian-piedmont-nb.csv",
        "ref_weekday": "tuesday",
        "spec": "carolinian-piedmont.list",
    },

    {
        "name": "Coast Starlight",
        "day": None,
        "sort": ["SEA", "SEA", "LAX", "LAX", "SEA"],
        "csv": SPECS_DIR / "coast-starlight.csv",
        "ref_weekday": "tuesday",
        "allowed_csv_trains": ['6610', '5011', '5014', '6619'],
    },

    {
        "name": "Crescent",
        "day": None,
        "sort": ["NYP", "NYP", "NOL", "NOL", "NYP", "NYP", "ATL", "ATL", "NYP"],
        "csv": SPECS_DIR / "crescent.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Empire Builder & Borealis",
        "day": None,
        "sort": ["CHI", "CHI", "PDX", "PDX", "CHI", "CHI", "SEA", "SEA", "CHI", "CHI", "MSP", "MSP", "CHI"],
        "csv": SPECS_DIR / "empire-builder-borealis.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Empire Service - Weekday Westbound",
        "day": "weekday",
        "sort": ["ALB", "NYP", "ALB", "ALB", "NFL"],
        "csv": SPECS_DIR / "empire-service-weekday-wb.csv",
        "ref_weekday": "wednesday",
        "spec": "empire-service.list",
    },
    {
        "name": "Empire Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekday-eb.csv",
        "ref_weekday": "wednesday",
        "spec": "empire-service.list",
    },
    {
        "name": "Empire Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["ALB", "NYP", "ALB", "ALB", "NFL"],
        "csv": SPECS_DIR / "empire-service-weekend-wb.csv",
        "ref_weekday": "saturday",
        "spec": "empire-service.list",
    },
    {
        "name": "Empire Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekend-eb.csv",
        "ref_weekday": "saturday",
        "spec": "empire-service.list",
    },

    {
        "name": "Ethan Allen Express",
        "day": None,
        "sort": ["BTN", "BTN", "NYP", "NYP", "BTN"],
        "csv": SPECS_DIR / "ethan-allen-express.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Floridian",
        "day": None,
        "sort": ["CHI", "CHI", "MIA", "MIA", "CHI"],
        "csv": SPECS_DIR / "floridian.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Heartland Flyer",
        "day": None,
        "sort": ["OKC", "OKC", "FTW", "FTW", "OKC"],
        "csv": SPECS_DIR / "heartland-flyer.csv",
        "ref_weekday": "tuesday",
        "allowed_csv_trains": ['3', '4', '21', '22', '8903', '8904']
    },

    {
        "name": "Hiawatha - Southbound",
        "day": None,
        "sort": ["MKE", "MKE", "CHI"],
        "csv": SPECS_DIR / "hiawatha-sb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['8', '28'],
        "spec": "hiawatha.list",
    },
    {
        "name": "Hiawatha - Northbound",
        "day": None,
        "sort": ["CHI", "CHI", "MKE"],
        "csv": SPECS_DIR / "hiawatha-nb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['7', '27'],
        "spec": "hiawatha.list",
    },

    {
        "name": "Illinois-Missouri Services (Lincoln Service / Missouri River Runner)",
        "day": None,
        "sort": ["CHI", "CHI", "STL", "STL", "CHI", "STL", "KCY", "KCY", "STL", "CHI", "KCY", "KCY", "CHI"],
        "csv": SPECS_DIR / "lincoln-service-missouri-river-runner.csv",
        "ref_weekday": "tuesday",
        "spec": "illinois-missouri-services.list",
    },
    {
        "name": "Illinois-Missouri Services (Galesburg and Quincy)",
        "day": None,
        "sort": ["CHI", "CHI", "GBB", "GBB", "CHI", "CHI", "QCY", "QCY", "CHI"],
        "csv": SPECS_DIR / "quincy.csv",
        "ref_weekday": "tuesday",
        "spec": "illinois-missouri-services.list",
    },
    {
        "name": "Illinois-Missouri Services (City of New Orleans / Illini / Saluki)",
        "day": None,
        "sort": ["CHI", "CHI", "CDL", "CDL", "CHI"],
        "csv": SPECS_DIR / "city-of-new-orleans-illini-saluki.csv",
        "ref_weekday": "tuesday",
        "spec": "illinois-missouri-services.list",
    },

    {
        "name": "Keystone Service - Weekday Westbound",
        "day": "weekday",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekday-wb.csv",
        "ref_weekday": "tuesday",
        "spec": "keystone-service.list",
    },
    {
        "name": "Keystone Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekday-eb.csv",
        "ref_weekday": "tuesday",
        "spec": "keystone-service.list",
    },  
    {
        "name": "Keystone Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekend-wb.csv",
        "ref_weekday": "tuesday",
        "spec": "keystone-service.list",
    },
    {
        "name": "Keystone Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekend-eb.csv",
        "ref_weekday": "tuesday",
        "spec": "keystone-service.list",
    },

    {
        "name": "Lake Shore Limited",
        "day": None,
        "sort": ["CHI", "CHI", "NYP", "NYP", "CHI", "CHI", "BOS", "BOS", "CHI"],
        "csv": SPECS_DIR / "lake-shore-limited.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['50'],
    },

    {
        "name": "Maple Leaf",
        "day": None,
        "sort": ["TWO", "TWO", "NFS", "NFS", "TWO", "NFL", "NYP", "NYP", "NFL"],
        "csv": SPECS_DIR / "maple-leaf.csv",
        "ref_weekday": "tuesday",
        "allowed_csv_trains": ['7097', '7098'],
        "ignore_trains": ['280', '281', '283', '284'],
    },

    {
        "name": "Mardi Gras",
        "day": None,
        "sort": ["MOE", "MOE", "NOL", "NOL", "MOE"],
        "csv": SPECS_DIR / "mardi-gras.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Michigan Services (Wolverine/Blue Water)",
        "day": None,
        "sort": ["CHI", "CHI", "BTL", "BTL", "CHI", "BTL", "PTH", "PTH", "BTL"],
        "csv": SPECS_DIR / "wolverine-blue-water.csv",
        "ref_weekday": "tuesday",
        "spec": "michigan-services.list",
    },
    {
        "name": "Michigan Services (Pere Marquette)",
        "day": None,
        "sort": ["CHI", "CHI", "GRR", "GRR", "CHI"],
        "csv": SPECS_DIR / "pere-marquette.csv",
        "ref_weekday": "tuesday",
        "spec": "michigan-services.list",
    },

    {
        "name": "NEC Boston-Washington - Weekday Southbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-sb.csv",
        "ref_weekday": "wednesday",
        "spec": "nec-bos-was.list",
    },
    {
        "name": "NEC Boston-Washington - Weekday Northbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-nb.csv",
        "ref_weekday": "monday",
        "spec": "nec-bos-was.list",
    },
    {
        "name": "NEC Boston-Washington - Saturday Southbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-sb.csv",
        "ref_weekday": "saturday",
        "spec": "nec-bos-was.list",
    },
    {
        "name": "NEC Boston-Washington - Saturday Northbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-nb.csv",
        "ref_weekday": "saturday",
        "ignore_trains": ['50'],
        "spec": "nec-bos-was.list",
    },
    {
        "name": "NEC Boston-Washington - Sunday Southbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-sb.csv",
        "ref_weekday": "sunday",
        "spec": "nec-bos-was.list",
    },
    {
        "name": "NEC Boston-Washington - Sunday Northbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-nb.csv",
        "ref_weekday": "sunday",
        "allowed_csv_trains": ['50'],
        "spec": "nec-bos-was.list",
    },

    {
        "name": "Pennsylvanian",
        "day": None,
        "sort": ["NYP", "NYP", "PGH", "PGH", "NYP", "PGH", "CHI", "CHI", "PGH"],
        "csv": SPECS_DIR / "pennsylvanian.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Silver Service / Palmetto (Carolinas and Georgia)",
        "day": None,
        "sort": ["NYP", "NYP", "SAV", "SAV", "NYP", "NYP", "RGH", "RGH", "NYP", "WAS", "SAV", "SAV", "WAS", "NYP", "SAV", "SAV", "NYP"],
        "csv": SPECS_DIR / "silver-service-1.csv",
        "ref_weekday": "tuesday",
        "spec": "silver-service.list",
    },
    {
        "name": "Silver Service (Florida)",
        "day": None,
        "sort": ["SAV", "SAV", "MIA", "MIA", "SAV"],
        "csv": SPECS_DIR / "silver-service-2.csv",
        "ref_weekday": "tuesday",
        "spec": "silver-service.list",
    },

    {
        "name": "Southwest Chief",
        "day": None,
        "sort": ["CHI", "CHI", "LAX", "LAX", "CHI"],
        "csv": SPECS_DIR / "southwest-chief.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['421', '422']
    },

    {
        "name": "Sunset Limited",
        "day": None,
        "sort": ["NOL", "NOL", "LAX", "LAX", "NOL"],
        "csv": SPECS_DIR / "sunset-limited.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Texas Eagle",
        "day": None,
        "sort": ["CHI", "CHI", "LRK", "LRK", "CHI", "LRK", "LAX", "LAX", "LRK"],
        "csv": SPECS_DIR / "texas-eagle.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Valley Flyer & Vermonter - Weekday",
        "day": "weekday",
        "sort": ["GFD", "GFD", "SPG", "SPG", "GFD", "GFD", "NHV", "NHV", "GFD"],
        "csv": SPECS_DIR / "valley-flyer-vermonter-weekday.csv",
        "ref_weekday": "tuesday",
        "spec": "valley-flyer-vermonter.list",
    },
    {
        "name": "Valley Flyer & Vermonter - Weekend",
        "day": "weekend",
        "sort": ["GFD", "GFD", "SPG", "SPG", "GFD", "GFD", "NHV", "NHV", "GFD"],
        "csv": SPECS_DIR / "valley-flyer-vermonter-weekend.csv",
        "ref_weekday": "saturday",
        "spec": "valley-flyer-vermonter.list",
    },

    {
        "name": "Vermonter",
        "day": None,
        "sort": ["SAB", "SAB", "WAS", "WAS", "SAB"],
        "csv": SPECS_DIR / "vermonter.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Virginia Services (Richmond - Weekday Southbound)",
        "day": "weekday",
        "sort": ["RVR", "WAS", "RVR"],
        "csv": SPECS_DIR / "richmond-weekday-sb.csv",
        "ref_weekday": "tuesday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Richmond - Weekday Northbound)",
        "day": "weekday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-weekday-nb.csv",
        "ref_weekday": "tuesday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Richmond - Weekend Southbound)",
        "day": "weekend",
        "sort": ["RVR", "WAS", "RVR"],
        "csv": SPECS_DIR / "richmond-weekend-sb.csv",
        "ref_weekday": "tuesday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Richmond - Saturday Northbound)",
        "day": "saturday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-saturday-nb.csv",
        "ref_weekday": "saturday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Richmond - Sunday Northbound)",
        "day": "sunday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-sunday-nb.csv",
        "ref_weekday": "sunday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Southbound)",
        "day": None,
        "sort": ["RVR", "WAS", "CVS", "WAS", "LYH", "WAS", "RNK"],
        "csv": SPECS_DIR / "lynchburg-roanoke-sb.csv",
        "ref_weekday": "tuesday",
        "spec": "virginia-services.list",
    },
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Northbound)",
        "day": None,
        "sort": ["RVR", "CVS", "WAS", "LYH", "WAS", "RNK", "WAS"],
        "csv": SPECS_DIR / "lynchburg-roanoke-nb.csv",
        "ref_weekday": "tuesday",
        "spec": "virginia-services.list",
    },

    {
        "name": "Winter Park Express",
        "day": None,
        "sort": ["DEN", "DEN", "WIP", "WIP", "DEN"],
        "csv": SPECS_DIR / "winter-park-express.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['5', '6'],
        "mismatch_note": "Seasonal train: operates primarily during winter ski season; off-season mismatches are expected.",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_gtfs_file_age() -> bool:
    """Checks GTFS file age. Prints a red warning if missing or >36h old, 
    otherwise prints a green 'OK' banner.
    Returns True if an age warning was triggered, False if OK.
    """
    if not GTFS_FILE_PATH.exists():
        msg = f"GTFS WARNING: Data file does not exist at {GTFS_FILE_PATH}"
        is_warning = True
    else:
        mtime = GTFS_FILE_PATH.stat().st_mtime
        age_seconds = time.time() - mtime
        age_hours = age_seconds / 3600.0

        if age_hours > GTFS_MAX_AGE_HOURS:
            msg = f"GTFS WARNING: GTFS file ({GTFS_FILE_PATH}) is {age_hours:.1f} hours old (exceeds {GTFS_MAX_AGE_HOURS}h threshold)."
            is_warning = True
        else:
            msg = f"GTFS DATA OK: Data file is current ({age_hours:.1f} hours old)."
            is_warning = False

    border = "*" * (len(msg) + 4)
    color = RED_BOLD if is_warning else GREEN_BOLD
    
    print(f"\n{color}{border}")
    print(f"* {msg} *")
    print(f"{border}{RESET}\n")
    
    return is_warning


def next_future_weekday(today: date, weekday_name: str, weeks_out: int = 2) -> date:
    target = WEEKDAYS[weekday_name.lower()]
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead + 7 * (weeks_out - 1))


def update_toml_reference_date(csv_path: Path, ref_date_str: str) -> None:
    """Find matching .toml file and update its reference_date line."""
    toml_path = csv_path.with_suffix(".toml")
    if not toml_path.exists():
        print(f"TOML Notice: File not found ({toml_path.name})")
        return

    content = toml_path.read_text(encoding="utf-8")
    
    updated_content, count = re.subn(
        r'^(reference_date\s*=\s*)["\'][^"\']*["\']',
        rf'\1"{ref_date_str}"',
        content,
        flags=re.MULTILINE
    )

    if count > 0:
        if content != updated_content:
            toml_path.write_text(updated_content, encoding="utf-8")
            print(f"Updated TOML: {toml_path.name} (reference_date = \"{ref_date_str}\")")
        else:
            print(f"TOML up to date: {toml_path.name} (reference_date = \"{ref_date_str}\")")
    else:
        print(f"TOML Notice: 'reference_date' key not found in {toml_path.name}")


def sync_recovered_toml_dates(spec: str, good_date: str) -> None:
    """Update TOML file(s) for a recovered spec target."""
    if spec.endswith(".list"):
        list_path = SPECS_DIR / spec
        if list_path.exists():
            for line in list_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    csv_name = line if line.endswith(".csv") else f"{line}.csv"
                    update_toml_reference_date(SPECS_DIR / csv_name, good_date)
        else:
            print(f"TOML Sync Notice: Could not find list file '{list_path.name}'")
    else:
        csv_name = spec if spec.endswith(".csv") else f"{spec}.csv"
        update_toml_reference_date(SPECS_DIR / csv_name, good_date)


def run_list_trains(script_cmd: str, reference_date: str, day: Optional[str], sort_args: list[str]) -> str:
    cmd = shlex.split(script_cmd)
    cmd.extend(["--reference-date", reference_date])
    if day:
        cmd.extend(["--day", day])
    cmd.extend(["--sort"] + sort_args)

    print(f"Full list_trains command: {shlex.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(LIST_TRAINS_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit(
            f"ERROR: could not find executable in '{script_cmd}' within {LIST_TRAINS_DIR}. "
            "Update LIST_TRAINS_DIR at the top of this script."
        )
    except subprocess.CalledProcessError as e:
        sys.exit(
            f"ERROR: {script_cmd} exited with status {e.returncode}\n"
            f"stdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        )

    found_lines = [line for line in result.stdout.splitlines() if "found" in line]
    cleaned_lines = [line.replace("'", "").replace(" ", "") for line in found_lines]
    return "\n".join(cleaned_lines)


def create_timetable(spec: str, output_dir: Path, author: str, auto_recover: bool = False) -> Tuple[str, int, Optional[str]]:
    """Executes the timetable creation script for a given spec name or .list file.
    
    Returns tuple: (status, exit_code, recovered_date)
      status: "CREATED", "RECOVERED", or "FAILED"
    """
    base_cmd = [
        str(LIST_TRAINS_DIR / TIMETABLE_SCRIPT),
        "-o", str(output_dir),
        "--spec", spec,
        "-w", author,
    ]
    
    print(f"=== Generating Timetable: {spec} ===")
    print(f"Command: {shlex.join(base_cmd)}")
    
    try:
        result = subprocess.run(
            base_cmd,
            cwd=str(LIST_TRAINS_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            print(f"  stdout:\n{result.stdout.strip()}")
        print("Status: SUCCESS\n")
        return "CREATED", 0, None

    except FileNotFoundError:
        print(f"ERROR: Could not find timetable generator script: {LIST_TRAINS_DIR / TIMETABLE_SCRIPT}\n")
        return "FAILED", 127, None

    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr or ""
        
        # Optional auto-recovery logic
        if auto_recover and "No trip found for" in stderr_output:
            print(f"\n[AUTO-RECOVERY] Detected 'No trip found' error for '{spec}'. Searching for a good date...")
            
            search_cmd = base_cmd + ["--search", "14"]
            print(f"Executing search: {shlex.join(search_cmd)}")
            
            try:
                search_result = subprocess.run(
                    search_cmd,
                    cwd=str(LIST_TRAINS_DIR),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                
                # Parse output for "Found good date YYYYMMDD"
                match = re.search(r"Found good date\s+(\d{8})", search_result.stdout)
                
                if match:
                    good_date = match.group(1)
                    print(f"[AUTO-RECOVERY] Found valid reference date: {good_date}")
                    
                    print(f"[AUTO-RECOVERY] Updating TOML reference date(s) to {good_date}...")
                    sync_recovered_toml_dates(spec, good_date)
                    
                    retry_cmd = base_cmd + ["--reference-date", good_date]
                    print(f"Retrying original command with --reference-date {good_date}...")
                    
                    retry_result = subprocess.run(
                        retry_cmd,
                        cwd=str(LIST_TRAINS_DIR),
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    if retry_result.stdout.strip():
                        print(f"  stdout:\n{retry_result.stdout.strip()}")
                    print("Status: SUCCESS (Recovered)\n")
                    return "RECOVERED", 0, good_date
                else:
                    print(f"[AUTO-RECOVERY FAILED] Could not extract date from search output:\n{search_result.stdout}")

            except subprocess.CalledProcessError as search_err:
                print(f"[AUTO-RECOVERY FAILED] Search or retry command failed.")
                if search_err.stderr:
                    print(f"  stderr:\n{search_err.stderr}")

        # Regular failure output
        print(f"ERROR: Timetable generation failed for {spec} (exit status {e.returncode})")
        if e.stdout:
            print(f"  stdout:\n{e.stdout}")
        if stderr_output:
            print(f"  stderr:\n{stderr_output}")
        print()
        return "FAILED", e.returncode, None


def extract_train_numbers(text: str, ignore_2000s: bool = False) -> set[str]:
    trains = set(re.findall(r"\d+", text))
    if ignore_2000s:
        trains = {t for t in trains if not re.match(r"^2\d{3}$", t)}
    return trains


def get_csv_first_line_trains(csv_path: Path, ignore_2000s: bool = False) -> set[str]:
    if not csv_path.exists():
        sys.exit(f"ERROR: CSV file not found: {csv_path}")

    with csv_path.open("r", newline="") as f:
        first_line = f.readline()

    return extract_train_numbers(first_line, ignore_2000s=ignore_2000s)


def run_check(idx: int, check: dict, today: date, weeks_out: int = 2) -> bool:
    script_cmd = check.get("script", "./list_trains.py")
    day = check.get("day")
    ref_date = next_future_weekday(today, check["ref_weekday"], weeks_out)
    ref_date_str = ref_date.strftime("%Y%m%d")
    ignore_trains = set(str(t) for t in check.get("ignore_trains", []))
    allowed_csv_trains = set(str(t) for t in check.get("allowed_csv_trains", []))
    ignore_2000s = check.get("ignore_2000s", False)
    mismatch_note = check.get("mismatch_note")

    print(f"=== [{idx}] {check['name']} ===")
    print(f"Reference date: {ref_date_str} ({ref_date.strftime('%A')})")
    if day:
        print(f"Day filter: {day}")
    print(f"CSV: {check['csv']}")
    
    update_toml_reference_date(check["csv"], ref_date_str)

    if ignore_trains:
        print(f"Ignoring train(s): {sorted(ignore_trains, key=int)}")
    if allowed_csv_trains:
        print(f"Allowed CSV-only train(s): {sorted(allowed_csv_trains, key=int)}")
    if ignore_2000s:
        print("Ignoring 4-digit 2000-series train numbers (2000-2999)")

    raw_output = run_list_trains(script_cmd, ref_date_str, day, check["sort"])
    live_trains = extract_train_numbers(raw_output, ignore_2000s=ignore_2000s) - ignore_trains
    csv_trains = get_csv_first_line_trains(check["csv"], ignore_2000s=ignore_2000s) - ignore_trains

    print(f"Trains from {script_cmd}: {sorted(live_trains, key=int)}")
    print(f"Trains from CSV first line: {sorted(csv_trains, key=int)}")

    added = live_trains - csv_trains
    removed = (csv_trains - live_trains) - allowed_csv_trains

    if not added and not removed:
        print("MATCH: Train numbers are identical.")
        matched = True
    else:
        print("MISMATCH DETECTED:")
        if mismatch_note:
            print(f"  NOTE: {mismatch_note}")
        if added:
            print(f"  Added (in {script_cmd} but not CSV):   {sorted(added, key=int)}")
        if removed:
            print(f"  Removed (in CSV but not {script_cmd}): {sorted(removed, key=int)}")
        matched = False

    print()
    return matched


def parse_selected_checks(raw_args: list[str]) -> set[int]:
    """Parse list of strings containing integers, ranges (e.g. 28-33), or search terms."""
    selected_indices = set()
    total_checks = len(CHECKS)

    for item in raw_args:
        range_match = re.match(r"^(\d+)-(\d+)$", item)
        if range_match:
            start, end = map(int, range_match.groups())
            for i in range(start, end + 1):
                if 0 <= i < total_checks:
                    selected_indices.add(i)
                else:
                    print(f"Warning: Index {i} out of range (0..{total_checks-1}). Ignored.")
            continue

        if item.isdigit():
            idx = int(item)
            if 0 <= idx < total_checks:
                selected_indices.add(idx)
            else:
                print(f"Warning: Index {idx} out of range (0..{total_checks-1}). Ignored.")
            continue

        matched_any = False
        for idx, check in enumerate(CHECKS):
            if item.lower() in check["name"].lower():
                selected_indices.add(idx)
                matched_any = True
        if not matched_any:
            print(f"Warning: No check name matched query '{item}'. Ignored.")

    return selected_indices


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate spec file train numbers against live script output and optionally create timetables."
    )
    parser.add_argument(
        "-w", "--weeks-out",
        type=int,
        default=2,
        help="Number of weeks out to set the reference date (default: 2)"
    )
    parser.add_argument(
        "-c", "--check",
        nargs="+",
        metavar="TARGET",
        help="Specific check index (e.g. 28), index range (e.g. 28-33), or text query (e.g. Acela)"
    )
    parser.add_argument(
        "-m", "--mismatches-only",
        action="store_true",
        help="Only display MISMATCH entries in the final summary report"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available checks with their index numbers and exit"
    )
    parser.add_argument(
        "-p", "--print-ok-files",
        action="store_true",
        help="Print filenames of .csv and .toml files for checks that passed validation"
    )
    parser.add_argument(
        "-r", "--run-create",
        action="store_true",
        help="Run timetable creation command for checks that pass validation"
    )
    parser.add_argument(
        "-a", "--auto-recover",
        action="store_true",
        help="Automatically search for a valid reference date and retry if a timetable creation fails with 'No trip found'"
    )
    parser.add_argument(
        "-f", "--force-individual",
        action="store_true",
        help="Force timetable generation for individual check specs, ignoring group list files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for generated timetables (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--author",
        type=str,
        default=DEFAULT_AUTHOR,
        help="Author credit string passed to timetable script"
    )
    args = parser.parse_args()

    # Initial GTFS status check at script startup
    check_gtfs_file_age()

    if args.list:
        print("Available Checks:")
        for idx, check in enumerate(CHECKS):
            print(f"  [{idx:2d}] {check['name']}")
        sys.exit(0)

    if args.check:
        target_indices = sorted(parse_selected_checks(args.check))
        if not target_indices:
            sys.exit("ERROR: No valid checks selected.")
        checks_to_run = [(i, CHECKS[i]) for i in target_indices]
    else:
        checks_to_run = list(enumerate(CHECKS))

    today = date.today()
    print(f"Today: {today.isoformat()}")
    print(f"Checking {args.weeks_out} week(s) out\n")

    results = {}
    ok_filenames = set()

    candidate_specs = []
    failed_specs = set()
    individual_specs_to_create = []

    for idx, check in checks_to_run:
        matched = run_check(
            idx,
            check,
            today,
            weeks_out=args.weeks_out
        )
        results[f"[{idx:2d}] {check['name']}"] = matched
        
        csv_stem = check["csv"].stem
        spec_target = csv_stem if args.force_individual else check.get("spec", csv_stem)
        
        if matched:
            ok_filenames.add(check["csv"].name)
            ok_filenames.add(check["csv"].with_suffix(".toml").name)

            if args.run_create:
                if args.force_individual:
                    if csv_stem not in individual_specs_to_create:
                        individual_specs_to_create.append(csv_stem)
                elif spec_target not in candidate_specs:
                    candidate_specs.append(spec_target)
        else:
            if args.force_individual and args.run_create:
                if csv_stem not in individual_specs_to_create:
                    individual_specs_to_create.append(csv_stem)
            else:
                failed_specs.add(spec_target)

    if args.force_individual:
        specs_to_create = individual_specs_to_create
        skipped_specs = []
    else:
        specs_to_create = [s for s in candidate_specs if s not in failed_specs]
        skipped_specs = sorted(failed_specs)

    # Optional Timetable Generation Phase
    created_timetables = []
    failed_generations = []

    if args.run_create:
        print("=== Running Timetable Generation Phase ===")
        if not specs_to_create:
            print("  No validated spec files available to build timetables.\n")
        else:
            for spec_target in specs_to_create:
                status, code, recovered_date = create_timetable(
                    spec_target,
                    args.output_dir,
                    args.author,
                    auto_recover=args.auto_recover
                )
                if status in ("CREATED", "RECOVERED"):
                    created_timetables.append((spec_target, status, recovered_date))
                else:
                    failed_generations.append((spec_target, code))

    print("=== Summary ===")
    all_ok = True
    mismatches_found = False

    for name, ok in results.items():
        if not ok:
            all_ok = False
            mismatches_found = True
            print(f"  [MISMATCH] {name}")
        elif not args.mismatches_only:
            print(f"  [OK]       {name}")

    if args.mismatches_only and not mismatches_found:
        print("  All selected checks matched successfully (0 mismatches).")

    if args.print_ok_files:
        print("\n=== Validated Spec Files (Ready to Upload) ===")
        if ok_filenames:
            for filename in sorted(ok_filenames):
                print(filename)
        else:
            print("  No files passed validation.")

    if args.run_create:
        print("\n=== Generated Timetables ===")
        if created_timetables:
            for spec, status, recovered_date in created_timetables:
                if status == "RECOVERED":
                    print(f"  [RECOVERED] {spec} (Auto-fixed reference date: {recovered_date})")
                else:
                    print(f"  [CREATED]   {spec}")
        else:
            print("  No timetables were successfully created.")

        if failed_generations:
            print("\n=== FAILED Timetable Generations ===")
            for spec, code in failed_generations:
                print(f"  [FAILED]    {spec} (Exit Status: {code})")

        if not args.force_individual:
            print("\n=== Skipped Timetables ===")
            if skipped_specs:
                for spec in skipped_specs:
                    print(f"  [SKIPPED]   {spec}")
            else:
                print("  No timetables were skipped.")

    # Final GTFS status check at conclusion
    check_gtfs_file_age()

    overall_success = all_ok and len(failed_generations) == 0
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
