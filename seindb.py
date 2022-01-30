#!./venv/bin/python3
# -*- coding: utf-8 -*-

import argparse
import example_data
import secrets
import pytz

from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from solaredge import Solaredge

# solaredge constants
SE_TIMEZONE = pytz.timezone("CET")  # solaredge data is in the local time zone
SE_FMT_DATE = '%Y-%m-%d'
SE_FMT_DATETIME = '%Y-%m-%d %H:%M:%S'

# influxdb constants
IDB_HOST = "openhab"
IDB_PORT = 8086
IDB_DATABASE = "test"
# IDB_DATABASE = "home_assistant"

IDB_TIMEZONE = pytz.utc
IDB_FMT = '%Y-%m-%dT%H:%M:%SZ'

CURRENT_POWER_MEASUREMENT = "sensor__power"
CURRENT_POWER_TAGS = {
    "entity_id": "solaredge_current_power",
    "domain": "sensor"
}
CURRENT_POWER_FIELD = "value"

LIFETIME_ENERGY_MEASUREMENT = "sensor__energy"
LIFETIME_ENERGY_TAGS = {
    "entity_id": "solaredge_lifetime_energy",
    "domain": "sensor"
}
LIFETIME_ENERGY_FIELD = "value"


def _parse_input_timestamp(timestamp: str) -> datetime:
    try:
        return datetime.strptime(timestamp, SE_FMT_DATE)
    except ValueError:
        return datetime.strptime(timestamp, SE_FMT_DATETIME)


def _parse_solaredge_timestamp(timestamp: str) -> datetime:
    dt = datetime.strptime(timestamp, SE_FMT_DATETIME)
    dt_local = SE_TIMEZONE.localize(dt)
    return dt_local.astimezone(IDB_TIMEZONE)


def _format_timestamp(dt: datetime, fmt: str) -> str:
    return dt.strftime(fmt)


def _offset_from_timeunit(timeunit: str) -> timedelta:
    if timeunit == 'WEEK':
        return timedelta(days=7)
    if timeunit == 'DAY':
        return timedelta(days=1)
    if timeunit == 'HOUR':
        return timedelta(hours=1)
    if timeunit == 'QUARTER_OF_AN_HOUR':
        return timedelta(minutes=15)

    raise Exception("Unsupported timeunit {}".format(timeunit))


def pull_current_power_data(client: Solaredge, begin: datetime, end: datetime):
    return client.get_power(secrets.solaredge_site_id,
                            _format_timestamp(begin, SE_FMT_DATETIME),
                            _format_timestamp(end, SE_FMT_DATETIME))


def pull_timeframe_energy_data(client: Solaredge, begin: datetime, end: datetime, timeunit: str):
    # to include the energy on the end date in the time frame data we need to add a day
    end = end + timedelta(days=1)
    return client.get_time_frame_energy(secrets.solaredge_site_id,
                                        _format_timestamp(begin, SE_FMT_DATE),
                                        _format_timestamp(end, SE_FMT_DATE),
                                        time_unit=timeunit)


def pull_energy_data(client: Solaredge, begin: datetime, end: datetime, timeunit: str):
    return client.get_energy(secrets.solaredge_site_id,
                             _format_timestamp(begin, SE_FMT_DATE),
                             _format_timestamp(end, SE_FMT_DATE),
                             time_unit=timeunit)


def parse_lifetime_energy_data(timeframe_energy_data, energy_data):
    data_points = []
    lifetime_energy = timeframe_energy_data['timeFrameEnergy']['startLifetimeEnergy']['energy']
    # end_lifetime_energy = timeframe_energy_data['timeFrameEnergy']['endLifetimeEnergy']['energy']
    timeunit = energy_data['energy']['timeUnit']
    offset = _offset_from_timeunit(timeunit)

    for ed in energy_data['energy']['values']:
        if ed['value'] is None:
            continue

        lifetime_energy += ed['value']
        data_points.append({
            'timestamp': _parse_solaredge_timestamp(ed['date']) + offset,
            'value': lifetime_energy
        })

    # no point in comparing with end_lifetime_energy, the returned data is always off for god knows what reason
    # if end_lifetime_energy != lifetime_energy:
    #     print("End lifetime energy mismatch; calculated={} timeframe data={}"
    #           .format(lifetime_energy, end_lifetime_energy))
    return data_points


def parse_current_power_data(power_data):
    data_points = []
    for pd in power_data['power']['values']:
        if pd['value'] is None:
            continue

        data_points.append({
            'timestamp': _parse_solaredge_timestamp(pd['date']),
            'value': pd['value']
        })

    return data_points


def write_data(client, data, measurement, tags, field_name):
    data_points = []
    for d in data:
        dp = {
            "measurement": measurement,
            "tags": tags,
            "time": _format_timestamp(d['timestamp'], IDB_FMT),
            "fields": {
                field_name: d['value']
            }
        }
        data_points.append(dp)

    client.write_points(data_points)


def main():
    parser = argparse.ArgumentParser(description='Pull data from the SolarEdge API and store it into an InfluxDB database.')
    parser.add_argument("begin", type=str, help="Begin timestamp in the format YYYY-MM-DD[ hh:mm:ss]")
    parser.add_argument("end", type=str, default=None, help="End timestamp in the format YYYY-MM-DD[ hh:mm:ss]")
    parser.add_argument("-p", "--power", action='store_true', help="Include current power data")
    parser.add_argument("-e", "--energy", action='store_true', help="Include lifetime energy data")
    parser.add_argument("-g", "--granularity", default='DAY', help="Granularity for energy data",
                        choices=['QUARTER_OF_AN_HOUR', 'HOUR', 'DAY', 'WEEK'])
    parser.add_argument("-v", "--verbose", action='store_true', help="Verbose output")
    parser.add_argument("-d", "--dry-run", action='store_true', help="Don't pull any actual data from the solaredge api,"
                                                                     " use example data instead")
    args = parser.parse_args()

    begin = _parse_input_timestamp(args.begin)
    end = _parse_input_timestamp(args.end) if args.end else datetime.now()

    solaredge_client = Solaredge(secrets.solaredge_token)

    influx_client = InfluxDBClient(host=IDB_HOST,
                                   port=IDB_PORT,
                                   username=secrets.influxdb_user,
                                   password=secrets.influxdb_pass)
    influx_client.switch_database(IDB_DATABASE)

    if not args.power and not args.energy:
        args.power = True
        args.energy = True

    if args.energy:
        energy_data = pull_energy_data(solaredge_client, begin, end, args.granularity) \
            if not args.dry_run else example_data.energy_data
        if args.verbose:
            print("Raw energy data:")
            print(energy_data)

        timeframe_data = pull_timeframe_energy_data(solaredge_client, begin, end, args.granularity) \
            if not args.dry_run else example_data.time_frame_energy_data
        if args.verbose:
            print("Raw timeframe data:")
            print(timeframe_data)

        lifetime_energy_data = parse_lifetime_energy_data(timeframe_data, energy_data)
        print("got {} lifetime energy data points".format(len(lifetime_energy_data)))
        if args.verbose:
            print("Parsed lifetime energy data:")
            print(lifetime_energy_data)

        write_data(influx_client,
                   lifetime_energy_data,
                   LIFETIME_ENERGY_MEASUREMENT,
                   LIFETIME_ENERGY_TAGS,
                   LIFETIME_ENERGY_FIELD)

    if args.power:
        current_power_data = pull_current_power_data(solaredge_client, begin, end) \
            if not args.dry_run else example_data.power_data
        if args.verbose:
            print("Raw current power data:")
            print(current_power_data)

        current_power_data = parse_current_power_data(current_power_data)
        print("got {} power data points".format(len(current_power_data)))
        if args.verbose:
            print("Parsed current power data:")
            print(current_power_data)

        write_data(influx_client,
                   current_power_data,
                   CURRENT_POWER_MEASUREMENT,
                   CURRENT_POWER_TAGS,
                   CURRENT_POWER_FIELD)


if __name__ == '__main__':
    main()
