#! /usr/bin/env python3
# feed_enhanced.pyi
# Part of timetable_kit
# Copyright 2022, 2023 Nathanael Nerode.  Licensed under GNU Affero GPL v.3 or later.

from typing import Type, Self

from gtfs_kit import Feed  # type: ignore # Tell MyPy this has no type stubs
from pandas import DataFrame, Series

GTFS_DAYS: tuple[str, str, str, str, str, str, str]

class FeedEnhanced(Feed):
    dist_units: str
    agency: DataFrame | None = None
    stops: DataFrame | None = None
    routes: DataFrame | None = None
    trips: DataFrame | None = None
    stop_times: DataFrame | None = None
    calendar: DataFrame | None = None
    calendar_dates: DataFrame | None = None
    fare_attributes: DataFrame | None = None
    fare_rules: DataFrame | None = None
    shapes: DataFrame | None = None
    frequencies: DataFrame | None = None
    transfers: DataFrame | None = None
    feed_info: DataFrame | None = None
    attributions: DataFrame | None = None

    @classmethod
    def enhance(cls: Type[Self], regular_feed: Feed) -> Self: ...
    def copy(self) -> Self: ...
    def filter_by_dates(self: Self, first_date, last_date) -> Self: ...
    def filter_by_day_of_week(self: Self, day: str) -> Self: ...
    def filter_by_days_of_week(self: Self, days: list[str]) -> Self: ...
    def filter_by_route_ids(self: Self, route_ids) -> Self: ...
    def filter_by_service_ids(self: Self, service_ids) -> Self: ...
    def filter_bad_service_ids(self: Self, bad_service_ids) -> Self: ...
    def filter_remove_one_day_calendars(self: Self) -> Self: ...
    def filter_find_one_day_calendars(self: Self) -> Self: ...
    def filter_by_trip_short_names(self: Self, trip_short_names) -> Self: ...
    def filter_by_trip_ids(self: Self, trip_ids) -> Self: ...
    def get_single_trip(self: Self) -> Series: ...
    def get_single_trip_stop_times(self: Self, trip_id) -> DataFrame: ...
    def get_trip_short_name(self: Self, trip_id) -> str: ...
