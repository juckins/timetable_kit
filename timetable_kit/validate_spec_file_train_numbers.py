#!/usr/bin/env python3
"""
validate_spec_file_train_numbers.py

Runs list_trains.py once per configured "check" (each check = a set of
list_trains args + a CSV file to validate against), and reports any train
numbers that have been added or removed relative to the first line of each CSV.

Usage Examples:
    # Run all checks 2 weeks out (default):
    ./validate_spec_file_train_numbers.py

    # List all available checks with their index numbers:
    ./validate_spec_file_train_numbers.py --list

    # Run specific checks by index or range:
    ./validate_spec_file_train_numbers.py --check 28
    ./validate_spec_file_train_numbers.py -c 28-33

    # Run specific checks by name search:
    ./validate_spec_file_train_numbers.py -c Acela

    # Combine flags:
    ./validate_spec_file_train_numbers.py -w 3 -c acela 1 5-8
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
# ---------------------------------------------------------------------------
CHECKS = [
    # Index 0
    {
        "name": "Carolinian/Piedmont - Southbound",
        "day": None,
        "sort": ["RGH", "RGH", "CLT", "GRO", "CLT"],
        "csv": SPECS_DIR / "carolinian-piedmont-sb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 1
    {
        "name": "Carolinian/Piedmont - Northbound",
        "day": None,
        "sort": ["CLT", "CLT", "GRO", "CLT", "RGH", "CLT", "NYP"],
        "csv": SPECS_DIR / "carolinian-piedmont-nb.csv",
        "ref_weekday": "tuesday",
    },
    
    # Index 2
    {
        "name": "Empire Service - Weekday Westbound",
        "day": "weekday",
        "sort": ["ALB", "NYP", "ALB", "ALB", "NFL"],
        "csv": SPECS_DIR / "empire-service-weekday-wb.csv",
        "ref_weekday": "wednesday",
    },
    # Index 3
    {
        "name": "Empire Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekday-eb.csv",
        "ref_weekday": "wednesday",
    },
    # Index 4
    {
        "name": "Empire Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["ALB", "NYP", "ALB", "ALB", "NFL"],
        "csv": SPECS_DIR / "empire-service-weekend-wb.csv",
        "ref_weekday": "saturday",
    },
    # Index 5
    {
        "name": "Empire Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["ALB", "ALB", "NYP", "NFL", "ALB"],
        "csv": SPECS_DIR / "empire-service-weekend-eb.csv",
        "ref_weekday": "saturday",
    },
    
    # Index 6
    {
        "name": "Hiawatha - Southbound",
        "day": None,
        "sort": ["MKE", "MKE", "CHI"],
        "csv": SPECS_DIR / "hiawatha-sb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ["8", "28"],
    },
    # Index 7
    {
        "name": "Hiawatha - Northbound",
        "day": None,
        "sort": ["CHI", "CHI", "MKE"],
        "csv": SPECS_DIR / "hiawatha-nb.csv",
        "ref_weekday": "tuesday",
        "ignore_trains": ["7", "27"],
    },

    # Index 8
    {
        "name": "Illinois-Missouri Services (Lincoln Service / Missouri River Runner)",
        "day": None,
        "sort": ["CHI", "CHI", "STL", "STL", "CHI", "STL", "KCY", "KCY", "STL", "CHI", "KCY", "KCY", "CHI"],
        "csv": SPECS_DIR / "lincoln-service-missouri-river-runner.csv",
        "ref_weekday": "tuesday",
    },
    # Index 9
    {
        "name": "Illinois-Missouri Services (Galesburg and Quincy)",
        "day": None,
        "sort": ["CHI", "CHI", "GBB", "GBB", "CHI", "CHI", "QCY", "QCY", "CHI"],
        "csv": SPECS_DIR / "quincy.csv",
        "ref_weekday": "tuesday",
    },
    # Index 10
    {
        "name": "Illinois-Missouri Services (City of New Orleans / Illini / Saluki)",
        "day": None,
        "sort": ["CHI", "CHI", "CDL", "CDL", "CHI"],
        "csv": SPECS_DIR / "city-of-new-orleans-illini-saluki.csv",
        "ref_weekday": "tuesday",
    },
    
    # Index 11
    {
        "name": "Keystone Service - Weekday Westbound",
        "day": "weekday",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekday-wb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 12
    {
        "name": "Keystone Service - Weekday Eastbound",
        "day": "weekday",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekday-eb.csv",
        "ref_weekday": "tuesday",
    },  
    # Index 13
    {
        "name": "Keystone Service - Weekend Westbound",
        "day": "weekend",
        "sort": ["PHL", "PHL", "HAR"],
        "csv": SPECS_DIR / "keystone-service-weekend-wb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 14
    {
        "name": "Keystone Service - Weekend Eastbound",
        "day": "weekend",
        "sort": ["PHL", "HAR", "PHL"],
        "csv": SPECS_DIR / "keystone-service-weekend-eb.csv",
        "ref_weekday": "tuesday",
    },
    
    # Index 15
    {
        "name": "Michigan Services (Wolverine/Blue Water)",
        "day": None,
        "sort": ["CHI", "CHI", "BTL", "BTL", "CHI", "BTL", "PTH", "PTH", "BTL"],
        "csv": SPECS_DIR / "wolverine-blue-water.csv",
        "ref_weekday": "tuesday",
    },
    # Index 16
    {
        "name": "Michigan Services (Pere Marquette)",
        "day": None,
        "sort": ["CHI", "CHI", "GRR", "GRR", "CHI"],
        "csv": SPECS_DIR / "pere-marquette.csv",
        "ref_weekday": "tuesday",
    },
    
    # Index 17
    {
        "name": "Silver Service / Palmetto (Carolinas and Georgia)",
        "day": None,
        "sort": ["NYP", "NYP", "SAV", "SAV", "NYP", "NYP", "RGH", "RGH", "NYP", "WAS", "SAV", "SAV", "WAS", "NYP", "SAV", "SAV", "NYP"],
        "csv": SPECS_DIR / "silver-service-1.csv",
        "ref_weekday": "tuesday",
    },
    # Index 18
    {
        "name": "Silver Service (Florida)",
        "day": None,
        "sort": ["SAV", "SAV", "MIA", "MIA", "SAV"],
        "csv": SPECS_DIR / "silver-service-2.csv",
        "ref_weekday": "tuesday",
    },

    # Index 19
    {
        "name": "Valley Flyer & Vermonter - Weekday",
        "day": "weekday",
        "sort": ["GFD", "GFD", "SPG", "SPG", "GFD", "GFD", "NHV", "NHV", "GFD"],
        "csv": SPECS_DIR / "valley-flyer-vermonter-weekday.csv",
        "ref_weekday": "tuesday",
    },
    # Index 20
    {
        "name": "Valley Flyer & Vermonter - Weekend",
        "day": "weekend",
        "sort": ["GFD", "GFD", "SPG", "SPG", "GFD", "GFD", "NHV", "NHV", "GFD"],
        "csv": SPECS_DIR / "valley-flyer-vermonter-weekend.csv",
        "ref_weekday": "saturday",
    },
    
    # Index 21
    {
        "name": "Virginia Services (Richmond - Weekday Southbound)",
        "day": "weekday",
        "sort": ["RVR", "WAS", "RVR"],
        "csv": SPECS_DIR / "richmond-weekday-sb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 22
    {
        "name": "Virginia Services (Richmond - Weekday Northbound)",
        "day": "weekday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-weekday-nb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 23
    {
        "name": "Virginia Services (Richmond - Weekend Southbound)",
        "day": "weekend",
        "sort": ["RVR", "WAS", "RVR"],
        "csv": SPECS_DIR / "richmond-weekend-sb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 24
    {
        "name": "Virginia Services (Richmond - Saturday Northbound)",
        "day": "saturday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-saturday-nb.csv",
        "ref_weekday": "saturday",
    },
    # Index 25
    {
        "name": "Virginia Services (Richmond - Sunday Northbound)",
        "day": "sunday",
        "sort": ["RVR", "RVR", "WAS"],
        "csv": SPECS_DIR / "richmond-sunday-nb.csv",
        "ref_weekday": "sunday",
    },
    # Index 26
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Southbound)",
        "day": None,
        "sort": ["RVR", "WAS", "CVS", "WAS", "LYH", "WAS", "RNK"],
        "csv": SPECS_DIR / "lynchburg-roanoke-sb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 27
    {
        "name": "Virginia Services (Lynchburg-Roanoke - Northbound)",
        "day": None,
        "sort": ["RVR", "CVS", "WAS", "LYH", "WAS", "RNK", "WAS"],
        "csv": SPECS_DIR / "lynchburg-roanoke-nb.csv",
        "ref_weekday": "tuesday",
    },
    
    # Index 28
    {
        "name": "Acela - Weekday Southbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-weekday-sb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 29
    {
        "name": "Acela - Weekday Northbound",
        "script": "./list_trains.py --acela",
        "day": "weekday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-weekday-nb.csv",
        "ref_weekday": "tuesday",
    },
    # Index 30
    {
        "name": "Acela - Saturday Southbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-saturday-sb.csv",
        "ref_weekday": "saturday",
    },
    # Index 31
    {
        "name": "Acela - Saturday Northbound",
        "script": "./list_trains.py --acela",
        "day": "saturday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-saturday-nb.csv",
        "ref_weekday": "saturday",
    },
    # Index 32
    {
        "name": "Acela - Sunday Southbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "BOS", "NYP", "NYP", "WAS"],
        "csv": SPECS_DIR / "acela-sunday-sb.csv",
        "ref_weekday": "sunday",
    },
    # Index 33
    {
        "name": "Acela - Sunday Northbound",
        "script": "./list_trains.py --acela",
        "day": "sunday",
        "sort": ["NYP", "WAS", "NYP", "NYP", "BOS"],
        "csv": SPECS_DIR / "acela-sunday-nb.csv",
        "ref_weekday": "sunday",
    },

    # Index 34
    {
        "name": "NEC - Weekday Southbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-sb.csv",
        "ref_weekday": "monday",
    },
    # Index 35
    {
        "name": "NEC - Weekday Northbound",
        "script": "./list_trains.py",
        "day": "weekday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-weekday-nb.csv",
        "ref_weekday": "monday",
    },
    # Index 36
    {
        "name": "NEC - Saturday Southbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-sb.csv",
        "ref_weekday": "saturday",
    },
    # Index 37
    {
        "name": "NEC - Saturday Northbound",
        "script": "./list_trains.py",
        "day": "saturday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-saturday-nb.csv",
        "ref_weekday": "saturday",
    },
    # Index 38
    {
        "name": "NEC - Sunday Southbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "BOS", "NYP", "NYP", "WAS", "NYP", "PHL", "PHL", "RNK", "PHL", "NPN", "PHL", "RNK"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-sb.csv",
        "ref_weekday": "sunday",
    },
    # Index 39
    {
        "name": "NEC - Sunday Northbound",
        "script": "./list_trains.py",
        "day": "sunday",
        "sort": ["PHL", "NYP", "BOS", "WAS", "NYP", "PHL", "NYP", "RNK", "PHL", "NPN", "PHL", "RNK", "PHL"],
        "csv": SPECS_DIR / "nec-bos-was-sunday-nb.csv",
        "ref_weekday": "sunday",
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


def run_list_trains(script_cmd: str, reference_date: str, day: Optional[str], sort_args: list[str]) -> str:
    # Use shlex.split so strings like "./list_trains.py --acela" become ['./list_trains.py', '--acela']
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
    ignore_2000s = check.get("ignore_2000s", False)

    print(f"=== [{idx}] {check['name']} ===")
    print(f"Command: {script_cmd}")
    print(f"Reference date: {ref_date_str} ({ref_date.strftime('%A')})")
    if day:
        print(f"Day filter: {day}")
    print(f"CSV: {check['csv']}")
    if ignore_trains:
        print(f"Ignoring train(s): {sorted(ignore_trains, key=int)}")
    if ignore_2000s:
        print("Ignoring 4-digit 2000-series train numbers (2000-2999)")

    raw_output = run_list_trains(script_cmd, ref_date_str, day, check["sort"])
    live_trains = extract_train_numbers(raw_output, ignore_2000s=ignore_2000s) - ignore_trains
    csv_trains = get_csv_first_line_trains(check["csv"], ignore_2000s=ignore_2000s) - ignore_trains

    print(f"Trains from {script_cmd}: {sorted(live_trains, key=int)}")
    print(f"Trains from CSV first line: {sorted(csv_trains, key=int)}")

    added = live_trains - csv_trains
    removed = csv_trains - live_trains

    if not added and not removed:
        print("MATCH: Train numbers are identical.")
        matched = True
    else:
        print("MISMATCH DETECTED:")
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
        "-l", "--list",
        action="store_true",
        help="List available checks with their index numbers and exit"
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
    for idx, check in checks_to_run:
        results[f"[{idx:2d}] {check['name']}"] = run_check(
            idx,
            check,
            today,
            weeks_out=args.weeks_out
        )

    print("=== Summary ===")
    all_ok = True
    for name, ok in results.items():
        status = "OK" if ok else "MISMATCH"
        print(f"  [{status}] {name}")
        if not ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
