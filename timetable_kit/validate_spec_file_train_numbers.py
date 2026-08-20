#!/usr/bin/env python3
"""
validate_spec_file_train_numbers.py

The purpose of this script is to help you easily find spec files that 
need their train numbers updated.  This happens *A LOT* for Acela and 
NEC trains but also happens for Keystone and Empire Service.  

Even if some routes do not have their train numbers changing, this script
will also update the corresponding .toml file for the latest working 
reference date.  

The script will run list_trains.py once per configured "check" 
(each check = a set of list_trains args + a CSV file to validate against), 
reports any train numbers that have been added or removed relative to the 
first line of each CSV, and updates the corresponding .toml spec file with 
the calculated reference date.

Usage Examples:
    # Run all checks 2 weeks out (default):
    ./validate_spec_file_train_numbers.py

    # Show only MISMATCH entries in the summary report:
    ./validate_spec_file_train_numbers.py --mismatches-only
    ./validate_spec_file_train_numbers.py -m

    # List all available checks with their index numbers:
    ./validate_spec_file_train_numbers.py --list
    ./validate_spec_file_train_numbers.py -l

    # Print .csv and .toml filenames for checks that pass validation:
    ./validate_spec_file_train_numbers.py --print-ok-files
    ./validate_spec_file_train_numbers.py -p

    # Run specific checks by index or range:
    ./validate_spec_file_train_numbers.py --check 28
    ./validate_spec_file_train_numbers.py -c 28-33

    # Run specific checks by name search:
    ./validate_spec_file_train_numbers.py -c Acela

    # Combine flags:
    ./validate_spec_file_train_numbers.py -w 3 -c acela 1 5-8 -m -p

    # Most-often used flags for quick status summary of needed changes:
    ./validate_spec_file_train_numbers.py -m -p
"""

import argparse
import subprocess
import sys
import re
import shlex
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration - adjust these if your paths differ
# ---------------------------------------------------------------------------

LIST_TRAINS_DIR = Path("/home/juckins/ttkit/timetable_kit/timetable_kit")
SPECS_DIR = LIST_TRAINS_DIR / "specs_amtrak"

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# ---------------------------------------------------------------------------
# Checks to run. Add a new dict here for each new CSV / command combination.
#
# Optional parameters for each check dict:
#   - ignore_trains: list[str]      -> Strips these trains from BOTH live & CSV headers
#   - allowed_csv_trains: list[str] -> Permits these trains in CSV header without flagging as removed
#   - ignore_2000s: bool            -> Filters out 2000-series train numbers (2000-2999)
#   - mismatch_note: str            -> Custom note printed when a mismatch occurs
# ---------------------------------------------------------------------------
CHECKS = [
    {
        "name": "Acela - Weekday Southbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-weekday-sb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Acela - Weekday Northbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-weekday-nb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Acela - Saturday Southbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-saturday-sb.csv",
        "ref_weekday": "saturday",
    },
    {
        "name": "Acela - Saturday Northbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-saturday-nb.csv",
        "ref_weekday": "saturday",
    },
    {
        "name": "Acela - Sunday Southbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-sunday-sb.csv",
        "ref_weekday": "sunday",
    },
    {
        "name": "Acela - Sunday Northbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-sunday-nb.csv",
        "ref_weekday": "sunday",
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
        # Connecting buses
        "allowed_csv_trains": ['5005', '5006'],
    },

    {
        "name": "Cardinal",
        "day": None,
        "sort": ["NYP", "NYP", "CHI", "CHI", "NYP"],
        "csv": SPECS_DIR / "cardinal.csv",
        # 51 Runs Su,We,Fr so choose Wednesday here
        "ref_weekday": "wednesday",
        # Don't need Lake Shore Limited
        "ignore_trains": ['48', '49'],
    },

    {
        "name": "Carolinian/Piedmont - Southbound",
        "day": None,
        "sort": ["RGH", "RGH", "CLT", "GRO", "CLT"],
        "csv": SPECS_DIR / "carolinian-piedmont-sb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Carolinian/Piedmont - Northbound",
        "day": None,
        "sort": ["CLT", "CLT", "GRO", "CLT", "RGH", "CLT", "NYP"],
        "csv": SPECS_DIR / "carolinian-piedmont-nb.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Coast Starlight",
        "day": None,
        "sort": ["SEA", "SEA", "LAX", "LAX", "SEA"],
        "csv": SPECS_DIR / "coast-starlight.csv",
        "ref_weekday": "tuesday",
        # Connecting buses
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
    },
    {
        "name": "Empire Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekday-eb.csv",
        "ref_weekday": "wednesday",
    },
    {
        "name": "Empire Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["ALB", "NYP", "ALB", "ALB", "NFL"],
        "csv": SPECS_DIR / "empire-service-weekend-wb.csv",
        "ref_weekday": "saturday",
    },
    {
        "name": "Empire Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekend-eb.csv",
        "ref_weekday": "saturday",
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
        # Connecting trains/buses
        "allowed_csv_trains": ['3', '4', '21', '22', '8903', '8904']
    },

    {
        "name": "Hiawatha - Southbound",
        "day": None,
        "sort": ["MKE", "MKE", "CHI"],
        "csv": SPECS_DIR / "hiawatha-sb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['8', '28'],
    },
    {
        "name": "Hiawatha - Northbound",
        "day": None,
        "sort": ["CHI", "CHI", "MKE"],
        "csv": SPECS_DIR / "hiawatha-nb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ['7', '27'],
    },

    {
        "name": "Illinois-Missouri Services (Lincoln Service / Missouri River Runner)",
        "day": None,
        "sort": ["CHI", "CHI", "STL", "STL", "CHI", "STL", "KCY", "KCY", "STL", "CHI", "KCY", "KCY", "CHI"],
        "csv": SPECS_DIR / "lincoln-service-missouri-river-runner.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Illinois-Missouri Services (Galesburg and Quincy)",
        "day": None,
        "sort": ["CHI", "CHI", "GBB", "GBB", "CHI", "CHI", "QCY", "QCY", "CHI"],
        "csv": SPECS_DIR / "quincy.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Illinois-Missouri Services (City of New Orleans / Illini / Saluki)",
        "day": None,
        "sort": ["CHI", "CHI", "CDL", "CDL", "CHI"],
        "csv": SPECS_DIR / "city-of-new-orleans-illini-saluki.csv",
        "ref_weekday": "tuesday",
    },
    
    {
        "name": "Keystone Service - Weekday Westbound",
        "day": "weekday",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekday-wb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Keystone Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekday-eb.csv",
        "ref_weekday": "tuesday",
    },  
    {
        "name": "Keystone Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekend-wb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Keystone Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekend-eb.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Lake Shore Limited",
        "day": None,
        "sort": ["CHI", "CHI", "NYP", "NYP", "CHI", "CHI", "BOS", "BOS", "CHI"],
        "csv": SPECS_DIR / "lake-shore-limited.csv",
        "ref_weekday": "tuesday",
        # Don't need Cardinal
        "ignore_trains": ['50'],
    },

    {
        "name": "Maple Leaf",
        "day": None,
        "sort": ["TWO", "TWO", "NFS", "NFS", "TWO", "NFL", "NYP", "NYP", "NFL"],
        "csv": SPECS_DIR / "maple-leaf.csv",
        "ref_weekday": "tuesday",
        "allowed_csv_trains": ['7097', '7098'],
        # Don't need Empire Service
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
    },
    {
        "name": "Michigan Services (Pere Marquette)",
        "day": None,
        "sort": ["CHI", "CHI", "GRR", "GRR", "CHI"],
        "csv": SPECS_DIR / "pere-marquette.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "NEC Boston-Washington - Weekday Southbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-sb.csv",
        # Use Wednesday for Cardinal
        "ref_weekday": "wednesday",
    },
    {
        "name": "NEC Boston-Washington - Weekday Northbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-nb.csv",
        "ref_weekday": "monday",
    },
    {
        "name": "NEC Boston-Washington - Saturday Southbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-sb.csv",
        "ref_weekday": "saturday",
    },
    {
        "name": "NEC Boston-Washington - Saturday Northbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-nb.csv",
        "ref_weekday": "saturday",
        # Cardinal originates in CHI on Saturday, travels NB on the NEC on Sunday
        "ignore_trains": ['50'],
    },
    {
        "name": "NEC Boston-Washington - Sunday Southbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-sb.csv",
        "ref_weekday": "sunday",
    },
    {
        "name": "NEC Boston-Washington - Sunday Northbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-nb.csv",
        "ref_weekday": "sunday",
        # Cardinal originates in CHI on Saturday, travels NB on the NEC on Sunday
        "allowed_csv_trains": ['50'],
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
    },
    {
        "name": "Silver Service (Florida)",
        "day": None,
        "sort": ["SAV", "SAV", "MIA", "MIA", "SAV"],
        "csv": SPECS_DIR / "silver-service-2.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Southwest Chief",
        "day": None,
        "sort": ["CHI", "CHI", "LAX", "LAX", "CHI"],
        "csv": SPECS_DIR / "southwest-chief.csv",
        "ref_weekday": "tuesday",
        # Don't need Texas Eagle
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
    },
    {
        "name": "Valley Flyer & Vermonter - Weekend",
        "day": "weekend",
        "sort": ["GFD", "GFD", "SPG", "SPG", "GFD", "GFD", "NHV", "NHV", "GFD"],
        "csv": SPECS_DIR / "valley-flyer-vermonter-weekend.csv",
        "ref_weekday": "saturday",
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
    },
    {
        "name": "Virginia Services (Richmond - Weekday Northbound)",
        "day": "weekday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-weekday-nb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Virginia Services (Richmond - Weekend Southbound)",
        "day": "weekend",
        "sort": ["RVR", "WAS", "RVR"],
        "csv": SPECS_DIR / "richmond-weekend-sb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Virginia Services (Richmond - Saturday Northbound)",
        "day": "saturday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-saturday-nb.csv",
        "ref_weekday": "saturday",
    },
    {
        "name": "Virginia Services (Richmond - Sunday Northbound)",
        "day": "sunday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-sunday-nb.csv",
        "ref_weekday": "sunday",
    },
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Southbound)",
        "day": None,
        "sort": ["RVR", "WAS", "CVS", "WAS", "LYH", "WAS", "RNK"],
        "csv": SPECS_DIR / "lynchburg-roanoke-sb.csv",
        "ref_weekday": "tuesday",
    },
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Northbound)",
        "day": None,
        "sort": ["RVR", "CVS", "WAS", "LYH", "WAS", "RNK", "WAS"],
        "csv": SPECS_DIR / "lynchburg-roanoke-nb.csv",
        "ref_weekday": "tuesday",
    },

    {
        "name": "Winter Park Express",
        "day": None,
        "sort": ["DEN", "DEN", "WIP", "WIP", "DEN"],
        "csv": SPECS_DIR / "winter-park-express.csv",
        "ref_weekday": "tuesday",
        # Don't need California Zephyr since Winter Park Express
        # is a special train designed for ski passengers
        "ignore_trains": ['5', '6'],
        "mismatch_note": "Seasonal train: operates primarily during winter ski season; off-season mismatches are expected.",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    
    # Matches reference_date = "..." or reference_date = '...'
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


def run_list_trains(script_cmd: str, reference_date: str, day: Optional[str], sort_args: list[str]) -> str:
    cmd = shlex.split(script_cmd)
    cmd.extend(["--reference-date", reference_date])
    if day:
        cmd.extend(["--day", day])
    cmd.extend(["--sort"] + sort_args)

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
    print(f"Command: {script_cmd}")
    print(f"Reference date: {ref_date_str} ({ref_date.strftime('%A')})")
    if day:
        print(f"Day filter: {day}")
    print(f"CSV: {check['csv']}")
    
    # Update matching .toml reference_date
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
    # Subtract allowed_csv_trains from missing set so they don't trigger a mismatch
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
        description="Validate spec file train numbers against live script output."
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
    args = parser.parse_args()

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

    for idx, check in checks_to_run:
        matched = run_check(
            idx,
            check,
            today,
            weeks_out=args.weeks_out
        )
        results[f"[{idx:2d}] {check['name']}"] = matched
        if matched:
            ok_filenames.add(check["csv"].name)
            ok_filenames.add(check["csv"].with_suffix(".toml").name)

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

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
