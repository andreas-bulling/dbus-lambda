> [!WARNING]
> This repository has been migrated to Codeberg and will not be updated anymore.
> Find the new repository here: https://codeberg.org/andreas-bulling/dbus-lambda

# dbus-lambda
LAMBDA heat pump integration for Victron Venus OS

## Purpose
This script supports reading values from heat pumps produced by LAMBDA/Zewotherm via Modbus.
Currently supported are: operating state, flow temperature, power consumption, total energy.

Writing values is not supported right now.

## Installation & Configuration
### Download the latest version of the code
Grab a copy of the main branch and copy it to `/data/dbus-lambda`.

```
wget https://github.com/andreas-bulling/dbus-lambda/archive/refs/heads/main.zip
unzip main.zip "dbus-lambda-main/*" -d /data
mv /data/dbus-lambda-main /data/dbus-lambda
```
### Change the configuration file
Change the configuration file `/data/dbus-lambda/config.ini` to fit your setup. The following table lists all available options.

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is written to the logfile `current.log` |
| DEFAULT  | Deviceinstance | Unique ID identifying the heat pump in Venus OS |
| DEFAULT  | Host | IP address or hostname of the heat pump |
| DEFAULT  | Port | Port (default: 502) |
| DEFAULT  | Position | 0: AC Out, 1: AC In (default: 0) |
| DEFAULT  | Model | Type of heat pump (e.g. EU13L) |
| DEFAULT  | Timeout | Time in milliseconds how often the values should be read and updated |

### Install and run the service
Make the install script executable and run it. Clean up afterwards.

```
chmod a+x /data/dbus-lambda/install.sh
/data/dbus-lambda/install.sh
rm main.zip
```
