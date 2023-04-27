#!/usr/bin/env python3

import os
import yaml
import configparser

'''
Set default measurement frequency for each sensor. Not included in the image.
Used to generate sensors_config.ini.
'''

SPECS_PATH = "/etc/mini-air-quality/sensor-spec/"
LOCKFILE = "/etc/mini-air-quality/sensor-spec/envs.lock"
CONFIG_FILE = "/etc/mini-air-quality/sensors_config.ini"

if __name__ == '__main__':
    spec_filenames = list(filter(lambda file: "yaml" in file, os.listdir(SPECS_PATH)))
    config = configparser.ConfigParser()
    config.add_section("sensors_config")

    for spec_filename in spec_filenames:
        with open(SPECS_PATH+spec_filename, 'r') as spec_file:
            sensors_data= yaml.load(spec_file, Loader=yaml.SafeLoader)
            for sensor in sensors_data['sensors']:
                sensor_env = sensor['env_name'].upper()
                sensor_default_measure_freq = str(sensor['default_measure_freq'])
                config.set("sensors_config", sensor_env, sensor_default_measure_freq)
    
    with open(CONFIG_FILE, 'w') as config_file:
        config.write(config_file)
