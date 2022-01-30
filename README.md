# solaredge-pull-influxdb
A script to pull historic data from the SolarEdge API into an InfluxDB instance

## Dependencies
- solaredge
- influxdb

## Usage
1. edit secrets.py with your own solaredge api key and site id, and optionally your influxdb credentials
2. edit seindb.py:
  - change `SE_TIMEZONE` and `IDB_TIMEZONE` to the proper timezones (see comments)
  - change InfluxDB settings: `IDB_HOST`, `IDB_PORT`, `IDB_DATABASE`
  - change the InfluxDB measurement names for power and energy: `CURRENT_POWER_MEASUREMENT`, `LIFETIME_ENERGY_MEASUREMENT`
  - change the tags to store with the measurements: `CURRENT_POWER_TAGS`, `LIFETIME_ENERGY_TAGS`
  - if needed, change the name of the fields where the value is stored: `CURRENT_POWER_FIELD`, `LIFETIME_ENERGY_FIELD`
3. run the script. Use the -h switch for help.

Notes:
- The current InfluxDB settings (measurements, tags, fields) are tailored for an InfluxDB controlled by Home Assistant with the SolarEdge plug-in.
- You might want to use the dry-run option and a test database first. Dry-run will not actually call the SolarEdge API, so it won't eat into your daily API usage limit. It uses some example data instead. Dry-run will however store the data into InfluxDB

**Script options:**
```
$ ./seindb.py -h
usage: seindb.py [-h] [-p] [-e] [-g {QUARTER_OF_AN_HOUR,HOUR,DAY,WEEK}] [-v] [-d] begin end

Pull data from the SolarEdge API and store it into an InfluxDB database.

positional arguments:
  begin                 Begin timestamp in the format YYYY-MM-DD[ hh:mm:ss]
  end                   End timestamp in the format YYYY-MM-DD[ hh:mm:ss]

optional arguments:
  -h, --help            show this help message and exit
  -p, --power           Include current power data
  -e, --energy          Include lifetime energy data
  -g {QUARTER_OF_AN_HOUR,HOUR,DAY,WEEK}, --granularity {QUARTER_OF_AN_HOUR,HOUR,DAY,WEEK}
                        Granularity for energy data
  -v, --verbose         Verbose output
  -d, --dry-run         Don't pull any actual data from the solaredge api, use example data instead

```
